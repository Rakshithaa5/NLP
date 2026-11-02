import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { checkHealth } from '../services/api'

export default function NavBar({tab, activate}) {
  const {pathname} = useLocation()
  const [healthy, setHealthy] = useState(null)
  const [collapsed, setCollapsed] = useState(false)
  const drawer = useRef(null)
  const trigger = useRef(null)
  useEffect(() => { checkHealth().then(() => setHealthy(true)).catch(() => setHealthy(false)) }, [])
  const close = () => drawer.current?.close()
  const content = <>
    <button className="sidebar-header sidebar-toggle" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={() => setCollapsed(v => !v)}>
      <span className="sidebar-logo" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="5" y="3" width="15" height="18" rx="3"/><path d="M3 7h4M3 12h4M3 17h4M10 8h6M10 12h6M10 16h4"/></svg></span>
      {!collapsed && <span className="sidebar-name">MeetingIntel<span className="brand-caption">A little clarity, after every meeting.</span></span>}
    </button>
    <nav className="sidebar-section" aria-label="Main navigation">
      <Link to="/" className="sidebar-item new-meeting" aria-current={pathname === '/' ? 'page' : undefined} onClick={close} title="New meeting">{collapsed ? '＋' : <><span aria-hidden="true">＋</span> New meeting</>}</Link>
      {!collapsed && <span className="sidebar-section-label">Workspace</span>}
      <Link to="/history" className={`sidebar-item${pathname === '/history' ? ' active' : ''}`} aria-current={pathname === '/history' ? 'page' : undefined} onClick={close} title="All meetings">{collapsed ? '▤' : <><span aria-hidden="true">▤</span> All meetings</>}</Link>
      {activate && <>{!collapsed && <span className="sidebar-section-label meeting-nav-label">This meeting</span>}{['overview','transcript','analytics','topics'].map((value,index) => <button key={value} className={`sidebar-item${tab === value ? ' active' : ''}`} aria-current={tab === value ? 'page' : undefined} onClick={() => {activate(value); close()}} title={value[0].toUpperCase()+value.slice(1)}>{collapsed ? <span className="nav-number">{`0${index+1}`}</span> : <><span className="nav-number" aria-hidden="true">0{index+1}</span>{value[0].toUpperCase()+value.slice(1)}</>}</button>)}</>}
    </nav>
    {!collapsed && <div className="sidebar-footer"><span className="connection-status" role="status"><i className={healthy === true ? 'online' : healthy === false ? 'offline' : ''}/>{healthy === null ? 'Connecting to workspace' : healthy ? 'Workspace connected' : 'Backend unavailable'}</span><p>Intelligent Meeting Analysis System</p></div>}
  </>
  return <>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className={`sidebar desktop-sidebar${collapsed ? ' sidebar-collapsed' : ''}`}>{content}</aside>
    <header className="mobile-nav"><span>MeetingIntel</span><button ref={trigger} className="btn btn-secondary" aria-label="Open navigation" aria-haspopup="dialog" onClick={() => drawer.current.showModal()}>Menu</button></header>
    <dialog ref={drawer} className="nav-drawer" aria-label="Workspace navigation" onClose={() => trigger.current?.focus()} onClick={e => {if(e.target === drawer.current) close()}}><div className="drawer-content"><button className="btn btn-secondary drawer-close" onClick={close}>Close menu</button>{content}</div></dialog>
  </>
}
