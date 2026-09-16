/**
 * pages/History.jsx — Meeting history list with analytics (Phase 4).
 *
 * Fetches all previously uploaded meetings from the backend and renders:
 *   - Summary stat cards (total meetings, total duration, avg duration)
 *   - Recharts BarChart — meetings uploaded over time
 *   - Sortable, filterable meeting cards with status badges
 *   - Links to transcript preview and dashboard for each meeting
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import { listMeetings } from '../services/api'

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function fmtDur(s) {
  if (!s && s !== 0) return '—'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  return h > 0 ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m ${String(sec).padStart(2, '0')}s`
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function fmtDateShort(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

const STATUS_STYLES = {
  done:       { bg: 'rgba(16,185,129,0.15)', color: '#10b981', label: 'Done' },
  processing: { bg: 'rgba(99,102,241,0.15)', color: '#6366f1', label: 'Processing' },
  uploaded:   { bg: 'rgba(245,158,11,0.15)', color: '#f59e0b', label: 'Uploaded' },
  error:      { bg: 'rgba(239,68,68,0.15)',  color: '#ef4444', label: 'Error' },
}

/* ── Sub-components ──────────────────────────────────────────────────────── */

function SummaryStat({ icon, label, value, sub }) {
  return (
    <div style={{
      flex: '1 1 160px',
      padding: '18px 20px',
      background: 'var(--grad-card)',
      border: '1px solid var(--clr-border)',
      borderRadius: 'var(--radius-lg)',
    }}>
      <div style={{ fontSize: 28, marginBottom: 8 }}>{icon}</div>
      <p style={{ fontSize: 26, fontWeight: 800, color: 'var(--clr-text)', margin: 0 }}>{value}</p>
      <p style={{ fontSize: 12, color: 'var(--clr-text-muted)', margin: '4px 0 0' }}>{label}</p>
      {sub && <p style={{ fontSize: 11, color: 'var(--clr-text-dim)', margin: '2px 0 0' }}>{sub}</p>}
    </div>
  )
}

function MeetingCard({ meeting, onView, onAnalyze }) {
  const status = meeting.status || 'uploaded'
  const ss = STATUS_STYLES[status] || STATUS_STYLES.uploaded
  const ext = meeting.filename?.split('.').pop()?.toUpperCase() || 'FILE'

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '40px 1fr auto auto auto',
      alignItems: 'center',
      gap: 16,
      padding: '16px 18px',
      background: 'var(--grad-card)',
      border: '1px solid var(--clr-border)',
      borderRadius: 'var(--radius-md)',
      transition: 'border-color var(--transition), transform var(--transition)',
      cursor: 'default',
    }}
      onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--clr-border-2)'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--clr-border)'}
    >
      {/* File icon */}
      <div style={{
        width: 40, height: 40, borderRadius: 10,
        background: 'rgba(99,102,241,0.15)',
        border: '1px solid rgba(99,102,241,0.3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 800, color: 'var(--clr-primary)',
        letterSpacing: '0.02em',
      }}>{ext}</div>

      {/* Info */}
      <div style={{ minWidth: 0 }}>
        <p style={{
          fontSize: 14, fontWeight: 600, color: 'var(--clr-text)',
          margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{meeting.filename || 'Untitled'}</p>
        <p style={{ fontSize: 11, color: 'var(--clr-text-dim)', margin: '3px 0 0' }}>
          {fmtDate(meeting.uploaded_at)} · {fmtDur(meeting.duration)} · {(meeting.language || '').toUpperCase()}
        </p>
      </div>

      {/* Status badge */}
      <span style={{
        padding: '4px 12px', borderRadius: 99, fontSize: 11, fontWeight: 700,
        background: ss.bg, color: ss.color, whiteSpace: 'nowrap',
      }}>{ss.label}</span>

      {/* View transcript */}
      <button
        id={`view-transcript-${meeting.id}`}
        onClick={() => onView(meeting.id)}
        style={smallBtn('ghost')}
      >📄 Transcript</button>

      {/* Dashboard */}
      <button
        id={`view-dashboard-${meeting.id}`}
        onClick={() => onAnalyze(meeting.id)}
        style={smallBtn('primary')}
      >🧠 Dashboard</button>
    </div>
  )
}

