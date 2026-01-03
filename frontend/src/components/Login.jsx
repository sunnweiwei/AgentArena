import React, { useState } from 'react'
import axios from 'axios'
import './Login.css'

const Login = ({ onLogin }) => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    
    if (!email || !email.trim()) {
      setError('Please enter a username')
      return
    }

    setLoading(true)
    try {
      const response = await axios.post('/api/auth/login', {
        email,
        password: password || undefined
      })
      onLogin(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>Welcome</h1>
        <p className="login-subtitle">Enter your username to start chatting</p>
        <form onSubmit={handleSubmit} className="login-form">
          <input
            type="text"
            placeholder="Enter username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="email-input"
            disabled={loading}
            autoFocus
          />
          <input
            type="password"
            placeholder="Password (optional)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="password-input"
            disabled={loading}
          />
          {error && <div className="error-message">{error}</div>}
          <button 
            type="submit" 
            className="login-button"
            disabled={loading || !email}
          >
            {loading ? 'Logging in...' : 'Continue'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default Login

