/**
 * App.jsx — Root application component.
 *
 * Phase 1: React Router wired up with routes for Home and TranscriptPreview.
 * Phase 4: Add History route and Dashboard route.
 */
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import NavBar from './components/NavBar'
import Home from './pages/Home'
import TranscriptPreview from './pages/TranscriptPreview'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <div style={{ minHeight: '100vh' }}>
        <NavBar />
        <main>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/transcript/:fileId" element={<TranscriptPreview />} />
            {/* Phase 4: <Route path="/history" element={<History />} /> */}
            {/* Phase 4: <Route path="/dashboard/:fileId" element={<Dashboard />} /> */}
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
