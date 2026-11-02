import { useEffect, useRef, useState } from 'react'
import { askMeeting } from '../../services/api'
import { timestamp, number } from './data'
import { useEnglishDisplay, useMeetingLanguage } from './translationHooks'

const COPY = {
  en: {
    starters: ['What decisions were made?', 'What are the key action items?', 'What remains unresolved?', 'Summarize this meeting'],
    title: 'Ask This Meeting', assistant: 'Your meeting assistant', close: 'Close meeting assistant', open: 'Open meeting assistant',
    caption: "Answers are grounded only in this meeting's transcript.", you: 'You', answer: 'Meeting answer', evidence: 'Evidence',
    limited: 'Based on selected transcript excerpts; some meeting details may be missing.',
    placeholder: 'Ask about this meeting...', input: 'Ask about this meeting', asking: 'Asking...', ask: 'Ask',
    retry: seconds => `Retry in ${seconds}s`, unavailable: 'The meeting chatbot is temporarily unavailable.',
  },
  fr: {
    starters: ['Quelles décisions ont été prises ?', 'Quelles sont les principales actions à réaliser ?', 'Quels points restent à résoudre ?', 'Résume cette réunion'],
    title: 'Interroger cette réunion', assistant: 'Votre assistant de réunion', close: 'Fermer l’assistant de réunion', open: 'Ouvrir l’assistant de réunion',
    caption: 'Les réponses reposent uniquement sur la transcription de cette réunion.', you: 'Vous', answer: 'Réponse', evidence: 'Sources',
    limited: 'Réponse basée sur des extraits sélectionnés ; certains détails de la réunion peuvent manquer.',
    placeholder: 'Posez une question sur cette réunion…', input: 'Poser une question sur cette réunion', asking: 'Recherche…', ask: 'Demander',
    retry: seconds => `Réessayer dans ${seconds} s`, unavailable: 'L’assistant de réunion est temporairement indisponible.',
  },
}

function segmentIndex(id) {
  const match = typeof id === 'string' ? id.match(/^SEG_(\d+)$/) : null
  return match ? Number(match[1]) : null
}

export default function AskThisMeeting({fileId, meeting, onJump}) {
  const {english} = useMeetingLanguage()
  const language = (english ? 'en' : meeting.language || '').toLowerCase().replace('_', '-').split('-')[0]
  const copy = COPY[language] || COPY.en
  const [open, setOpen] = useState(false)
  const launcher = useRef(null)
  const input = useRef(null)
  const messageList = useRef(null)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const displayMessages = useEnglishDisplay(messages)
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
      const result = await askMeeting(fileId, prompt, history, english ? 'en' : null)
      setMessages(current => [...current, {role: 'assistant', content: result.answer, evidence: result.evidence_segment_ids || [], contextLimited: result.context_limited}])
    } catch (requestError) {
      setMessages(current => current.slice(0, -1))
      setQuestion(prompt)
      if (requestError.status === 429) {
        const seconds = Math.max(1, requestError.retryAfter || 60)
        setRemaining(seconds)
        setRetryAt(Date.now() + seconds * 1000)
      }
      setError(requestError.message || copy.unavailable)
    } finally { inFlight.current = false; setBusy(false) }
  }

  return <div className="mi-assistant">
    <section id="meeting-assistant" className="mi-assistant-window" role="dialog" aria-label={copy.title} hidden={!open} onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close() } }}>
      <header className="mi-assistant-header"><div><span className="mi-eyebrow">{copy.assistant}</span><h2>{copy.title}</h2></div><button type="button" className="mi-assistant-close" aria-label={copy.close} onClick={close}>&times;</button></header>
      <div className="mi-assistant-body">
      <p className="mi-caption mi-muted">{copy.caption}</p>
    {!messages.length && <div className="mi-chat-starters">{copy.starters.map(starter => <button type="button" key={starter} disabled={busy || remaining > 0} onClick={() => submit(starter)}>{starter}</button>)}</div>}
    {messages.length > 0 && <div className="mi-chat-messages" ref={messageList} aria-live="polite">{displayMessages.map((message, index) => <article className={`mi-chat-message mi-chat-${message.role}`} key={`${message.role}-${index}`}>
      <span className="mi-eyebrow">{message.role === 'user' ? copy.you : copy.answer}</span><p dir="auto">{message.content}</p>
      {message.contextLimited && <p className="mi-muted">{copy.limited}</p>}
      {message.role === 'assistant' && message.evidence?.length > 0 && <div className="mi-chat-evidence"><span className="mi-muted">{copy.evidence}</span>{message.evidence.map(id => {
        const index = segmentIndex(id), segment = index == null ? null : meeting.segments[index]
        return segment ? <button type="button" className="mi-link" key={id} onClick={() => { close(); onJump({segment_ids: [index], timestamp: segment.start}) }}>{number(segment.start) !== null ? `▶ ${timestamp(segment.start)}` : `View excerpt ${index + 1}`}</button> : null
      })}</div>}
    </article>)}</div>}
      </div>
    {busy && <p role="status" className="chat-loading">Finding an answer in this meeting…</p>}
    {error && <div role="alert" className="mi-chat-error">{error}</div>}
    <form className="mi-chat-form" onSubmit={event => {event.preventDefault(); submit()}}><input ref={input} aria-label={copy.input} value={question} onChange={event => setQuestion(event.target.value)} placeholder={copy.placeholder} disabled={busy}/><button className="mi-primary" type="submit" disabled={busy || remaining > 0 || !question.trim()}>{busy ? copy.asking : remaining > 0 ? copy.retry(remaining) : copy.ask}</button></form>
    </section>
    <button ref={launcher} type="button" className="mi-assistant-launcher" aria-label={open ? copy.close : copy.open} aria-expanded={open} aria-controls="meeting-assistant" onClick={() => open ? close() : setOpen(true)}>
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3v3M9 3h6"/><rect x="4" y="6" width="16" height="14" rx="5"/><path d="M1 11v4m22-4v4M9 15h6"/><circle cx="8.5" cy="11" r=".75" fill="currentColor"/><circle cx="15.5" cy="11" r=".75" fill="currentColor"/></svg>
      <span>{open ? copy.close : copy.title}</span><span aria-hidden="true">{open ? '−' : '+'}</span>
    </button>
  </div>
}