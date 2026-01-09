import React, { useState } from 'react'
import AdminAnnotationUpload from './AdminAnnotationUpload'
import AdminAnnotationDashboard from './AdminAnnotationDashboard'
import AdminAnnotationBatchView from './AdminAnnotationBatchView'
import './AdminAnnotationView.css'

const AdminAnnotationView = ({ user }) => {
  const [activeView, setActiveView] = useState('dashboard') // 'dashboard', 'upload', 'batch', 'surveys'
  const [selectedBatchId, setSelectedBatchId] = useState(null)

  return (
    <div className="admin-annotation-view">
      <div className="admin-nav-tabs">
        <button
          className={activeView === 'dashboard' ? 'active' : ''}
          onClick={() => {
            setActiveView('dashboard')
            setSelectedBatchId(null)
          }}
        >
          Dashboard
        </button>
        <button
          className={activeView === 'upload' ? 'active' : ''}
          onClick={() => {
            setActiveView('upload')
            setSelectedBatchId(null)
          }}
        >
          Upload CSV
        </button>
        {selectedBatchId && (
          <button
            className={activeView === 'batch' ? 'active' : ''}
            onClick={() => setActiveView('batch')}
          >
            Batch Details
          </button>
        )}
      </div>

      <div className="admin-content">
        {activeView === 'dashboard' && (
          <AdminAnnotationDashboard
            user={user}
            onViewBatch={(batchId) => {
              setSelectedBatchId(batchId)
              setActiveView('batch')
            }}
          />
        )}
        {activeView === 'upload' && (
          <AdminAnnotationUpload
            user={user}
            onUploadSuccess={() => {
              setActiveView('dashboard')
            }}
          />
        )}
        {activeView === 'batch' && selectedBatchId && (
          <AdminAnnotationBatchView
            user={user}
            batchId={selectedBatchId}
            onBack={() => {
              setActiveView('dashboard')
              setSelectedBatchId(null)
            }}
          />
        )}
      </div>
    </div>
  )
}

export default AdminAnnotationView

