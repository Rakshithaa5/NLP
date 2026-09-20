import { useEffect, useRef, useState } from 'react'
import { Panel, Empty } from './Overview'
import { list, text, timestamp } from './data'

function Highlight({value, query}) {
  if (!query) return value
  const lower = value.toLocaleLowerCase(), needle = query.toLocaleLowerCase(), parts = []
  let cursor = 0, index = lower.indexOf(needle)
  while (index >= 0) {
    parts.push(value.slice(cursor, index), <mark key={index}>{value.slice(index, index + needle.length)}</mark>)
    cursor = index + needle.length
    index = lower.indexOf(needle, cursor)
  }
  parts.push(value.slice(cursor))
  return parts
}
export default function TranscriptViewer({meeting, intelligence, target}) {
  const [query, setQuery] = useState(''), [speaker, setSpeaker] = useState(''), [filter, setFilter] = useState('All')
  const container = useRef(null)
  const segments = meeting.segments.length ? meeting.segments : meeting.full_text ? [{id: 0, text: meeting.full_text, start: null, speaker: null}] : []
  const speakers = [...new Set(segments.map(s => s.speaker).filter(Boolean))]
  const labels = new Map()
  for (const [key, label] of [['action_items', 'Actions'], ['decisions', 'Decisions'], ['questions', 'Questions']]) {
    for (const item of list(intelligence[key])) for (const id of list(item.segment_ids)) {
      const values = labels.get(id) || new Set(); values.add(label); labels.set(id, values)
    }
  }
  useEffect(() => {
    if (target?.id == null) return
    const timer = setTimeout(() => {
      const node = container.current?.querySelector(`[data-segment="${target.id}"]`)
      node?.scrollIntoView({block: 'center', behavior: 'smooth'}); node?.focus({preventScroll: true})
    }, 50)
    return () => clearTimeout(timer)
  }, [target])
  const needle = query.trim()
  const visible = segments.filter(s => (!speaker || s.speaker === speaker) && (!needle || s.text.toLocaleLowerCase().includes(needle.toLocaleLowerCase())) && (filter === 'All' || labels.get(s.id)?.has(filter)))
  return <Panel title="Transcript" subtitle="Original recording text. Timestamps refer to transcript segments, not audio playback.">
    <div className="mi-transcript-controls"><label className="mi-search"><span>Search transcript</span><input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Find a word or phrase..."/></label>
      {speakers.length > 0 && <label className="mi-search"><span>Speaker</span><select value={speaker} onChange={e => setSpeaker(e.target.value)}><option value="">All speakers</option>{speakers.map(name => <option key={name}>{name}</option>)}</select></label>}</div>
    <div className="mi-filter-row" aria-label="Filter transcript">{['All', 'Actions', 'Decisions', 'Questions'].map(label => <button key={label} aria-pressed={filter === label} onClick={() => setFilter(label)}>{label}</button>)}<span className="mi-muted">{visible.length} of {segments.length} segments</span></div>
    {!speakers.length && <p className="mi-caption mi-muted">Speaker labels are unavailable for this recording.</p>}
    <div className="mi-transcript" ref={container}>{!visible.length ? <Empty>{segments.length ? 'No transcript segments match these filters.' : 'No transcript is available.'}</Empty> : visible.map(s => <article key={s.id} data-segment={s.id} tabIndex={-1} className={`mi-segment ${target?.id === s.id ? 'mi-segment-selected' : ''}`}>
      <div className="mi-segment-meta"><span>{s.start !== null ? timestamp(s.start) : 'No timestamp'}</span>{s.speaker && <strong>{text(s.speaker)}</strong>}{[...(labels.get(s.id) || [])].map(label => <span className="mi-pill" key={label}>{label}</span>)}</div>
      <p dir="auto"><Highlight value={s.text} query={needle}/></p></article>)}</div>
  </Panel>
}
