import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import UploadCard from '../components/UploadCard'
import { listMeetings } from '../services/api'

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
    <header className="workspace-heading"><p className="mi-eyebrow">Your meeting workspace</p><h1>Make room for <span className="doodle-underline">what matters.</span></h1><p>Bring your recording. Leave with clear notes and next steps.</p></header>
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
