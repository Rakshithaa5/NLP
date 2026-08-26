/**
 * App.jsx — Root application component.
 *
 * Phase 0: renders a minimal shell with a nav bar and a placeholder
 *          content area. Full page routing is added in Phase 4.
 */
import React from 'react'
import './App.css'

function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* Nav */}
      <nav className="border-b border-slate-700 px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center font-bold text-white text-sm">
          MA
        </div>
        <span className="font-semibold text-lg tracking-tight">Meeting Analyzer</span>
      </nav>

      {/* Shell content */}
      <main className="flex flex-col items-center justify-center min-h-[calc(100vh-64px)] gap-4 text-center px-4">
        <h1 className="text-4xl font-bold text-indigo-400">Meeting Analyzer</h1>
        <p className="text-slate-400 max-w-md">
          AI-powered NLP pipeline for automated meeting analysis.
          Upload a recording to extract transcripts, action items, decisions, and summaries.
        </p>
        <span className="text-xs text-slate-600 mt-8">Phase 0 — skeleton shell ✓</span>
      </main>
    </div>
  )
}

export default App
