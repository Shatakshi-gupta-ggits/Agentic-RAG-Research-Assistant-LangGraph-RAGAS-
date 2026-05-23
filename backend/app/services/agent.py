"""
LangGraph Agentic RAG
State machine:  START → planner → tool_router → [retriever | web_search | direct] → synthesiser → END
"""
from __future__ import annotations

import json
from typing import TypedDict, Annotated, Sequence, Literal
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END

from app.core.config import settings
from app.services.ingestion import hybrid_retrieve
from app.tools.web_search import web_search_tool


# ── State ─────────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    query: str
    retrieved_docs: list[dict]
    web_results: list[dict]
    route: Literal["retriever", "web_search", "both", "direct"]
    answer: str
    sources: list[dict]
    filename_filter: str | None


# ── LLM ───────────────────────────────────────────────────────────────────────
def _get_llm() -> ChatOllama:
    return ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        temperature=0.1,
    )


# ── Node 1: Planner — decide route ───────────────────────────────────────────
PLANNER_PROMPT = """You are a research assistant router. Given the user query, decide the best retrieval strategy.

Respond with ONLY a JSON object like:
{{"route": "retriever"}}   ← use uploaded documents only
{{"route": "web_search"}}  ← use live web search only
{{"route": "both"}}        ← use both documents and web search
{{"route": "direct"}}      ← answer directly without retrieval (greetings, simple math, etc.)

Query: {query}"""

def planner_node(state: AgentState) -> AgentState:
    llm = _get_llm()
    response = llm.invoke([HumanMessage(content=PLANNER_PROMPT.format(query=state["query"]))])
    try:
        parsed = json.loads(response.content.strip())
        route = parsed.get("route", "retriever")
    except Exception:
        route = "retriever"   # safe default

    return {**state, "route": route}


# ── Node 2a: Document retriever ───────────────────────────────────────────────
def retriever_node(state: AgentState) -> AgentState:
    docs = hybrid_retrieve(
        query=state["query"],
        filename_filter=state.get("filename_filter"),
    )
    return {**state, "retrieved_docs": docs}


# ── Node 2b: Web search ───────────────────────────────────────────────────────
def web_search_node(state: AgentState) -> AgentState:
    results = web_search_tool(state["query"])
    return {**state, "web_results": results}


# ── Node 3: Synthesiser — generate final answer ───────────────────────────────
SYNTHESIS_PROMPT = """You are a knowledgeable research assistant. Answer the user's question accurately and concisely.

{context_block}

Conversation history:
{history}

Question: {query}

Instructions:
- Base your answer on the provided context where available.
- If citing a document, mention the filename.
- If citing a web result, mention the source URL.
- Be concise but complete. Use bullet points for lists.
- If you don't know, say so clearly.

Answer:"""

def synthesiser_node(state: AgentState) -> AgentState:
    # Build context
    context_parts = []

    if state.get("retrieved_docs"):
        doc_context = "\n\n".join(
            f"[Document: {d['metadata']['filename']}, chunk {d['metadata']['chunk_index']}]\n{d['content']}"
            for d in state["retrieved_docs"]
        )
        context_parts.append(f"--- DOCUMENT CONTEXT ---\n{doc_context}")

    if state.get("web_results"):
        web_context = "\n\n".join(
            f"[Web: {r['url']}]\n{r['snippet']}"
            for r in state["web_results"]
        )
        context_parts.append(f"--- WEB CONTEXT ---\n{web_context}")

    context_block = "\n\n".join(context_parts) if context_parts else "No external context available."

    # Build conversation history (last 6 messages)
    history_msgs = state["messages"][-6:]
    history = "\n".join(
        f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
        for m in history_msgs
    )

    prompt = SYNTHESIS_PROMPT.format(
        context_block=context_block,
        history=history,
        query=state["query"],
    )

    llm = _get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    answer = response.content.strip()

    # Collect sources
    sources = []
    for d in (state.get("retrieved_docs") or []):
        sources.append({"type": "document", "filename": d["metadata"]["filename"], "score": d["score"]})
    for w in (state.get("web_results") or []):
        sources.append({"type": "web", "url": w["url"], "title": w.get("title", "")})

    new_messages = list(state["messages"]) + [
        HumanMessage(content=state["query"]),
        AIMessage(content=answer),
    ]

    return {**state, "answer": answer, "sources": sources, "messages": new_messages}


# ── Router function ───────────────────────────────────────────────────────────
def route_after_planner(state: AgentState) -> str:
    route = state.get("route", "retriever")
    if route == "direct":
        return "synthesiser"
    if route == "web_search":
        return "web_search"
    if route == "both":
        return "retriever_and_web"
    return "retriever"   # default


# ── Graph ─────────────────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("planner", planner_node)
    g.add_node("retriever", retriever_node)
    g.add_node("web_search", web_search_node)
    g.add_node("synthesiser", synthesiser_node)

    # Parallel retriever + web_search for "both" route
    # LangGraph doesn't have native fan-out yet so we chain them
    def retriever_then_web(state: AgentState) -> AgentState:
        s = retriever_node(state)
        return web_search_node(s)

    g.add_node("retriever_and_web", retriever_then_web)

    g.set_entry_point("planner")

    g.add_conditional_edges("planner", route_after_planner, {
        "retriever": "retriever",
        "web_search": "web_search",
        "retriever_and_web": "retriever_and_web",
        "synthesiser": "synthesiser",
    })

    g.add_edge("retriever", "synthesiser")
    g.add_edge("web_search", "synthesiser")
    g.add_edge("retriever_and_web", "synthesiser")
    g.add_edge("synthesiser", END)

    return g.compile()


# Singleton compiled graph
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def run_agent(query: str, history: list[BaseMessage],
                    filename_filter: str | None = None) -> dict:
    """Run the agent and return answer + sources."""
    graph = get_graph()
    initial_state: AgentState = {
        "messages": history,
        "query": query,
        "retrieved_docs": [],
        "web_results": [],
        "route": "retriever",
        "answer": "",
        "sources": [],
        "filename_filter": filename_filter,
    }
    final_state = await graph.ainvoke(initial_state)
    return {
        "answer": final_state["answer"],
        "sources": final_state["sources"],
        "route_used": final_state["route"],
    }
