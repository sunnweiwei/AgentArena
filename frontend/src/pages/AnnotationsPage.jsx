import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useTheme } from '../contexts/ThemeContext'
import AdminAnnotationView from '../components/annotations/admin/AdminAnnotationView'
import AnnotatorDashboard from '../components/annotations/annotator/AnnotatorDashboard'
import './AnnotationsPage.css'

const AnnotationsPage = ({ user, onLogout }) => {
  const { theme } = useTheme()
  const [loading, setLoading] = useState(true)
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    if (!user) {
      // Redirect to home if not logged in
      window.location.href = '/'
      return
    }

    // Check if user is admin
    // In Vite, use import.meta.env with VITE_ prefix
    // Support both VITE_ADMIN_EMAILS and VITE_REACT_APP_ADMIN_EMAILS for backward compatibility
    const adminEmails = (import.meta.env.VITE_ADMIN_EMAILS || import.meta.env.VITE_REACT_APP_ADMIN_EMAILS || '').split(',').map(e => e.trim()).filter(Boolean)
    const userIsAdmin = adminEmails.includes(user.email?.trim())
    setIsAdmin(userIsAdmin)
    setLoading(false)
  }, [user])

  if (loading) {
    return (
      <div className="annotations-page loading">
        <div className="loading-spinner"></div>
        <div>Loading...</div>
      </div>
    )
  }

  if (!user) {
    return null // Will redirect
  }

  return (
    <div className={`annotations-page theme-${theme}`}>
      <div className="annotations-header">
        <h1>Annotation System</h1>
        <button onClick={() => window.location.href = '/'} className="back-button">
          ← Back to Chat
        </button>
      </div>
      {isAdmin ? (
        <AdminAnnotationView user={user} />
      ) : (
        <AnnotatorDashboard user={user} />
      )}
    </div>
  )
}

export default AnnotationsPage

