import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './AdminAnnotationBatchView.css'

const AdminAnnotationBatchView = ({ user, batchId, onBack }) => {
  const [batchData, setBatchData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filterInstanceId, setFilterInstanceId] = useState('')
  const [filterAgentId, setFilterAgentId] = useState('')

  useEffect(() => {
    loadBatchData()
  }, [batchId])

  const loadBatchData = async () => {
    try {
      setError(null)
      const response = await axios.get(
        `/api/admin/annotations/batches/${batchId}/tasks?user_id=${user.user_id}`
      )
      setBatchData(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load batch data')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="batch-view loading">
        <div className="loading-spinner"></div>
        <div>Loading batch details...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="batch-view error">
        <div className="error-message">{error}</div>
        <button onClick={onBack} className="back-button">Go Back</button>
      </div>
    )
  }

  const filteredTasks = batchData?.tasks?.filter(task => {
    if (filterInstanceId && !task.instance_id.toLowerCase().includes(filterInstanceId.toLowerCase())) {
      return false
    }
    if (filterAgentId && !task.agent_id.toLowerCase().includes(filterAgentId.toLowerCase())) {
      return false
    }
    return true
  }) || []

  return (
    <div className="batch-view">
      <div className="batch-header">
        <div>
          <h2>{batchData?.batch_filename || 'Batch Details'}</h2>
          <p className="batch-info">
            {batchData?.tasks?.length || 0} tasks total
          </p>
        </div>
        <button onClick={onBack} className="back-button">← Back to Dashboard</button>
      </div>

      <div className="filters">
        <input
          type="text"
          placeholder="Filter by instance_id..."
          value={filterInstanceId}
          onChange={(e) => setFilterInstanceId(e.target.value)}
          className="filter-input"
        />
        <input
          type="text"
          placeholder="Filter by agent_id..."
          value={filterAgentId}
          onChange={(e) => setFilterAgentId(e.target.value)}
          className="filter-input"
        />
      </div>

      <div className="tasks-table-container">
        <table className="tasks-table">
          <thead>
            <tr>
              <th>Instance ID</th>
              <th>Agent ID</th>
              <th>Data Link</th>
              <th>Assignments</th>
              <th>Status</th>
              <th>Annotators</th>
            </tr>
          </thead>
          <tbody>
            {filteredTasks.length === 0 ? (
              <tr>
                <td colSpan="6" className="empty-state">
                  {filterInstanceId || filterAgentId ? 'No tasks match filters' : 'No tasks in batch'}
                </td>
              </tr>
            ) : (
              filteredTasks.map(task => (
                <tr key={task.id}>
                  <td className="instance-id-cell">{task.instance_id}</td>
                  <td className="agent-id-cell">{task.agent_id}</td>
                  <td className="data-link-cell">
                    <a
                      href={task.data_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="data-link"
                    >
                      {task.data_link.length > 50 ? task.data_link.substring(0, 50) + '...' : task.data_link}
                    </a>
                  </td>
                  <td>{task.assignment_count}</td>
                  <td>
                    <div className="status-badges">
                      {task.assignments?.length > 0 ? (
                        <>
                          {task.assignments.filter(a => a.status === 'completed').length > 0 && (
                            <span className="badge completed">
                              {task.assignments.filter(a => a.status === 'completed').length} completed
                            </span>
                          )}
                          {task.assignments.filter(a => a.status === 'in_progress').length > 0 && (
                            <span className="badge in-progress">
                              {task.assignments.filter(a => a.status === 'in_progress').length} in progress
                            </span>
                          )}
                          {task.assignments.filter(a => a.status === 'claimed').length > 0 && (
                            <span className="badge claimed">
                              {task.assignments.filter(a => a.status === 'claimed').length} claimed
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="badge available">Available</span>
                      )}
                    </div>
                  </td>
                  <td>
                    <div className="annotators-list">
                      {task.assignments?.length > 0 ? (
                        task.assignments.map(assignment => (
                          <div key={assignment.id} className="annotator-item">
                            <span className="annotator-email">{assignment.user_email}</span>
                            <span className={`annotator-status ${assignment.status}`}>
                              {assignment.status}
                            </span>
                          </div>
                        ))
                      ) : (
                        <span className="no-annotators">None</span>
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
  )
}

export default AdminAnnotationBatchView

