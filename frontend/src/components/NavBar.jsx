/**
 * components/NavBar.jsx -- replaced by Topbar component.
 * This file now re-exports the Topbar for backward compatibility.
 * The actual topbar UI is in Topbar.jsx.
 */
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { checkHealth } from '../services/api'

export default function NavBar() {
  const location = useLocation()
  const [healthy, setHealthy] = useState(null)

  useEffect(() => {
    checkHealth()
      .then(() => setHealthy(true))
      .catch(() => setHealthy(false))
  }, [])

  const navLinks = [
    { to: '/', label: 'Upload', id: 'nav-upload' },
    { to: '/history', label: 'All Meetings', id: 'nav-history' },
  ]

  return (
    <nav className="topbar" role="navigation" aria-label="Main navigation">
      <Link to="/" id="nav-brand" className="topbar-brand">
        <div className="topbar-logo" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </div>
        <span className="topbar-name">Meeting Intelligence</span>
      </Link>

      <div className="topbar-nav">
        {navLinks.map(link => {
          const isActive = location.pathname === link.to ||
            (link.to !== '/' && location.pathname.startsWith(link.to))
          return (
            <Link
              key={link.to}
              to={link.to}
              id={link.id}
              className={`topbar-link${isActive ? ' active' : ''}`}
            >
              {link.label}
            </Link>
          )
        })}
        <div
          id="health-indicator"
          title={healthy === null ? 'Checking backend...' : healthy ? 'Backend online' : 'Backend offline'}
          style={{
            width: 8, height: 8, borderRadius: '50%', marginLeft: 12,
            background: healthy === null ? 'var(--clr-warn)' : healthy ? 'var(--clr-success)' : 'var(--clr-error)',
            boxShadow: `0 0 0 2px ${healthy ? 'rgba(22,163,74,0.2)' : healthy === false ? 'rgba(220,38,38,0.2)' : 'rgba(217,119,6,0.2)'}`,
            transition: 'background 0.5s',
            flexShrink: 0,
          }}
          aria-label={healthy === null ? 'Checking backend' : healthy ? 'Backend online' : 'Backend offline'}
          role="status"
        />
      </div>
    </nav>
  )
}
