import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import './MessageInput.css'

const MessageInput = ({ onSendMessage, onStopGeneration, disabled, isStreaming }) => {
  const [message, setMessage] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [isRequestingAccess, setIsRequestingAccess] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [isSecureContextState, setIsSecureContextState] = useState(
    typeof window !== 'undefined'
      ? (window.isSecureContext ?? window.location.protocol === 'https:')
      : false
  )
  const textareaRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const isRecordingRef = useRef(false)
  const lastAmplitudeRef = useRef(0)
  const [audioLevel, setAudioLevel] = useState(0)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [message])

  useEffect(() => {
    const checkSecureContext = () => {
      setIsSecureContextState(window.isSecureContext ?? window.location.protocol === 'https:')
    }
    checkSecureContext()
    window.addEventListener('focus', checkSecureContext)
    return () => window.removeEventListener('focus', checkSecureContext)
  }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (message.trim() && !disabled) {
      onSendMessage(message)
      setMessage('')
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const startRecording = async () => {
    try {
      // Check if we're on HTTPS or localhost (required for getUserMedia in most browsers)
      const isSecure = location.protocol === 'https:' || 
                       location.hostname === 'localhost' || 
                       location.hostname === '127.0.0.1' ||
                       window.isSecureContext
      
      if (!isSecure) {
        // Silently fail - browser will handle the error
        console.warn('Microphone access may not be available on HTTP. Try HTTPS if available.')
        return
      }

    // Check if getUserMedia is available
    if (!navigator.mediaDevices) {
      console.error('navigator.mediaDevices is not available')
      alert('Your browser does not support microphone access. Please use a modern browser like Chrome, Firefox, or Safari.')
      return
    }

    const hasGetUserMedia = typeof navigator.mediaDevices.getUserMedia === 'function'
      
      if (!hasGetUserMedia) {
        console.error('getUserMedia not available:', {
          hasMediaDevices: !!navigator.mediaDevices,
          getUserMediaType: typeof navigator.mediaDevices?.getUserMedia,
          userAgent: navigator.userAgent,
          protocol: location.protocol,
          hostname: location.hostname
        })
        alert('Your browser does not support microphone access. Please use a modern browser like Chrome, Firefox, or Safari.')
        return
      }

      console.log('Requesting microphone access...')
      lastAmplitudeRef.current = 0
      setAudioLevel(0)
      setIsRequestingAccess(true) // Show loading state
      // Request highest quality audio settings
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 48000, // Higher sample rate for better quality
          channelCount: 1,
          // Request specific constraints for best quality
          googEchoCancellation: true,
          googNoiseSuppression: true,
          googAutoGainControl: true,
          googHighpassFilter: true,
          googTypingNoiseDetection: true
        }
      })
      console.log('Microphone access granted')
      
      // Get actual audio track settings to verify quality
      const audioTrack = stream.getAudioTracks()[0]
      const settings = audioTrack.getSettings()
      console.log('Audio track settings:', settings)
      
      // Set up audio visualization
      try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)()
        const analyser = audioContext.createAnalyser()
        const source = audioContext.createMediaStreamSource(stream)
        source.connect(analyser)
        analyser.fftSize = 256
        analyser.smoothingTimeConstant = 0.85
        audioContextRef.current = audioContext
        analyserRef.current = analyser
        
        // Start visualization loop
        const visualize = () => {
          if (!isRecordingRef.current || !analyserRef.current) {
            return
          }
          const bufferLength = analyser.frequencyBinCount
          const dataArray = new Uint8Array(bufferLength)
          analyser.getByteFrequencyData(dataArray)

          let sum = 0
          for (let i = 0; i < bufferLength; i++) {
            sum += dataArray[i]
          }
          const average = sum / bufferLength
          const normalized = Math.min(1, average / 180)
          const smoothed = (lastAmplitudeRef.current * 0.25) + (normalized * 0.75)
          lastAmplitudeRef.current = smoothed

          setAudioLevel(smoothed)
          
          if (isRecordingRef.current) {
            requestAnimationFrame(visualize)
          }
        }
        requestAnimationFrame(visualize)
      } catch (e) {
        console.warn('Audio visualization not available:', e)
      }
      
      // Try to use the best available codec - prefer opus for quality
      let mimeType = 'audio/webm;codecs=opus'
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus'
      } else if (MediaRecorder.isTypeSupported('audio/webm')) {
        mimeType = 'audio/webm'
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4'
      } else if (MediaRecorder.isTypeSupported('audio/wav')) {
        mimeType = 'audio/wav' // WAV is uncompressed, highest quality
      }
      console.log('Using MIME type:', mimeType)
      
      // Store mimeType in a way accessible to onstop handler
      const recordedMimeType = mimeType
      
      // Use highest quality bitrate available
      let bitrate = 256000 // 256 kbps for high quality
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        // Fallback to default if codec not supported
        bitrate = undefined
      }
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: mimeType,
        audioBitsPerSecond: bitrate // High quality bitrate
      })
      
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          console.log('Audio chunk received:', event.data.size, 'bytes')
          audioChunksRef.current.push(event.data)
        }
      }
      
      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event.error)
        isRecordingRef.current = false
        setIsRecording(false)
        setIsRequestingAccess(false)
        lastAmplitudeRef.current = 0
        setAudioLevel(0)
        if (audioContextRef.current) {
          audioContextRef.current.close()
        }
        alert('Recording error occurred. Please try again.')
      }

      mediaRecorder.onstop = async () => {
        console.log('Recording stopped, chunks:', audioChunksRef.current.length)
        isRecordingRef.current = false
        setAudioLevel(0)
        if (audioContextRef.current) {
          audioContextRef.current.close()
          audioContextRef.current = null
        }
        
        if (audioChunksRef.current.length === 0) {
          console.warn('No audio chunks recorded, skipping transcription')
          stream.getTracks().forEach(track => track.stop())
          return
        }
        
        const audioBlob = new Blob(audioChunksRef.current, { type: recordedMimeType })
        console.log('Audio blob created:', audioBlob.size, 'bytes, type:', audioBlob.type)
        
        if (audioBlob.size < 1000) {
          console.warn('Audio blob is very small, skipping transcription')
          stream.getTracks().forEach(track => track.stop())
          return
        }
        
        await transcribeAudio(audioBlob)
        
        // Stop all tracks to release microphone
        stream.getTracks().forEach(track => track.stop())
      }

      // Start recording immediately and update UI states
      mediaRecorder.start()
      isRecordingRef.current = true
      setIsRequestingAccess(false)
      setIsRecording(true)
      console.log('Recording started with MIME type:', mimeType)
    } catch (error) {
      console.error('Error starting recording:', error)
      isRecordingRef.current = false
      
      let errorMessage = 'Failed to access microphone. '
      
      if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        errorMessage += 'Microphone permission was denied. Please:\n' +
          '1. Click the lock icon in your browser\'s address bar\n' +
          '2. Allow microphone access\n' +
          '3. Refresh the page and try again'
      } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        errorMessage += 'No microphone found. Please connect a microphone and try again.'
      } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
        errorMessage += 'Microphone is already in use by another application. Please close other apps using the microphone.'
      } else if (error.name === 'OverconstrainedError' || error.name === 'ConstraintNotSatisfiedError') {
        errorMessage += 'Microphone constraints could not be satisfied. Please try a different microphone.'
      } else {
        errorMessage += `Error: ${error.message || error.name}. Please check your browser settings and try again.`
      }
      
      setIsRequestingAccess(false)
      alert(errorMessage)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      isRecordingRef.current = false
      setIsRecording(false)
      lastAmplitudeRef.current = 0
      setAudioLevel(0)
      if (audioContextRef.current) {
        audioContextRef.current.close()
        audioContextRef.current = null
      }
    }
  }

  const transcribeAudio = async (audioBlob) => {
    setIsTranscribing(true)
    try {
      console.log('Sending audio for transcription, size:', audioBlob.size, 'type:', audioBlob.type)
      
      // Determine file extension based on blob type
      let filename = 'recording.webm'
      if (audioBlob.type.includes('mp4')) {
        filename = 'recording.m4a'
      } else if (audioBlob.type.includes('wav')) {
        filename = 'recording.wav'
      }
      
      const formData = new FormData()
      formData.append('file', audioBlob, filename)

      const response = await axios.post('/api/audio/transcribe', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 60000, // 60 second timeout for longer recordings
      })

      console.log('Transcription response:', response.data)
      
      if (response.data && response.data.text) {
        const transcribedText = response.data.text.trim()
        console.log('Transcribed text:', transcribedText)
        
        if (!transcribedText) {
          alert('Transcription returned empty text. Please try speaking more clearly or longer.')
          return
        }
        
        setMessage(prev => prev ? `${prev} ${transcribedText}` : transcribedText)
        // Focus the textarea after transcription
        if (textareaRef.current) {
          textareaRef.current.focus()
        }
      } else {
        console.error('Invalid transcription response:', response.data)
        alert('Transcription failed: Invalid response from server.')
      }
    } catch (error) {
      console.error('Transcription error:', error)
      if (error.response) {
        console.error('Error response:', error.response.data)
        alert(`Failed to transcribe audio: ${error.response.data?.detail || error.response.statusText}. Please try again.`)
      } else if (error.request) {
        alert('Failed to connect to server. Please check your connection and try again.')
      } else {
        alert(`Failed to transcribe audio: ${error.message}. Please try again.`)
      }
    } finally {
      setIsTranscribing(false)
    }
  }

  const handleVoiceButtonClick = () => {
    if (isRecording) {
      stopRecording()
    } else {
      startRecording()
    }
  }

  const normalizedVolume = Math.min(1, Math.max(0, (audioLevel - 0.01) / 0.15))
  const recordingScale = 0.65 + normalizedVolume * 0.45

  return (
    <div className="message-input-container">
      <form onSubmit={handleSubmit} className="message-input-form">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? "Connecting..." : isRecording ? "Recording..." : "Ask anything"}
          className="message-input"
          rows={1}
          disabled={disabled || isTranscribing || isRecording}
        />
        <button
          type="button"
          className={`voice-button ${isRecording ? 'recording' : ''} ${isRequestingAccess ? 'requesting' : ''} ${isTranscribing ? 'transcribing' : ''}`}
          onClick={handleVoiceButtonClick}
          disabled={disabled || isTranscribing || isRequestingAccess}
          aria-label={
            isRecording
              ? "Stop recording"
              : isRequestingAccess
                ? "Requesting microphone access..."
                : "Start voice recording"
          }
          title={
            isRecording
              ? "Stop recording"
              : isRequestingAccess
                ? "Requesting microphone access..."
                : isTranscribing
                  ? "Transcribing..."
                  : "Start voice recording"
          }
        >
          {isRequestingAccess ? (
            <span className="voice-spinner" aria-hidden="true" />
          ) : isTranscribing ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="spinning">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
          ) : isRecording ? (
            <div className="voice-stop-indicator">
              <div
                className="voice-stop-indicator-inner"
                style={{
                  transform: `scale(${recordingScale})`
                }}
              />
            </div>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          )}
        </button>
        {isStreaming ? (
          <button
            type="button"
            className="send-button stop-button"
            onClick={onStopGeneration}
            aria-label="Stop generation"
            title="Stop generation"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <rect x="5" y="5" width="14" height="14" rx="2" />
            </svg>
          </button>
        ) : (
          <button
            type="submit"
            className="send-button"
            disabled={!message.trim() || disabled || isTranscribing || isStreaming}
            aria-label="Send message"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="19" x2="12" y2="5" />
              <polyline points="5 12 12 5 19 12" />
            </svg>
          </button>
        )}
      </form>
    </div>
  )
}

export default MessageInput

