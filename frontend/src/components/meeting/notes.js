// Personal annotations stay on this device, outside extracted meeting records.
export function actionNoteKey(fileId, item) {
  return `meetingintel:action-note:${JSON.stringify([fileId, item.task || '', item.evidence || '', item.segment_ids || []])}`
}
export function readActionNote(storage, key) {
  return storage.getItem(key) || ''
}
export function saveActionNote(storage, key, value) {
  const note = value.trim()
  if (note) storage.setItem(key, note)
  else storage.removeItem(key)
  return note
}
