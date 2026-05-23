import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { uploadPDF } from '../hooks/api'

export default function FileUpload({ onUploaded }) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)

  const onDrop = useCallback(async (files) => {
    const file = files[0]
    if (!file) return
    if (!file.name.endsWith('.pdf')) {
      toast.error('Only PDF files are supported.')
      return
    }
    setUploading(true)
    setProgress(0)
    try {
      await uploadPDF(file, setProgress)
      toast.success(`"${file.name}" uploaded! Ingestion in progress...`)
      onUploaded?.()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed.')
    } finally {
      setUploading(false)
      setProgress(0)
    }
  }, [onUploaded])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { 'application/pdf': ['.pdf'] }, multiple: false, disabled: uploading,
  })

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors
        ${isDragActive ? 'border-brand bg-brand-light' : 'border-slate-300 hover:border-brand hover:bg-brand-light'}`}
    >
      <input {...getInputProps()} />
      <div className="text-3xl mb-2">📄</div>
      {uploading ? (
        <div>
          <p className="text-sm text-slate-500 mb-2">Uploading… {progress}%</p>
          <div className="w-full bg-slate-200 rounded-full h-1.5">
            <div className="bg-brand h-1.5 rounded-full transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-500">
          {isDragActive ? 'Drop your PDF here' : 'Drag & drop a PDF, or click to browse'}
        </p>
      )}
    </div>
  )
}
