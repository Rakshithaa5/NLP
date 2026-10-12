/**
 * App.jsx — Root application component.
 *
 * Layout strategy:
 * - Dashboard page owns its own sidebar (full-bleed layout).
 * - Home / History / TranscriptPreview use the shared topbar (NavBar).
 */
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import NavBar from './components/NavBar'
import Home from './pages/Home'
import TranscriptPreview from './pages/TranscriptPreview'
import Dashboard from './pages/Dashboard'
import History from './pages/History'

function AppShell() {
  const { pathname } = useLocation()
  // Dashboard pages own their full layout (sidebar + content)
  const isDashboard = pathname.startsWith('/dashboard/')
  if (isDashboard) return <Routes><Route path="/dashboard/:fileId" element={<Dashboard />} /></Routes>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <NavBar />
      <main style={{ flex: 1 }}>
        <Routes>
          <Route path="/"                   element={<Home />} />
          <Route path="/transcript/:fileId" element={<TranscriptPreview />} />
          <Route path="/history"            element={<History />} />
        </Routes>
      </main>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}

export default App
