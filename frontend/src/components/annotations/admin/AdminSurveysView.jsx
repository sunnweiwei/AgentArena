import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './AdminSurveysView.css'

const AdminSurveysView = ({ user }) => {
  const [surveys, setSurveys] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filterBatchId, setFilterBatchId] = useState('')
  const [filterUserEmail, setFilterUserEmail] = useState('')

  useEffect(() => {
    loadSurveys()
    // Refresh every 30 seconds
    const interval = setInterval(loadSurveys, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadSurveys = async () => {
    try {
      setError(null)
      const response = await axios.get(
        `/api/admin/annotations/surveys?user_id=${user.user_id}${filterBatchId ? `&batch_id=${filterBatchId}` : ''}`
      )
      setSurveys(response.data.surveys || [])
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load surveys')
    } finally {
      setLoading(false)
    }
  }

  const handleViewSurvey = (survey) => {
    const surveyWindow = window.open('', '_blank', 'width=600,height=700')
    surveyWindow.document.write(`
      <html>
        <head><title>Survey Response - ${survey.user_email}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
          .survey-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
          h2 { margin-top: 0; color: #333; }
          .survey-field { margin-bottom: 15px; }
          .field-label { font-weight: 600; color: #555; margin-bottom: 5px; }
          .field-value { color: #333; padding: 8px; background: #f9f9f9; border-radius: 4px; word-break: break-all; }
          .meta-info { margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }
          a { color: #4f46e5; text-decoration: none; }
          a:hover { text-decoration: underline; }
        </style>
        </head>
        <body>
          <div class="survey-container">
            <h2>Survey Response</h2>
            <div class="survey-field">
              <div class="field-label">Annotator:</div>
              <div class="field-value">${survey.user_email}</div>
            </div>
            <div class="survey-field">
              <div class="field-label">Instance ID:</div>
              <div class="field-value">${survey.instance_id || 'N/A'}</div>
            </div>
              <div class="survey-field">
              <div class="field-label">Agent ID:</div>
              <div class="field-value">${survey.agent_id || 'N/A'}</div>
            </div>
            ${survey.survey_data?.annotation_name ? `
            <div class="survey-field">
              <div class="field-label">Annotation Name:</div>
              <div class="field-value">${survey.survey_data.annotation_name}</div>
            </div>
            ` : ''}
            ${survey.survey_data?.prolific_id ? `
            <div class="survey-field">
              <div class="field-label">Prolific ID:</div>
              <div class="field-value">${survey.survey_data.prolific_id}</div>
            </div>
            ` : ''}
            ${survey.survey_data?.final_return_link ? `
            <div class="survey-field">
              <div class="field-label">Final Return Link:</div>
              <div class="field-value"><a href="${survey.survey_data.final_return_link}" target="_blank">${survey.survey_data.final_return_link}</a></div>
            </div>
            ` : ''}
            <div class="meta-info">
              <div>Completed: ${survey.completed_at ? new Date(survey.completed_at).toLocaleString() : 'N/A'}</div>
              <div>Survey Submitted: ${survey.survey_submitted_at ? new Date(survey.survey_submitted_at).toLocaleString() : 'N/A'}</div>
            </div>
          </div>
        </body>
      </html>
    `)
  }

  const filteredSurveys = surveys.filter(survey => {
    if (filterUserEmail && !survey.user_email.toLowerCase().includes(filterUserEmail.toLowerCase())) {
      return false
    }
    return true
  })

  if (loading) {
    return (
      <div className="surveys-view loading">
        <div className="loading-spinner"></div>
        <div>Loading surveys...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="surveys-view error">
        <div className="error-message">{error}</div>
        <button onClick={loadSurveys} className="retry-button">Retry</button>
      </div>
    )
  }

  return (
    <div className="surveys-view">
      <div className="surveys-header">
        <h2>Completed Surveys</h2>
        <div className="surveys-count">{filteredSurveys.length} survey{filteredSurveys.length !== 1 ? 's' : ''}</div>
      </div>

      <div className="filters">
        <input
          type="text"
          placeholder="Filter by annotator email..."
          value={filterUserEmail}
          onChange={(e) => setFilterUserEmail(e.target.value)}
          className="filter-input"
        />
        <button onClick={loadSurveys} className="refresh-button">Refresh</button>
      </div>

      <div className="surveys-table-container">
        <table className="surveys-table">
          <thead>
            <tr>
              <th>Annotator</th>
              <th>Instance ID</th>
              <th>Agent ID</th>
              <th>Annotation Name</th>
              <th>Prolific ID</th>
              <th>Completed</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredSurveys.length === 0 ? (
              <tr>
                <td colSpan="7" className="empty-state">
                  {filterUserEmail ? 'No surveys match filter' : 'No completed surveys yet'}
                </td>
              </tr>
            ) : (
              filteredSurveys.map(survey => (
                <tr key={survey.assignment_id}>
                  <td className="user-email">{survey.user_email}</td>
                  <td className="instance-id-cell">{survey.instance_id || 'N/A'}</td>
                  <td className="agent-id-cell">{survey.agent_id || 'N/A'}</td>
                  <td>{survey.survey_data?.annotation_name || '-'}</td>
                  <td>{survey.survey_data?.prolific_id || '-'}</td>
                  <td>{survey.completed_at ? new Date(survey.completed_at).toLocaleDateString() : 'N/A'}</td>
                  <td>
                    <button
                      onClick={() => handleViewSurvey(survey)}
                      className="view-survey-button"
                    >
                      View Full Survey
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default AdminSurveysView

