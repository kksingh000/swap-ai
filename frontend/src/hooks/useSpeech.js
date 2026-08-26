import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Browser Web Speech API wrapper - the reason demo mode is completely free.
 * Recognition and synthesis both run on-device; no STT/TTS bill, no server audio.
 *
 * Chrome and Edge support en-IN and hi-IN. Firefox has no SpeechRecognition,
 * so callers fall back to the text input.
 */

const LANG_CODES = {
  english: 'en-IN',
  hinglish: 'en-IN', // en-IN handles code-switched Hinglish far better than hi-IN
  hindi: 'hi-IN',
  marathi: 'mr-IN',
  bengali: 'bn-IN',
  telugu: 'te-IN',
  kannada: 'kn-IN',
  tamil: 'ta-IN',
  gujarati: 'gu-IN',
  punjabi: 'pa-IN',
  malayalam: 'ml-IN',
  odia: 'or-IN',
}

export function useSpeechRecognition({ language = 'english', onResult, onError } = {}) {
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const recognitionRef = useRef(null)
  const onResultRef = useRef(onResult)
  const shouldStopRef = useRef(false)

  useEffect(() => {
    onResultRef.current = onResult
  }, [onResult])

  const supported =
    typeof window !== 'undefined' &&
    Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)

  const start = useCallback(() => {
    if (!supported || listening) return
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new Recognition()

    recognition.lang = LANG_CODES[language] || 'en-IN'
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      shouldStopRef.current = false
      setListening(true)
      setInterim('')
    }
    recognition.onresult = (event) => {
      let finalText = ''
      let interimText = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const chunk = event.results[i][0].transcript
        if (event.results[i].isFinal) finalText += chunk
        else interimText += chunk
      }
      setInterim(interimText)
      if (finalText.trim()) {
        shouldStopRef.current = true
        setInterim('')
        onResultRef.current?.(finalText.trim())
      }
    }
    recognition.onerror = (event) => {
      setListening(false)
      if (event.error !== 'no-speech' && event.error !== 'aborted') {
        onError?.(event.error)
      }
    }
    recognition.onend = () => {
      setListening(false)
      setInterim('')
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch {
      setListening(false)
    }
  }, [supported, listening, language, onError])

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
    setListening(false)
  }, [])

  useEffect(() => () => recognitionRef.current?.abort(), [])

  return { supported, listening, interim, start, stop }
}

export function useSpeechSynthesis() {
  const [speaking, setSpeaking] = useState(false)
  const [enabled, setEnabled] = useState(true)
  const voicesRef = useRef([])

  useEffect(() => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return
    const load = () => {
      voicesRef.current = window.speechSynthesis.getVoices()
    }
    load()
    window.speechSynthesis.onvoiceschanged = load
    return () => {
      window.speechSynthesis.onvoiceschanged = null
    }
  }, [])

  const speak = useCallback(
    (text, language = 'english') => {
      if (!enabled || !text || typeof window === 'undefined' || !window.speechSynthesis) return
      window.speechSynthesis.cancel()

      const utterance = new SpeechSynthesisUtterance(text)
      const code = LANG_CODES[language] || 'en-IN'
      utterance.lang = code
      utterance.rate = 1.02
      utterance.pitch = 1.05

      // Prefer an Indian voice, then any voice for the base language.
      const voices = voicesRef.current
      const base = code.split('-')[0]
      utterance.voice =
        voices.find((v) => v.lang === code) ||
        voices.find((v) => v.lang?.startsWith(base) && v.lang.endsWith('IN')) ||
        voices.find((v) => v.lang?.startsWith(base)) ||
        null

      utterance.onstart = () => setSpeaking(true)
      utterance.onend = () => setSpeaking(false)
      utterance.onerror = () => setSpeaking(false)
      window.speechSynthesis.speak(utterance)
    },
    [enabled],
  )

  const cancel = useCallback(() => {
    window.speechSynthesis?.cancel()
    setSpeaking(false)
  }, [])

  return {
    speak,
    cancel,
    speaking,
    enabled,
    setEnabled,
    supported: typeof window !== 'undefined' && Boolean(window.speechSynthesis),
  }
}
