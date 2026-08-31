/**
 * pages/Home.jsx — Landing / upload page.
 *
 * Phase 1: Full upload UI using UploadCard.
 *   - Displays hero section with product tagline
 *   - Mounts UploadCard and handles success/error callbacks
 *   - On success: navigates to /transcript/:fileId with data in router state
 */

import { useNavigate } from 'react-router-dom'
import UploadCard from '../components/UploadCard'

export default function Home() {
  const navigate = useNavigate()

  const handleSuccess = (data) => {
    // Pass the full transcript data via router state to avoid a redundant API call
    navigate(`/transcript/${data.file_id}`, { state: { transcript: data } })
  }

  const handleError = (msg) => {
    // UploadCard handles its own error display; nothing extra to do at page level
    console.error('[Home] Upload error:', msg)
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '64px 24px' }}>

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <div style={{ textAlign: 'center', marginBottom: 56 }} className="animate-fade-up">
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '6px 16px', borderRadius: 99,
          background: 'rgba(99,102,241,0.12)',
          border: '1px solid rgba(99,102,241,0.3)',
          marginBottom: 24,
        }}>
          <span style={{ fontSize: 14, color: 'var(--clr-primary-h)', fontWeight: 600 }}>
            🎙 AI-Powered Meeting Analysis
          </span>
        </div>

        <h1 style={{
          fontSize: 'clamp(36px, 5vw, 60px)',
          fontWeight: 800, lineHeight: 1.1,
          marginBottom: 20, letterSpacing: '-0.03em',
        }}>
          <span className="gradient-text">Transform Meetings</span>
          <br />
          <span style={{ color: 'var(--clr-text)' }}>into Actionable Intelligence</span>
        </h1>

        <p style={{
          fontSize: 17, color: 'var(--clr-text-muted)',
          maxWidth: 540, margin: '0 auto 40px',
          lineHeight: 1.7,
        }}>
          Upload any recording. Our NLP pipeline extracts transcripts, action items,
          decisions, and summaries — automatically.
        </p>

        {/* Pipeline steps */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 0, marginBottom: 48, flexWrap: 'wrap' }}>
          {[
            { step: 'Upload', icon: '📁' },
            { step: 'Transcribe', icon: '🔊' },
            { step: 'Analyze', icon: '🧠' },
            { step: 'Dashboard', icon: '📊' },
          ].map((item, i, arr) => (
            <div key={item.step} style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
                padding: '10px 16px',
                opacity: i > 1 ? 0.4 : 1,  // Phase 1 only unlocks first 2
              }}>
                <span style={{ fontSize: 20 }}>{item.icon}</span>
                <span style={{
                  fontSize: 11, fontWeight: 700, letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  color: i <= 1 ? 'var(--clr-primary-h)' : 'var(--clr-text-dim)',
                }}>
                  {item.step}
                </span>
              </div>
              {i < arr.length - 1 && (
                <span style={{ color: 'var(--clr-border-2)', fontSize: 18, margin: '0 4px' }}>→</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Upload Card ──────────────────────────────────────────────────── */}
      <UploadCard onSuccess={handleSuccess} onError={handleError} />

      {/* ── Feature highlights ───────────────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 16, marginTop: 56,
      }}>
        {[
          { icon: '⚡', title: 'Faster-Whisper STT', desc: 'CTranslate2-optimised speech recognition — fast even on CPU.' },
          { icon: '🧠', title: 'spaCy NER', desc: 'Named entity recognition for people, orgs, dates, and locations.' },
          { icon: '📋', title: 'Action Item Extraction', desc: 'Dependency parsing pulls person + task + deadline automatically.' },
          { icon: '📄', title: 'BART Summarization', desc: 'Extractive + abstractive summaries powered by Hugging Face.' },
        ].map(feat => (
          <div key={feat.title} className="card" style={{ textAlign: 'left' }}>
            <span style={{ fontSize: 28, display: 'block', marginBottom: 10 }}>{feat.icon}</span>
            <p style={{ fontWeight: 700, marginBottom: 6, fontSize: 14 }}>{feat.title}</p>
            <p style={{ fontSize: 13, color: 'var(--clr-text-muted)', lineHeight: 1.6 }}>{feat.desc}</p>
          </div>
        ))}
      </div>

    </div>
  )
}
