'use client'

import { useState } from 'react'
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
  Package
} from 'lucide-react'

interface TaskStatus {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  message: string
  download_url?: string
  error?: string
}

export default function CollectingPage() {
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [maxVideos, setMaxVideos] = useState(1)
  const [isProcessing, setIsProcessing] = useState(false)
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null)
  const [pollInterval, setPollInterval] = useState<NodeJS.Timeout | null>(null)

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
        headers: { 'Content-Type': 'application/json' },
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

      const interval = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/collecting/status/${taskId}`)
          const statusData = await statusRes.json()
          
          setTaskStatus(statusData)

          if (statusData.status === 'completed' || statusData.status === 'failed') {
            clearInterval(interval)
            setIsProcessing(false)
          }
        } catch (error) {
          console.error('Poll error:', error)
        }
      }, 2000)

      setPollInterval(interval)

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

  const downloadResult = () => {
    if (taskStatus?.download_url) {
      window.location.href = taskStatus.download_url
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <Loader2 className="w-5 h-5 animate-spin text-yellow-400" />
      case 'processing': return <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
      case 'completed': return <CheckCircle className="w-5 h-5 text-green-400" />
      case 'failed': return <XCircle className="w-5 h-5 text-red-400" />
      default: return null
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
                  onChange={(e) => setMaxVideos(parseInt(e.target.value) || 1)}
                  min={1}
                  max={50}
                  className="w-32 px-4 py-3 bg-dark-900 border border-dark-700 rounded-xl text-white focus:border-brand-500 focus:outline-none transition-colors"
                  disabled={isProcessing}
                />
                <p className="mt-1 text-xs text-dark-500">
                  Nhập 1 nếu chỉ xử lý 1 video. Tối đa 50 video cho playlist.
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
                </span>
              </div>
              <span className="text-2xl font-bold text-brand-400">{taskStatus.progress}%</span>
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
                    onClick={downloadResult}
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

            {/* Reset on Error */}
            {taskStatus.status === 'failed' && (
              <button
                onClick={resetForm}
                className="mt-4 px-6 py-3 bg-dark-800 hover:bg-dark-700 text-white rounded-xl font-medium transition-all"
              >
                Thử lại
              </button>
            )}
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

