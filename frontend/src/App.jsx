import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import NavBar from './components/NavBar'
import Home from './pages/Home'
import TranscriptPreview from './pages/TranscriptPreview'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import './workspace.css'

function AppShell() {
  const {pathname} = useLocation()
  if (pathname.startsWith('/dashboard/')) return <Routes><Route path="/dashboard/:fileId" element={<Dashboard />} /></Routes>
  return <div className="workspace-shell"><NavBar/><main id="main-content" tabIndex={-1} className="workspace-content"><Routes>
    <Route path="/" element={<Home/>}/><Route path="/history" element={<History/>}/><Route path="/transcript/:fileId" element={<TranscriptPreview/>}/>
    <Route path="*" element={<div className="page-container"><h1>Page not found</h1><p>Use All meetings to return to your workspace.</p></div>}/>
  </Routes></main></div>
}
export default function App() {return <BrowserRouter><AppShell/></BrowserRouter>}
