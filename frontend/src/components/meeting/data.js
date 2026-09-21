// Shape validation only; semantic extraction belongs to the backend.
export const list = value => Array.isArray(value) ? value : []
export const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {}
export const text = value => typeof value === 'string' ? value : ''
export const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
export function timestamp(value) {
  const seconds = number(value)
  if (seconds === null) return 'Time unavailable'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor(seconds % 3600 / 60)
  const s = Math.floor(seconds % 60)
  return `${h ? `${h}:` : ''}${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
export function normalizeMeeting(value) {
  const m = object(value)
  return {...m, filename: text(m.filename), full_text: text(m.full_text), language: text(m.language),
    duration: number(m.duration), uploaded_at: text(m.uploaded_at),
    segments: list(m.segments).map((value, index) => {
      const s = object(value)
      return {id: index, text: text(s.text), start: number(s.start), end: number(s.end),
        speaker: text(s.speaker) || text(s.speaker_id) || null}
    })}
}
export function normalizeAnalysis(value) {
  const a = object(value), i = object(a.intelligence || object(a.topics).intelligence)
  const rows = key => list(i[key]).map(object).filter(row => Object.keys(row).length)
  return {...a, intelligence: {...i, summary: list(i.summary).filter(s => typeof s === 'string'),
    key_takeaway: text(i.key_takeaway), limitations: list(i.limitations).filter(s => typeof s === 'string'),
    action_items: rows('action_items'), decisions: rows('decisions'), questions: rows('questions'),
    topics: rows('topics'), entities: object(i.entities)}, classifications: list(a.classifications).map(object),
    summary: object(a.summary)}
}
export function speakerStats(segments) {
  const stats = new Map()
  let previous = null, covered = 0, total = 0
  for (const s of segments) {
    const duration = s.start !== null && s.end !== null && s.end >= s.start ? s.end - s.start : 0
    total += duration
    if (!s.speaker) { previous = null; continue }
    const item = stats.get(s.speaker) || {speaker: s.speaker, seconds: 0, turns: 0}
    item.seconds += duration
    if (previous !== s.speaker) item.turns += 1
    stats.set(s.speaker, item)
    covered += duration
    previous = s.speaker
  }
  return {rows: [...stats.values()].map(s => ({...s, percentage: total ? s.seconds / total * 100 : null})),
    coverage: total ? covered / total : null}
}
