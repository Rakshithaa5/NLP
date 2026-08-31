/**
 * services/api.js — HTTP client for the FastAPI backend.
 *
 * All REST calls to the backend are centralized here.
 * Phase 1: uploadMeeting, getTranscript, listMeetings, checkHealth.
 * Phase 2–3: add analyzeMeeting, getAnalysis.
 * Phase 4: add exportPdf.
 *
 * Base URL is read from the VITE_API_BASE_URL env variable,
 * falling back to the Vite dev proxy (/api) so the proxy config in
 * vite.config.js handles dev-time CORS automatically.
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

/** Internal helper — throw a rich error from a non-OK Response. */
async function _handleResponse(res) {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail ?? body.message ?? detail
    } catch {
      // response was not JSON
    }
    throw new Error(detail)
  }
  return res.json()
}

// ── Phase 1 ──────────────────────────────────────────────────────────────────

/**
 * Upload an audio/video file to the backend.
 * Streams the raw File object as multipart/form-data.
 *
 * @param {File}     file        The File object from an <input> or drag-drop.
 * @param {Function} onProgress  Optional callback (0–100) for upload progress.
 * @returns {Promise<{file_id, filename, duration, language, segments, full_text, uploaded_at}>}
 */
export async function uploadMeeting(file, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData()
    formData.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}/api/upload/`)

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch {
          reject(new Error('Invalid JSON response from server'))
        }
      } else {
        let detail = `Upload failed (${xhr.status})`
        try {
          const body = JSON.parse(xhr.responseText)
          detail = body.detail ?? body.message ?? detail
        } catch {
          // not JSON
        }
        reject(new Error(detail))
      }
    }

    xhr.onerror = () => reject(new Error('Network error — is the backend running?'))
    xhr.ontimeout = () => reject(new Error('Upload timed out'))
    xhr.timeout = 20 * 60 * 1000  // 20-minute timeout for large files

    xhr.send(formData)
  })
}

/**
 * Retrieve stored transcript and metadata for a meeting ID.
 *
 * @param {string} fileId
 * @returns {Promise<{file_id, filename, duration, language, segments, full_text}>}
 */
export async function getTranscript(fileId) {
  const res = await fetch(`${BASE}/api/upload/${fileId}`)
  return _handleResponse(res)
}

/**
 * List all previously uploaded meetings.
 *
 * @returns {Promise<{meetings: Array<{id, filename, duration, language, uploaded_at, status}>}>}
 */
export async function listMeetings() {
  const res = await fetch(`${BASE}/api/upload/`)
  return _handleResponse(res)
}

// ── Phase 2–3 (stubs — implement in the next phase) ──────────────────────────

/**
 * [STUB — Phase 2]
 * Trigger the NLP analysis pipeline for a given file ID.
 * @param {string} fileId
 * @returns {Promise<object>} full analysis payload
 */
export async function analyzeMeeting(fileId) {
  throw new Error('analyzeMeeting — implement in Phase 2')
}

/**
 * [STUB — Phase 4]
 * Download the PDF report for a meeting.
 * @param {string} fileId
 * @returns {Promise<Blob>}
 */
export async function exportPdf(fileId) {
  throw new Error('exportPdf — implement in Phase 4')
}

// ── Health ────────────────────────────────────────────────────────────────────

/**
 * Check backend health. Used on app start to verify connectivity.
 * @returns {Promise<{status: string}>}
 */
export async function checkHealth() {
  const res = await fetch(`${BASE}/health`)
  if (!res.ok) throw new Error('Backend unreachable')
  return res.json()
}
