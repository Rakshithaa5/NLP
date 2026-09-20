/**
 * pages/Dashboard.jsx — Full meeting intelligence dashboard (Phase 4).
 *
 * Fetches analysis results for a meeting and renders:
 *   - Header stat pills (duration, action items, decisions, questions)
 *   - Executive summary panel (abstractive + extractive comparison)
 *   - Key topics panel (TF-IDF keywords + topic clusters)
 *   - Action items panel (person → task → deadline → status table)
 *   - Decisions panel
 *   - Unresolved questions panel
 *   - Named entities panel
 *   - Classification breakdown chart (Recharts RadialBarChart)
 *   - PDF export button
 *
 * Route: /dashboard/:fileId
 */

import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  RadialBarChart, RadialBar, Legend, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Cell,
} from 'recharts'
import { getAnalysis, analyzeMeeting, exportPdf } from '../services/api'

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function fmtDur(s) {
  if (!s) return '—'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  return h > 0 ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m ${String(sec).padStart(2, '0')}s`
}

const LABEL_COLORS = {
  'ACTION ITEM': '#6366f1',
  DECISION:      '#06b6d4',
  QUESTION:      '#f59e0b',
  DISCUSSION:    '#10b981',
  INFORMATION:   '#94a3b8',
}

const STATUS_COLORS = {
  Pending:     '#f59e0b',
  Completed:   '#10b981',
  'In Progress': '#6366f1',
  Blocked:     '#ef4444',
}

const ENTITY_ICONS = {
  PERSON:     '👤', ORG: '🏢', LOCATION: '📍',
  DATE:       '📅', TIME: '⏰', MONEY: '💰',
  PERCENT:    '📊', EVENT: '🎯', TECHNOLOGY: '⚙️', PROJECT: '🚀',
}

/* ── Sub-components ──────────────────────────────────────────────────────── */

function StatPill({ icon, label, value, color = 'var(--clr-primary)' }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '14px 20px', flex: '1 1 160px',
      background: 'var(--grad-card)',
      border: '1px solid var(--clr-border)',
      borderRadius: 'var(--radius-lg)',
      transition: 'border-color var(--transition)',
    }}>
      <div style={{
        width: 42, height: 42, borderRadius: 12,
        background: `${color}22`,
        border: `1px solid ${color}44`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 20,
      }}>{icon}</div>
      <div>
        <p style={{ fontSize: 11, color: 'var(--clr-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>{label}</p>
        <p style={{ fontSize: 22, fontWeight: 800, color: 'var(--clr-text)' }}>{value}</p>
      </div>
    </div>
  )
}

function Section({ title, icon, children, badge }) {
  return (
    <div style={{
      background: 'var(--grad-card)', border: '1px solid var(--clr-border)',
      borderRadius: 'var(--radius-lg)', padding: '22px 24px', marginBottom: 20,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <span style={{ fontSize: 18 }}>{icon}</span>
        <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--clr-text)' }}>{title}</h2>
        {badge != null && (
          <span style={{
            marginLeft: 'auto', fontSize: 11, fontWeight: 600,
            padding: '3px 10px', borderRadius: 99,
            background: 'rgba(99,102,241,0.15)', color: 'var(--clr-primary)',
            border: '1px solid rgba(99,102,241,0.3)',
          }}>{badge}</span>
        )}
      </div>
      {children}
    </div>
  )
}

function EmptyState({ msg }) {
  return <p style={{ color: 'var(--clr-text-dim)', fontSize: 13, fontStyle: 'italic' }}>{msg}</p>
}

function ActionItemRow({ item, index }) {
  const status = item.status || 'Pending'
  const color = STATUS_COLORS[status] || '#94a3b8'
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 2.5fr 1.2fr 0.8fr',
      gap: 12,
      padding: '12px 14px',
      borderRadius: 10,
      background: index % 2 === 0 ? 'rgba(30,41,59,0.4)' : 'transparent',
      alignItems: 'start',
    }}>
      <div>
        {item.person
          ? <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--clr-accent)' }}>👤 {item.person}</span>
          : <span style={{ color: 'var(--clr-text-dim)', fontSize: 13 }}>—</span>}
      </div>
      <p style={{ fontSize: 13, color: 'var(--clr-text-muted)', margin: 0, lineHeight: 1.5 }}>
        {item.task || item.original}
      </p>
      <p style={{ fontSize: 12, color: item.deadline ? 'var(--clr-warn)' : 'var(--clr-text-dim)', margin: 0 }}>
        {item.deadline ? `📅 ${item.deadline}` : '—'}
      </p>
      <span style={{
        display: 'inline-block', padding: '3px 8px', borderRadius: 99,
        fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
        background: `${color}22`, color, border: `1px solid ${color}44`,
      }}>{status}</span>
    </div>
  )
}

function ActionItemsHeader() {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 2.5fr 1.2fr 0.8fr',
      gap: 12, padding: '8px 14px', marginBottom: 4,
    }}>
      {['Person', 'Task', 'Deadline', 'Status'].map(h => (
        <p key={h} style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--clr-text-dim)', margin: 0 }}>{h}</p>
      ))}
    </div>
  )
}

function ClassificationChart({ classifications }) {
  if (!classifications?.length) return null

  const counts = {}
  for (const c of classifications) {
    counts[c.label] = (counts[c.label] || 0) + 1
  }
  const data = Object.entries(counts).map(([label, count]) => ({
    name: label, value: count, fill: LABEL_COLORS[label] || '#94a3b8',
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} />
        <Tooltip
          contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 10, fontSize: 12 }}
          labelStyle={{ color: '#f1f5f9' }}
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
        />
        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
          {data.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function EntityBadge({ text, label }) {
  const icon = ENTITY_ICONS[label] || '🔹'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '4px 10px', borderRadius: 99, margin: '3px',
      fontSize: 12, fontWeight: 500,
      background: 'rgba(99,102,241,0.12)', color: 'var(--clr-text-muted)',
      border: '1px solid rgba(99,102,241,0.2)',
    }}>
      {icon} {text}
    </span>
  )
}

/* ── Spinner ─────────────────────────────────────────────────────────────── */
function Spinner({ label }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16 }}>
      <div style={{
        width: 56, height: 56, borderRadius: '50%',
        border: '3px solid var(--clr-border)',
        borderTopColor: 'var(--clr-primary)',
        animation: 'spin 0.8s linear infinite',
      }} />
      {label && <p style={{ color: 'var(--clr-text-muted)', fontSize: 14 }}>{label}</p>}
    </div>
  )
}

/* ── Main Page ───────────────────────────────────────────────────────────── */
export default function Dashboard() {
  const { fileId } = useParams()
  const navigate   = useNavigate()

  const [data,         setData]         = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [analyzing,    setAnalyzing]    = useState(false)
  const [error,        setError]        = useState(null)
  const [summaryTab,   setSummaryTab]   = useState('abstractive') // 'abstractive' | 'extractive'
  const [exporting,    setExporting]    = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getAnalysis(fileId)
      setData(result)
    } catch (e) {
      // 404 / "No analysis found" means the meeting hasn't been analysed yet
      // — show the "Run Analysis" prompt instead of an error screen.
      const msg = (e.message || '').toLowerCase()
      const isNotAnalysed =
        msg.includes('404') ||
        msg.includes('not found') ||
        msg.includes('no analysis found') ||
        msg.includes('call post')
      if (isNotAnalysed) {
        setData(null)
      } else {
        setError(e.message || 'Failed to load analysis.')
      }
    } finally {
      setLoading(false)
    }
  }, [fileId])

  useEffect(() => { load() }, [load])

  const runAnalysis = async () => {
    setAnalyzing(true)
    setError(null)
    try {
      const result = await analyzeMeeting(fileId)
      setData(result)
    } catch (e) {
      setError(e.message || 'Analysis failed.')
    } finally {
      setAnalyzing(false)
    }
  }

  const handleExport = () => {
    setExporting(true)
    exportPdf(fileId)
    setTimeout(() => setExporting(false), 2000)
  }

  /* ── States ─────────────────────────────────────────────────────────────── */
  if (loading) return <Spinner label="Loading analysis…" />

  if (error) return (
    <div style={{ maxWidth: 600, margin: '80px auto', textAlign: 'center', padding: 24 }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
      <p style={{ color: 'var(--clr-error)', fontWeight: 600, marginBottom: 20 }}>{error}</p>
      <button id="dashboard-back-btn" onClick={() => navigate(-1)} style={btnStyle('secondary')}>← Back</button>
    </div>
  )

  if (analyzing) return <Spinner label="Running NLP analysis pipeline… this may take a minute." />

  if (!data) return (
    <div style={{ maxWidth: 600, margin: '80px auto', textAlign: 'center', padding: 24 }} className="animate-fade-up">
      <div style={{ fontSize: 64, marginBottom: 20 }}>🧠</div>
      <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 10 }} className="gradient-text">Analysis Not Run Yet</h1>
      <p style={{ color: 'var(--clr-text-muted)', marginBottom: 28, lineHeight: 1.7 }}>
        This meeting has been transcribed but hasn&apos;t gone through the NLP pipeline yet.
        Click below to run the full analysis (NER, classification, topics, action items, decisions, summarization).
      </p>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
        <button id="run-analysis-btn" onClick={runAnalysis} style={btnStyle('primary')}>
          🚀 Run Full NLP Analysis
        </button>
        <button id="back-btn" onClick={() => navigate(-1)} style={btnStyle('secondary')}>← Back</button>
      </div>
    </div>
  )

  /* ── Data destructuring ─────────────────────────────────────────────────── */
  const {
    entities       = [],
    classifications = [],
    topics         = {},
    action_items   = [],
    decisions      = [],
    questions      = [],
    summary        = {},
    analyzed_at,
  } = data

  const keywords      = topics.keywords || []
  const topicClusters = topics.topics   || []
  const summary_abs   = summary.abstractive || ''
  const summary_ext   = summary.extractive  || ''

  /* ── Group entities by label ────────────────────────────────────────────── */
  const entityGroups = {}
  for (const e of entities) {
    entityGroups[e.label] = entityGroups[e.label] || []
    entityGroups[e.label].push(e.text)
  }

  /* ── Classification stats ───────────────────────────────────────────────── */
  const total = classifications.length
  const labelCounts = {}
  for (const c of classifications) {
    labelCounts[c.label] = (labelCounts[c.label] || 0) + 1
  }

  /* ── Render ─────────────────────────────────────────────────────────────── */
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '28px 20px' }} className="animate-fade-up">

      {/* ── Top toolbar ────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <button id="dashboard-back-btn" onClick={() => navigate(-1)} style={{
            background: 'none', border: 'none', color: 'var(--clr-text-muted)',
            fontSize: 13, cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', gap: 6,
          }}>← Back</button>
          <h1 style={{ fontSize: 28, fontWeight: 800, marginTop: 8, marginBottom: 4 }} className="gradient-text">
            Meeting Dashboard
          </h1>
          {analyzed_at && (
            <p style={{ fontSize: 12, color: 'var(--clr-text-dim)' }}>
              Analysed {new Date(analyzed_at).toLocaleString()}
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button id="reanalyze-btn" onClick={runAnalysis} style={btnStyle('ghost')}>🔄 Re-analyse</button>
          <button id="export-pdf-btn" onClick={handleExport} disabled={exporting} style={btnStyle('primary')}>
            {exporting ? '⏳ Opening…' : '📄 Export PDF'}
          </button>
        </div>
      </div>

      {/* ── Header stat pills ───────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
        <StatPill icon="✅" label="Action Items"      value={action_items.length}   color="#6366f1" />
        <StatPill icon="⚖️" label="Decisions"         value={decisions.length}      color="#06b6d4" />
        <StatPill icon="❓" label="Open Questions"    value={questions.length}       color="#f59e0b" />
        <StatPill icon="📝" label="Sentences"          value={total}                 color="#10b981" />
        <StatPill icon="🏷️" label="Entities Found"    value={entities.length}        color="#8b5cf6" />
      </div>

      {/* ── Summary ─────────────────────────────────────────────────────────── */}
      <Section title="Executive Summary" icon="📋" badge={summary.preferred === 'abstractive' ? 'AI Abstractive' : 'Extractive'}>
        {(summary_abs || summary_ext) ? (
          <>
            {/* Tab switcher */}
            {summary_abs && summary_ext && (
              <div style={{ display: 'flex', gap: 2, marginBottom: 14, background: 'var(--clr-surface)', borderRadius: 8, padding: 4, width: 'fit-content' }}>
                {[['abstractive', '🤖 AI Summary'], ['extractive', '📊 Extractive']].map(([tab, label]) => (
                  <button key={tab} id={`summary-tab-${tab}`} onClick={() => setSummaryTab(tab)} style={{
                    padding: '6px 16px', borderRadius: 6, border: 'none', fontSize: 12, cursor: 'pointer',
                    background: summaryTab === tab ? 'var(--clr-surface-2)' : 'transparent',
                    color: summaryTab === tab ? 'var(--clr-text)' : 'var(--clr-text-muted)',
                    fontWeight: summaryTab === tab ? 600 : 400,
                    transition: 'all var(--transition)',
                  }}>{label}</button>
                ))}
              </div>
            )}
            <p style={{ fontSize: 14, lineHeight: 1.8, color: 'var(--clr-text-muted)', margin: 0 }}>
              {summaryTab === 'abstractive' ? (summary_abs || summary_ext) : (summary_ext || summary_abs)}
            </p>
          </>
        ) : <EmptyState msg="No summary generated." />}
      </Section>

      {/* ── Two-column layout ─────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>

        {/* Key Topics */}
        <Section title="Key Topics" icon="🏷️" badge={`${keywords.length} keywords`}>
          {keywords.length > 0 ? (
            <>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
                {keywords.slice(0, 18).map((kw, i) => (
                  <span key={i} style={{
                    padding: '4px 10px', borderRadius: 99, fontSize: 12,
                    background: `rgba(6,182,212,${0.1 + (0.02 * (18 - i))})`,
                    color: 'var(--clr-accent)', border: '1px solid rgba(6,182,212,0.2)',
                  }}>{kw}</span>
                ))}
              </div>
              {topicClusters.length > 0 && (
                <>
                  <p style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--clr-text-dim)', marginBottom: 8 }}>Topic Clusters (LDA)</p>
                  {topicClusters.slice(0, 4).map((t, i) => (
                    <div key={i} style={{ marginBottom: 8 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--clr-primary)', marginRight: 6 }}>
                        Topic {i + 1}:
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--clr-text-muted)' }}>
                        {(t.terms || []).slice(0, 6).join(', ')}
                      </span>
                    </div>
                  ))}
                </>
              )}
            </>
          ) : <EmptyState msg="No topics extracted." />}
        </Section>

        {/* Classification breakdown */}
        <Section title="Sentence Classification" icon="📊" badge={`${total} sentences`}>
          {total > 0 ? (
            <>
              <ClassificationChart classifications={classifications} />
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
                {Object.entries(labelCounts).map(([label, count]) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--clr-text-muted)' }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: LABEL_COLORS[label] || '#94a3b8' }} />
                    {label} ({count})
                  </div>
                ))}
              </div>
            </>
          ) : <EmptyState msg="No classifications." />}
        </Section>
      </div>

      {/* ── Action Items ────────────────────────────────────────────────────── */}
      <Section title="Action Items" icon="✅" badge={action_items.length}>
        {action_items.length > 0 ? (
          <>
            <ActionItemsHeader />
            {action_items.map((item, i) => <ActionItemRow key={i} item={item} index={i} />)}
          </>
        ) : <EmptyState msg="No action items detected in this meeting." />}
      </Section>

      {/* ── Two column: Decisions + Questions ───────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>

        <Section title="Decisions" icon="⚖️" badge={decisions.length}>
          {decisions.length > 0 ? decisions.map((d, i) => (
            <div key={i} style={{
              display: 'flex', gap: 10, padding: '10px 12px',
              borderRadius: 8, marginBottom: 6,
              background: i % 2 === 0 ? 'rgba(30,41,59,0.4)' : 'transparent',
            }}>
              <span style={{ color: 'var(--clr-accent)', fontWeight: 700, fontSize: 13, minWidth: 20 }}>{i + 1}.</span>
              <p style={{ fontSize: 13, color: 'var(--clr-text-muted)', margin: 0, lineHeight: 1.6 }}>
                {d.statement || d.original}
              </p>
            </div>
          )) : <EmptyState msg="No decisions recorded." />}
        </Section>

        <Section title="Unresolved Questions" icon="❓" badge={questions.length}>
          {questions.length > 0 ? questions.map((q, i) => (
            <div key={i} style={{
              display: 'flex', gap: 10, padding: '10px 12px',
              borderRadius: 8, marginBottom: 6, alignItems: 'flex-start',
              background: i % 2 === 0 ? 'rgba(30,41,59,0.4)' : 'transparent',
            }}>
              <span style={{ color: 'var(--clr-warn)', fontWeight: 700, fontSize: 13, minWidth: 20 }}>{i + 1}.</span>
              <div>
                <p style={{ fontSize: 13, color: 'var(--clr-text-muted)', margin: 0, lineHeight: 1.6 }}>
                  {q.question || q.original}
                </p>
                {q.is_action_required && (
                  <span style={{
                    fontSize: 10, fontWeight: 700, color: 'var(--clr-error)',
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                  }}>⚡ Action Required</span>
                )}
              </div>
            </div>
          )) : <EmptyState msg="No unresolved questions." />}
        </Section>
      </div>

      {/* ── Named Entities ──────────────────────────────────────────────────── */}
      <Section title="Named Entities" icon="🏷️" badge={entities.length}>
        {Object.keys(entityGroups).length > 0 ? (
          Object.entries(entityGroups).map(([label, texts]) => (
            <div key={label} style={{ marginBottom: 12 }}>
              <p style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--clr-text-dim)', marginBottom: 6 }}>
                {ENTITY_ICONS[label] || '🔹'} {label}
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                {texts.map((t, i) => <EntityBadge key={i} text={t} label={label} />)}
              </div>
            </div>
          ))
        ) : <EmptyState msg="No entities detected." />}
      </Section>

    </div>
  )
}

function btnStyle(variant) {
  const base = {
    padding: '10px 20px', borderRadius: 10, fontWeight: 600,
    fontSize: 13, cursor: 'pointer', border: 'none',
    transition: 'all var(--transition)',
  }
  if (variant === 'primary')   return { ...base, background: 'var(--grad-brand)', color: '#fff' }
  if (variant === 'ghost')     return { ...base, background: 'rgba(99,102,241,0.12)', color: 'var(--clr-primary)', border: '1px solid rgba(99,102,241,0.3)' }
  return { ...base, background: 'var(--clr-surface-2)', color: 'var(--clr-text)' }
}