/* ── Chart — meetings per day ─────────────────────────────────────────────── */
function UploadChart({ meetings }) {
  if (!meetings.length) return null

  const counts = {}
  for (const m of meetings) {
    const day = fmtDateShort(m.uploaded_at)
    counts[day] = (counts[day] || 0) + 1
  }

  // Keep last 14 days
  const data = Object.entries(counts)
    .slice(-14)
    .map(([date, count]) => ({ date, count }))

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
        <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip
          contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 10, fontSize: 12 }}
          labelStyle={{ color: '#f1f5f9' }}
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
        />
        <Bar dataKey="count" radius={[5, 5, 0, 0]}>
          {data.map((_, i) => <Cell key={i} fill={i === data.length - 1 ? '#6366f1' : '#1e3a5f'} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ── Main ────────────────────────────────────────────────────────────────── */
export default function History() {
  const navigate = useNavigate()

  const [meetings, setMeetings] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)
  const [search,   setSearch]   = useState('')
  const [sortKey,  setSortKey]  = useState('uploaded_at')  // 'uploaded_at' | 'duration' | 'filename'

  useEffect(() => {
    listMeetings()
      .then(res => setMeetings(res.meetings || []))
      .catch(e => setError(e.message || 'Failed to load meeting history.'))
      .finally(() => setLoading(false))
  }, [])

  /* ── Derived data ─────────────────────────────────────────────────────── */
  const totalDuration = meetings.reduce((s, m) => s + (m.duration || 0), 0)
  const avgDuration   = meetings.length ? totalDuration / meetings.length : 0
  const doneCount     = meetings.filter(m => m.status === 'done').length

  const filtered = meetings
    .filter(m => !search || (m.filename || '').toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortKey === 'duration')    return (b.duration || 0) - (a.duration || 0)
      if (sortKey === 'filename')    return (a.filename || '').localeCompare(b.filename || '')
      return new Date(b.uploaded_at || 0) - new Date(a.uploaded_at || 0)
    })

  /* ── States ─────────────────────────────────────────────────────────────── */
  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16 }}>
      <div style={{
        width: 52, height: 52, borderRadius: '50%',
        border: '3px solid var(--clr-border)',
        borderTopColor: 'var(--clr-primary)',
        animation: 'spin 0.8s linear infinite',
      }} />
      <p style={{ color: 'var(--clr-text-muted)', fontSize: 14 }}>Loading meeting history…</p>
    </div>
  )

  if (error) return (
    <div style={{ maxWidth: 600, margin: '80px auto', textAlign: 'center', padding: 24 }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
      <p style={{ color: 'var(--clr-error)', fontWeight: 600 }}>{error}</p>
    </div>
  )

  /* ── Render ─────────────────────────────────────────────────────────────── */
  return (
    <div style={{ maxWidth: 1050, margin: '0 auto', padding: '28px 20px' }} className="animate-fade-up">

      <h1 style={{ fontSize: 28, fontWeight: 800, marginBottom: 6 }} className="gradient-text">
        Meeting History
      </h1>
      <p style={{ fontSize: 14, color: 'var(--clr-text-muted)', marginBottom: 28 }}>
        All your analysed meetings in one place.
      </p>

      {/* ── Summary stats ──────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 28 }}>
        <SummaryStat icon="🎙️" label="Total Meetings"   value={meetings.length} />
        <SummaryStat icon="⏱️" label="Total Duration"   value={fmtDur(totalDuration)} />
        <SummaryStat icon="📊" label="Avg Duration"     value={fmtDur(avgDuration)} />
        <SummaryStat icon="✅" label="Fully Analysed"   value={doneCount}
          sub={`${meetings.length - doneCount} pending`} />
      </div>

      {/* ── Upload frequency chart ─────────────────────────────────────────── */}
      {meetings.length > 1 && (
        <div style={{
          background: 'var(--grad-card)', border: '1px solid var(--clr-border)',
          borderRadius: 'var(--radius-lg)', padding: '20px 24px', marginBottom: 24,
        }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--clr-text-muted)', marginBottom: 12 }}>
            📈 Uploads over time
          </p>
          <UploadChart meetings={meetings} />
        </div>
      )}

      {/* ── Toolbar ───────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          id="history-search"
          type="text"
          placeholder="🔍  Search by filename…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            flex: '1 1 220px', padding: '9px 14px',
            borderRadius: 10, border: '1px solid var(--clr-border)',
            background: 'var(--clr-surface)', color: 'var(--clr-text)',
            fontSize: 13, outline: 'none',
          }}
        />
        <div style={{ display: 'flex', gap: 2, background: 'var(--clr-surface)', borderRadius: 8, padding: 3 }}>
          {[['uploaded_at', '🕐 Date'], ['duration', '⏱ Duration'], ['filename', '🔤 Name']].map(([key, label]) => (
            <button key={key} id={`sort-${key}`} onClick={() => setSortKey(key)} style={{
              padding: '6px 14px', borderRadius: 6, border: 'none', fontSize: 12, cursor: 'pointer',
              background: sortKey === key ? 'var(--clr-surface-2)' : 'transparent',
              color: sortKey === key ? 'var(--clr-text)' : 'var(--clr-text-muted)',
              fontWeight: sortKey === key ? 600 : 400,
              transition: 'all var(--transition)',
            }}>{label}</button>
          ))}
        </div>
      </div>

      {/* ── Meeting list ──────────────────────────────────────────────────── */}
      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 24px' }}>
          <div style={{ fontSize: 52, marginBottom: 16 }}>📭</div>
          <p style={{ color: 'var(--clr-text-muted)', fontSize: 14 }}>
            {search ? 'No meetings match your search.' : 'No meetings uploaded yet. Upload your first recording!'}
          </p>
          {!search && (
            <button id="go-upload-btn" onClick={() => navigate('/')} style={{
              marginTop: 16, padding: '10px 24px', borderRadius: 10,
              background: 'var(--grad-brand)', color: '#fff', fontWeight: 700, fontSize: 13, border: 'none', cursor: 'pointer',
            }}>Upload a Meeting →</button>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(m => (
            <MeetingCard
              key={m.id}
              meeting={m}
              onView={id => navigate(`/transcript/${id}`)}
              onAnalyze={id => navigate(`/dashboard/${id}`)}
            />
          ))}
        </div>
      )}

    </div>
  )
}

function smallBtn(variant) {
  const base = {
    padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
    cursor: 'pointer', border: 'none', whiteSpace: 'nowrap',
    transition: 'all var(--transition)',
  }
  if (variant === 'primary') return { ...base, background: 'var(--grad-brand)', color: '#fff' }
  return { ...base, background: 'rgba(99,102,241,0.12)', color: 'var(--clr-primary)', border: '1px solid rgba(99,102,241,0.25)' }
}
