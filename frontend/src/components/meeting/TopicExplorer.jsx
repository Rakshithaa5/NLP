/**
 * TopicExplorer.jsx — Topic Segmentation & Evolution UI
 *
 * Integrated into the existing Dashboard as a new tab.
 * Reuses Panel, Empty, Evidence from Overview and existing CSS tokens.
 */
import { useEffect, useState, useCallback } from 'react'
import { runTopicSegmentation, getTopicSegmentation, getCrossMeetingTopics } from '../../services/api'
import { Panel, Empty } from './Overview'
import { timestamp, list, number } from './data'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'

// ── Colour palette for canonical topics (deterministic by id) ────────────────
const TOPIC_COLORS = [
  '#2db55d', '#3b82f6', '#f59e0b', '#8b5cf6', '#ef4444',
  '#06b6d4', '#ec4899', '#10b981', '#f97316', '#6366f1',
]
function topicColor(id) { return TOPIC_COLORS[id % TOPIC_COLORS.length] }

// ── Small helpers ─────────────────────────────────────────────────────────────
function KeywordChips({ keywords }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
      {list(keywords).map((kw, i) => (
        <span key={i} className="mi-chip" style={{ fontSize: 11 }}>{kw}</span>
      ))}
    </div>
  )
}

function TimeRange({ start, end }) {
  const s = number(start), e = number(end)
  if (s === null && e === null) return <span className="mi-muted" style={{ fontSize: 11 }}>Position unavailable</span>
  return (
    <span style={{ fontSize: 11, color: 'var(--clr-primary)', fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
      {s !== null ? timestamp(s) : '?'}{e !== null ? ` – ${timestamp(e)}` : ''}
    </span>
  )
}

// ── Topic Timeline ────────────────────────────────────────────────────────────
function TopicTimeline({ segments, selectedId, onSelect, hasTimestamps }) {
  if (!segments.length) return <Empty>No topic segments detected.</Empty>

  const totalUnits = segments.reduce((sum, s) => sum + (s.sentence_count || 1), 0)

  return (
    <div style={{ marginBottom: 16 }}>
      {!hasTimestamps && (
        <p className="mi-caption mi-muted" style={{ marginBottom: 8 }}>
          No timestamps available — segment widths represent relative transcript position.
        </p>
      )}
      {/* Timeline bar */}
      <div style={{
        display: 'flex', height: 36, borderRadius: 8, overflow: 'hidden',
        border: '1px solid var(--clr-border)', marginBottom: 12,
      }}>
        {segments.map(seg => {
          const width = `${((seg.sentence_count || 1) / totalUnits) * 100}%`
          const color = topicColor(seg.canonical_topic_id)
          const isSelected = seg.canonical_topic_id === selectedId
          return (
            <div
              key={seg.segment_index}
              title={seg.label}
              onClick={() => onSelect(seg.canonical_topic_id)}
              style={{
                width, background: color, opacity: isSelected ? 1 : 0.55,
                cursor: 'pointer', transition: 'opacity 0.15s',
                borderRight: '1px solid rgba(255,255,255,0.3)',
                outline: isSelected ? `2px solid ${color}` : 'none',
              }}
            />
          )
        })}
      </div>

      {/* Segment list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {segments.map(seg => {
          const color = topicColor(seg.canonical_topic_id)
          const isSelected = seg.canonical_topic_id === selectedId
          return (
            <div
              key={seg.segment_index}
              onClick={() => onSelect(seg.canonical_topic_id)}
              style={{
                display: 'flex', alignItems: 'flex-start', gap: 10,
                padding: '10px 12px', borderRadius: 8, cursor: 'pointer',
                border: `1px solid ${isSelected ? color : 'var(--clr-border)'}`,
                background: isSelected ? color + '0d' : 'var(--clr-surface)',
                transition: 'all 0.15s',
              }}
            >
              <div style={{
                width: 10, height: 10, borderRadius: '50%', background: color,
                flexShrink: 0, marginTop: 4,
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--clr-text)' }}>
                    {seg.label}
                  </span>
                  <TimeRange start={seg.start_time} end={seg.end_time} />
                  <span style={{ fontSize: 11, color: 'var(--clr-text-dim)' }}>
                    {seg.sentence_count} sentence{seg.sentence_count !== 1 ? 's' : ''}
                  </span>
                </div>
                <p style={{
                  fontSize: 12, color: 'var(--clr-text-muted)', margin: '4px 0 0',
                  lineHeight: 1.6, overflow: 'hidden', display: '-webkit-box',
                  WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                }}>
                  {seg.excerpt}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Topic Detail Panel ────────────────────────────────────────────────────────
function TopicDetail({ canonicalTopic, segments, onJump }) {
  if (!canonicalTopic) return (
    <Panel title="Topic detail">
      <Empty>Select a topic segment to see details.</Empty>
    </Panel>
  )

  const color = topicColor(canonicalTopic.canonical_topic_id)
  const topicSegs = segments.filter(s => s.canonical_topic_id === canonicalTopic.canonical_topic_id)

  return (
    <Panel title={canonicalTopic.label}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{ width: 12, height: 12, borderRadius: '50%', background: color }} />
        <span style={{ fontSize: 12, color: 'var(--clr-text-muted)' }}>
          {canonicalTopic.occurrence_count} segment{canonicalTopic.occurrence_count !== 1 ? 's' : ''}
          {canonicalTopic.occurrence_count > 1 ? ' — topic revisited' : ''}
        </span>
      </div>

      <KeywordChips keywords={canonicalTopic.keywords} />

      <div style={{ marginTop: 16 }}>
        {topicSegs.map((seg, i) => (
          <div key={seg.segment_index} style={{
            padding: '12px 0', borderTop: i > 0 ? '1px solid var(--clr-border)' : 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span className="mi-eyebrow">
                {canonicalTopic.occurrence_count > 1
                  ? (i === 0 ? 'First occurrence' : `Revisit ${i}`)
                  : 'Segment'}
              </span>
              <TimeRange start={seg.start_time} end={seg.end_time} />
            </div>
            <p style={{ fontSize: 13, color: 'var(--clr-text-2)', lineHeight: 1.7, margin: '0 0 8px' }}>
              {seg.excerpt}
            </p>
            {seg.related_decisions?.length > 0 && (
              <div style={{ marginBottom: 6 }}>
                <span className="mi-eyebrow" style={{ color: '#059669' }}>Decisions</span>
                {seg.related_decisions.map((d, j) => (
                  <p key={j} style={{ fontSize: 12, color: 'var(--clr-text-muted)', margin: '2px 0' }}>• {d}</p>
                ))}
              </div>
            )}
            {seg.related_actions?.length > 0 && (
              <div style={{ marginBottom: 6 }}>
                <span className="mi-eyebrow" style={{ color: '#2563eb' }}>Actions</span>
                {seg.related_actions.map((a, j) => (
                  <p key={j} style={{ fontSize: 12, color: 'var(--clr-text-muted)', margin: '2px 0' }}>• {a}</p>
                ))}
              </div>
            )}
            {seg.related_questions?.length > 0 && (
              <div>
                <span className="mi-eyebrow" style={{ color: '#d97706' }}>Open questions</span>
                {seg.related_questions.map((q, j) => (
                  <p key={j} style={{ fontSize: 12, color: 'var(--clr-text-muted)', margin: '2px 0' }}>• {q}</p>
                ))}
              </div>
            )}
            {onJump && typeof seg.unit_start === 'number' && (
              <button
                className="mi-link"
                style={{ marginTop: 6 }}
                onClick={() => onJump({ segment_ids: seg.unit_indices, timestamp: seg.start_time })}
              >
                View in transcript ↗
              </button>
            )}
          </div>
        ))}
      </div>
    </Panel>
  )
}

// ── Topic Distribution Chart ──────────────────────────────────────────────────
function TopicDistribution({ canonicalTopics, segments }) {
  const totalSentences = segments.reduce((sum, s) => sum + (s.sentence_count || 1), 0)
  if (!totalSentences) return null

  const data = canonicalTopics.map(ct => ({
    name: ct.label,
    value: ct.total_sentences,
    id: ct.canonical_topic_id,
  }))

  return (
    <Panel title="Topic distribution" subtitle={`Denominator: ${totalSentences} total sentences`}>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%"
            outerRadius={70} innerRadius={36}>
            {data.map(entry => (
              <Cell key={entry.id} fill={topicColor(entry.id)} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => [`${Math.round(value / totalSentences * 100)}%`, name]}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
        {data.map(entry => (
          <div key={entry.id} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: topicColor(entry.id) }} />
            <span style={{ color: 'var(--clr-text-muted)' }}>{entry.name}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

// ── Cross-Meeting Evolution ───────────────────────────────────────────────────
function CrossMeetingEvolution() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const result = await getCrossMeetingTopics()
      setData(result)
    } catch (e) {
      setError(e.message || 'Failed to load cross-meeting topics.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <Panel title="Cross-meeting topic evolution"><div className="mi-loading"><div /><div /></div></Panel>
  if (error) return <Panel title="Cross-meeting topic evolution"><p className="mi-empty" style={{ color: 'var(--clr-error)' }}>{error}</p></Panel>
  if (!data) return null

  const { cross_meeting_topics, meeting_count } = data

  return (
    <Panel title="Cross-meeting topic evolution"
      subtitle={`${meeting_count} meeting${meeting_count !== 1 ? 's' : ''} with topic analysis`}>
      {!cross_meeting_topics?.length
        ? <Empty>Analyze topics in multiple meetings to see cross-meeting evolution.</Empty>
        : cross_meeting_topics.map(group => (
          <div key={group.cross_topic_id} style={{
            padding: '14px 0', borderTop: '1px solid var(--clr-border)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: topicColor(group.cross_topic_id) }} />
              <span style={{ fontSize: 14, fontWeight: 600 }}>{group.label}</span>
              <span style={{ fontSize: 11, color: 'var(--clr-text-dim)' }}>
                {group.meeting_count} meeting{group.meeting_count !== 1 ? 's' : ''}
              </span>
            </div>
            <KeywordChips keywords={group.keywords} />
            <div style={{ marginTop: 10, paddingLeft: 18, borderLeft: `2px solid ${topicColor(group.cross_topic_id)}44` }}>
              {group.occurrences.map((occ, i) => (
                <div key={i} style={{ marginBottom: 8 }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--clr-text-muted)' }}>
                    {occ.filename || occ.meeting_id}
                  </span>
                  {occ.first_start_time !== null && occ.first_start_time !== undefined && (
                    <span style={{ fontSize: 11, color: 'var(--clr-primary)', marginLeft: 8 }}>
                      @ {timestamp(occ.first_start_time)}
                    </span>
                  )}
                  <span style={{ fontSize: 11, color: 'var(--clr-text-dim)', marginLeft: 8 }}>
                    {occ.occurrence_count} segment{occ.occurrence_count !== 1 ? 's' : ''}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))
      }
    </Panel>
  )
}

// ── Overview stats ────────────────────────────────────────────────────────────
function TopicOverview({ segments, canonicalTopics }) {
  const mostDiscussed = canonicalTopics.reduce(
    (best, ct) => ct.total_sentences > (best?.total_sentences ?? 0) ? ct : best, null
  )
  const mostRevisited = canonicalTopics.reduce(
    (best, ct) => ct.occurrence_count > (best?.occurrence_count ?? 0) ? ct : best, null
  )

  const stats = [
    { label: 'Canonical topics', value: canonicalTopics.length },
    { label: 'Topic segments', value: segments.length },
    { label: 'Most discussed', value: mostDiscussed?.label ?? '—' },
    { label: 'Most revisited', value: mostRevisited && mostRevisited.occurrence_count > 1 ? mostRevisited.label : '—' },
  ]

  return (
    <Panel title="Topic overview">
      <dl className="mi-stats-list">
        {stats.map(({ label, value }) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  )
}

// ── Main TopicExplorer ────────────────────────────────────────────────────────
export default function TopicExplorer({ fileId, onJump }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [selectedCanonicalId, setSelectedCanonicalId] = useState(null)

  // Try to load saved result on mount — 404 is normal (not yet analyzed)
  useEffect(() => {
    let active = true
    getTopicSegmentation(fileId)
      .then(result => { if (active) { setData(result); setLoading(false) } })
      .catch(e => {
        if (active) {
          // 404 = not yet analyzed, show welcome screen
          // Any other error = show it
          if (e.status !== 404) setError(e.message || 'Failed to load topic analysis.')
          setLoading(false)
        }
      })
    return () => { active = false }
  }, [fileId])

  async function runSegmentation(force = false) {
    setRunning(true); setError('')
    try {
      const result = await runTopicSegmentation(fileId, force)
      setData(result)
      if (result.canonical_topics?.length) {
        setSelectedCanonicalId(result.canonical_topics[0].canonical_topic_id)
      }
    } catch (e) {
      setError(e.message || 'Topic segmentation failed.')
    } finally {
      setRunning(false)
    }
  }

  const segments = list(data?.segments)
  const canonicalTopics = list(data?.canonical_topics)
  const hasTimestamps = segments.some(s => s.start_time !== null && s.start_time !== undefined)
  const selectedTopic = canonicalTopics.find(ct => ct.canonical_topic_id === selectedCanonicalId) ?? null

  if (loading) {
    return (
      <div className="mi-loading">
        <span className="mi-eyebrow">Loading topic analysis</span>
        <div /><div /><div />
      </div>
    )
  }

  return (
    <div>
      {/* Header actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        {!data ? (
          <button className="mi-primary" disabled={running} onClick={() => runSegmentation(false)}>
            {running ? 'Analysing topics…' : 'Analyse topics'}
          </button>
        ) : (
          <button disabled={running} onClick={() => runSegmentation(true)}>
            {running ? 'Re-analysing…' : 'Re-analyse topics'}
          </button>
        )}
        {data && (
          <span style={{ fontSize: 11, color: 'var(--clr-text-dim)' }}>
            Model: {data.model}
          </span>
        )}
      </div>

      {error && (
        <div role="alert" className="mi-notice mi-error" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}

      {running && (
        <div role="status" className="mi-notice" style={{ marginBottom: 12 }}>
          Running NLP topic segmentation — this may take a moment on first run while the embedding model loads.
        </div>
      )}

      {!data && !running && (
        <section className="mi-panel mi-welcome">
          <span className="mi-eyebrow">Topic Explorer</span>
          <h2>Discover the structure of this meeting.</h2>
          <p>
            Automatically segments the transcript into meaningful topic blocks,
            identifies recurring discussions, and links decisions and actions to their topics.
          </p>
        </section>
      )}

      {data && !segments.length && (
        <Panel title="Topic segmentation">
          <Empty>The transcript is too short or uniform to segment into distinct topics.</Empty>
        </Panel>
      )}

      {data && segments.length > 0 && (
        <>
          <div className="mi-grid" style={{ marginBottom: 16 }}>
            <TopicOverview segments={segments} canonicalTopics={canonicalTopics} />
            <TopicDistribution canonicalTopics={canonicalTopics} segments={segments} />
          </div>

          <Panel title="Topic timeline"
            subtitle={hasTimestamps ? 'Click a segment to explore its content.' : 'Relative transcript position — no timestamps available.'}>
            <TopicTimeline
              segments={segments}
              selectedId={selectedCanonicalId}
              onSelect={setSelectedCanonicalId}
              hasTimestamps={hasTimestamps}
            />
          </Panel>

          <TopicDetail
            canonicalTopic={selectedTopic}
            segments={segments}
            onJump={onJump}
          />

          <CrossMeetingEvolution />
        </>
      )}
    </div>
  )
}
