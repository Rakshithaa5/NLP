import { timestamp } from './data.js'

export function normalizeSegmentId(value) {
  if (typeof value === 'number' && Number.isInteger(value)) return value
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return null
    if (/^\d+$/.test(trimmed)) return Number(trimmed)
    return trimmed
  }
  return null
}

export function formatClock(value) {
  return timestamp(value)
}

export function findSegmentAtTime(segments, seconds) {
  if (!Array.isArray(segments) || !segments.length) return null
  const numeric = Number.isFinite(Number(seconds)) ? Number(seconds) : 0
  const list = segments
    .map((segment, index) => ({ ...segment, __index: index }))
    .filter(segment => Number.isFinite(segment.start) && Number.isFinite(segment.end) && segment.end >= segment.start)
    .sort((a, b) => a.start - b.start)

  if (!list.length) return null

  let low = 0
  let high = list.length - 1
  let best = null

  while (low <= high) {
    const mid = Math.floor((low + high) / 2)
    const candidate = list[mid]
    if (candidate.start <= numeric && candidate.end > numeric) return candidate
    if (candidate.start > numeric) {
      high = mid - 1
    } else {
      best = candidate
      low = mid + 1
    }
  }

  return best || list[0]
}

export function findActiveSegment(segments, seconds) {
  const match = findSegmentAtTime(segments, seconds)
  if (!match) return null
  return { id: match.id ?? match.__index, start: match.start, end: match.end, text: match.text, speaker: match.speaker }
}

export function resolveEvidenceTarget(evidence, segments) {
  if (!evidence || !Array.isArray(segments) || !segments.length) return null

  const raw = typeof evidence === 'object' ? evidence : {}
  const ids = Array.isArray(raw.segment_ids) ? raw.segment_ids : []
  const candidateIds = ids
    .map(normalizeSegmentId)
    .filter(value => value !== null)
    .filter(value => segments.some((segment, index) => normalizeSegmentId(segment.id) === value || index === value))

  const timestamp = Number.isFinite(raw.timestamp) ? raw.timestamp : Number.isFinite(raw.start) ? raw.start : Number.isFinite(raw.start_time) ? raw.start_time : null

  if (candidateIds.length) {
    const preferred = timestamp !== null ? findSegmentAtTime(segments, timestamp) : null
    const target = preferred && candidateIds.some(value => {
      const normalized = normalizeSegmentId(preferred.id ?? preferred.__index)
      return value === normalized || value === preferred.__index
    })
      ? preferred
      : segments.find((segment, index) => {
          const segmentId = normalizeSegmentId(segment.id)
          return candidateIds.some(value => value === segmentId || value === index)
        })

    if (target) {
      const seconds = Number.isFinite(target.start) ? target.start : timestamp ?? 0
      return {
        segmentId: target.id ?? target.__index ?? 0,
        segmentIds: candidateIds.map(value => value),
        seconds,
        reason: timestamp !== null ? 'segment-id' : 'segment-id'
      }
    }
  }

  if (timestamp !== null) {
    const target = findSegmentAtTime(segments, timestamp)
    if (target) {
      return {
        segmentId: target.id ?? target.__index ?? 0,
        segmentIds: [target.id ?? target.__index ?? 0],
        seconds: Number.isFinite(target.start) ? target.start : timestamp,
        reason: 'timestamp'
      }
    }
  }

  const text = typeof raw.evidence === 'string' ? raw.evidence.trim() : ''
  if (text) {
    const lower = text.toLocaleLowerCase()
    for (const segment of segments) {
      const segmentText = typeof segment.text === 'string' ? segment.text : ''
      if (!segmentText) continue
      if (segmentText.toLocaleLowerCase().includes(lower) || lower.includes(segmentText.toLocaleLowerCase())) {
        return {
          segmentId: segment.id ?? segment.__index ?? 0,
          segmentIds: [segment.id ?? segment.__index ?? 0],
          seconds: Number.isFinite(segment.start) ? segment.start : 0,
          reason: 'text'
        }
      }
    }
  }

  return null
}
