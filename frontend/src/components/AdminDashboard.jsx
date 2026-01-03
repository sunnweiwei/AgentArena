import React from 'react'
import './AdminDashboard.css'

const AdminDashboard = ({ stats }) => {
  if (!stats) {
    return (
      <div className="admin-dashboard loading">
        <div className="loading-spinner"></div>
        <div>Loading statistics...</div>
      </div>
    )
  }

  const { summary, hourly_stats, user_stats } = stats

  const metrics = [
    { key: 'new_chats', label: 'New Chats', color: '#4f46e5' },
    { key: 'new_surveys', label: 'New Surveys', color: '#10b981' },
    { key: 'active_users', label: 'Active Users', color: '#f59e0b' },
    { key: 'messages', label: 'Messages', color: '#8b5cf6' }
  ]

  const getMaxValue = (metric) => {
    return Math.max(...hourly_stats.map(h => h[metric] || 0), 1)
  }

  const renderChart = (metric) => {
    const maxValue = getMaxValue(metric.key)
    const total = hourly_stats.reduce((sum, h) => sum + (h[metric.key] || 0), 0)

    return (
      <div key={metric.key} className="chart-box">
        <div className="chart-box-header">
          <h3>{metric.label}</h3>
          <div className="chart-total">Total: <strong>{total}</strong></div>
        </div>
        <div className="hourly-chart">
          {hourly_stats.map((hour, index) => {
            const value = hour[metric.key] || 0
            const height = value > 0 ? Math.max((value / maxValue) * 100, 5) : 0

            return (
              <div key={index} className="hour-bar">
                <div className="bar-container">
                  {value > 0 && (
                    <div 
                      className="bar-fill"
                      style={{ 
                        height: `${height}%`,
                        backgroundColor: metric.color
                      }}
                      title={`${value} ${metric.label}`}
                    >
                      <span className="bar-value">{value}</span>
                    </div>
                  )}
                </div>
                <div className="hour-label">
                  {new Date(hour.hour).toLocaleString('en-US', { 
                    hour: 'numeric', 
                    hour12: false,
                    timeZone: 'America/New_York'
                  }).replace(':00', '')}h
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="admin-dashboard">
      <div className="dashboard-header">
        <h1>Admin Dashboard</h1>
        <div className="last-updated">Last updated: {new Date().toLocaleTimeString()}</div>
      </div>

      {/* Summary Cards */}
      <div className="summary-grid">
        <div className="stat-card">
          <div className="stat-content">
            <div className="stat-label">Active Users (1h)</div>
            <div className="stat-value">{summary.active_users}</div>
            <div className="stat-sublabel">of {summary.total_users} total</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-content">
            <div className="stat-label">Total Chats</div>
            <div className="stat-value">{summary.total_chats}</div>
            <div className="stat-sublabel">{summary.total_users} users</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-content">
            <div className="stat-label">Surveys</div>
            <div className="stat-value">{summary.chats_with_survey}</div>
            <div className="stat-sublabel">submitted</div>
          </div>
        </div>
      </div>

      {/* 4 Separate Hourly Charts */}
      <div className="charts-grid">
        {metrics.map(metric => renderChart(metric))}
      </div>

      {/* User Statistics Table */}
      <div className="dashboard-section">
        <h2>User Statistics</h2>
        <div className="user-stats-table">
          <table>
            <thead>
              <tr>
                <th>User</th>
                <th>Total Chats</th>
                <th>Total Surveys</th>
                <th colSpan="2">Last 1h</th>
                <th colSpan="2">Last 24h</th>
              </tr>
              <tr className="sub-header">
                <th></th>
                <th></th>
                <th></th>
                <th>Chats</th>
                <th>Surveys</th>
                <th>Chats</th>
                <th>Surveys</th>
              </tr>
            </thead>
            <tbody>
              {user_stats.map((user) => (
                <tr key={user.user_id}>
                  <td className="user-email">{user.user_email}</td>
                  <td>{user.total_chats}</td>
                  <td>{user.surveys_submitted}</td>
                  <td>
                    {user.recent_chats_1h > 0 && (
                      <span className="activity-badge">{user.recent_chats_1h}</span>
                    )}
                  </td>
                  <td>
                    {user.recent_surveys_1h > 0 && (
                      <span className="activity-badge">{user.recent_surveys_1h}</span>
                    )}
                  </td>
                  <td>
                    {user.recent_chats_24h > 0 && (
                      <span className="activity-badge">{user.recent_chats_24h}</span>
                    )}
                  </td>
                  <td>
                    {user.recent_surveys_24h > 0 && (
                      <span className="activity-badge">{user.recent_surveys_24h}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {user_stats.length === 0 && (
            <div className="empty-state">No user activity yet</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AdminDashboard
