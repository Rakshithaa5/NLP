import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeAnalysis, normalizeMeeting, speakerStats, timestamp } from './data.js'

test('malformed and partial responses normalize without fabricated values', () => {
  const m = normalizeMeeting({filename: {}, segments: [null, {text: {}, start: '0', speaker: {}}]})
  assert.equal(m.filename, '')
  assert.equal(m.segments[1].start, null)
  assert.equal(m.segments[1].speaker, null)
  const a = normalizeAnalysis({intelligence: {summary: [null, {}, 'Valid'], action_items: null}, classifications: null})
  assert.deepEqual(a.intelligence.summary, ['Valid'])
  assert.deepEqual(a.intelligence.action_items, [])
  assert.deepEqual(a.classifications, [])
})
test('zero timestamp is valid; missing timestamp is not fabricated', () => {
  assert.equal(timestamp(0), '00:00')
  assert.equal(timestamp(null), 'Time unavailable')
})
test('speaker turns combine adjacent blocks and include unlabeled time in denominator', () => {
  const m = normalizeMeeting({segments: [
    {text: 'a', start: 0, end: 10, speaker: 'A'},
    {text: 'b', start: 10, end: 20, speaker: 'A'},
    {text: 'c', start: 20, end: 30},
    {text: 'd', start: 30, end: 40, speaker: 'A'}]})
  const stats = speakerStats(m.segments)
  assert.equal(stats.rows[0].turns, 2)
  assert.equal(stats.rows[0].percentage, 75)
  assert.equal(stats.coverage, .75)
})
test('no speaker labels means no invented participants', () => {
  assert.deepEqual(speakerStats(normalizeMeeting({segments: [{text: 'Sarah is mentioned.'}]}).segments).rows, [])
})
