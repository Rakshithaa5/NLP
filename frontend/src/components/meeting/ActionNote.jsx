import { useState } from 'react'
import { readActionNote, saveActionNote } from './notes'

export default function ActionNote({storageKey}) {
  const [initial] = useState(() => {
    try { return {note: readActionNote(window.localStorage, storageKey), error: ''} }
    catch { return {note: '', error: 'Browser storage is unavailable. Personal notes cannot be saved here.'} }
  })
  const [note, setNote] = useState(initial.note)
  const [draft, setDraft] = useState(initial.note)
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState(initial.error)
  const [feedback, setFeedback] = useState('')
  function save(value) {
    try {
      const saved = saveActionNote(window.localStorage, storageKey, value)
      setNote(saved); setDraft(saved); setEditing(false); setError('')
      setFeedback(saved ? 'Note saved.' : 'Note deleted.')
    } catch { setError('Could not save your note. Browser storage may be full or disabled. Your draft is still here.') }
  }
  function edit() { setDraft(note); setEditing(true); setFeedback('') }
  return <div className="mi-personal-note">
    {note && !editing && <><span className="mi-eyebrow">Personal note</span><p className="mi-note-text" dir="auto">{note}</p></>}
    {editing ? <form className="mi-action-editor" onSubmit={event => {event.preventDefault(); if(draft.trim()) save(draft)}}>
      <label>Personal note<textarea autoFocus value={draft} maxLength={5000} rows={3} onChange={event => setDraft(event.target.value)} placeholder="Add your own context or a reminder…" /></label>
      <p className="mi-caption">Saved only in this browser. Not included in the meeting analysis or PDF.</p>
      <div className="mi-action-editor-buttons"><button type="submit" disabled={!draft.trim()}>Save note</button><button type="button" onClick={() => {setEditing(false);setDraft(note)}}>Cancel</button></div>
    </form> : <div className="mi-note-controls"><button type="button" className="mi-link" onClick={edit}>{note ? 'Edit note' : 'Add note'}</button>{note && <button type="button" className="mi-link" onClick={() => save('')}>Delete note</button>}</div>}
    {error && <p role="alert" className="mi-error">{error}</p>}
    {feedback && <p role="status" className="mi-caption">{feedback}</p>}
  </div>
}
