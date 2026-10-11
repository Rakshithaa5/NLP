import { useEffect, useRef, useState } from 'react'
import { Panel } from './Overview'
import { askMeeting } from '../../services/api'
import { timestamp } from './data'

const STARTERS = ['What decisions were made?', 'What are the key action items?', 'What remains unresolved?', 'Summarize this meeting']

function segmentIndex(id) {
  const match = typeof id === 'string' ? id.match(/^SEG_(\d+)$/) : null
  return match ? Number(match[1]) : null
}

export default function AskThisMeeting({fileId, meeting, onJump}) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [retryAt, setRetryAt] = useState(0)
  const [remaining, setRemaining] = useState(0)
  const inFlight = useRef(false)
  useEffect(() => {
    if (!retryAt) return
    const tick = () => setRemaining(Math.max(0, Math.ceil((retryAt - Date.now()) / 1000)))
    tick()
    const timer = setInterval(tick, 1000)
    return () => clearInterval(timer)
  }, [retryAt])

  async function submit(value = question) {
    const prompt = value.trim()
    if (!prompt || inFlight.current || Date.now() < retryAt) return
    inFlight.current = true
    const history = messages.slice(-6).map(({role, content}) => ({role, content}))
    setMessages(current => [...current, {role: 'user', content: prompt}])
    setQuestion(''); setError(''); setBusy(true)
    try {
      const result = await askMeeting(fileId, prompt, history)
      setMessages(current => [...current, {role: 'assistant', content: result.answer, evidence: result.evidence_segment_ids || [], contextLimited: result.context_limited}])
    } catch (requestError) {
      setMessages(current => current.slice(0, -1))
      setQuestion(prompt)
      if (requestError.status === 429) {
        const seconds = Math.max(1, requestError.retryAfter || 60)
        setRemaining(seconds)
        setRetryAt(Date.now() + seconds * 1000)
      }
      setError(requestError.message || 'The meeting chatbot is temporarily unavailable.')
    } finally { inFlight.current = false; setBusy(false) }
  }

  return <Panel title="Ask This Meeting" className="mi-chat" subtitle="Answers are grounded only in this meeting's transcript.">
    {!messages.length && <div className="mi-chat-starters">{STARTERS.map(starter => <button type="button" key={starter} disabled={busy || remaining > 0} onClick={() => submit(starter)}>{starter}</button>)}</div>}
    {messages.length > 0 && <div className="mi-chat-messages" aria-live="polite">{messages.map((message, index) => <article className={`mi-chat-message mi-chat-${message.role}`} key={`${message.role}-${index}`}>
      <span className="mi-eyebrow">{message.role === 'user' ? 'You' : 'Meeting answer'}</span><p dir="auto">{message.content}</p>
      {message.contextLimited && <p className="mi-muted">Based on selected transcript excerpts; some meeting details may be missing.</p>}
      {message.role === 'assistant' && message.evidence?.length > 0 && <div className="mi-chat-evidence"><span className="mi-muted">Evidence</span>{message.evidence.map(id => {
        const index = segmentIndex(id), segment = index == null ? null : meeting.segments[index]
        return segment ? <button type="button" className="mi-link" key={id} onClick={() => onJump({segment_ids: [index], timestamp: segment.start})}>▶ {timestamp(segment.start)}</button> : null
      })}</div>}
    </article>)}</div>}
    {error && <div role="alert" className="mi-chat-error">{error}</div>}
    <form className="mi-chat-form" onSubmit={event => {event.preventDefault(); submit()}}><input aria-label="Ask about this meeting" value={question} onChange={event => setQuestion(event.target.value)} placeholder="Ask about this meeting..." disabled={busy}/><button className="mi-primary" type="submit" disabled={busy || remaining > 0 || !question.trim()}>{busy ? 'Asking...' : remaining > 0 ? `Retry in ${remaining}s` : 'Ask'}</button></form>
  </Panel>
}