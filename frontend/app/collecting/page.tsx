'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { 
  Zap, 
  ArrowLeft, 
  Download, 
  Play, 
  CheckCircle, 
  XCircle,
  Loader2,
  FileVideo,
  Scissors,
  FileText,
  Package,
  History,
  Clock,
  Trash2,
  Upload,
  FolderUp
} from 'lucide-react'

interface TaskStatus {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  message: string
  created_at?: string
  download_url?: string
  error?: string
}

interface UserTasksResponse {
  tasks: TaskStatus[]
  active_task: TaskStatus | null
}

export default function CollectingPage() {
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [maxVideos, setMaxVideos] = useState(1)
  const [isProcessing, setIsProcessing] = useState(false)
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null)
  const [pollInterval, setPollInterval] = useState<NodeJS.Timeout | null>(null)
  const [taskHistory, setTaskHistory] = useState<TaskStatus[]>([])
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [isLoadingTasks, setIsLoadingTasks] = useState(true)
  const [userRole, setUserRole] = useState<string>('')
  
  // Upload states
  const [isUploading, setIsUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<{imported: number, skipped: number, signer_videos?: number, errors: string[], dataset_name?: string} | null>(null)
  const [selectedSplit, setSelectedSplit] = useState('train')
  const [datasetName, setDatasetName] = useState('')

  // Get auth token from localStorage
  const getAuthHeaders = useCallback((): Record<string, string> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
    return token ? { 'Authorization': `Bearer ${token}` } : {}
  }, [])

  // Check if user is logged in and load their tasks
  const loadUserTasks = useCallback(async () => {
    const token = localStorage.getItem('access_token')
    const userStr = localStorage.getItem('user')
    
    if (!token) {
      setIsLoggedIn(false)
      setIsLoadingTasks(false)
      return
    }

    setIsLoggedIn(true)
    
    // Get user role from localStorage
    if (userStr) {
      try {
        const user = JSON.parse(userStr)
        setUserRole(user.role || 'annotator')
      } catch {
        setUserRole('annotator')
      }
    }

    try {
      const response = await fetch('/api/collecting/my-tasks', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        const data: UserTasksResponse = await response.json()
        setTaskHistory(data.tasks)

        // If there's an active task, resume tracking
        if (data.active_task) {
          setTaskStatus(data.active_task)
          setIsProcessing(true)
          startPolling(data.active_task.task_id)
        }
      } else if (response.status === 401) {
        // Token expired, clear it
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        setIsLoggedIn(false)
        setUserRole('')
      }
    } catch (error) {
      console.error('Error loading tasks:', error)
    } finally {
      setIsLoadingTasks(false)
    }
  }, [])

  // Start polling for task status
  const startPolling = useCallback((taskId: string) => {
    // Clear any existing interval
    if (pollInterval) {
      clearInterval(pollInterval)
    }

    const interval = setInterval(async () => {
      try {
        const statusRes = await fetch(`/api/collecting/status/${taskId}`)
        const statusData = await statusRes.json()
        
        setTaskStatus(statusData)

        if (statusData.status === 'completed' || statusData.status === 'failed' || statusData.status === 'cancelled') {
          clearInterval(interval)
          setIsProcessing(false)
          // Reload task history
          loadUserTasks()
        }
      } catch (error) {
        console.error('Poll error:', error)
      }
    }, 2000)

    setPollInterval(interval)
  }, [pollInterval, loadUserTasks])

  // Load tasks on mount
  useEffect(() => {
    loadUserTasks()
    
    // Cleanup on unmount
    return () => {
      if (pollInterval) {
        clearInterval(pollInterval)
      }
    }
  }, [])

  const startProcessing = async () => {
    if (!youtubeUrl.trim()) {
      alert('Vui lòng nhập YouTube URL')
      return
    }

    if (!youtubeUrl.includes('youtube.com') && !youtubeUrl.includes('youtu.be')) {
      alert('URL không hợp lệ. Vui lòng nhập link YouTube.')
      return
    }

    setIsProcessing(true)
    setTaskStatus(null)

    try {
      const response = await fetch('/api/collecting/process', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify({ 
          youtube_url: youtubeUrl, 
          max_videos: maxVideos 
        })
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Lỗi không xác định')
      }

      // Start polling for status
      const taskId = data.task_id
      setTaskStatus({
        task_id: taskId,
        status: 'pending',
        progress: 0,
        message: 'Đang khởi tạo...'
      })

      startPolling(taskId)

    } catch (error: any) {
      alert(error.message)
      setIsProcessing(false)
    }
  }

  const resetForm = () => {
    if (pollInterval) {
      clearInterval(pollInterval)
    }
    setYoutubeUrl('')
    setMaxVideos(1)
    setTaskStatus(null)
    setIsProcessing(false)
  }

  const downloadResult = (downloadUrl?: string) => {
    const url = downloadUrl || taskStatus?.download_url
    if (url) {
      window.location.href = url
    }
  }

  const deleteTask = async (taskId: string) => {
    if (!confirm('Bạn có chắc muốn xóa task này?')) return

    try {
      const response = await fetch(`/api/collecting/task/${taskId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      })

      if (response.ok) {
        setTaskHistory(prev => prev.filter(t => t.task_id !== taskId))
        if (taskStatus?.task_id === taskId) {
          resetForm()
        }
      }
    } catch (error) {
      console.error('Error deleting task:', error)
    }
  }

  const cancelTask = async (taskId?: string) => {
    const id = taskId || taskStatus?.task_id
    if (!id) return

    if (!confirm('Bạn có chắc muốn hủy task đang chạy?')) return

    try {
      const response = await fetch(`/api/collecting/cancel/${id}`, {
        method: 'POST',
        headers: getAuthHeaders()
      })

      if (response.ok) {
        // Stop polling
        if (pollInterval) {
          clearInterval(pollInterval)
          setPollInterval(null)
        }
        
        // Update local state
        setTaskStatus(prev => prev ? { ...prev, status: 'cancelled', message: 'Task đã bị hủy' } : null)
        setIsProcessing(false)
        
        // Reload task history
        loadUserTasks()
      } else {
        const data = await response.json()
        alert(data.detail || 'Không thể hủy task')
      }
    } catch (error) {
      console.error('Error cancelling task:', error)
      alert('Lỗi khi hủy task')
    }
  }

  // Upload ZIP to labeling (Admin only)
  const uploadZipToLabeling = async (file: File) => {
    if (!datasetName.trim()) {
      alert('Vui lòng nhập tên Dataset')
      return
    }
    
    setIsUploading(true)
    setUploadResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(
        `/api/labeling/upload-zip?dataset_name=${encodeURIComponent(datasetName)}&split=${selectedSplit}`, 
        {
          method: 'POST',
          headers: getAuthHeaders(),
          body: formData
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Lỗi upload')
      }

      setUploadResult({
        imported: data.imported,
        skipped: data.skipped,
        errors: data.errors || [],
        dataset_name: data.dataset_name
      })
      
      // Clear dataset name after success
      setDatasetName('')

    } catch (error: any) {
      alert(error.message || 'Lỗi upload file')
    } finally {
      setIsUploading(false)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (!file.name.endsWith('.zip')) {
        alert('Vui lòng chọn file ZIP')
        return
      }
      if (!datasetName.trim()) {
        alert('Vui lòng nhập tên Dataset trước')
        e.target.value = ''
        return
      }
      uploadZipToLabeling(file)
    }
    // Reset input
    e.target.value = ''
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <Loader2 className="w-5 h-5 animate-spin text-yellow-400" />
      case 'processing': return <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
      case 'completed': return <CheckCircle className="w-5 h-5 text-green-400" />
      case 'failed': return <XCircle className="w-5 h-5 text-red-400" />
      case 'cancelled': return <XCircle className="w-5 h-5 text-orange-400" />
      default: return null
    }
  }

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      case 'processing': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      case 'completed': return 'bg-green-500/20 text-green-400 border-green-500/30'
      case 'failed': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'cancelled': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
      default: return 'bg-dark-700 text-dark-400'
    }
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return ''
    try {
      return new Date(dateStr).toLocaleString('vi-VN')
    } catch {
      return dateStr
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0b]">
      {/* Header */}
      <header className="border-b border-dark-800 bg-[#0a0a0b]/90 backdrop-blur-xl">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/" className="p-2 hover:bg-dark-800 rounded-lg transition-colors">
                <ArrowLeft className="w-5 h-5 text-dark-400" />
              </Link>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
                  <FileVideo className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-white">Thu thập Video</h1>
                  <p className="text-xs text-dark-400">Tải và xử lý video từ YouTube</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 py-10">
        {/* Active Task Notification */}
        {isLoggedIn && taskStatus && (taskStatus.status === 'pending' || taskStatus.status === 'processing') && (
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4 mb-6 flex items-center gap-3">
            <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
            <span className="text-blue-300">
              Đang có task đang chạy. Tiến trình sẽ được giữ nguyên nếu bạn thoát trang.
            </span>
          </div>
        )}

        {/* Input Card */}
        <div className="bg-dark-950 border border-dark-800 rounded-2xl p-8 mb-8">
          <div className="space-y-6">
            {/* YouTube URL */}
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                YouTube Video / Playlist URL
              </label>
              <input
                type="text"
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=... hoặc playlist URL"
                className="w-full px-4 py-3 bg-dark-900 border border-dark-700 rounded-xl text-white placeholder-dark-500 focus:border-brand-500 focus:outline-none transition-colors"
                disabled={isProcessing}
              />
            </div>

            {/* Max Videos */}
            <div className="flex items-end gap-4">
              <div className="flex-1">
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  Số video xử lý (với playlist)
                </label>
                <input
                  type="number"
                  value={maxVideos}
                  onChange={(e) => {
                    const val = parseInt(e.target.value)
                    setMaxVideos(val > 0 ? val : 1)
                  }}
                  min={1}
                  className="w-40 px-4 py-3 bg-dark-900 border border-dark-700 rounded-xl text-white focus:border-brand-500 focus:outline-none transition-colors text-center"
                  disabled={isProcessing}
                />
                <p className="mt-1 text-xs text-dark-500">
                  Nhập số video muốn xử lý từ playlist. Nhập 1 nếu chỉ xử lý 1 video.
                </p>
              </div>

              <button
                onClick={startProcessing}
                disabled={isProcessing}
                className="px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white rounded-xl font-medium flex items-center gap-2 shadow-lg shadow-blue-500/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Đang xử lý...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    Xử lý
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Progress Section */}
        {taskStatus && (
          <div className="bg-dark-950 border border-dark-800 rounded-2xl p-8 mb-8">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                {getStatusIcon(taskStatus.status)}
                <span className="font-medium text-white capitalize">
                  {taskStatus.status === 'pending' && 'Đang chờ...'}
                  {taskStatus.status === 'processing' && 'Đang xử lý...'}
                  {taskStatus.status === 'completed' && 'Hoàn tất!'}
                  {taskStatus.status === 'failed' && 'Thất bại'}
                  {taskStatus.status === 'cancelled' && 'Đã hủy'}
                </span>
              </div>
              <div className="flex items-center gap-3">
                {/* Cancel button for running tasks */}
                {(taskStatus.status === 'pending' || taskStatus.status === 'processing') && (
                  <button
                    onClick={() => cancelTask()}
                    className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 rounded-lg text-sm font-medium transition-colors"
                  >
                    Hủy
                  </button>
                )}
                <span className="text-2xl font-bold text-brand-400">{taskStatus.progress}%</span>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="h-3 bg-dark-800 rounded-full overflow-hidden mb-4">
              <div 
                className="h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full transition-all duration-300"
                style={{ width: `${taskStatus.progress}%` }}
              />
            </div>

            <p className="text-dark-400 text-sm">{taskStatus.message}</p>

            {/* Error */}
            {taskStatus.status === 'failed' && taskStatus.error && (
              <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
                <p className="text-red-400 text-sm">{taskStatus.error}</p>
              </div>
            )}

            {/* Cancelled notice */}
            {taskStatus.status === 'cancelled' && (
              <div className="mt-4 p-4 bg-orange-500/10 border border-orange-500/30 rounded-xl">
                <p className="text-orange-400 text-sm">Task đã bị hủy</p>
              </div>
            )}

            {/* Download Button */}
            {taskStatus.status === 'completed' && taskStatus.download_url && (
              <div className="mt-6 p-6 bg-green-500/10 border border-green-500/30 rounded-xl text-center">
                <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-white mb-2">Xử lý hoàn tất!</h3>
                <p className="text-dark-400 text-sm mb-4">
                  File ZIP chứa các video clip và metadata đã sẵn sàng.
                </p>
                <div className="flex items-center justify-center gap-3">
                  <button
                    onClick={() => downloadResult()}
                    className="px-6 py-3 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white rounded-xl font-medium flex items-center gap-2 shadow-lg shadow-green-500/25 transition-all"
                  >
                    <Download className="w-5 h-5" />
                    Tải xuống ZIP
                  </button>
                  <button
                    onClick={resetForm}
                    className="px-6 py-3 bg-dark-800 hover:bg-dark-700 text-white rounded-xl font-medium transition-all"
                  >
                    Xử lý video khác
                  </button>
                </div>
              </div>
            )}

            {/* Reset on Error or Cancelled */}
            {(taskStatus.status === 'failed' || taskStatus.status === 'cancelled') && (
              <button
                onClick={resetForm}
                className="mt-4 px-6 py-3 bg-dark-800 hover:bg-dark-700 text-white rounded-xl font-medium transition-all"
              >
                Thử lại
              </button>
            )}
          </div>
        )}

        {/* Task History (only for logged in users) */}
        {isLoggedIn && taskHistory.length > 0 && (
          <div className="bg-dark-950 border border-dark-800 rounded-2xl p-6 mb-8">
            <div className="flex items-center gap-2 mb-4">
              <History className="w-5 h-5 text-dark-400" />
              <h3 className="text-lg font-semibold text-white">Lịch sử xử lý</h3>
            </div>
            
            <div className="space-y-3">
              {taskHistory.slice(0, 10).map((task) => (
                <div 
                  key={task.task_id}
                  className="flex items-center justify-between p-4 bg-dark-900 rounded-xl hover:bg-dark-800 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {getStatusIcon(task.status)}
                    <div>
                      <p className="text-sm text-white font-medium">
                        Task {task.task_id.slice(0, 8)}...
                      </p>
                      <div className="flex items-center gap-2 text-xs text-dark-500">
                        <Clock className="w-3 h-3" />
                        {formatDate(task.created_at)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 text-xs rounded-lg border ${getStatusBadgeColor(task.status)}`}>
                      {task.status === 'completed' && 'Hoàn tất'}
                      {task.status === 'failed' && 'Thất bại'}
                      {task.status === 'processing' && `${task.progress}%`}
                      {task.status === 'pending' && 'Đang chờ'}
                      {task.status === 'cancelled' && 'Đã hủy'}
                    </span>

                    {task.status === 'completed' && task.download_url && (
                      <button
                        onClick={() => downloadResult(task.download_url)}
                        className="p-2 hover:bg-dark-700 rounded-lg transition-colors"
                        title="Tải xuống"
                      >
                        <Download className="w-4 h-4 text-green-400" />
                      </button>
                    )}

                    {(task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') && (
                      <button
                        onClick={() => deleteTask(task.task_id)}
                        className="p-2 hover:bg-dark-700 rounded-lg transition-colors"
                        title="Xóa"
                      >
                        <Trash2 className="w-4 h-4 text-red-400" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Login reminder */}
        {!isLoggedIn && !isLoadingTasks && (
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 mb-8 text-center">
            <p className="text-yellow-300 text-sm">
              💡 <Link href="/login" className="underline hover:text-yellow-200">Đăng nhập</Link> để lưu lịch sử và theo dõi tiến trình khi quay lại.
            </p>
          </div>
        )}

        {/* Upload ZIP to Labeling - Admin Only */}
        {isLoggedIn && userRole === 'admin' && (
          <div className="bg-dark-950 border border-dark-800 rounded-2xl p-6 mb-8">
            <div className="flex items-center gap-3 mb-4">
              <FolderUp className="w-6 h-6 text-brand-400" />
              <h3 className="text-lg font-semibold text-white">Import vào Gán nhãn</h3>
              <span className="px-2 py-1 bg-brand-500/20 text-brand-400 text-xs rounded-lg">Admin</span>
            </div>
            
            <p className="text-dark-400 text-sm mb-4">
              Tải file ZIP (đã tải về từ task hoàn tất) để tạo Dataset mới trong trang Gán nhãn.
            </p>

            <div className="flex flex-wrap items-end gap-4">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  Tên Dataset <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  placeholder="VD: VTV_News_2024"
                  className="w-full px-4 py-2 bg-dark-900 border border-dark-700 rounded-lg text-white placeholder-dark-500 focus:border-brand-500 focus:outline-none"
                  disabled={isUploading}
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  Phân loại (Split)
                </label>
                <select
                  value={selectedSplit}
                  onChange={(e) => setSelectedSplit(e.target.value)}
                  className="px-4 py-2 bg-dark-900 border border-dark-700 rounded-lg text-white focus:border-brand-500 focus:outline-none"
                  disabled={isUploading}
                >
                  <option value="train">Train</option>
                  <option value="val">Validation</option>
                  <option value="test">Test</option>
                </select>
              </div>

              <label className="cursor-pointer">
                <input
                  type="file"
                  accept=".zip"
                  onChange={handleFileSelect}
                  className="hidden"
                  disabled={isUploading || !datasetName.trim()}
                />
                <div className={`px-6 py-2 rounded-xl font-medium flex items-center gap-2 transition-all ${
                  isUploading || !datasetName.trim()
                    ? 'bg-dark-700 text-dark-400 cursor-not-allowed' 
                    : 'bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 text-white shadow-lg shadow-brand-500/25'
                }`}>
                  {isUploading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Đang upload...
                    </>
                  ) : (
                    <>
                      <Upload className="w-5 h-5" />
                      Chọn file ZIP
                    </>
                  )}
                </div>
              </label>
            </div>

            {/* Upload Result */}
            {uploadResult && (
              <div className="mt-4 p-4 bg-green-500/10 border border-green-500/30 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-5 h-5 text-green-400" />
                  <span className="font-medium text-green-400">Import thành công!</span>
                </div>
                <div className="text-sm text-dark-300 space-y-1">
                  {uploadResult.dataset_name && (
                    <p>📁 Dataset: <span className="text-brand-400 font-medium">{uploadResult.dataset_name}</span></p>
                  )}
                  <p>✓ Đã import: <span className="text-green-400 font-medium">{uploadResult.imported}</span> segments</p>
                  {uploadResult.signer_videos !== undefined && uploadResult.signer_videos > 0 && (
                    <p>✓ Signer videos: <span className="text-blue-400 font-medium">{uploadResult.signer_videos}</span> videos</p>
                  )}
                  {uploadResult.skipped > 0 && (
                    <p>○ Bỏ qua (đã tồn tại): <span className="text-yellow-400">{uploadResult.skipped}</span></p>
                  )}
                  {uploadResult.errors.length > 0 && (
                    <div className="mt-2">
                      <p className="text-red-400">Lỗi:</p>
                      {uploadResult.errors.map((err, i) => (
                        <p key={i} className="text-red-300 text-xs">• {err}</p>
                      ))}
                    </div>
                  )}
                </div>
                <Link 
                  href="/labeling" 
                  className="inline-flex items-center gap-2 mt-3 text-brand-400 hover:text-brand-300 text-sm"
                >
                  Đi đến trang Gán nhãn →
                </Link>
              </div>
            )}
          </div>
        )}
        
        {/* Notice for non-admin */}
        {isLoggedIn && userRole === 'annotator' && (
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4 mb-8 text-center">
            <p className="text-blue-300 text-sm">
              💡 Bạn là Annotator. Vui lòng vào <Link href="/labeling" className="underline hover:text-blue-200">trang Gán nhãn</Link> để bắt đầu công việc.
            </p>
          </div>
        )}

        {/* Features */}
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-dark-950 border border-dark-800 rounded-xl p-5 text-center">
            <Download className="w-8 h-8 text-blue-400 mx-auto mb-3" />
            <h4 className="font-medium text-white mb-1">Tải video</h4>
            <p className="text-xs text-dark-500">Từ YouTube</p>
          </div>
          <div className="bg-dark-950 border border-dark-800 rounded-xl p-5 text-center">
            <Scissors className="w-8 h-8 text-purple-400 mx-auto mb-3" />
            <h4 className="font-medium text-white mb-1">Crop signer</h4>
            <p className="text-xs text-dark-500">Cắt vùng ký hiệu</p>
          </div>
          <div className="bg-dark-950 border border-dark-800 rounded-xl p-5 text-center">
            <FileText className="w-8 h-8 text-green-400 mx-auto mb-3" />
            <h4 className="font-medium text-white mb-1">Transcribe</h4>
            <p className="text-xs text-dark-500">WhisperX AI</p>
          </div>
          <div className="bg-dark-950 border border-dark-800 rounded-xl p-5 text-center">
            <Package className="w-8 h-8 text-orange-400 mx-auto mb-3" />
            <h4 className="font-medium text-white mb-1">Split & ZIP</h4>
            <p className="text-xs text-dark-500">Chia thành clips</p>
          </div>
        </div>
      </main>
    </div>
  )
}
