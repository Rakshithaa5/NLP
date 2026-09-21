import { Panel, Empty } from './Overview'
import { list, text, timestamp, speakerStats } from './data'

export function Meter({label, count, percentage}) {
  return <div className="mi-meter"><div><span>{label}</span><span>{count}{percentage !== null ? ` ? ${Math.round(percentage)}%` : ''}</span></div>{percentage !== null && <div className="mi-meter-track"><div style={{width: `${Math.min(100, Math.max(0, percentage))}%`}}/></div>}</div>
}
export default function Analytics({analysis, meeting}) {
  const speakers = speakerStats(meeting.segments)
  const counts = {
    'Action items': analysis.intelligence.action_items.length,
    Decisions: analysis.intelligence.decisions.length,
    'Unresolved questions': analysis.intelligence.questions.filter(q => q.status === 'Unresolved').length,
    'Resolved questions': analysis.intelligence.questions.filter(q => q.status === 'Resolved').length,
  }
  const total = Object.values(counts).reduce((sum, value) => sum + value, 0)
  const wordCount = meeting.full_text.trim() ? meeting.full_text.trim().split(/\s+/u).length : 0
  return <div className="mi-grid"><Panel title="Speaker analytics" subtitle="Talk time uses available labeled segment durations; turns count consecutive speaker blocks.">
    {!speakers.rows.length ? <Empty>Speaker analytics are unavailable. This recording has no speaker labels.</Empty> : <>{speakers.rows.map(row => <Meter key={row.speaker} label={row.speaker} count={`${row.turns} turns`} percentage={row.percentage}/>)}{speakers.coverage !== null && speakers.coverage < 1 && <p className="mi-caption mi-muted">{Math.round(speakers.coverage * 100)}% of segment duration has speaker labels. Unlabeled time is included in the denominator.</p>}</>}
  </Panel><Panel title="Extracted insights" subtitle="Counts of supported insights; an excerpt may support more than one category.">{!total ? <Empty>No actions, decisions, or important questions were identified.</Empty> : Object.entries(counts).map(([label, count]) => <Meter key={label} label={label} count={count} percentage={null}/>)}</Panel>
    <Panel title="Discussion topics" subtitle="Concepts supported by transcript evidence.">{!analysis.intelligence.topics.length ? <Empty>No reliable topics are available.</Empty> : analysis.intelligence.topics.map((topic, index) => <Meter key={index} label={text(topic.label)} count="" percentage={typeof topic.relevance === 'number' ? topic.relevance * 100 : null}/>)}</Panel>
    <Panel title="Meeting statistics"><dl className="mi-stats-list"><div><dt>Duration</dt><dd>{meeting.duration !== null ? timestamp(meeting.duration) : 'Unavailable'}</dd></div><div><dt>Words (space-delimited)</dt><dd>{wordCount.toLocaleString()}</dd></div><div><dt>Detected language</dt><dd>{meeting.language.toUpperCase() || 'Unavailable'}</dd></div><div><dt>Identified speakers</dt><dd>{speakers.rows.length || 'Unavailable'}</dd></div><div><dt>Transcript segments</dt><dd>{meeting.segments.length}</dd></div></dl></Panel>
    <Panel title="Entity statistics">{Object.keys(analysis.intelligence.entities).length ? Object.entries(analysis.intelligence.entities).map(([key, values]) => <Meter key={key} label={key} count={list(values).length} percentage={null}/>) : <Empty>No reliable entities are available.</Empty>}</Panel></div>
}
