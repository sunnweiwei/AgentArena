import React, { useState, useEffect } from 'react'
import './AnnotationSurvey.css'

const AnnotationSurvey = ({ survey, initialData = null, onSubmit, onCancel }) => {
  const [responses, setResponses] = useState(initialData || {})
  
  // Auto-fill from initialData when component mounts or initialData changes
  useEffect(() => {
    if (initialData) {
      setResponses(prev => ({ ...initialData, ...prev }))
    }
  }, [initialData])

  const handleResponseChange = (questionId, value) => {
    setResponses(prev => ({ ...prev, [questionId]: value }))
  }

  const handleSubmit = () => {
    // Validate all questions are answered
    const allAnswered = survey.questions.every(q => {
      const response = responses[q.id]
      return response !== undefined && response !== null && response !== ''
    })

    if (!allAnswered) {
      alert('Please answer all questions before submitting.')
      return
    }

    onSubmit(responses)
  }

  return (
    <div className="annotation-survey">
      <div className="survey-questions">
        {survey.questions.map((question, idx) => (
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
                    >
                      <input
                        type="radio"
                        name={question.id}
                        value={value}
                        checked={isChecked}
                        onChange={() => handleResponseChange(question.id, value)}
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
                        name={question.id}
                        value={option}
                        checked={isChecked}
                        onChange={() => handleResponseChange(question.id, option)}
                      />
                      <span className="select-label">{option}</span>
                    </label>
                  )
                })}
              </div>
            )}
            
            {question.type === 'text' && (
              <input
                type="text"
                value={responses[question.id] || ''}
                onChange={(e) => handleResponseChange(question.id, e.target.value)}
                placeholder={question.description || "Type your answer here..."}
                className="survey-text-input"
              />
            )}
            
            {question.type === 'textarea' && (
              <textarea
                value={responses[question.id] || ''}
                onChange={(e) => handleResponseChange(question.id, e.target.value)}
                placeholder={question.description || "Type your answer here..."}
                className="survey-textarea"
                rows={3}
              />
            )}
          </div>
        ))}
      </div>
      
      <div className="survey-actions">
        {onCancel && (
          <button onClick={onCancel} className="cancel-button">
            Cancel
          </button>
        )}
        <button onClick={handleSubmit} className="submit-button">
          Submit Survey
        </button>
      </div>
    </div>
  )
}

export default AnnotationSurvey

