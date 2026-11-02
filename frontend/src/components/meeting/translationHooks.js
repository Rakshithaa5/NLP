import { createContext, useContext, useEffect, useState } from 'react'
import { translateDisplay } from './translation'

export const TranslationContext = createContext({english: false, revision: 0})

export function useMeetingLanguage() { return useContext(TranslationContext) }

export function useEnglishDisplay(source) {
  const {english, translate, revision} = useMeetingLanguage()
  const [result, setResult] = useState(null)
  useEffect(() => {
    if (!english || source == null) return
    let active = true
    translateDisplay(source, translate, () => active).then(value => {
      if (active) setResult({source, value})
    }).catch(() => {}) // The shared status shows actionable errors and retry.
    return () => { active = false }
  }, [source, english, translate, revision])
  return english && result?.source === source ? result.value : source
}

