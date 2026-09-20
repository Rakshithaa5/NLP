import { timestamp, speakerStats } from './data'
export default function MeetingHeader({meeting, busy, exporting, hasAnalysis, onAnalyze, onExport}) {
  const speakers = speakerStats(meeting.segments).rows.length
  const date = meeting.uploaded_at ? new Date(meeting.uploaded_at) : null
  return <header className="mi-header"><div><span className="mi-eyebrow">Meeting intelligence</span><h1>{meeting.filename || 'Meeting analysis'}</h1><div className="mi-header-meta">
    {date && !Number.isNaN(date.getTime()) && <span>Uploaded {date.toLocaleDateString(undefined, {day: 'numeric', month: 'short', year: 'numeric'})}</span>}
    {meeting.duration !== null && <span>{timestamp(meeting.duration)} duration</span>}
    {meeting.language && <span>{meeting.language.toUpperCase()}</span>}
    {speakers > 0 && <span>{speakers} identified speakers</span>}
  </div></div><div className="mi-header-actions"><button disabled={busy} onClick={onAnalyze}>{busy ? 'Analysing...' : hasAnalysis ? 'Re-analyse' : 'Analyse meeting'}</button><button className="mi-primary" disabled={!hasAnalysis || exporting || busy} onClick={onExport}>{exporting ? 'Exporting...' : 'Export PDF'}</button></div></header>
}
