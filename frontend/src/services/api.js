/**
 * services/api.js — HTTP client for the FastAPI backend.
 *
 * All REST calls to the backend are centralized here.
 * Phase 1: implement uploadMeeting, getTranscript.
 * Phase 2–3: add analyzeMeeting, getAnalysis.
 * Phase 4: add getMeetingHistory, exportPdf.
 *
 * Base URL is read from the VITE_API_BASE_URL env variable,
 * falling back to the Vite dev proxy (/api).
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

/**
 * [STUB — Phase 1]
 * Upload an audio/video file and return the created file ID.
 * @param {File} file
 * @returns {Promise<{file_id: string}>}
 */
export async function uploadMeeting(file) {
  throw new Error('uploadMeeting — implement in Phase 1')
}

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
 * Check backend health. Used on app start to verify connectivity.
 * @returns {Promise<{status: string}>}
 */
export async function checkHealth() {
  const res = await fetch(`${BASE}/health`)
  if (!res.ok) throw new Error('Backend unreachable')
  return res.json()
}
