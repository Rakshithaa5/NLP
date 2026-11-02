import test from 'node:test'
import assert from 'node:assert/strict'
import {languageName, mapDisplayText, translateDisplay, splitText, batchTexts} from './translation.js'

test('language names are readable and tolerate missing or malformed metadata', () => {
  assert.equal(languageName('fr'), 'French')
  assert.equal(languageName('en'), 'English')
  assert.equal(languageName(''), 'Unknown')
  assert.equal(languageName('not a code'), 'not a code')
})

test('translation covers all visible content while preserving citations, enums, owners and timing', async () => {
  const source = {
    meeting: {language: 'fr', filename: 'reunion.mp4', segments: [{id: 0, text: 'Bonjour', start: 1.2, end: 3}]},
    analysis: {summary: ['Bonjour'], action_items: [{task: 'Faire', owner: 'Jean', deadline: 'demain',
      priority: 'High', evidence: 'Bonjour', segment_ids: [0], timestamp: 1.2}],
      questions: [{question: 'Pourquoi ?', status: 'Unresolved'}],
      entities: {people: ['Jean'], dates: ['demain']}},
    topics: {canonical_topics: [{canonical_topic_id: 4, label: 'Projet', keywords: ['projet']}],
      segments: [{excerpt: 'Bonjour', related_decisions: ['Oui'], unit_indices: [0]}]},
    messages: [{role: 'assistant', content: 'Bonjour', evidence: ['SEG_0']}],
  }
  const snapshot = structuredClone(source), sent = []
  const result = await translateDisplay(source, async texts => { sent.push(...texts); return texts.map(t => `English: ${t}`) })
  assert.deepEqual(source, snapshot)
  assert.equal(result.meeting.segments[0].text, 'English: Bonjour')
  assert.equal(result.analysis.action_items[0].task, 'English: Faire')
  assert.equal(result.analysis.action_items[0].evidence, 'English: Bonjour')
  assert.equal(result.analysis.questions[0].status, 'Unresolved')
  assert.equal(result.analysis.action_items[0].owner, 'Jean')
  assert.deepEqual(result.analysis.action_items[0].segment_ids, [0])
  assert.equal(result.analysis.action_items[0].timestamp, 1.2)
  assert.equal(result.meeting.segments[0].start, 1.2)
  assert.equal(result.meeting.filename, 'reunion.mp4')
  assert.equal(result.meeting.language, 'fr')
  assert.deepEqual(result.messages[0].evidence, ['SEG_0'])
  assert.equal(result.messages[0].content, 'English: Bonjour')
  assert.equal(result.topics.canonical_topics[0].label, 'English: Projet')
  assert.deepEqual(result.topics.segments[0].unit_indices, [0])
  assert.equal(sent.filter(t => t === 'Bonjour').length, 1)
  assert.ok(!sent.includes('SEG_0'))
})

test('long Unicode content is complete and respects request byte limits', () => {
  const source = 'a'.repeat(1499) + '\u{1F600}'.repeat(4000) + ' fin'
  const pieces = splitText(source)
  assert.equal(pieces.join(''), source)
  for (const part of pieces) {
    assert.ok(part.length <= 1500)
    assert.equal(Buffer.from(part).toString('utf8'), part)
  }
  for (const batch of batchTexts(pieces)) {
    assert.ok(batch.length <= 64)
    assert.ok(batch.reduce((n, t) => n + Buffer.byteLength(t), 0) <= 8000)
  }
})

test('failed or truncated translations are rejected instead of silently losing text', async () => {
  await assert.rejects(translateDisplay({text: 'Bonjour'}, async () => []), /incomplete/)
  await assert.rejects(translateDisplay({text: 'Bonjour'}, async () => ['']), /incomplete/)
  assert.equal(mapDisplayText(null, () => 'x'), null)
})

test('switching views stops remaining translation batches', async () => {
  let active = true, requests = 0
  const source = {text: Array.from({length: 10000}, (_, i) => String(i)).join(' ')}
  await assert.rejects(translateDisplay(source, async texts => {
    requests++; active = false; return texts
  }, () => active), /view changed/)
  assert.equal(requests, 1)
})
