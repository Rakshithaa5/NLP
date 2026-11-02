import test from 'node:test'
import assert from 'node:assert/strict'

import { formatClock, findActiveSegment, resolveEvidenceTarget } from './playback.js'

test('formatClock formats standard durations', () => {
  assert.equal(formatClock(42), '00:42')
  assert.equal(formatClock(154), '02:34')
  assert.equal(formatClock(3737), '01:02:17')
})

test('findActiveSegment picks the current transcript segment', () => {
  const segments = [
    { id: 'SEG_1', start: 0, end: 10, text: 'one' },
    { id: 'SEG_2', start: 10, end: 20, text: 'two' },
    { id: 'SEG_3', start: 20, end: 30, text: 'three' }
  ]
  assert.equal(findActiveSegment(segments, 15)?.id, 'SEG_2')
  assert.equal(findActiveSegment(segments, 30)?.id, 'SEG_3')
})

test('resolveEvidenceTarget keeps evidence navigation deterministic', () => {
  const segments = [
    { id: 'SEG_1', start: 10, end: 20, text: 'We need authentication before release.' },
    { id: 'SEG_2', start: 22, end: 30, text: 'Use the temporary method for the demo.' }
  ]
  const target = resolveEvidenceTarget({
    evidence: 'Use the temporary method for the demo.',
    timestamp: 22,
    segment_ids: ['SEG_1', 'SEG_2']
  }, segments)
  assert.equal(target.segmentId, 'SEG_2')
  assert.equal(target.seconds, 22)
  assert.equal(target.reason, 'segment-id')
})


test('untimed evidence selects its transcript without inventing a playback timestamp', () => {
  const segments = [{id: 0, start: null, end: null, text: 'Original meeting excerpt'}]
  assert.equal(resolveEvidenceTarget({segment_ids: [0]}, segments).seconds, null)
  assert.equal(resolveEvidenceTarget({evidence: 'Original meeting excerpt'}, segments).seconds, null)
})
