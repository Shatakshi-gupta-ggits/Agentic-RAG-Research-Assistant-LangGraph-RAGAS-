import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import toast from 'react-hot-toast'
import { sendChat, clearSession } from '../hooks/api'

const ROUTE_LABELS = {
  retriever: { label: 'Documents', color: 'bg-blue-100 text-blue-700' },
  web_search: { label: 'Web', color: 'bg-green-100 text-green-700' },
  both: { label: 'Docs + Web', color: 'bg-purple-100 text-purple-700' },
  direct: { label: 'Direct', color: 'bg-slate-100 text-slate-500' },
}

export default function ChatWindow({ documents, sessionId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async () => {
    const query = input.trim()
    if (!query || loading) return

    const userMsg = { role: 'user', content: query }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await sendChat({
        session_id: sessionId,
        query,
        filename_filter: filter || null,
      })
      const aiMsg = {
        role: 'assistant',
        content: res.answer,
        sources: res.sources,
        route: res.route_used,
      }
      setMessages(prev => [...prev, aiMsg])
    } catch {
      toast.error('Failed to get a response. Is Ollama running?')
      setMessages(prev => prev.slice(0, -1))
    } finally {
      setLoading(false)
    }
  }

  const handleClear = async () => {
    await clearSession(sessionId)
    setMessages([])
    toast.success('Conversation cleared.')
  }

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      {documents.length > 0 && (
        <div className="flex items-center gap-2 px-4 py-2 border-b bg-white text-sm">
          <span className="text-slate-400">Filter:</span>
          <select
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="border rounded px-2 py-1 text-slate-700 text-xs"
          >
            <option value="">All documents</option>
            {documents.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          <button onClick={handleClear} className="ml-auto text-slate-400 hover:text-red-500 text-xs">
            Clear chat
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-slate-400 mt-20">
            <div className="text-4xl mb-3">🔬</div>
            <p className="text-sm">Upload PDFs and ask anything.<br/>The agent will search your documents, the web, or both.</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm
              ${msg.role === 'user'
                ? 'bg-brand text-white rounded-br-sm'
                : 'bg-white border border-slate-200 rounded-bl-sm shadow-sm'}`}
            >
              {msg.role === 'assistant' ? (
                <>
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                  {/* Route badge + sources */}
                  <div className="mt-2 flex flex-wrap gap-1 items-center">
                    {msg.route && (
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROUTE_LABELS[msg.route]?.color}`}>
                        {ROUTE_LABELS[msg.route]?.label}
                      </span>
                    )}
                    {msg.sources?.slice(0, 3).map((s, j) => (
                      <span key={j} className="text-xs text-slate-400 bg-slate-50 border rounded px-1.5 py-0.5">
                        {s.type === 'document' ? `📄 ${s.filename}` : `🌐 ${s.title || s.url}`}
                      </span>
                    ))}
                  </div>
                </>
              ) : (
                <p>{msg.content}</p>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
              <div className="flex gap-1 items-center">
                <span className="w-2 h-2 bg-brand rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-brand rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-brand rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t bg-white">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder="Ask anything about your documents…"
            className="flex-1 border border-slate-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand"
            disabled={loading}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="bg-brand hover:bg-brand-dark text-white px-4 py-2.5 rounded-xl text-sm font-medium disabled:opacity-40 transition-colors"
          >
            Send
          </button>
        </div>
        <p className="text-xs text-slate-400 mt-1.5 pl-1">Enter to send · Shift+Enter for newline</p>
      </div>
    </div>
  )
}
