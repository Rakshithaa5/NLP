/**
 * components/NavBar.jsx — Top navigation bar.
 *
 * Phase 4: Add route links (Home, History).
 * Phase 0: Static shell — extracted from App.jsx so Phase 1 can
 *          import it without touching App.jsx.
 */

export default function NavBar() {
  return (
    <nav className="border-b border-slate-700 px-6 py-4 flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center font-bold text-white text-sm">
        MA
      </div>
      <span className="font-semibold text-lg tracking-tight">Meeting Analyzer</span>
    </nav>
  )
}
