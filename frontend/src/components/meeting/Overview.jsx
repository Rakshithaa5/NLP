import { useState } from 'react'
import { list, text, timestamp } from './data'

export function Panel({title, count, children, className = '', subtitle, id}) {
  return <section id={id} tabIndex={id ? -1 : undefined} className={`mi-panel ${className}`}><div className="mi-section-title"><h2>{title}</h2>{count != null && <span className="mi-count">{count}</span>}</div>{subtitle && <p className="mi-muted mi-caption">{subtitle}</p>}{children}</section>
}
export function Empty({children}) { return <p className="mi-empty">{children}</p> }
export function Evidence({item, onJump, segments}) {
  const quote = text(item.evidence)
  const ids = list(item.segment_ids).filter(id => Number.isInteger(id) && segments[id]?.text)
  const hasTarget = ids.length > 0 || typeof item.timestamp === 'number'
  if (!quote && !hasTarget) return null
  return <details className="mi-evidence"><summary>Transcript evidence</summary><blockquote dir="auto">{quote || 'Evidence is available in the transcript.'}</blockquote>
    {hasTarget ? (
      <button type="button" className="mi-link" onClick={() => onJump(item)}>View in transcript{typeof item.timestamp === 'number' ? ` at ${timestamp(item.timestamp)}` : ''} <span aria-hidden="true">&#8599;</span></button>
    ) : (
      <button type="button" className="mi-link mi-link-disabled" disabled>Evidence unavailable</button>
    )}
  </details>
}
export function MeetingSummary({intelligence}) {
  return <Panel id="overview-summary" title="AI Meeting Summary" className="mi-summary" subtitle="Source-backed highlights from your meeting">
    {intelligence.summary.length ? <ul className="mi-summary-list">{intelligence.summary.map((line, index) => <li key={index} dir="auto">{line}</li>)}</ul> : <Empty>There is not enough meaningful transcript content to summarize.</Empty>}
    <div id="overview-key-points" tabIndex={-1} className="mi-takeaway"><span className="mi-eyebrow">Key takeaway</span><p dir="auto">{intelligence.key_takeaway || 'No dominant overall outcome was identified.'}</p></div>
  </Panel>
}
function ActionItem({item, index, onSaveAction, editingDisabled, ...evidenceProps}) {
  const [editing, setEditing] = useState(false)
  const [owner, setOwner] = useState('')
  const [deadline, setDeadline] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  function edit() {
    setOwner(text(item.owner)); setDeadline(text(item.deadline))
    setError(''); setSaved(false); setEditing(true)
  }
  async function submit(event) {
    event.preventDefault()
    if (saving || editingDisabled) return
    setSaving(true); setError('')
    try { await onSaveAction(index, {owner, deadline}); setEditing(false); setSaved(true) }
    catch (e) { setError(e.message || 'Could not save changes. Please retry.') }
    finally { setSaving(false) }
  }
  return <article className="mi-action">
    <span className="mi-item-index">{String(index + 1).padStart(2, '0')}</span>
    <div className="mi-action-body"><h3 dir="auto">{text(item.task)}</h3>
      <dl className="mi-action-meta"><div><dt>Deadline{item.manually_edited && ' (manually edited)'}</dt><dd>{text(item.deadline) || 'Not specified'}</dd></div><div><dt>Priority</dt><dd>{text(item.priority) || 'Not specified'}</dd></div></dl>
      {editing ? <form className="mi-action-editor" onSubmit={submit}>
        <label>Owner<input value={owner} maxLength={200} onChange={e => setOwner(e.target.value)} disabled={saving} placeholder="Enter a name" /></label>
        <label>Deadline<input value={deadline} maxLength={200} onChange={e => setDeadline(e.target.value)} disabled={saving} placeholder="e.g. 25 Oct 2026 or next Friday" /></label>
        <p className="mi-caption mi-muted">These details are entered manually. Leave a field blank to clear it.</p>
        {error && <p role="alert" className="mi-error">{error}</p>}
        <div className="mi-action-editor-buttons"><button type="submit" disabled={saving || editingDisabled}>{saving ? 'Saving...' : 'Save details'}</button><button type="button" disabled={saving} onClick={() => setEditing(false)}>Cancel</button></div>
      </form> : onSaveAction && <button type="button" className="mi-link" disabled={editingDisabled} onClick={edit} aria-label={`Edit details for action ${index + 1}`}>Edit details</button>}
      {saved && <p role="status" className="mi-caption">Details saved.</p>}
      <Evidence item={item} {...evidenceProps}/>
    </div>
  </article>
}
export function ActionItems({items, ...props}) {
  return <Panel id="overview-actions" title="Action items" count={items.length} className="mi-actions">
    {!items.length ? <Empty>No action items were identified.</Empty> : <div className="mi-action-list">{items.map((item, index) => <ActionItem key={`${index}-${item.task}`} item={item} index={index} {...props}/>)}</div>}
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
export default function Overview({analysis, segments, onJump, onSaveAction, editingDisabled}) {
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
    <ActionItems key={analysis.analyzed_at} items={i.action_items} onSaveAction={onSaveAction} editingDisabled={editingDisabled} {...evidenceProps}/><div className="mi-grid"><Decisions items={i.decisions} {...evidenceProps}/><OpenQuestions items={i.questions} followUps={list(i.follow_ups)} {...evidenceProps}/></div>
    <div className="mi-grid"><DiscussionTopics items={i.topics} {...evidenceProps}/><EntityPanel entities={i.entities}/></div></div>
}
