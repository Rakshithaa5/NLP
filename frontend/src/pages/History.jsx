/**
 * pages/History.jsx -- Evernote-inspired meeting history page.
 * Full functionality preserved, premium visual redesign.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { listMeetings } from '../services/api'

function fmtDur(s) {
  if (!s && s !== 0) return '--'
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60)
  return h > 0 ? `${h}h ${String(m).padStart(2,'0')}m` : `${m}m ${String(sec).padStart(2,'0')}s`
}
function fmtDate(iso) {
  if (!iso) return '--'
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}
function fmtDateShort(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

const STATUS_MAP = {
  done:       { label: 'Analyzed',   cls: 'pill-green' },
  processing: { label: 'Processing', cls: 'pill-blue'  },
  uploaded:   { label: 'Uploaded',   cls: 'pill-amber' },
  error:      { label: 'Error',      cls: 'pill-red'   },
}

function StatCard({ icon, label, value, sub }) {
  return (
    <div style={{
      flex: '1 1 160px', padding: '20px 24px',
      background: 'var(--clr-surface)', border: '1px solid var(--clr-border)',
      borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-xs)',
    }}>
      <div style={{ fontSize: 24, marginBottom: 10 }}>{icon}</div>
      <p style={{ fontSize: 28, fontWeight: 800, color: 'var(--clr-text)', margin: 0, fontFamily: '"Plus Jakarta Sans",sans-serif', letterSpacing: '-0.03em' }}>{value}</p>
      <p style={{ fontSize: 12, color: 'var(--clr-text-muted)', margin: '4px 0 0' }}>{label}</p>
      {sub && <p style={{ fontSize: 11, color: 'var(--clr-text-dim)', margin: '2px 0 0' }}>{sub}</p>}
    </div>
  )
}

function MeetingCard({ meeting, onView, onAnalyze }) {
  const status = meeting.status || 'uploaded'
  const ss = STATUS_MAP[status] || STATUS_MAP.uploaded
  const ext = meeting.filename?.split('.').pop()?.toUpperCase() || 'FILE'
  return (
    <div className="meeting-row">
      <div style={{
        width: 40, height: 40, borderRadius: 'var(--radius-sm)',
        background: 'var(--clr-surface-2)', border: '1px solid var(--clr-border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 9, fontWeight: 800, color: 'var(--clr-text-dim)',
        letterSpacing: '0.03em', flexShrink: 0,
      }}>{ext}</div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--clr-text)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {meeting.filename || 'Untitled'}
        </p>
        <p style={{ fontSize: 12, color: 'var(--clr-text-dim)', margin: '3px 0 0' }}>
          {fmtDate(meeting.uploaded_at)}{meeting.duration ? ` · ${fmtDur(meeting.duration)}` : ''}{meeting.language ? ` · ${meeting.language.toUpperCase()}` : ''}
        </p>
      </div>

      <span className={`pill ${ss.cls}`}>{ss.label}</span>

      <button id={`view-transcript-${meeting.id}`} onClick={() => onView(meeting.id)}
        style={{ padding: '7px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--clr-border-2)', background: 'var(--clr-surface)', color: 'var(--clr-text-2)', fontSize: 12, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all var(--transition)' }}
        onMouseEnter={e => e.currentTarget.style.background = 'var(--clr-surface-2)'}
        onMouseLeave={e => e.currentTarget.style.background = 'var(--clr-surface)'}
      >Transcript</button>

      <button id={`view-dashboard-${meeting.id}`} onClick={() => onAnalyze(meeting.id)}
        style={{ padding: '7px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--clr-primary)', background: 'var(--clr-primary)', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all var(--transition)' }}
        onMouseEnter={e => e.currentTarget.style.background = 'var(--clr-primary-h)'}
        onMouseLeave={e => e.currentTarget.style.background = 'var(--clr-primary)'}
      >Dashboard</button>
    </div>
  )
}

function UploadChart({ meetings }) {
  if (!meetings.length) return null
  const counts = {}
  for (const m of meetings) { const day = fmtDateShort(m.uploaded_at); counts[day] = (counts[day] || 0) + 1 }
  const data = Object.entries(counts).slice(-14).map(([date, count]) => ({ date, count }))
  return (
    <ResponsiveContainer width="100%" height={140}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--clr-border)" />
        <XAxis dataKey="date" tick={{ fill: 'var(--clr-text-dim)', fontSize: 10 }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fill: 'var(--clr-text-dim)', fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip contentStyle={{ background: 'var(--clr-surface)', border: '1px solid var(--clr-border)', borderRadius: 10, fontSize: 12, color: 'var(--clr-text)' }} labelStyle={{ color: 'var(--clr-text)' }} cursor={{ fill: 'rgba(0,0,0,0.04)' }} />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => <Cell key={i} fill={i === data.length - 1 ? 'var(--clr-primary)' : 'var(--clr-primary-l)'} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default function History() {
  const navigate = useNavigate()
  const [meetings, setMeetings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState('uploaded_at')

  useEffect(() => {
    listMeetings()
      .then(res => setMeetings(res.meetings || []))
      .catch(e => setError(e.message || 'Failed to load meeting history.'))
      .finally(() => setLoading(false))
  }, [])

  const totalDuration = meetings.reduce((s, m) => s + (m.duration || 0), 0)
  const avgDuration   = meetings.length ? totalDuration / meetings.length : 0
  const doneCount     = meetings.filter(m => m.status === 'done').length

  const filtered = meetings
    .filter(m => !search || (m.filename || '').toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortKey === 'duration') return (b.duration || 0) - (a.duration || 0)
      if (sortKey === 'filename') return (a.filename || '').localeCompare(b.filename || '')
      return new Date(b.uploaded_at || 0) - new Date(a.uploaded_at || 0)
    })

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 14 }}>
      <svg className="animate-spin" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--clr-primary)" strokeWidth="2.5" strokeLinecap="round">
        <circle cx="12" cy="12" r="10" strokeOpacity="0.15"/>
        <path d="M12 2a10 10 0 0 1 10 10"/>
      </svg>
      <p style={{ color: 'var(--clr-text-muted)', fontSize: 14 }}>Loading meeting history…</p>
    </div>
  )

  if (error) return (
    <div style={{ maxWidth: 520, margin: '80px auto', textAlign: 'center', padding: 24 }}>
      <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#fff5f5', border: '1px solid #fecaca', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--clr-error)" strokeWidth="2.5" strokeLinecap="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <p style={{ color: 'var(--clr-error)', fontWeight: 600, marginBottom: 8 }}>{error}</p>
      <p style={{ color: 'var(--clr-text-muted)', fontSize: 13 }}>Check that the backend is running and try again.</p>
    </div>
  )

  return (
    <div className="page-container animate-fade-up">

      <div style={{ marginBottom: 32 }}>
        <p style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--clr-text-dim)', marginBottom: 6 }}>
          Meeting Library
        </p>
        <h1 style={{ fontSize: 30, fontWeight: 800, marginBottom: 6, letterSpacing: '-0.03em' }}>All Meetings</h1>
        <p style={{ fontSize: 14, color: 'var(--clr-text-muted)' }}>Your complete analysis history.</p>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 28 }}>
        <StatCard icon="🎙" label="Total Meetings" value={meetings.length} />
        <StatCard icon="⏱" label="Total Duration" value={fmtDur(totalDuration)} />
        <StatCard icon="📊" label="Avg Duration" value={fmtDur(avgDuration)} />
        <StatCard icon="✅" label="Fully Analyzed" value={doneCount} sub={`${meetings.length - doneCount} pending`} />
      </div>

      {/* Chart */}
      {meetings.length > 1 && (
        <div style={{ background: 'var(--clr-surface)', border: '1px solid var(--clr-border)', borderRadius: 'var(--radius-lg)', padding: '20px 24px', marginBottom: 24, boxShadow: 'var(--shadow-xs)' }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--clr-text-muted)', marginBottom: 16 }}>Upload frequency</p>
          <UploadChart meetings={meetings} />
        </div>
      )}

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1 1 220px' }}>
          <svg style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--clr-text-dim)" strokeWidth="2.5" strokeLinecap="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            id="history-search" type="text" placeholder="Search by filename…"
            value={search} onChange={e => setSearch(e.target.value)}
            style={{ width: '100%', padding: '9px 14px 9px 32px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--clr-border-2)', background: 'var(--clr-surface)', color: 'var(--clr-text)', fontSize: 13, outline: 'none' }}
          />
        </div>
        <div style={{ display: 'flex', gap: 2, background: 'var(--clr-surface-2)', borderRadius: 'var(--radius-sm)', padding: 3, border: '1px solid var(--clr-border)' }}>
          {[['uploaded_at','Date'],['duration','Duration'],['filename','Name']].map(([key, label]) => (
            <button key={key} id={`sort-${key}`} onClick={() => setSortKey(key)} style={{
              padding: '6px 12px', borderRadius: 6, border: 'none', fontSize: 12, cursor: 'pointer',
              background: sortKey === key ? 'var(--clr-surface)' : 'transparent',
              color: sortKey === key ? 'var(--clr-text)' : 'var(--clr-text-muted)',
              fontWeight: sortKey === key ? 600 : 400,
              boxShadow: sortKey === key ? 'var(--shadow-xs)' : 'none',
              transition: 'all var(--transition)',
            }}>{label}</button>
          ))}
        </div>
      </div>

      {/* List */}
      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 24px', background: 'var(--clr-surface)', border: '1px solid var(--clr-border)', borderRadius: 'var(--radius-lg)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>{search ? '🔍' : '📭'}</div>
          <p style={{ color: 'var(--clr-text-muted)', fontSize: 14, marginBottom: 16 }}>
            {search ? 'No meetings match your search.' : 'No meetings uploaded yet. Upload your first recording!'}
          </p>
          {!search && (
            <button id="go-upload-btn" onClick={() => navigate('/')} style={{ padding: '10px 24px', borderRadius: 'var(--radius-sm)', background: 'var(--clr-primary)', color: '#fff', fontWeight: 700, fontSize: 13, border: 'none', cursor: 'pointer' }}>
              Upload a Meeting →
            </button>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {filtered.map(m => (
            <MeetingCard
              key={m.id} meeting={m}
              onView={id => navigate(`/transcript/${id}`)}
              onAnalyze={id => navigate(`/dashboard/${id}`)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
