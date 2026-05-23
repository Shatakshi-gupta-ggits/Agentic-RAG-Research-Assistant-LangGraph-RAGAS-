import { useState, useEffect, useCallback } from 'react'
import { Toaster } from 'react-hot-toast'
import FileUpload from './components/FileUpload'
import ChatWindow from './components/ChatWindow'
import { listDocuments, healthCheck } from './hooks/api'

const SESSION_ID = `session_${Date.now()}`

export default function App() {
  const [documents, setDocuments] = useState([])
  const [model, setModel] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const refreshDocs = useCallback(async () => {
    try { setDocuments(await listDocuments()) } catch {}
  }, [])

  useEffect(() => {
    refreshDocs()
    healthCheck().then(d => setModel(d.model)).catch(() => {})
    const interval = setInterval(refreshDocs, 5000)   // poll for new ingestions
    return () => clearInterval(interval)
  }, [refreshDocs])

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Toaster position="top-right" />

      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-72' : 'w-0 overflow-hidden'} transition-all duration-200 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col`}>
        <div className="p-4 border-b">
          <h1 className="font-semibold text-brand text-sm">🔬 Agentic RAG</h1>
          {model && <p className="text-xs text-slate-400 mt-0.5">Model: {model}</p>}
        </div>

        <div className="p-4 border-b">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Upload PDF</p>
          <FileUpload onUploaded={refreshDocs} />
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
            Documents ({documents.length})
          </p>
          {documents.length === 0 ? (
            <p className="text-xs text-slate-400">No documents yet.</p>
          ) : (
            <ul className="space-y-1">
              {documents.map(d => (
                <li key={d} className="text-xs text-slate-600 bg-slate-50 rounded-lg px-3 py-2 flex items-center gap-2">
                  <span>📄</span>
                  <span className="truncate">{d}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="p-3 border-t">
          <p className="text-xs text-slate-400 text-center">Built with LangGraph + Ollama</p>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-12 bg-white border-b border-slate-200 flex items-center px-4 gap-3">
          <button
            onClick={() => setSidebarOpen(o => !o)}
            className="text-slate-400 hover:text-slate-600"
            aria-label="Toggle sidebar"
          >
            ☰
          </button>
          <h2 className="font-medium text-sm text-slate-700">Research Assistant</h2>
          <span className="ml-auto text-xs text-slate-400">Powered by Ollama · LangGraph · ChromaDB</span>
        </header>

        <div className="flex-1 overflow-hidden">
          <ChatWindow documents={documents} sessionId={SESSION_ID} />
        </div>
      </div>
    </div>
  )
}
