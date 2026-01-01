import React, { useState } from 'react'
import './SurveyModal.css'

const SurveyModal = ({
  chatId,
  userPreferences,
  onSubmit,
  onSkip,
  isMandatory = false,
  onClose
}) => {
  const [responses, setResponses] = useState({
    proactiveness_questions: 0,
    proactiveness_clarity: 0,
    personalization_alignment: 0,
    feedback_text: '',
    specific_examples: ''
  })

  const [currentSection, setCurrentSection] = useState('likert') // 'likert' or 'qualitative'

  const likertQuestions = [
    {
      key: 'proactiveness_questions',
      question: 'The agent asked clarifying questions when needed',
      description: 'Consider whether the agent proactively sought information to better understand your task'
    },
    {
      key: 'proactiveness_clarity',
      question: 'The agent\'s questions were clear and easy to answer',
      description: 'Think about whether you could easily provide the information the agent requested'
    },
    {
      key: 'personalization_alignment',
      question: 'The agent\'s behavior aligned with my stated preferences',
      description: 'Reflect on whether the agent followed the instructions and preferences you provided'
    }
  ]

  const qualitativePrompts = [
    "What did the agent do particularly well?",
    "What could the agent improve?",
    "Did the agent follow your instructions? Provide specific examples.",
    "Were there moments when the agent seemed confused or off-track?"
  ]

  const handleLikertChange = (key, value) => {
    setResponses(prev => ({ ...prev, [key]: value }))
  }

  const canProceedToQualitative = () => {
    return responses.proactiveness_questions > 0 &&
           responses.proactiveness_clarity > 0 &&
           responses.personalization_alignment > 0
  }

  const handleSubmit = () => {
    if (!canProceedToQualitative()) {
      alert('Please answer all Likert scale questions')
      return
    }
    onSubmit(responses)
  }

  const handleSkip = () => {
    if (!isMandatory && onSkip) {
      onSkip()
    }
  }

  return (
    <div className="survey-modal-overlay" onClick={!isMandatory ? onClose : undefined}>
      <div className="survey-modal" onClick={(e) => e.stopPropagation()}>
        <div className="survey-header">
          <h2>Task Feedback</h2>
          {!isMandatory && (
            <button className="survey-close-btn" onClick={onClose}>×</button>
          )}
        </div>

        {/* Progress indicator */}
        <div className="survey-progress">
          <div className={`progress-step ${currentSection === 'likert' ? 'active' : 'completed'}`}>
            1. Rating
          </div>
          <div className={`progress-step ${currentSection === 'qualitative' ? 'active' : ''}`}>
            2. Feedback
          </div>
        </div>

        {currentSection === 'likert' && (
          <div className="survey-content">
            <p className="survey-intro">
              Please rate your experience with the agent on the following dimensions:
            </p>

            {/* Show user preferences if available */}
            {userPreferences && (
              <div className="user-preferences-context">
                <h4>Your Instructions for this Task:</h4>
                <div className="preferences-content">{userPreferences}</div>
              </div>
            )}

            {likertQuestions.map(({ key, question, description }) => (
              <div key={key} className="likert-question">
                <div className="question-text">{question}</div>
                <div className="question-description">{description}</div>
                <div className="likert-scale">
                  {[1, 2, 3, 4, 5].map(value => (
                    <label key={value} className="likert-option">
                      <input
                        type="radio"
                        name={key}
                        value={value}
                        checked={responses[key] === value}
                        onChange={() => handleLikertChange(key, value)}
                      />
                      <span className="likert-label">{value}</span>
                    </label>
                  ))}
                </div>
                <div className="likert-labels">
                  <span>Strongly Disagree</span>
                  <span>Strongly Agree</span>
                </div>
              </div>
            ))}

            <div className="survey-actions">
              {!isMandatory && (
                <button className="survey-btn survey-btn-secondary" onClick={handleSkip}>
                  Skip
                </button>
              )}
              <button
                className="survey-btn survey-btn-primary"
                onClick={() => setCurrentSection('qualitative')}
                disabled={!canProceedToQualitative()}
              >
                Next
              </button>
            </div>
          </div>
        )}

        {currentSection === 'qualitative' && (
          <div className="survey-content">
            <h3>Share Your Thoughts</h3>
            <p className="survey-intro">
              Please provide specific examples to help us understand your experience better.
            </p>

            <div className="qualitative-section">
              <label htmlFor="feedback">General Feedback</label>
              <div className="prompt-hints">
                {qualitativePrompts.map((prompt, idx) => (
                  <div key={idx} className="prompt-hint">• {prompt}</div>
                ))}
              </div>
              <textarea
                id="feedback"
                className="survey-textarea"
                rows={6}
                placeholder="Share your thoughts here..."
                value={responses.feedback_text}
                onChange={(e) => setResponses(prev => ({ ...prev, feedback_text: e.target.value }))}
              />
            </div>

            <div className="qualitative-section">
              <label htmlFor="examples">Specific Examples</label>
              <p className="field-description">
                Please provide concrete examples that illustrate your ratings above (e.g., specific questions the agent asked, moments where it followed or didn't follow your preferences).
              </p>
              <textarea
                id="examples"
                className="survey-textarea"
                rows={6}
                placeholder="Example: 'When I asked about X, the agent responded with Y...'"
                value={responses.specific_examples}
                onChange={(e) => setResponses(prev => ({ ...prev, specific_examples: e.target.value }))}
              />
            </div>

            <div className="survey-actions">
              <button
                className="survey-btn survey-btn-secondary"
                onClick={() => setCurrentSection('likert')}
              >
                Back
              </button>
              {!isMandatory && (
                <button className="survey-btn survey-btn-secondary" onClick={handleSkip}>
                  Skip
                </button>
              )}
              <button className="survey-btn survey-btn-primary" onClick={handleSubmit}>
                Submit
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default SurveyModal
