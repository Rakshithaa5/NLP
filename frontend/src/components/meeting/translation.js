// Only prose fields are translated. Identifiers, enums, timestamps and filenames stay intact.
const FIELDS = new Set(['text', 'full_text', 'summary', 'key_takeaway', 'limitations',
  'task', 'decision', 'question', 'answer', 'evidence', 'label', 'excerpt', 'keywords',
  'related_decisions', 'related_actions', 'related_questions', 'content', 'deadline',
  'dates', 'locations', 'description', 'extractive', 'abstractive'])

export function languageName(code) {
  if (!code) return 'Unknown'
  try { return new Intl.DisplayNames(['en'], {type: 'language'}).of(code.replaceAll('_', '-')) || code }
  catch { return code }
}

export function mapDisplayText(value, convert, field = '') {
  if (typeof value === 'string') return FIELDS.has(field) && value.trim() && !/^SEG_\d+$/.test(value) ? convert(value) : value
  if (Array.isArray(value)) return value.map(item => mapDisplayText(item, convert, field))
  if (value && typeof value === 'object') return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, mapDisplayText(item, convert, key)]))
  return value
}

export function splitText(text) {
  // Bound each provider input without dropping any characters.
  const parts = []
  let remaining = text
  while (remaining.length > 1500) {
    let end = remaining.lastIndexOf(' ', 1500)
    if (end < 750) {
      end = 1500
      // Do not split a UTF-16 surrogate pair.
      const code = remaining.charCodeAt(end - 1)
      if (code >= 0xD800 && code <= 0xDBFF) end -= 1
    } else end += 1
    parts.push(remaining.slice(0, end)); remaining = remaining.slice(end)
  }
  if (remaining) parts.push(remaining)
  return parts
}

export function batchTexts(texts) {
  const batches = []
  let batch = [], size = 0
  for (const text of texts) {
    const bytes = new TextEncoder().encode(text).length
    if (batch.length && (size + bytes > 8000 || batch.length >= 64)) {
      batches.push(batch); batch = []; size = 0
    }
    batch.push(text); size += bytes
  }
  if (batch.length) batches.push(batch)
  return batches
}

export async function translateDisplay(value, translate, isCurrent = () => true) {
  const texts = new Set()
  mapDisplayText(value, text => { texts.add(text); return text })
  const chunks = [...new Set([...texts].flatMap(splitText).filter(text => text.trim()))]
  const translated = new Map()
  for (const batch of batchTexts(chunks)) {
    if (!isCurrent()) throw new Error('Translation view changed')
    const values = await translate(batch)
    if (!Array.isArray(values) || values.length !== batch.length || values.some(v => typeof v !== 'string' || !v.trim())) {
      throw new Error('Translation was incomplete. Please retry.')
    }
    batch.forEach((text, i) => translated.set(text, values[i]))
  }
  return mapDisplayText(value, text => splitText(text).map(part => translated.get(part) ?? part).join(' '))
}
