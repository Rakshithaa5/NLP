import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { translateMeetingText } from '../../services/api'
import { languageName } from './translation'
import { TranslationContext, useMeetingLanguage } from './translationHooks'

export function TranslationProvider({fileId, children}) {
  const [english, setEnglish] = useState(false)
  const [pending, setPending] = useState(0)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [retryAt, setRetryAt] = useState(0)
  const [now, setNow] = useState(0)
  const cache = useRef(new Map())
  const blocked = useRef(null)
  // Serialize requests across transcript, topics and chat to avoid quota bursts.
  const queue = useRef(Promise.resolve())
  useEffect(() => {
    if (!retryAt) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [retryAt])
  const translate = useCallback(texts => {
    const key = JSON.stringify(texts)
    if (!cache.current.has(key)) {
      const request = queue.current.catch(() => {}).then(async () => {
        setPending(count => count + 1)
        try {
          if (blocked.current) throw blocked.current
          const values = (await translateMeetingText(fileId, texts)).translations
          if (!Array.isArray(values) || values.length !== texts.length || values.some(v => typeof v !== 'string' || !v.trim())) {
            throw new Error('Translation was incomplete. Please retry.')
          }
          return values
        }
        catch (e) {
          blocked.current = e
          cache.current.delete(key)
          setError(e.message || 'Translation failed.')
          if (e.status === 429 && !e.cooldownRecorded) { e.cooldownRecorded = true; setNow(Date.now()); setRetryAt(Date.now() + e.retryAfter * 1000) }
          throw e
        } finally { setPending(count => count - 1) }
      })
      queue.current = request
      cache.current.set(key, request)
    }
    return cache.current.get(key)
  }, [fileId])
  const retry = useCallback(() => { blocked.current = null; setError(''); setRevision(value => value + 1) }, [])
  const value = useMemo(() => ({english, setEnglish, pending, error, translate, revision, retry,
    retrySeconds: Math.max(0, Math.ceil((retryAt - now) / 1000))}),
  [english, pending, error, translate, revision, retry, retryAt, now])
  return <TranslationContext.Provider value={value}>{children}</TranslationContext.Provider>
}

export function MeetingLanguageControl({language}) {
  const {english, setEnglish} = useMeetingLanguage()
  const canTranslate = language && language.toLowerCase().split(/[-_]/)[0] !== 'en'
  return <div className="mi-language-control">
    <span>Detected language: <strong>{languageName(language)}</strong></span>
    {canTranslate && <button type="button" role="switch" aria-checked={english}
      aria-label="Show meeting in English" className="mi-language-switch" onClick={() => setEnglish(value => !value)}>
      <span className="mi-switch-track" aria-hidden="true"><span /></span>
      Show in English
    </button>}
  </div>
}

export function TranslationStatus() {
  const {english, pending, error, retry, retrySeconds} = useMeetingLanguage()
  if (!english) return null
  return <div className="mi-notice" role={error ? 'alert' : 'status'}>
    <span style={{flex: 1}}>{error
      ? `${error} Some text is still shown in its original language.`
      : pending ? 'Translating into English. Original text is shown until each section is ready.'
      : 'English view. Translations preserve the original recording timestamps.'}</span>
    {error && <button type="button" onClick={retry} disabled={pending > 0 || retrySeconds > 0}>
      {retrySeconds > 0 ? `Retry in ${retrySeconds}s` : 'Retry translation'}
    </button>}
  </div>
}
