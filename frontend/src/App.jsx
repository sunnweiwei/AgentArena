import React, { useState, useEffect } from 'react'
import { ThemeProvider } from './contexts/ThemeContext'
import ChatInterface from './components/ChatInterface'
import './App.css'

function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    try {
      // Check if user is already logged in (stored in localStorage)
      const savedUser = localStorage.getItem('user')
      if (savedUser) {
        try {
          setUser(JSON.parse(savedUser))
        } catch (e) {
          console.error('Error parsing saved user:', e)
          localStorage.removeItem('user')
        }
      }
    } catch (e) {
      console.error('Error in App initialization:', e)
    } finally {
      setLoading(false)
    }
    
    // Safety timeout - force loading to false after 5 seconds
    const timeout = setTimeout(() => {
      setLoading(false)
    }, 5000)
    
    return () => clearTimeout(timeout)
  }, [])

  const handleLogin = (userData) => {
    setUser(userData)
    localStorage.setItem('user', JSON.stringify(userData))
  }

  const handleLogout = () => {
    setUser(null)
    localStorage.removeItem('user')
  }

  if (loading) {
    return <div className="loading">Loading...</div>
  }

  return (
    <ThemeProvider>
      <div className="app">
        <ChatInterface user={user} onLogout={handleLogout} onLogin={handleLogin} />
      </div>
    </ThemeProvider>
  )
}

export default App

