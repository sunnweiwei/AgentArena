import React, { useState } from 'react'
import './SurveyBlock.css'

/**
 * SurveyBlock component - renders an inline survey in the chat
 * Survey format (JSON inside <|survey|> tags):
 * {
 *   "questions": [
 *     { "id": "q1", "type": "likert", "question": "...", "scale": 5 },
 *     { "id": "q2", "type": "select", "question": "...", "options": ["A", "B"] },
 *     { "id": "q3", "type": "text", "question": "..." }
 *   ]
 * }
 */
export function SurveyBlock({ content, onSubmit, isSubmitted = false, submittedValues = null, messageId = null }) {
  const [localResponses, setLocalResponses] = useState({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Use submitted values if survey is submitted, otherwise use local state
  const responses = isSubmitted && submittedValues ? submittedValues : localResponses

  // Debug: log only when submitted values first appear
  const prevSubmittedRef = React.useRef(null)
  React.useEffect(() => {
    if (isSubmitted && submittedValues && submittedValues !== prevSubmittedRef.current) {
      console.log(`[SurveyBlock ${messageId}] Submitted values:`, submittedValues)
      prevSubmittedRef.current = submittedValues
    }
  }, [isSubmitted, submittedValues, messageId])

  // Parse survey JSON
  let surveyData
  try {
    surveyData = JSON.parse(content)
  } catch (e) {
    console.error('Failed to parse survey JSON:', e)
    return <div className="survey-error">Invalid survey format</div>
  }

  const handleResponseChange = (questionId, value) => {
    setLocalResponses(prev => ({ ...prev, [questionId]: value }))
  }

  const handleSubmit = async () => {
    // Validate all questions are answered
    const allAnswered = surveyData.questions.every(q => {
      const response = responses[q.id]
      return response !== undefined && response !== null && response !== ''
    })

    if (!allAnswered) {
      alert('Please answer all questions before submitting.')
      return
    }

    setIsSubmitting(true)
    try {
      await onSubmit(responses)
    } catch (error) {
      console.error('Survey submission failed:', error)
      alert('Failed to submit survey. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="survey-block">
      <div className="survey-header">
        Feedback Survey
      </div>
      
      <div className="survey-questions">
        {surveyData.questions.map((question, idx) => (
          <div key={question.id} className="survey-question">
            <div className="question-label">
              <span className="question-number">{idx + 1}.</span>
              <div style={{ flex: 1 }}>
                <div className="question-text">{question.question}</div>
                {question.description && (
                  <div className="question-description">{question.description}</div>
                )}
              </div>
            </div>
            
            {question.type === 'likert' && (
              <div className="likert-scale">
                {Array.from({ length: question.scale || 5 }, (_, i) => i + 1).map(value => {
                  const currentValue = responses[question.id]
                  const isChecked = currentValue !== undefined && Number(currentValue) === value

                  return (
                    <label
                      key={value}
                      className={`likert-option ${isChecked ? 'checked' : ''}`}
                      data-checked={isChecked}
                      data-value={value}
                      data-current={currentValue}
                    >
                      <input
                        type="radio"
                        name={`${messageId}-${question.id}`}
                        value={value}
                        checked={isChecked}
                        onChange={() => handleResponseChange(question.id, value)}
                        disabled={isSubmitted}
                      />
                      <span className="likert-label">{value}</span>
                    </label>
                  )
                })}
              </div>
            )}
            
            {question.type === 'select' && (
              <div className="select-options">
                {question.options.map((option, optIdx) => {
                  const currentValue = responses[question.id]
                  const isChecked = currentValue === option

                  return (
                    <label
                      key={optIdx}
                      className={`select-option ${isChecked ? 'checked' : ''}`}
                    >
                      <input
                        type="radio"
                        name={`${messageId}-${question.id}`}
                        value={option}
                        checked={isChecked}
                        onChange={() => handleResponseChange(question.id, option)}
                        disabled={isSubmitted}
                      />
                      <span className="select-label">{option}</span>
                    </label>
                  )
                })}
              </div>
            )}
            
            {question.type === 'text' && (
              <textarea
                value={responses[question.id] || ''}
                onChange={(e) => handleResponseChange(question.id, e.target.value)}
                disabled={isSubmitted}
                placeholder="Type your answer here..."
                className="survey-textarea"
                rows={3}
              />
            )}
            
            {question.type === 'multiselect' && (
              <div className="multiselect-options">
                {question.options.map((option, optIdx) => (
                  <label key={optIdx} className="multiselect-option">
                    <input
                      type="checkbox"
                      checked={(responses[question.id] || []).includes(option)}
                      onChange={(e) => {
                        const current = responses[question.id] || []
                        const updated = e.target.checked
                          ? [...current, option]
                          : current.filter(v => v !== option)
                        handleResponseChange(question.id, updated)
                      }}
                      disabled={isSubmitted}
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      
      {!isSubmitted && (
        <button
          className="survey-submit-button"
          onClick={handleSubmit}
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Submitting...' : 'Submit Survey'}
        </button>
      )}
    </div>
  )
}

