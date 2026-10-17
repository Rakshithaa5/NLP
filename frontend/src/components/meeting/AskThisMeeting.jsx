import { useEffect, useRef, useState } from 'react'
import { askMeeting } from '../../services/api'
import { timestamp } from './data'

const STARTERS = ['What decisions were made?', 'What are the key action items?', 'What remains unresolved?', 'Summarize this meeting']

function segmentIndex(id) {
  const match = typeof id === 'string' ? id.match(/^SEG_(\d+)$/) : null
  return match ? Number(match[1]) : null
}

export default function AskThisMeeting({fileId, meeting, onJump}) {
  const [open, setOpen] = useState(false)
  const launcher = useRef(null)
  const input = useRef(null)
  const messageList = useRef(null)
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

  useEffect(() => {
    if (open) input.current?.focus()
  }, [open])
  useEffect(() => {
    if (open && messageList.current) messageList.current.scrollTop = messageList.current.scrollHeight
  }, [messages, busy, open])
  function close() {
    setOpen(false)
    launcher.current?.focus()
  }

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

  return <div className="mi-assistant">
    <section id="meeting-assistant" className="mi-assistant-window" role="dialog" aria-label="Ask This Meeting" hidden={!open} onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close() } }}>
      <header className="mi-assistant-header"><div><span className="mi-eyebrow">Your meeting assistant</span><h2>Ask This Meeting</h2></div><button type="button" className="mi-assistant-close" aria-label="Close meeting assistant" onClick={close}>&times;</button></header>
      <div className="mi-assistant-body">
      <p className="mi-caption mi-muted">Answers are grounded only in this meeting's transcript.</p>
    {!messages.length && <div className="mi-chat-starters">{STARTERS.map(starter => <button type="button" key={starter} disabled={busy || remaining > 0} onClick={() => submit(starter)}>{starter}</button>)}</div>}
    {messages.length > 0 && <div className="mi-chat-messages" ref={messageList} aria-live="polite">{messages.map((message, index) => <article className={`mi-chat-message mi-chat-${message.role}`} key={`${message.role}-${index}`}>
      <span className="mi-eyebrow">{message.role === 'user' ? 'You' : 'Meeting answer'}</span><p dir="auto">{message.content}</p>
      {message.contextLimited && <p className="mi-muted">Based on selected transcript excerpts; some meeting details may be missing.</p>}
      {message.role === 'assistant' && message.evidence?.length > 0 && <div className="mi-chat-evidence"><span className="mi-muted">Evidence</span>{message.evidence.map(id => {
        const index = segmentIndex(id), segment = index == null ? null : meeting.segments[index]
        return segment ? <button type="button" className="mi-link" key={id} onClick={() => { close(); onJump({segment_ids: [index], timestamp: segment.start}) }}>▶ {timestamp(segment.start)}</button> : null
      })}</div>}
    </article>)}</div>}
      </div>
    {error && <div role="alert" className="mi-chat-error">{error}</div>}
    <form className="mi-chat-form" onSubmit={event => {event.preventDefault(); submit()}}><input ref={input} aria-label="Ask about this meeting" value={question} onChange={event => setQuestion(event.target.value)} placeholder="Ask about this meeting..." disabled={busy}/><button className="mi-primary" type="submit" disabled={busy || remaining > 0 || !question.trim()}>{busy ? 'Asking...' : remaining > 0 ? `Retry in ${remaining}s` : 'Ask'}</button></form>
    </section>
    <button ref={launcher} type="button" className="mi-assistant-launcher" aria-label={open ? 'Close meeting assistant' : 'Open meeting assistant'} aria-expanded={open} aria-controls="meeting-assistant" onClick={() => open ? close() : setOpen(true)}>
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3v3M9 3h6"/><rect x="4" y="6" width="16" height="14" rx="5"/><path d="M1 11v4m22-4v4M9 15h6"/><circle cx="8.5" cy="11" r=".75" fill="currentColor"/><circle cx="15.5" cy="11" r=".75" fill="currentColor"/></svg>
    </button>
  </div>
}