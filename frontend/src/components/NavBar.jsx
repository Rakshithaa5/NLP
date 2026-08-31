/**
 * components/NavBar.jsx — Top navigation bar.
 *
 * Phase 1: Static nav with Home link + backend health indicator.
 * Phase 4: Add History link and active-route styling.
 */

import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { checkHealth } from '../services/api'

export default function NavBar() {
  const location = useLocation()
  const [healthy, setHealthy] = useState(null)  // null = checking, true = ok, false = down

  useEffect(() => {
    checkHealth()
      .then(() => setHealthy(true))
      .catch(() => setHealthy(false))
  }, [])

  const navLinks = [
    { to: '/', label: 'Upload', id: 'nav-upload' },
    // Phase 4: { to: '/history', label: 'History', id: 'nav-history' },
  ]

  return (
    <nav style={{
      position: 'sticky', top: 0, zIndex: 100,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 28px',
      background: 'rgba(8, 13, 26, 0.85)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      borderBottom: '1px solid var(--clr-border)',
    }}>
      {/* Brand */}
      <Link to="/" id="nav-brand" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
        <div style={{
          width: 34, height: 34,
          borderRadius: 10,
          background: 'var(--grad-brand)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 800, color: '#fff', fontSize: 13,
          boxShadow: 'var(--glow-primary)',
        }}>
          MA
        </div>
        <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--clr-text)', letterSpacing: '-0.01em' }}>
          Meeting Analyzer
        </span>
      </Link>

      {/* Nav links */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        {navLinks.map(link => {
          const isActive = location.pathname === link.to
          return (
            <Link
              key={link.to}
              to={link.to}
              id={link.id}
              style={{
                padding: '7px 16px',
                borderRadius: 'var(--radius-sm)',
                fontWeight: isActive ? 600 : 400,
                fontSize: 14,
                color: isActive ? 'var(--clr-text)' : 'var(--clr-text-muted)',
                background: isActive ? 'var(--clr-surface-2)' : 'transparent',
                textDecoration: 'none',
                transition: 'all var(--transition)',
              }}
            >
              {link.label}
            </Link>
          )
        })}

        {/* Health status dot */}
        <div
          id="health-indicator"
          title={healthy === null ? 'Checking backend…' : healthy ? 'Backend online' : 'Backend offline'}
          style={{
            width: 8, height: 8,
            borderRadius: '50%',
            background: healthy === null ? 'var(--clr-warn)' : healthy ? 'var(--clr-success)' : 'var(--clr-error)',
            marginLeft: 12,
            boxShadow: `0 0 6px ${healthy ? 'var(--clr-success)' : healthy === false ? 'var(--clr-error)' : 'var(--clr-warn)'}`,
            transition: 'background 0.5s',
          }}
        />
      </div>
    </nav>
  )
}
