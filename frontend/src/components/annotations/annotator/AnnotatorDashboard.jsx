import React, { useState, useEffect } from 'react'
import axios from 'axios'
import AnnotationTaskCard from './AnnotationTaskCard'
import './AnnotatorDashboard.css'

const AnnotatorDashboard = ({ user }) => {
  const [availableTasks, setAvailableTasks] = useState([])
  const [myTasks, setMyTasks] = useState({ claimed: [], in_progress: [], completed: [] })
  const [myStats, setMyStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filterInstanceId, setFilterInstanceId] = useState('')
  const [filterAgentId, setFilterAgentId] = useState('')

  useEffect(() => {
    loadData()
    // Refresh every 30 seconds
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      setError(null)
      const [availableRes, myTasksRes, statsRes] = await Promise.all([
        axios.get(`/api/annotations/available?user_id=${user.user_id}`),
        axios.get(`/api/annotations/my-tasks?user_id=${user.user_id}`),
        axios.get(`/api/annotations/my-stats?user_id=${user.user_id}`)
      ])
      setAvailableTasks(availableRes.data.tasks || [])
      setMyTasks(myTasksRes.data)
      setMyStats(statsRes.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const handleTaskAction = () => {
    // Reload data after any task action
    loadData()
  }

  const filteredAvailable = availableTasks.filter(task => {
    if (filterInstanceId && !task.instance_id.toLowerCase().includes(filterInstanceId.toLowerCase())) {
      return false
    }
    if (filterAgentId && !task.agent_id.toLowerCase().includes(filterAgentId.toLowerCase())) {
      return false
    }
    return true
  })

  if (loading) {
    return (
      <div className="annotator-dashboard loading">
        <div className="loading-spinner"></div>
        <div>Loading tasks...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="annotator-dashboard error">
        <div className="error-message">{error}</div>
        <button onClick={loadData} className="retry-button">Retry</button>
      </div>
    )
  }

  return (
    <div className="annotator-dashboard">
      {/* My Stats */}
      {myStats && (
        <div className="my-stats-section">
          <div className="stat-item">
            <span className="stat-label">Completed:</span>
            <span className="stat-value">{myStats.completed_count}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">In Progress:</span>
            <span className="stat-value">{myStats.in_progress_count}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Completion Rate:</span>
            <span className="stat-value">{myStats.completion_rate}%</span>
          </div>
        </div>
      )}

      <div className="dashboard-layout">
        {/* Available Tasks Panel */}
        <div className="panel available-panel">
          <div className="panel-header">
            <h2>Available Tasks</h2>
            <span className="task-count">{filteredAvailable.length}</span>
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

          <div className="tasks-list">
            {filteredAvailable.length === 0 ? (
              <div className="empty-state">
                {filterInstanceId || filterAgentId ? 'No tasks match filters' : 'No available tasks'}
              </div>
            ) : (
              filteredAvailable.map(task => (
                <AnnotationTaskCard
                  key={task.id}
                  task={task}
                  user={user}
                  onAction={handleTaskAction}
                />
              ))
            )}
          </div>
        </div>

        {/* My Tasks Panel */}
        <div className="panel my-tasks-panel">
          <div className="panel-header">
            <h2>My Tasks</h2>
          </div>

          <div className="my-tasks-sections">
            {myTasks.in_progress.length > 0 && (
              <div className="task-section">
                <h3 className="section-title">In Progress ({myTasks.in_progress.length})</h3>
                {myTasks.in_progress.map(task => (
                  <AnnotationTaskCard
                    key={task.assignment_id}
                    task={task}
                    user={user}
                    onAction={handleTaskAction}
                  />
                ))}
              </div>
            )}

            {myTasks.claimed.length > 0 && (
              <div className="task-section">
                <h3 className="section-title">Claimed ({myTasks.claimed.length})</h3>
                {myTasks.claimed.map(task => (
                  <AnnotationTaskCard
                    key={task.assignment_id}
                    task={task}
                    user={user}
                    onAction={handleTaskAction}
                  />
                ))}
              </div>
            )}

            {myTasks.completed.length > 0 && (
              <div className="task-section">
                <h3 className="section-title">Completed ({myTasks.completed.length})</h3>
                {myTasks.completed.map(task => (
                  <AnnotationTaskCard
                    key={task.assignment_id}
                    task={task}
                    user={user}
                    onAction={handleTaskAction}
                  />
                ))}
              </div>
            )}

            {myTasks.in_progress.length === 0 && 
             myTasks.claimed.length === 0 && 
             myTasks.completed.length === 0 && (
              <div className="empty-state">No tasks claimed yet</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default AnnotatorDashboard

