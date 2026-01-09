import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './AdminAnnotationDashboard.css'

const AdminAnnotationDashboard = ({ user, onViewBatch }) => {
  const [stats, setStats] = useState(null)
  const [batches, setBatches] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadData()
    // Refresh every 30 seconds
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      setError(null)
      const [statsRes, batchesRes] = await Promise.all([
        axios.get(`/api/admin/annotations/progress?user_id=${user.user_id}`),
        axios.get(`/api/admin/annotations/batches?user_id=${user.user_id}`)
      ])
      setStats(statsRes.data)
      setBatches(batchesRes.data.batches || [])
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const handleBatchAction = async (batchId, action) => {
    try {
      await axios.post(`/api/admin/annotations/batches/${batchId}/${action}?user_id=${user.user_id}`)
      loadData() // Refresh data
    } catch (err) {
      alert(err.response?.data?.detail || err.message || `Failed to ${action} batch`)
    }
  }

  if (loading) {
    return (
      <div className="admin-dashboard loading">
        <div className="loading-spinner"></div>
        <div>Loading dashboard...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="admin-dashboard error">
        <div className="error-message">{error}</div>
        <button onClick={loadData} className="retry-button">Retry</button>
      </div>
    )
  }

  const { summary, annotator_stats, batch_stats } = stats || {}

  return (
    <div className="admin-annotation-dashboard">
      {/* Summary Cards */}
      <div className="summary-grid">
        <div className="stat-card">
          <div className="stat-label">Total Tasks</div>
          <div className="stat-value">{summary?.total_tasks || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Completed</div>
          <div className="stat-value">{summary?.completed_tasks || 0}</div>
          <div className="stat-sublabel">{summary?.completion_rate || 0}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">In Progress</div>
          <div className="stat-value">{summary?.in_progress_tasks || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Annotators</div>
          <div className="stat-value">{annotator_stats?.length || 0}</div>
        </div>
      </div>

      {/* Batch List */}
      <div className="dashboard-section">
        <h2>Batches</h2>
        <div className="batches-table">
          <table>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Status</th>
                <th>Tasks</th>
                <th>Completed</th>
                <th>In Progress</th>
                <th>Completion Rate</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {batches.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty-state">No batches uploaded yet</td>
                </tr>
              ) : (
                batches.map(batch => (
                  <tr key={batch.id}>
                    <td className="filename-cell">{batch.filename}</td>
                    <td>
                      <span className={`status-badge status-${batch.status || 'active'}`}>
                        {batch.status || 'active'}
                      </span>
                    </td>
                    <td>{batch.task_count}</td>
                    <td>{batch.completed_assignments}</td>
                    <td>{batch.in_progress_assignments}</td>
                    <td>
                      <div className="completion-bar-container">
                        <div className="completion-bar" style={{ width: `${batch.completion_rate}%` }}>
                          {batch.completion_rate}%
                        </div>
                      </div>
                    </td>
                    <td>{new Date(batch.uploaded_at).toLocaleDateString()}</td>
                    <td>
                      <div className="batch-actions">
                        <button
                          onClick={() => onViewBatch(batch.id)}
                          className="view-button"
                        >
                          View
                        </button>
                        {batch.status === 'active' && (
                          <>
                            <button
                              onClick={() => handleBatchAction(batch.id, 'pause')}
                              className="pause-button"
                              title="Pause batch (can be resumed later)"
                            >
                              Pause
                            </button>
                            <button
                              onClick={() => {
                                if (confirm('Stop this batch? This cannot be undone.')) {
                                  handleBatchAction(batch.id, 'stop')
                                }
                              }}
                              className="stop-button"
                              title="Stop batch permanently"
                            >
                              Stop
                            </button>
                          </>
                        )}
                        {batch.status === 'paused' && (
                          <>
                            <button
                              onClick={() => handleBatchAction(batch.id, 'resume')}
                              className="resume-button"
                              title="Resume batch"
                            >
                              Resume
                            </button>
                            <button
                              onClick={() => {
                                if (confirm('Stop this batch? This cannot be undone.')) {
                                  handleBatchAction(batch.id, 'stop')
                                }
                              }}
                              className="stop-button"
                              title="Stop batch permanently"
                            >
                              Stop
                            </button>
                          </>
                        )}
                        {batch.status === 'stopped' && (
                          <span className="stopped-label">Stopped</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Annotator Statistics */}
      <div className="dashboard-section">
        <h2>Annotator Statistics</h2>
        <div className="annotator-stats-table">
          <table>
            <thead>
              <tr>
                <th>Annotator</th>
                <th>Total Claimed</th>
                <th>Completed</th>
                <th>In Progress</th>
                <th>Avg Time (hours)</th>
              </tr>
            </thead>
            <tbody>
              {annotator_stats?.length === 0 ? (
                <tr>
                  <td colSpan="5" className="empty-state">No annotator activity yet</td>
                </tr>
              ) : (
                annotator_stats.map(annotator => (
                  <tr key={annotator.user_id}>
                    <td className="user-email">{annotator.user_email}</td>
                    <td>{annotator.total_claimed}</td>
                    <td>{annotator.completed_count}</td>
                    <td>{annotator.in_progress_count}</td>
                    <td>{annotator.avg_completion_time_hours || 'N/A'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default AdminAnnotationDashboard

