import React, { useState } from 'react'
import axios from 'axios'
import './AdminAnnotationUpload.css'

const AdminAnnotationUpload = ({ user, onUploadSuccess }) => {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [preview, setPreview] = useState(null)

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0]
    if (!selectedFile) return

    if (!selectedFile.name.endsWith('.csv')) {
      setError('Please select a CSV file')
      return
    }

    setFile(selectedFile)
    setError(null)
    setSuccess(null)

    // Preview first few rows
    const reader = new FileReader()
    reader.onload = (event) => {
      const text = event.target.result
      const lines = text.split('\n').slice(0, 6) // First 5 data rows + header
      setPreview(lines.join('\n'))
    }
    reader.readAsText(selectedFile)
  }

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file')
      return
    }

    setUploading(true)
    setError(null)
    setSuccess(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await axios.post(
        `/api/admin/annotations/upload?user_id=${user.user_id}`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      )

      setSuccess(`Successfully uploaded ${response.data.task_count} tasks! Batch ID: ${response.data.batch_id}`)
      setFile(null)
      setPreview(null)
      
      // Clear file input
      const fileInput = document.querySelector('input[type="file"]')
      if (fileInput) fileInput.value = ''

      // Call success callback after a delay
      setTimeout(() => {
        if (onUploadSuccess) onUploadSuccess()
      }, 2000)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="admin-upload">
      <div className="upload-section">
        <h2>Upload Annotation Tasks CSV</h2>
        <p className="upload-description">
          Upload a CSV file with columns: <code>instance_id</code>, <code>agent_id</code>, <code>data_link</code>
        </p>

        <div className="file-upload-area">
          <input
            type="file"
            accept=".csv"
            onChange={handleFileSelect}
            disabled={uploading}
            id="csv-upload"
          />
          <label htmlFor="csv-upload" className="file-upload-label">
            {file ? file.name : 'Choose CSV File'}
          </label>
        </div>

        {preview && (
          <div className="preview-section">
            <h3>Preview (first 5 rows):</h3>
            <pre className="csv-preview">{preview}</pre>
          </div>
        )}

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {success && (
          <div className="success-message">
            {success}
          </div>
        )}

        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="upload-button"
        >
          {uploading ? 'Uploading...' : 'Upload CSV'}
        </button>
      </div>

      <div className="upload-info">
        <h3>CSV Format Requirements:</h3>
        <ul>
          <li>Required columns: <code>instance_id</code>, <code>agent_id</code>, <code>data_link</code></li>
          <li>All fields must be non-empty</li>
          <li><code>data_link</code> must be a valid URL</li>
          <li>Maximum 10,000 rows per upload</li>
        </ul>
        <h3>Example:</h3>
        <pre className="example-csv">
{`instance_id,agent_id,data_link
example_task,default,http://example.com/task1
astropy__astropy-12907,0ifd,http://example.com/task2`}
        </pre>
      </div>
    </div>
  )
}

export default AdminAnnotationUpload

