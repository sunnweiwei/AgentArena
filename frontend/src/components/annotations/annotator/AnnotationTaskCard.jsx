import React, { useState } from 'react'
import axios from 'axios'
import AnnotationSurvey from './AnnotationSurvey'
import './AnnotationTaskCard.css'

const AnnotationTaskCard = ({ task, user, onAction }) => {
  const [loading, setLoading] = useState(false)
  const [showSurvey, setShowSurvey] = useState(false)
  const [surveyData, setSurveyData] = useState(null)

  // Determine task status and available actions
  const status = task.user_status || task.status || 'available'
  const assignmentId = task.user_assignment_id || task.assignment_id
  const isAvailable = status === 'available'
  const isClaimed = status === 'claimed'
  const isInProgress = status === 'in_progress'
  const isCompleted = status === 'completed'
  const hasSurvey = task.has_survey || (task.survey_submitted_at !== null)

  const handleClaim = async () => {
    setLoading(true)
    try {
      await axios.post(`/api/annotations/${task.task_id || task.id}/claim?user_id=${user.user_id}`)
      if (onAction) onAction()
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Failed to claim task')
    } finally {
      setLoading(false)
    }
  }

  const handleOpenLink = async () => {
    if (!assignmentId) {
      alert('Please claim the task first')
      return
    }

    // Open link in new tab
    window.open(task.data_link, '_blank')

    // Mark as opened
    setLoading(true)
    try {
      await axios.post(`/api/annotations/assignments/${assignmentId}/open?user_id=${user.user_id}`)
      if (onAction) onAction()
    } catch (err) {
      console.error('Failed to mark as opened:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleShowSurvey = () => {
    setShowSurvey(true)
  }

  const handleSurveySubmit = async (surveyResponses) => {
    if (!assignmentId) {
      alert('Assignment not found')
      return
    }

    setLoading(true)
    try {
      await axios.post(
        `/api/annotations/assignments/${assignmentId}/survey?user_id=${user.user_id}`,
        { survey_data: surveyResponses }
      )
      setSurveyData(surveyResponses)
      setShowSurvey(false)
      if (onAction) onAction()
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Failed to submit survey')
    } finally {
      setLoading(false)
    }
  }

  const handleComplete = async () => {
    if (!assignmentId) {
      alert('Assignment not found')
      return
    }

    if (!hasSurvey) {
      alert('Please submit the survey before marking as complete')
      return
    }

    if (!confirm('Mark this task as complete?')) {
      return
    }

    setLoading(true)
    try {
      await axios.post(`/api/annotations/assignments/${assignmentId}/complete?user_id=${user.user_id}`)
      if (onAction) onAction()
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Failed to complete task')
    } finally {
      setLoading(false)
    }
  }

  // Default survey structure (can be customized)
  const defaultSurvey = {
    questions: [
      {
        id: "quality",
        type: "likert",
        question: "Rate response quality",
        scale: 5,
        description: "1 = Poor, 5 = Excellent"
      },
      {
        id: "correctness",
        type: "select",
        question: "Was it correct?",
        options: ["Yes", "No", "Partial"]
      },
      {
        id: "feedback",
        type: "text",
        question: "Comments:"
      }
    ]
  }

  return (
    <>
      <div className={`task-card status-${status}`}>
        <div className="task-header">
          <div className="task-info">
            <div className="task-id">
              <span className="label">Instance:</span>
              <span className="value">{task.instance_id}</span>
            </div>
            <div className="task-id">
              <span className="label">Agent:</span>
              <span className="value">{task.agent_id}</span>
            </div>
            {task.total_assignments !== undefined && (
              <div className="assignment-count">
                {task.total_assignments} annotation{task.total_assignments !== 1 ? 's' : ''}
              </div>
            )}
          </div>
          <div className={`status-badge ${status}`}>
            {status.replace('_', ' ')}
          </div>
        </div>

        <div className="task-actions">
          {isAvailable && (
            <button
              onClick={handleClaim}
              disabled={loading}
              className="action-button claim-button"
            >
              {loading ? 'Claiming...' : 'Claim Task'}
            </button>
          )}

          {(isClaimed || isInProgress) && (
            <>
              <button
                onClick={handleOpenLink}
                disabled={loading}
                className="action-button open-button"
              >
                Open Link
              </button>
              <button
                onClick={handleShowSurvey}
                disabled={loading}
                className="action-button survey-button"
              >
                {hasSurvey ? 'View/Edit Survey' : 'Fill Survey'}
              </button>
              {hasSurvey && (
                <button
                  onClick={handleComplete}
                  disabled={loading || isCompleted}
                  className="action-button complete-button"
                >
                  {isCompleted ? 'Completed' : 'Mark Complete'}
                </button>
              )}
            </>
          )}

          {isCompleted && (
            <div className="completed-indicator">
              ✓ Completed
              {task.completed_at && (
                <span className="completed-date">
                  {new Date(task.completed_at).toLocaleDateString()}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {showSurvey && (
        <div className="survey-modal-overlay" onClick={() => setShowSurvey(false)}>
          <div className="survey-modal" onClick={(e) => e.stopPropagation()}>
            <div className="survey-modal-header">
              <h3>Annotation Survey</h3>
              <button
                onClick={() => setShowSurvey(false)}
                className="close-button"
              >
                ×
              </button>
            </div>
            <div className="survey-modal-content">
              <AnnotationSurvey
                survey={defaultSurvey}
                initialData={surveyData}
                onSubmit={handleSurveySubmit}
                onCancel={() => setShowSurvey(false)}
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default AnnotationTaskCard

