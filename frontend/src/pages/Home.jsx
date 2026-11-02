import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import UploadCard from '../components/UploadCard'
import { listMeetings } from '../services/api'

const FEATURES = [
  { emoji: '🎙️', title: 'Auto Transcription', desc: 'Faster-Whisper converts audio & video to text — any accent, any length.', color: '#EDF4EC', border: '#347447', rot: '-1.2deg' },
  { emoji: '🌍', title: 'Multilingual NLP', desc: 'spaCy + NLTK run on the original language. No forced English translation.', color: '#EDF2F6', border: '#3B6EA8', rot: '0.8deg' },
  { emoji: '🏷️', title: 'Named Entity Recognition', desc: 'People, orgs, dates, products & locations extracted with spaCy NER.', color: '#FFF4CC', border: '#A68B37', rot: '-0.6deg' },
  { emoji: '✅', title: 'Action Items', desc: 'TF-IDF + dependency parsing surfaces every task with owner & deadline.', color: '#FAEEE5', border: '#B05A2F', rot: '1deg' },
  { emoji: '🗳️', title: 'Decision Extraction', desc: 'Rule-based + LR classifier finds explicit decisions grounded in the transcript.', color: '#F0E8F5', border: '#7B4FA6', rot: '-0.9deg' },
  { emoji: '🧠', title: 'Topic Modelling', desc: 'LDA & NMF over TF-IDF vectors reveal the real themes of every meeting.', color: '#E8F5F0', border: '#2E8B6A', rot: '0.5deg' },
  { emoji: '💬', title: 'Ask the Meeting', desc: 'RAG-style chatbot — ask anything, get answers cited from the transcript.', color: '#FFF0F0', border: '#B03A3A', rot: '-0.7deg' },
  { emoji: '📝', title: 'Abstractive Summary', desc: 'BART / T5 transformer drafts a concise human-readable meeting summary.', color: '#F5F0E8', border: '#8B6A2E', rot: '1.1deg' },
]

export default function Home() {
  const navigate = useNavigate()
  const [recent, setRecent] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  useEffect(() => {
    let current = true
    listMeetings().then(res => {if(current) setRecent((res.meetings || []).slice(0,5))}).catch(e => {if(current) setError(e.message || 'Could not load recent meetings.')}).finally(() => {if(current) setLoading(false)})
    return () => {current = false}
  }, [reload])

  return <div className="page-container home-workspace">
    <header className="workspace-heading home-branding">
      <h1 className="hero-brand"><span className="hero-logo" aria-hidden="true"><svg width="38" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><rect x="5" y="3" width="15" height="18" rx="3"/><path d="M3 7h4M3 12h4M3 17h4M10 8h6M10 12h6M10 16h4"/></svg></span><span>Meeting<span className="doodle-underline">Intel</span></span><svg className="brand-spark" aria-hidden="true" width="32" height="34" viewBox="0 0 32 34" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="m5 18 9-3M15 6l-2 5M24 9l-5 5M23 24l-6-4"/></svg></h1>
      <p className="hero-tagline">Turn conversations into clear next steps.</p>
      <p className="hero-description">Upload your meeting. Get summaries, action items, decisions, and answers.</p>
    </header>

    {/* ── NLP Feature strip ── */}
    <div className="features-marquee-wrap">
      <div className="features-marquee">
        {[...FEATURES, ...FEATURES].map(({ emoji, title, color, border }, i) => (
          <span key={i} className="marquee-chip" style={{ background: color, borderColor: border, '--chip-shadow': border }}>
            {emoji} {title}
          </span>
        ))}
      </div>
    </div>

    <div className="upload-layout"><section className="upload-section"><div className="section-heading"><span className="step-label">01</span><div><h2>Start a new meeting</h2><p>Upload a recording to create your transcript.</p></div><svg className="upload-doodle" aria-hidden="true" width="64" height="46" viewBox="0 0 64 46" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M5 8c29-15 48 7 35 24-6 7-16 4-13-3 4-9 25-2 30 7m-10-2 10 2-1-10"/></svg></div>
    <UploadCard onSuccess={data => navigate(`/transcript/${data.file_id}`,{state:{transcript:data}})}/>
    <div className="upload-note"><span aria-hidden="true">↗</span><p>You can review the original transcript before running the analysis.</p></div>
    <div className="workflow-steps">{[['02','Review transcript','Search the original words and revisit the recording.'],['03','Find the next steps','Explore summaries, decisions, and action items.']].map(([n,title,body]) => <div key={n}><span className="step-label">{n}</span><h3>{title}</h3><p>{body}</p></div>)}</div></section>
    <aside className="card recent-meetings"><div className="section-heading"><h2>Recent meetings</h2><Link to="/history">View all ↗</Link></div>
      {loading ? <div role="status" className="mi-loading"><span>Loading your meetings…</span><div/><div/></div> : error ? <div role="alert"><p className="mi-caption">{error}</p><button className="btn btn-secondary" onClick={() => {setError('');setLoading(true);setReload(v=>v+1)}}>Try again</button></div> : !recent.length ? <div className="recent-empty"><span aria-hidden="true">↗</span><h3>Your notes start here</h3><p>Your uploaded meetings will appear here, ready to revisit.</p></div> : <div className="recent-list">{recent.map(m => <Link key={m.id} to={m.status === 'done' ? `/dashboard/${m.id}` : `/transcript/${m.id}`}><span className="file-badge" aria-hidden="true">{m.filename?.split('.').pop()?.toUpperCase() || 'FILE'}</span><span><strong>{m.filename || 'Untitled meeting'}</strong><small>{m.uploaded_at && Number.isFinite(Date.parse(m.uploaded_at)) ? new Date(m.uploaded_at).toLocaleDateString(undefined,{month:'short',day:'numeric'}) : 'Date unavailable'} · {({done:'Analyzed',processing:'Processing',uploaded:'Uploaded',error:'Failed'})[m.status] || 'Status unavailable'}</small></span><span aria-hidden="true">↗</span></Link>)}</div>}
    </aside></div>
    <footer className="workspace-footnote">From conversation to clarity. One meeting at a time.</footer>
  </div>
}