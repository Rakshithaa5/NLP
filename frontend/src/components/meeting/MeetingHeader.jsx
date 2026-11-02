import { timestamp } from './data'
import { languageName } from './translation'
export default function MeetingHeader({meeting, busy, analyzeDisabled, exporting, hasAnalysis, onAnalyze, onExport}) {
  const date = meeting.uploaded_at ? new Date(meeting.uploaded_at) : null
  return <header className="mi-header"><div><span className="mi-eyebrow">Meeting intelligence</span><h1>{meeting.filename || 'Meeting analysis'}</h1><div className="mi-header-meta">
    {date && !Number.isNaN(date.getTime()) && <span>Uploaded {date.toLocaleDateString(undefined, {day: 'numeric', month: 'short', year: 'numeric'})}</span>}
    {meeting.duration !== null && <span>{timestamp(meeting.duration)} duration</span>}
    {meeting.language && <span>Detected language: {languageName(meeting.language)}</span>}
  </div></div><div className="mi-header-actions"><button disabled={analyzeDisabled ?? busy} onClick={onAnalyze}>{busy ? 'Analysing...' : hasAnalysis ? 'Re-analyse' : 'Analyse meeting'}</button><button className="mi-primary" disabled={!hasAnalysis || exporting || busy} onClick={onExport}>{exporting ? 'Exporting...' : 'Export PDF'}</button></div></header>
}
