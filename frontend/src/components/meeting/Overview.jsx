import { useState } from 'react'
import ActionNote from './ActionNote'
import { actionNoteKey } from './notes'
import { resolveEvidenceTarget } from './playback'
import { list, text, timestamp, number } from './data'

export function Panel({title, count, children, className = '', subtitle, id}) {
  return <section id={id} tabIndex={id ? -1 : undefined} className={`mi-panel ${className}`}><div className="mi-section-title"><h2>{title}</h2>{count != null && <span className="mi-count">{count}</span>}</div>{subtitle && <p className="mi-muted mi-caption">{subtitle}</p>}{children}</section>
}
export function Empty({children}) { return <p className="mi-empty">{children}</p> }
export function Evidence({item, onJump, segments}) {
  const quote = text(item.evidence)
  const ids = list(item.segment_ids).filter(id => Number.isInteger(id) && segments[id]?.text)
  const resolved = resolveEvidenceTarget(item, segments)
  const seconds = number(resolved?.seconds) ?? number(item.timestamp)
  const hasTarget = ids.length > 0 || seconds !== null
  if (!quote && !hasTarget) return null
  return <details className="mi-evidence"><summary>Transcript evidence</summary><blockquote dir="auto">{quote || 'Evidence is available in the transcript.'}</blockquote>
    {seconds !== null ? (
      <button type="button" className="mi-link" onClick={() => onJump({...item, playbackSeconds: seconds})}>Play recording at {timestamp(seconds)} <span aria-hidden="true">&#8599;</span></button>
    ) : (
      <button type="button" className="mi-link mi-link-disabled" disabled>Recording timestamp unavailable</button>
    )}
  </details>
}
export function MeetingSummary({intelligence}) {
  return <Panel id="overview-summary" title="AI Meeting Summary" className="mi-summary" subtitle="Source-backed highlights from your meeting">
    {intelligence.summary.length ? <ul className="mi-summary-list">{intelligence.summary.map((line, index) => <li key={index} dir="auto">{line}</li>)}</ul> : <Empty>There is not enough meaningful transcript content to summarize.</Empty>}
    <div id="overview-key-points" tabIndex={-1} className="mi-takeaway"><span className="mi-eyebrow takeaway-label"><svg aria-hidden="true" width="20" height="24" viewBox="0 0 24 28" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M8 19c0-4-4-5-4-10a8 8 0 0 1 16 0c0 5-4 6-4 10M8 20h8M9 24h6M10 27h4M10 17v-6l4 2v4"/></svg>Key takeaway</span><p dir="auto">{intelligence.key_takeaway || 'No dominant overall outcome was identified.'}</p></div>
  </Panel>
}
function ActionItem({item, index, noteKey, ...evidenceProps}) {
  return <article className="mi-action">
    <span className="mi-item-index">{String(index + 1).padStart(2, '0')}</span>
    <div className="mi-action-body"><h3 dir="auto">{text(item.task)}</h3>
      <dl className="mi-action-meta"><div><dt>Deadline</dt><dd>{text(item.deadline) || 'Not specified'}</dd></div><div><dt>Priority</dt><dd>{text(item.priority) || 'Not specified'}</dd></div></dl>
      <ActionNote key={noteKey} storageKey={noteKey}/>
      <Evidence item={item} {...evidenceProps}/>
    </div>
  </article>
}
export function ActionItems({items, fileId, sourceItems, ...props}) {
  return <Panel id="overview-actions" title="Action items" count={items.length} className="mi-actions">
    {!items.length ? <Empty>No action items were identified.</Empty> : <div className="mi-action-list">{items.map((item, index) => <ActionItem key={`${index}-${item.task}`} item={item} index={index} noteKey={actionNoteKey(fileId, sourceItems[index] || item)} {...props}/>)}</div>}
  </Panel>
}
export function Decisions({items, ...evidenceProps}) {
  return <Panel id="overview-decisions" title="Decisions made" count={items.length} className="mi-decisions">{!items.length ? <Empty>No explicit decisions were identified in this meeting.</Empty> : items.map((item, index) => <article className="mi-insight" key={index}><p dir="auto">{text(item.decision)}</p><Evidence item={item} {...evidenceProps}/></article>)}</Panel>
}
export function OpenQuestions({items, followUps = [], ...evidenceProps}) {
  items = [...items, ...followUps.map(item => ({...item, question: item.task}))]
  return <Panel id="overview-questions" title="Open questions & follow-ups" count={items.length} className="mi-questions">
    {!items.length ? <Empty>No important questions were identified.</Empty> : items.map((item, index) => <article className="mi-insight" key={item.id || index}><span className={`mi-pill ${item.status === 'Resolved' ? 'mi-resolved' : ''}`}>{text(item.status) || 'Not assessed'}</span><p dir="auto">{text(item.question)}</p>{text(item.answer) && <p className="mi-answer">Answer: {item.answer}</p>}<Evidence item={item} {...evidenceProps}/>{item.answer_evidence && <Evidence item={item.answer_evidence} {...evidenceProps}/>}</article>)}
  </Panel>
}
export function DiscussionTopics({items, ...evidenceProps}) {
  return <Panel id="overview-topics" title="Discussion topics" count={items.length}>{!items.length ? <Empty>No reliable discussion topics were identified.</Empty> : <div className="mi-topic-list">{items.map((item, index) => <article key={index}><h3 dir="auto">{text(item.label)}</h3><Evidence item={item} {...evidenceProps}/></article>)}</div>}</Panel>
}
export function EntityPanel({entities}) {
  const labels = {people: 'People mentioned', organizations: 'Organizations', dates: 'Dates & times', products: 'Products & technologies', locations: 'Locations'}
  const groups = Object.entries(labels).filter(([key]) => list(entities[key]).some(v => text(v)))
  return <Panel id="overview-entities" title="Entities mentioned" subtitle="Mentioned people are not necessarily meeting participants.">{!groups.length ? <Empty>No reliable named entities were detected.</Empty> : groups.map(([key, label]) => <div className="mi-entity-group" key={key}><h3 className="mi-eyebrow">{label}</h3><div className="mi-chips">{list(entities[key]).filter(v => text(v)).map((value, index) => <span className="mi-chip" key={index} dir="auto">{value}</span>)}</div></div>)}</Panel>
}
export default function Overview({analysis, segments, onJump, fileId, sourceItems}) {
  const i = analysis.intelligence, evidenceProps = {segments, onJump}
  const [selected, setSelected] = useState('summary')
  const sections = [['summary', 'Summary'], ['key-points', 'Key points'], ['actions', 'Actions'], ['decisions', 'Decisions'], ['questions', 'Questions & follow-ups'], ['topics', 'Topics'], ['entities', 'Entities']]
  function navigate(event, id) {
    event.preventDefault()
    setSelected(id)
    const section = document.getElementById(`overview-${id}`)
    section?.focus({preventScroll: true})
    section?.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start'})
  }
  return <div className="mi-overview">
    <nav className="mi-overview-nav" aria-label="Overview sections">{sections.map(([id, label]) => <a key={id} href={`#overview-${id}`} aria-current={selected === id ? 'location' : undefined} onClick={event => navigate(event, id)}>{label}</a>)}</nav>
    <MeetingSummary intelligence={i}/>
    <ActionItems key={analysis.analyzed_at} items={i.action_items} fileId={fileId} sourceItems={sourceItems} {...evidenceProps}/><div className="overview-insights"><Decisions items={i.decisions} {...evidenceProps}/><OpenQuestions items={i.questions} followUps={list(i.follow_ups)} {...evidenceProps}/></div>
    <div className="overview-details"><DiscussionTopics items={i.topics} {...evidenceProps}/><EntityPanel entities={i.entities}/></div></div>
}
