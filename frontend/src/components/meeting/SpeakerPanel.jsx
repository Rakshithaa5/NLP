/**
 * SpeakerPanel.jsx — Speaker diarization controls and speaker list.
 *
 * Responsibilities:
 *  - Show diarization state (none / running / complete / failed)
 *  - Allow running / re-running diarization independently of analysis
 *  - Show detected speakers with editable display names
 *  - Toggle speaker labels on/off in the transcript
 *
 * Constraints:
 *  - Renaming only changes the display name; stable speaker IDs are untouched.
 *  - Re-running diarization never triggers re-transcription or re-analysis.
 *  - If diarization fails, the original transcript is shown normally.
 */
import { useState } from 'react'
import { runDiarization, renameSpeaker } from '../../services/api'

function EditableName({ fileId, speakerId, name, onRenamed }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(name)
  const [saving, setSaving] = useState(false)

  async function save() {
    const trimmed = value.trim()
    if (!trimmed || trimmed === name) { setEditing(false); setValue(name); return }
    setSaving(true)
    try {
      await renameSpeaker(fileId, speakerId, trimmed)
      onRenamed(speakerId, trimmed)
      setEditing(false)
    } catch {
      setValue(name)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <span className="mi-speaker-edit">
        <input
          autoFocus
          value={value}
          maxLength={80}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') { setEditing(false); setValue(name) } }}
          onBlur={save}
          disabled={saving}
          aria-label="Edit speaker name"
        />
      </span>
    )
  }
  return (
    <button
      type="button"
      className="mi-speaker-name-btn"
      onClick={() => setEditing(true)}
      title="Click to rename"
    >
      {name}
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true" style={{marginLeft: 4, opacity: 0.5}}>
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
      </svg>
    </button>
  )
}

export default function SpeakerPanel({ fileId, diarization, onDiarizationUpdate, showLabels, onToggleLabels }) {
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const state = diarization?.state ?? 'none'
  const speakers = diarization?.speakers ?? {}
  const speakerCount = diarization?.speaker_count ?? 0

  async function handleRun(force = false) {
    setRunning(true)
    setError('')
    try {
      const result = await runDiarization(fileId, force)
      onDiarizationUpdate(result)
    } catch (e) {
      setError(e.message || 'Diarization failed. Please retry.')
    } finally {
      setRunning(false)
    }
  }

  function handleRenamed(speakerId, newName) {
    if (!diarization) return
    const updated = {
      ...diarization,
      speakers: {
        ...diarization.speakers,
        [speakerId]: { ...diarization.speakers[speakerId], display_name: newName },
      },
      segments: (diarization.segments || []).map(s =>
        s.speaker_id === speakerId ? { ...s, speaker_name: newName } : s
      ),
    }
    onDiarizationUpdate(updated)
  }

  return (
    <section className="mi-panel mi-speaker-panel" aria-label="Speaker diarization">
      <div className="mi-section-title">
        <h2>Speakers</h2>
        {state === 'complete' && speakerCount > 0 && (
          <span className="mi-count">{speakerCount}</span>
        )}
      </div>
      <p className="mi-muted mi-caption">
        Automatic speaker detection from audio. Labels are anonymous by default — click a name to rename.
      </p>

      {error && (
        <div role="alert" className="mi-notice mi-error" style={{ marginBottom: 8 }}>
          <span style={{ flex: 1 }}>{error}</span>
        </div>
      )}

      {state === 'none' && (
        <div className="mi-speaker-empty">
          <p className="mi-muted">Speaker labels have not been generated for this recording.</p>
          <button
            className="mi-primary"
            disabled={running}
            onClick={() => handleRun(false)}
          >
            {running ? 'Detecting speakers…' : 'Detect speakers'}
          </button>
        </div>
      )}

      {state === 'failed' && (
        <div className="mi-speaker-empty">
          <p className="mi-muted">Speaker detection failed. The transcript is still available without labels.</p>
          <button
            className="mi-primary"
            disabled={running}
            onClick={() => handleRun(true)}
          >
            {running ? 'Retrying…' : 'Retry detection'}
          </button>
        </div>
      )}

      {state === 'complete' && (
        <>
          <div className="mi-speaker-controls">
            <label className="mi-toggle-label">
              <input
                type="checkbox"
                checked={showLabels}
                onChange={e => onToggleLabels(e.target.checked)}
              />
              Show speaker labels in transcript
            </label>
            <button
              type="button"
              className="mi-btn-secondary"
              disabled={running}
              onClick={() => handleRun(true)}
              title="Re-run diarization without re-transcribing or re-analysing"
            >
              {running ? 'Re-running…' : 'Re-run detection'}
            </button>
          </div>

          {Object.keys(speakers).length > 0 ? (
            <ul className="mi-speaker-list">
              {Object.entries(speakers)
                .sort((a, b) => (a[1].order ?? 0) - (b[1].order ?? 0))
                .map(([id, meta]) => (
                  <li key={id} className="mi-speaker-item">
                    <span className="mi-speaker-avatar" aria-hidden="true">
                      {(meta.display_name || 'S')[0].toUpperCase()}
                    </span>
                    <EditableName
                      fileId={fileId}
                      speakerId={id}
                      name={meta.display_name}
                      onRenamed={handleRenamed}
                    />
                    <span className="mi-speaker-id mi-muted">{id}</span>
                  </li>
                ))}
            </ul>
          ) : (
            <p className="mi-empty">No speakers were detected in this recording.</p>
          )}

          <p className="mi-caption mi-muted" style={{ marginTop: 8 }}>
            Speaker count is estimated automatically from acoustic evidence.
            Accuracy depends on audio quality and speaker overlap.
          </p>
        </>
      )}

      {running && state !== 'complete' && (
        <div role="status" className="mi-notice" style={{ marginTop: 8 }}>
          Analysing audio for speaker voices. This may take a moment…
        </div>
      )}
    </section>
  )
}
