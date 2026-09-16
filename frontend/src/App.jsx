/**
 * App.jsx — Root application component.
 *
 * Phase 4: History and Dashboard routes wired in.
 */
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import NavBar from './components/NavBar'
import Home from './pages/Home'
import TranscriptPreview from './pages/TranscriptPreview'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <div style={{ minHeight: '100vh' }}>
        <NavBar />
        <main>
          <Routes>
            <Route path="/"                       element={<Home />} />
            <Route path="/transcript/:fileId"     element={<TranscriptPreview />} />
            <Route path="/dashboard/:fileId"      element={<Dashboard />} />
            <Route path="/history"                element={<History />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
