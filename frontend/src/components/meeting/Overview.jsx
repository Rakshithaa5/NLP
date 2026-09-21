import { list, text, timestamp } from './data'

export function Panel({title, count, children, className = '', subtitle}) {
  return <section className={`mi-panel ${className}`}><div className="mi-section-title"><h2>{title}</h2>{count != null && <span className="mi-count">{count}</span>}</div>{subtitle && <p className="mi-muted mi-caption">{subtitle}</p>}{children}</section>
}
export function Empty({children}) { return <p className="mi-empty">{children}</p> }
export function Evidence({item, onJump, segments}) {
  const quote = text(item.evidence)
  const ids = list(item.segment_ids).filter(id => Number.isInteger(id) && segments[id]?.text)
  if (!quote) return null
  return <details className="mi-evidence"><summary>Transcript evidence</summary><blockquote dir="auto">{quote}</blockquote>
    {ids.length > 0 && <button className="mi-link" onClick={() => onJump(ids[0])}>View transcript{typeof item.timestamp === 'number' ? ` at ${timestamp(item.timestamp)}` : ''} <span aria-hidden="true">&#8599;</span></button>}
  </details>
}
export function MeetingSummary({intelligence}) {
  return <Panel title="AI Meeting Summary" className="mi-summary" subtitle="Source-backed highlights from your meeting">
    {intelligence.summary.length ? <ul className="mi-summary-list">{intelligence.summary.map((line, index) => <li key={index} dir="auto">{line}</li>)}</ul> : <Empty>There is not enough meaningful transcript content to summarize.</Empty>}
    <div className="mi-takeaway"><span className="mi-eyebrow">Key takeaway</span><p dir="auto">{intelligence.key_takeaway || 'No dominant overall outcome was identified.'}</p></div>
  </Panel>
}
export function ActionItems({items, ...evidenceProps}) {
  return <Panel title="Action items" count={items.length} className="mi-actions">
    {!items.length ? <Empty>No action items were identified.</Empty> : <div className="mi-action-list">{items.map((item, index) => <article className="mi-action" key={index}>
      <span className="mi-item-index">{String(index + 1).padStart(2, '0')}</span><div className="mi-action-body"><h3 dir="auto">{text(item.task)}</h3>
      <dl className="mi-action-meta"><div><dt>Owner</dt><dd>{text(item.owner) || 'Unassigned'}</dd></div><div><dt>Deadline</dt><dd>{text(item.deadline) || 'Not specified'}</dd></div><div><dt>Priority</dt><dd>{text(item.priority) || 'Not specified'}</dd></div><div><dt>Status</dt><dd><span className="mi-pill">{text(item.status) || 'Pending'}</span></dd></div></dl>
      <Evidence item={item} {...evidenceProps}/></div></article>)}</div>}
  </Panel>
}
export function Decisions({items, ...evidenceProps}) {
  return <Panel title="Decisions made" count={items.length} className="mi-decisions">{!items.length ? <Empty>No explicit decisions were identified in this meeting.</Empty> : items.map((item, index) => <article className="mi-insight" key={index}><p dir="auto">{text(item.decision)}</p><Evidence item={item} {...evidenceProps}/></article>)}</Panel>
}
export function OpenQuestions({items, ...evidenceProps}) {
  return <Panel title="Open questions & follow-ups" count={items.length} className="mi-questions">
    {!items.length ? <Empty>No important questions were identified.</Empty> : items.map((item, index) => <article className="mi-insight" key={index}><span className={`mi-pill ${item.status === 'Resolved' ? 'mi-resolved' : ''}`}>{text(item.status) || 'Not assessed'}</span><p dir="auto">{text(item.question)}</p>{text(item.answer) && <p className="mi-answer">Answer: {item.answer}</p>}<Evidence item={item} {...evidenceProps}/>{item.answer_evidence && <Evidence item={item.answer_evidence} {...evidenceProps}/>}</article>)}
  </Panel>
}
export function DiscussionTopics({items, ...evidenceProps}) {
  return <Panel title="Discussion topics" count={items.length}>{!items.length ? <Empty>No reliable discussion topics were identified.</Empty> : <div className="mi-topic-list">{items.map((item, index) => <article key={index}><h3 dir="auto">{text(item.label)}</h3><Evidence item={item} {...evidenceProps}/></article>)}</div>}</Panel>
}
export function EntityPanel({entities}) {
  const labels = {people: 'People mentioned', organizations: 'Organizations', dates: 'Dates & times', products: 'Products & technologies', locations: 'Locations'}
  const groups = Object.entries(labels).filter(([key]) => list(entities[key]).some(v => text(v)))
  return <Panel title="Entities mentioned" subtitle="Mentioned people are not necessarily meeting participants.">{!groups.length ? <Empty>No reliable named entities were detected.</Empty> : groups.map(([key, label]) => <div className="mi-entity-group" key={key}><h3 className="mi-eyebrow">{label}</h3><div className="mi-chips">{list(entities[key]).filter(v => text(v)).map((value, index) => <span className="mi-chip" key={index} dir="auto">{value}</span>)}</div></div>)}</Panel>
}
export default function Overview({analysis, segments, onJump}) {
  const i = analysis.intelligence, evidenceProps = {segments, onJump}
  return <div className="mi-overview"><MeetingSummary intelligence={i}/>
    <ActionItems items={i.action_items} {...evidenceProps}/><div className="mi-grid"><Decisions items={i.decisions} {...evidenceProps}/><OpenQuestions items={i.questions} {...evidenceProps}/></div>
    <div className="mi-grid"><DiscussionTopics items={i.topics} {...evidenceProps}/><EntityPanel entities={i.entities}/></div></div>
}
