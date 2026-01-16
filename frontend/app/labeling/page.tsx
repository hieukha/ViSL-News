'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { 
  Play, 
  Pause, 
  SkipBack, 
  SkipForward, 
  Save, 
  CheckCircle, 
  ChevronLeft,
  ChevronRight,
  Clock,
  FileText,
  RefreshCw,
  Volume2,
  VolumeX,
  AlertCircle,
  ArrowLeft,
  Tag,
  Check,
  X,
  History,
  User,
  Database,
  MessageSquare,
  AlertTriangle,
  Shield,
  Trash2
} from 'lucide-react'

interface Dataset {
  id: number
  name: string
  description: string | null
  segment_count: number
  raw_count: number
  labeled_count: number
  needs_fix_count: number
  reviewed_count: number
}

interface Segment {
  id: number
  clip_name: string
  clip_path: string
  video_source: string
  start_time: number
  end_time: number
  duration: number
  asr_text: string
  status: string
  split: string
  review_comment?: string
  latest_annotation?: Annotation
}

interface Annotation {
  id: number
  final_text: string
  gloss_sequence: string
  start_time: number
  end_time: number
  comment: string
  version: number
  expert_id?: number
  expert_name?: string
  created_at: string
}

interface Stats {
  total_segments: number
  raw_count: number
  in_progress_count: number
  labeled_count: number
  needs_fix_count: number
  reviewed_count: number
  train_count: number
  val_count: number
  test_count: number
  total_annotations: number
  avg_duration: number | null
}

const API_BASE = '/backend-api'

export default function LabelingPage() {
  // Auth State
  const [userRole, setUserRole] = useState<string>('annotator')
  const [userName, setUserName] = useState<string>('')
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  
  // Dataset State
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedDataset, setSelectedDataset] = useState<number | null>(null)
  
  // Segments State
  const [segments, setSegments] = useState<Segment[]>([])
  const [currentSegment, setCurrentSegment] = useState<Segment | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null)
  
  // Video player state
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [videoDuration, setVideoDuration] = useState(0)
  const [isMuted, setIsMuted] = useState(false)
  const [videoRef, setVideoRef] = useState<HTMLVideoElement | null>(null)
  const [playbackRate, setPlaybackRate] = useState(1)
  
  // Form state
  const [finalText, setFinalText] = useState('')
  const [glossSequence, setGlossSequence] = useState('')
  const [startTime, setStartTime] = useState(0)
  const [endTime, setEndTime] = useState(0)
  const [comment, setComment] = useState('')
  
  // Admin review state
  const [reviewComment, setReviewComment] = useState('')
  const [showRejectModal, setShowRejectModal] = useState(false)
  
  // Delete dataset state
  const [showDeleteDatasetModal, setShowDeleteDatasetModal] = useState(false)
  const [deleteWithFiles, setDeleteWithFiles] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  
  // Annotation history
  const [annotationHistory, setAnnotationHistory] = useState<Annotation[]>([])
  const [showHistory, setShowHistory] = useState(false)
  
  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>('raw')
  const [splitFilter, setSplitFilter] = useState<string>('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  // Check auth on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    const user = localStorage.getItem('user')
    if (token && user) {
      try {
        const userData = JSON.parse(user)
        setIsLoggedIn(true)
        setUserRole(userData.role || 'annotator')
        setUserName(userData.full_name || userData.email || '')
      } catch {
        setIsLoggedIn(false)
      }
    }
  }, [])

  // Fetch datasets on mount
  useEffect(() => {
    fetchDatasets()
  }, [])

  // Fetch segments when dataset/filters change
  useEffect(() => {
    fetchSegments()
    fetchStats()
  }, [page, statusFilter, splitFilter, selectedDataset])

  // Fetch annotation history when segment changes
  useEffect(() => {
    if (currentSegment) {
      fetchAnnotationHistory(currentSegment.id)
    }
  }, [currentSegment?.id])

  const fetchDatasets = async () => {
    try {
      const res = await fetch(`${API_BASE}/datasets`)
      if (res.ok) {
        const data = await res.json()
        setDatasets(data)
      }
    } catch (error) {
      console.error('Error fetching datasets:', error)
    }
  }

  const fetchSegments = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: page.toString(), per_page: '20' })
      if (statusFilter) params.append('status', statusFilter)
      if (splitFilter) params.append('split', splitFilter)
      if (selectedDataset) params.append('dataset_id', selectedDataset.toString())
      
      const res = await fetch(`${API_BASE}/segments?${params}`)
      
      if (!res.ok) {
        throw new Error('Backend không phản hồi')
      }
      
      const data = await res.json()
      
      const segmentList = data.segments || []
      setSegments(segmentList)
      setTotalPages(Math.ceil((data.total || 0) / (data.per_page || 20)))
      
      if (segmentList.length > 0 && !currentSegment) {
        selectSegment(segmentList[0], 0)
      }
    } catch (error) {
      console.error('Error fetching segments:', error)
      setSegments([])
      showToast('Backend chưa chạy - Vui lòng khởi động backend', 'error')
    }
    setLoading(false)
  }

  const fetchStats = async () => {
    try {
      const params = new URLSearchParams()
      if (selectedDataset) params.append('dataset_id', selectedDataset.toString())
      const res = await fetch(`${API_BASE}/stats?${params}`)
      const data = await res.json()
      setStats(data)
    } catch (error) {
      console.error('Error fetching stats:', error)
    }
  }

  const fetchAnnotationHistory = async (segmentId: number) => {
    try {
      const res = await fetch(`${API_BASE}/annotations/${segmentId}`)
      if (res.ok) {
        const data = await res.json()
        setAnnotationHistory(data)
      }
    } catch (error) {
      console.error('Error fetching annotation history:', error)
    }
  }

  const selectSegment = (segment: Segment, index: number) => {
    // Determine the target start time for this segment
    const targetStartTime = segment.latest_annotation?.start_time || segment.start_time
    
    // Check if video source changed (need to wait for video load)
    const videoSourceChanged = !currentSegment || currentSegment.video_source !== segment.video_source
    
    setCurrentSegment(segment)
    setCurrentIndex(index)
    
    if (segment.latest_annotation) {
      const ann = segment.latest_annotation
      setFinalText(ann.final_text || segment.asr_text || '')
      setGlossSequence(ann.gloss_sequence || '')
      setStartTime(ann.start_time || segment.start_time)
      setEndTime(ann.end_time || segment.end_time)
      setComment(ann.comment || '')
    } else {
      setFinalText(segment.asr_text || '')
      setGlossSequence('')
      setStartTime(segment.start_time)
      setEndTime(segment.end_time)
      setComment('')
    }
    
    // Reset review comment
    setReviewComment('')
    setIsPlaying(false)
    setCurrentTime(targetStartTime)
    
    // Seek video to target start time
    if (videoSourceChanged) {
      // Video source changed - the seek will happen in handleLoadedMetadata via pendingSeekTime
      // Store the target time in a data attribute on the video element as a workaround
      if (videoRef) {
        videoRef.dataset.pendingSeek = targetStartTime.toString()
      }
    } else {
      // Same video source - seek immediately (video is already loaded)
      if (videoRef && videoRef.readyState >= 1) {
        videoRef.currentTime = targetStartTime
      } else {
        // Video not ready yet, try after a short delay
        setTimeout(() => {
          if (videoRef) {
            videoRef.currentTime = targetStartTime
          }
        }, 50)
      }
    }
  }

  const goToNext = () => {
    if (currentIndex < segments.length - 1) {
      selectSegment(segments[currentIndex + 1], currentIndex + 1)
    } else if (page < totalPages) {
      setPage(page + 1)
      setCurrentIndex(0)
    }
  }

  const goToPrevious = () => {
    if (currentIndex > 0) {
      selectSegment(segments[currentIndex - 1], currentIndex - 1)
    } else if (page > 1) {
      setPage(page - 1)
      setCurrentIndex(19)
    }
  }

  const resetToOriginal = () => {
    if (!currentSegment) return
    
    setFinalText(currentSegment.asr_text || '')
    setGlossSequence('')
    setStartTime(currentSegment.start_time)
    setEndTime(currentSegment.end_time)
    setComment('')
    
    seekTo(currentSegment.start_time)
    showToast('Đã reset về giá trị ban đầu', 'success')
  }

  // Annotator: Save annotation
  const saveAnnotation = async () => {
    if (!currentSegment) return
    
    if (!isLoggedIn) {
      showToast('Vui lòng đăng nhập để gán nhãn', 'error')
      return
    }
    
    if (userRole === 'admin') {
      showToast('Admin không có quyền gán nhãn, chỉ có quyền duyệt', 'warning')
      return
    }
    
    setSaving(true)
    
    try {
      const token = localStorage.getItem('access_token')
      const res = await fetch(`${API_BASE}/annotations`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          segment_id: currentSegment.id,
          final_text: finalText,
          gloss_sequence: glossSequence,
          start_time: startTime,
          end_time: endTime,
          comment: comment
        })
      })
      
      if (res.ok) {
        showToast('Đã lưu thành công!', 'success')
        
        // Update local segment status
        const updatedSegments = [...segments]
        updatedSegments[currentIndex] = {
          ...updatedSegments[currentIndex],
          status: 'expert_labeled',
          review_comment: undefined
        }
        setSegments(updatedSegments)
        setCurrentSegment({ ...currentSegment, status: 'expert_labeled', review_comment: undefined })
        
        fetchStats()
        fetchAnnotationHistory(currentSegment.id)
        
        // Go to next after 1 second
        setTimeout(() => goToNext(), 1000)
      } else {
        const error = await res.json()
        showToast(error.detail || 'Lỗi khi lưu dữ liệu', 'error')
      }
    } catch (error) {
      showToast('Lỗi kết nối server', 'error')
    }
    setSaving(false)
  }

  // Admin: Approve segment
  const approveSegment = async () => {
    if (!currentSegment) return
    
    if (userRole !== 'admin') {
      showToast('Chỉ Admin mới có quyền duyệt', 'error')
      return
    }
    
    setSaving(true)
    
    try {
      const token = localStorage.getItem('access_token')
      const res = await fetch(`${API_BASE}/segments/${currentSegment.id}/review/approve`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (res.ok) {
        showToast('Đã duyệt segment!', 'success')
        
        // Update local segment status
        const updatedSegments = [...segments]
        updatedSegments[currentIndex] = {
          ...updatedSegments[currentIndex],
          status: 'reviewed',
          review_comment: undefined
        }
        setSegments(updatedSegments)
        setCurrentSegment({ ...currentSegment, status: 'reviewed', review_comment: undefined })
        
        fetchStats()
        
        // Go to next after 1 second
        setTimeout(() => goToNext(), 1000)
      } else {
        const error = await res.json()
        showToast(error.detail || 'Lỗi khi duyệt', 'error')
      }
    } catch (error) {
      showToast('Lỗi kết nối server', 'error')
    }
    setSaving(false)
  }

  // Admin: Reject segment
  const rejectSegment = async () => {
    if (!currentSegment) return
    
    if (userRole !== 'admin') {
      showToast('Chỉ Admin mới có quyền trả về', 'error')
      return
    }
    
    setSaving(true)
    
    try {
      const token = localStorage.getItem('access_token')
      const res = await fetch(`${API_BASE}/segments/${currentSegment.id}/review/reject`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          comment: reviewComment
        })
      })
      
      if (res.ok) {
        showToast('Đã trả về để sửa!', 'warning')
        setShowRejectModal(false)
        
        // Update local segment status
        const updatedSegments = [...segments]
        updatedSegments[currentIndex] = {
          ...updatedSegments[currentIndex],
          status: 'needs_fix',
          review_comment: reviewComment
        }
        setSegments(updatedSegments)
        setCurrentSegment({ ...currentSegment, status: 'needs_fix', review_comment: reviewComment })
        
        fetchStats()
        
        // Go to next after 1 second
        setTimeout(() => goToNext(), 1000)
      } else {
        const error = await res.json()
        showToast(error.detail || 'Lỗi khi trả về', 'error')
      }
    } catch (error) {
      showToast('Lỗi kết nối server', 'error')
    }
    setSaving(false)
    setReviewComment('')
  }

  // Admin: Delete dataset
  const deleteDataset = async () => {
    if (!selectedDataset) return
    
    if (userRole !== 'admin') {
      showToast('Chỉ Admin mới có quyền xóa dataset', 'error')
      return
    }
    
    setIsDeleting(true)
    
    try {
      const token = localStorage.getItem('access_token')
      const res = await fetch(`${API_BASE}/datasets/${selectedDataset}?delete_files=${deleteWithFiles}`, {
        method: 'DELETE',
        headers: { 
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (res.ok) {
        const data = await res.json()
        const resetMsg = data.sequence_reset ? ' (ID đã reset về 1)' : ''
        showToast(`Đã xóa dataset: ${data.segments_deleted} segments, ${data.annotations_deleted} annotations${deleteWithFiles ? `, ${data.files_deleted} files` : ''}${resetMsg}`, 'success')
        setShowDeleteDatasetModal(false)
        setSelectedDataset(null)
        setCurrentSegment(null)
        setSegments([])
        fetchDatasets()
        fetchStats()
      } else {
        const error = await res.json()
        showToast(error.detail || 'Lỗi khi xóa dataset', 'error')
      }
    } catch (error) {
      showToast('Lỗi kết nối server', 'error')
    }
    setIsDeleting(false)
    setDeleteWithFiles(false)
  }

  // Video controls
  const togglePlay = () => {
    if (videoRef) {
      if (isPlaying) {
        videoRef.pause()
      } else {
        videoRef.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  const handleTimeUpdate = () => {
    if (videoRef) {
      setCurrentTime(videoRef.currentTime)
    }
  }

  const handleLoadedMetadata = () => {
    if (videoRef) {
      setVideoDuration(videoRef.duration)
      videoRef.playbackRate = playbackRate
      
      // Check for pending seek time (set when video source changed)
      const pendingSeek = videoRef.dataset.pendingSeek
      if (pendingSeek) {
        const seekTime = parseFloat(pendingSeek)
        videoRef.currentTime = seekTime
        setCurrentTime(seekTime)
        delete videoRef.dataset.pendingSeek // Clear the pending seek
      } else if (currentSegment) {
        // Fallback: seek to segment's start time
        const targetTime = startTime || currentSegment.start_time
        videoRef.currentTime = targetTime
        setCurrentTime(targetTime)
      }
    }
  }

  const seekTo = (time: number) => {
    if (videoRef) {
      videoRef.currentTime = time
      setCurrentTime(time)
    }
  }

  const changePlaybackRate = (rate: number) => {
    setPlaybackRate(rate)
    if (videoRef) {
      videoRef.playbackRate = rate
    }
  }

  const cyclePlaybackRate = () => {
    const speeds = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2]
    const idx = speeds.indexOf(playbackRate)
    const nextIdx = (idx + 1) % speeds.length
    changePlaybackRate(speeds[nextIdx])
  }

  const showToast = (message: string, type: 'success' | 'error' | 'warning') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    const ms = Math.floor((seconds % 1) * 100)
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`
  }

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'raw': return 'bg-dark-700 text-dark-300'
      case 'in_progress': return 'bg-yellow-500/20 text-yellow-400'
      case 'expert_labeled': return 'bg-orange-500/20 text-orange-400'
      case 'needs_fix': return 'bg-red-500/20 text-red-400'
      case 'reviewed': return 'bg-green-500/20 text-green-400'
      default: return 'bg-dark-700 text-dark-300'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'raw': return 'Chưa label'
      case 'in_progress': return 'Đang xử lý'
      case 'expert_labeled': return 'Đã label'
      case 'needs_fix': return 'Cần sửa'
      case 'reviewed': return 'Đã duyệt'
      default: return status
    }
  }

  const isAdmin = userRole === 'admin'
  const canLabel = isLoggedIn && !isAdmin && currentSegment && currentSegment.status !== 'reviewed'
  const canReview = isAdmin && currentSegment?.status === 'expert_labeled'

  return (
    <div className="min-h-screen bg-[#0a0a0b]">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-dark-800 bg-[#0a0a0b]/90 backdrop-blur-xl">
        <div className="max-w-[1920px] mx-auto px-4 py-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/" className="p-2 hover:bg-dark-800 rounded-lg transition-colors">
                <ArrowLeft className="w-5 h-5 text-dark-400" />
              </Link>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-brand-600 rounded-lg flex items-center justify-center">
                  <Tag className="w-4 h-4 text-white" />
                </div>
                <div>
                  <h1 className="text-base font-bold text-white">Gán nhãn Dữ liệu</h1>
                </div>
              </div>
            </div>
            
            {/* User info & Stats */}
            <div className="flex items-center gap-4">
              {/* User Role Badge */}
              {isLoggedIn && (
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs ${
                  isAdmin ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'
                }`}>
                  {isAdmin ? <Shield className="w-3 h-3" /> : <User className="w-3 h-3" />}
                  <span>{isAdmin ? 'Admin' : 'Annotator'}</span>
                  {userName && <span className="text-dark-400">• {userName}</span>}
                </div>
              )}
              
              {/* Quick Stats */}
              {stats && (
                <div className="flex items-center gap-4 text-xs">
                  <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-dark-400">Đã duyệt:</span>
                    <span className="font-semibold text-green-400">{stats.reviewed_count}</span>
                  </div>
                  <div className="h-5 w-px bg-dark-700" />
                  <div className="flex items-center gap-1.5">
                    <span className="text-dark-400">Đã label:</span>
                    <span className="font-semibold text-orange-400">{stats.labeled_count}</span>
                  </div>
                  {stats.needs_fix_count > 0 && (
                    <>
                      <div className="h-5 w-px bg-dark-700" />
                      <div className="flex items-center gap-1.5">
                        <span className="text-dark-400">Cần sửa:</span>
                        <span className="font-semibold text-red-400">{stats.needs_fix_count}</span>
                      </div>
                    </>
                  )}
                  <div className="h-5 w-px bg-dark-700" />
                  <div className="flex items-center gap-1.5">
                    <span className="text-dark-400">Tổng:</span>
                    <span className="font-semibold text-white">{stats.total_segments}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-[1920px] mx-auto px-4 py-3">
        <div className="grid grid-cols-12 gap-4">
          
          {/* Sidebar - Segment List */}
          <aside className="col-span-3 flex flex-col h-[calc(100vh-140px)]">
            {/* Dataset Selector */}
            <div className="bg-dark-950 border border-dark-800 rounded-xl p-3 mb-3 flex-shrink-0">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-dark-400" />
                  <span className="text-xs font-medium text-dark-400">Dataset</span>
                </div>
                {/* Admin: Delete dataset button */}
                {isAdmin && selectedDataset && (
                  <button
                    onClick={() => setShowDeleteDatasetModal(true)}
                    className="p-1 hover:bg-red-500/20 rounded transition-colors text-red-400"
                    title="Xóa dataset"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <select
                value={selectedDataset || ''}
                onChange={(e) => { 
                  setSelectedDataset(e.target.value ? parseInt(e.target.value) : null)
                  setPage(1)
                  setCurrentSegment(null)
                }}
                className="w-full px-2 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-white"
              >
                <option value="">Tất cả dataset</option>
                {datasets.map(ds => (
                  <option key={ds.id} value={ds.id}>
                    {ds.name} ({ds.segment_count} segments)
                  </option>
                ))}
              </select>
            </div>
            
            {/* Filters */}
            <div className="bg-dark-950 border border-dark-800 rounded-xl p-3 mb-3 flex-shrink-0">
              <div className="flex gap-2">
                <select
                  value={statusFilter}
                  onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                  className="flex-1 px-2 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-white"
                >
                  <option value="">Tất cả trạng thái</option>
                  <option value="raw">Chưa label</option>
                  <option value="expert_labeled">Đã label</option>
                  <option value="needs_fix">Cần sửa</option>
                  <option value="reviewed">Đã duyệt</option>
                </select>
                <select
                  value={splitFilter}
                  onChange={(e) => { setSplitFilter(e.target.value); setPage(1); }}
                  className="flex-1 px-2 py-1.5 bg-dark-900 border border-dark-700 rounded-lg text-xs text-white"
                >
                  <option value="">Tất cả split</option>
                  <option value="train">Train</option>
                  <option value="val">Val</option>
                  <option value="test">Test</option>
                </select>
              </div>
            </div>

            {/* Segment List */}
            <div className="bg-dark-950 border border-dark-800 rounded-xl overflow-hidden flex-1 flex flex-col">
              <div className="px-3 py-2 border-b border-dark-800 flex items-center justify-between flex-shrink-0">
                <h3 className="text-xs font-medium text-dark-400">Danh sách ({segments.length})</h3>
                <button onClick={fetchSegments} className="p-1 hover:bg-dark-800 rounded transition-colors">
                  <RefreshCw className="w-3.5 h-3.5 text-dark-400" />
                </button>
              </div>
              
              <div className="flex-1 overflow-y-auto">
                {loading ? (
                  <div className="p-3 space-y-2">
                    {[...Array(5)].map((_, i) => (
                      <div key={i} className="h-14 skeleton rounded-lg" />
                    ))}
                  </div>
                ) : segments.length === 0 ? (
                  <div className="p-6 text-center">
                    <FileText className="w-8 h-8 text-dark-600 mx-auto mb-2" />
                    <p className="text-xs text-dark-500">Không có segment nào</p>
                    <p className="text-[10px] text-dark-600 mt-1">Thay đổi bộ lọc hoặc chọn dataset khác</p>
                  </div>
                ) : (
                  <div className="divide-y divide-dark-800/50">
                    {segments.map((segment, index) => (
                      <button
                        key={segment.id}
                        onClick={() => selectSegment(segment, index)}
                        className={`w-full px-3 py-2 text-left transition-all hover:bg-dark-900 ${
                          currentIndex === index ? 'bg-dark-900 border-l-2 border-brand-500' : ''
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] font-mono text-dark-500">#{(page - 1) * 20 + index + 1}</span>
                          <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${getStatusColor(segment.status)}`}>
                            {getStatusText(segment.status)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-dark-300 line-clamp-2 leading-relaxed">
                          {segment.asr_text || 'Không có transcript'}
                        </p>
                        <div className="mt-1 flex items-center gap-1.5 text-[10px] text-dark-500">
                          <Clock className="w-2.5 h-2.5" />
                          <span>{segment.duration?.toFixed(1)}s</span>
                          {segment.review_comment && (
                            <>
                              <span className="text-dark-700">•</span>
                              <MessageSquare className="w-2.5 h-2.5 text-red-400" />
                            </>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Pagination */}
              <div className="px-2 py-2 border-t border-dark-800 flex items-center justify-between flex-shrink-0">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="p-1 hover:bg-dark-800 rounded transition-colors disabled:opacity-50"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>
                <span className="text-[10px] text-dark-500">{page}/{totalPages || 1}</span>
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages || totalPages === 0}
                  className="p-1 hover:bg-dark-800 rounded transition-colors disabled:opacity-50"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </aside>

          {/* Main Content */}
          <main className="col-span-9">
            {currentSegment ? (
              <div className="grid grid-cols-5 gap-4 h-[calc(100vh-140px)]">
                {/* Left: Video Player with Timeline */}
                <div className="col-span-2 flex flex-col">
                  <div className="bg-dark-950 border border-dark-800 rounded-xl overflow-hidden flex-1 flex flex-col">
                    {/* Video - Load signer video (full video containing all sentences) */}
                    <div className="h-[260px] bg-black relative flex-shrink-0">
                      <video
                        ref={(el) => setVideoRef(el)}
                        src={`/api/signer-video/${currentSegment.video_source}`}
                        className="w-full h-full object-contain"
                        onTimeUpdate={handleTimeUpdate}
                        onLoadedMetadata={handleLoadedMetadata}
                        onEnded={() => setIsPlaying(false)}
                        muted={isMuted}
                      />
                      <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity bg-black/20">
                        <button
                          onClick={togglePlay}
                          className="w-14 h-14 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center hover:bg-white/30 transition-colors"
                        >
                          {isPlaying ? (
                            <Pause className="w-6 h-6 text-white" fill="white" />
                          ) : (
                            <Play className="w-6 h-6 text-white ml-1" fill="white" />
                          )}
                        </button>
                      </div>
                      <div className="absolute bottom-2 right-2 bg-black/70 px-2 py-1 rounded text-xs font-mono text-white">
                        {formatTime(currentTime)}
                      </div>
                    </div>
                    
                    {/* Timeline */}
                    <div className="p-3 bg-dark-900/50 flex-shrink-0">
                      <div className="relative h-10 mb-2">
                        <div className="absolute top-4 left-0 right-0 h-2 bg-dark-700 rounded-full">
                          <div 
                            className="absolute top-0 h-full bg-brand-500/30 rounded-full"
                            style={{
                              left: `${(startTime / (videoDuration || 1)) * 100}%`,
                              width: `${((endTime - startTime) / (videoDuration || 1)) * 100}%`
                            }}
                          />
                          <div 
                            className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-lg cursor-ew-resize z-30 hover:scale-125 transition-transform"
                            style={{ left: `calc(${(currentTime / (videoDuration || 1)) * 100}% - 8px)` }}
                            onMouseDown={(e) => {
                              e.preventDefault()
                              const track = e.currentTarget.parentElement
                              if (!track) return
                              const rect = track.getBoundingClientRect()
                              const handleDrag = (moveEvent: MouseEvent) => {
                                const x = Math.max(0, Math.min(moveEvent.clientX - rect.left, rect.width))
                                const newTime = (x / rect.width) * (videoDuration || 1)
                                seekTo(newTime)
                              }
                              const handleUp = () => {
                                document.removeEventListener('mousemove', handleDrag)
                                document.removeEventListener('mouseup', handleUp)
                              }
                              document.addEventListener('mousemove', handleDrag)
                              document.addEventListener('mouseup', handleUp)
                            }}
                          />
                        </div>
                        
                        {/* Start Marker */}
                        <div 
                          className="absolute top-0 w-4 h-10 cursor-ew-resize z-10"
                          style={{ left: `calc(${(startTime / (videoDuration || 1)) * 100}% - 8px)` }}
                          onMouseDown={(e) => {
                            e.preventDefault()
                            const track = e.currentTarget.parentElement
                            if (!track) return
                            const rect = track.getBoundingClientRect()
                            const handleDrag = (moveEvent: MouseEvent) => {
                              const x = Math.max(0, Math.min(moveEvent.clientX - rect.left, rect.width))
                              const newTime = (x / rect.width) * (videoDuration || 1)
                              if (newTime < endTime - 0.1) {
                                setStartTime(parseFloat(newTime.toFixed(3)))
                              }
                            }
                            const handleUp = () => {
                              document.removeEventListener('mousemove', handleDrag)
                              document.removeEventListener('mouseup', handleUp)
                            }
                            document.addEventListener('mousemove', handleDrag)
                            document.addEventListener('mouseup', handleUp)
                          }}
                        >
                          <div className="w-1 h-full bg-green-500 rounded-full mx-auto" />
                          <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-t-[8px] border-l-transparent border-r-transparent border-t-green-500" />
                        </div>
                        
                        {/* End Marker */}
                        <div 
                          className="absolute top-0 w-4 h-10 cursor-ew-resize z-10"
                          style={{ left: `calc(${(endTime / (videoDuration || 1)) * 100}% - 8px)` }}
                          onMouseDown={(e) => {
                            e.preventDefault()
                            const track = e.currentTarget.parentElement
                            if (!track) return
                            const rect = track.getBoundingClientRect()
                            const handleDrag = (moveEvent: MouseEvent) => {
                              const x = Math.max(0, Math.min(moveEvent.clientX - rect.left, rect.width))
                              const newTime = (x / rect.width) * (videoDuration || 1)
                              if (newTime > startTime + 0.1) {
                                setEndTime(parseFloat(newTime.toFixed(3)))
                              }
                            }
                            const handleUp = () => {
                              document.removeEventListener('mousemove', handleDrag)
                              document.removeEventListener('mouseup', handleUp)
                            }
                            document.addEventListener('mousemove', handleDrag)
                            document.addEventListener('mouseup', handleUp)
                          }}
                        >
                          <div className="w-1 h-full bg-red-500 rounded-full mx-auto" />
                          <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-t-[8px] border-l-transparent border-r-transparent border-t-red-500" />
                        </div>
                        
                        <div 
                          className="absolute top-2 left-0 right-0 h-6 cursor-pointer z-0"
                          onClick={(e) => {
                            const rect = e.currentTarget.getBoundingClientRect()
                            const x = e.clientX - rect.left
                            const newTime = (x / rect.width) * (videoDuration || 1)
                            seekTo(newTime)
                          }}
                        />
                      </div>
                      
                      <div className="flex justify-center gap-6 text-[10px] font-mono text-dark-500 mb-3">
                        <span className="text-green-400">Start gốc: {formatTime(currentSegment.start_time)}</span>
                        <span className="text-red-400">End gốc: {formatTime(currentSegment.end_time)}</span>
                      </div>
                      
                      {/* Playback Controls */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1">
                          <button onClick={() => seekTo(Math.max(0, currentTime - 0.1))} className="p-1.5 hover:bg-dark-700 rounded-lg" title="-0.1s">
                            <SkipBack className="w-4 h-4" />
                          </button>
                          <button onClick={togglePlay} className="p-2.5 bg-brand-500 hover:bg-brand-600 rounded-lg">
                            {isPlaying ? <Pause className="w-5 h-5" fill="white" /> : <Play className="w-5 h-5 ml-0.5" fill="white" />}
                          </button>
                          <button onClick={() => seekTo(Math.min(videoDuration, currentTime + 0.1))} className="p-1.5 hover:bg-dark-700 rounded-lg" title="+0.1s">
                            <SkipForward className="w-4 h-4" />
                          </button>
                        </div>
                        <div className="flex items-center gap-2">
                          <button 
                            onClick={cyclePlaybackRate}
                            className="px-2 py-1 bg-blue-500/20 hover:bg-blue-500/30 rounded text-xs text-blue-400 font-mono min-w-[45px]"
                          >
                            {playbackRate}x
                          </button>
                          <button onClick={() => setIsMuted(!isMuted)} className="p-1.5 hover:bg-dark-700 rounded-lg">
                            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                          </button>
                          <button onClick={() => seekTo(startTime)} className="px-2 py-1 bg-green-500/20 hover:bg-green-500/30 rounded text-xs text-green-400">
                            → Start
                          </button>
                          <button onClick={() => seekTo(endTime)} className="px-2 py-1 bg-red-500/20 hover:bg-red-500/30 rounded text-xs text-red-400">
                            → End
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Transcript */}
                    <div className="p-3 border-t border-dark-800 flex-1 overflow-auto">
                      <p className="text-[10px] text-dark-500 mb-1">ASR gốc:</p>
                      <p className="text-xs text-dark-300 leading-relaxed">{currentSegment.asr_text || 'Không có transcript'}</p>
                    </div>
                  </div>
                </div>

                {/* Right: Annotation Form & Admin Actions */}
                <div className="col-span-3 bg-dark-950 border border-dark-800 rounded-xl p-4 flex flex-col">
                  <div className="flex items-center justify-between mb-3 flex-shrink-0">
                    <h2 className="text-base font-semibold">
                      {isAdmin ? 'Xem & Duyệt dữ liệu' : 'Căn chỉnh dữ liệu'}
                    </h2>
                    <div className="flex items-center gap-2">
                      <div className={`px-2 py-0.5 rounded-full text-xs ${getStatusColor(currentSegment.status)}`}>
                        {getStatusText(currentSegment.status)}
                      </div>
                      <button
                        onClick={() => setShowHistory(!showHistory)}
                        className={`p-1.5 rounded-lg transition-colors ${showHistory ? 'bg-brand-500/20 text-brand-400' : 'hover:bg-dark-800 text-dark-400'}`}
                        title="Lịch sử gán nhãn"
                      >
                        <History className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Review Comment Warning */}
                  {currentSegment.review_comment && currentSegment.status === 'needs_fix' && (
                    <div className="mb-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex-shrink-0">
                      <div className="flex items-center gap-2 mb-1">
                        <AlertTriangle className="w-4 h-4 text-red-400" />
                        <span className="text-xs font-medium text-red-400">Phản hồi từ Admin:</span>
                      </div>
                      <p className="text-xs text-red-300">{currentSegment.review_comment}</p>
                    </div>
                  )}
                  
                  <div className="space-y-3 flex-1 overflow-auto">
                    <div className="p-2 bg-dark-900/50 rounded-lg text-xs text-dark-500 space-y-1">
                      <div className="flex gap-2"><span className="text-dark-400 flex-shrink-0">STT:</span> <span className="font-mono">#{(page - 1) * 20 + currentIndex + 1}</span></div>
                      <div className="flex gap-2"><span className="text-dark-400 flex-shrink-0">Clip:</span> <span className="font-mono text-dark-300 truncate">{currentSegment.clip_name}</span></div>
                      <div className="flex gap-2"><span className="text-dark-400 flex-shrink-0">Duration:</span> <span className="font-mono">{currentSegment.duration?.toFixed(2)}s</span></div>
                      {currentSegment.latest_annotation?.expert_name && (
                        <div className="flex gap-2">
                          <span className="text-dark-400 flex-shrink-0">Người gán nhãn:</span> 
                          <span className="font-mono text-brand-400">{currentSegment.latest_annotation.expert_name}</span>
                        </div>
                      )}
                    </div>

                    {/* Annotation History Panel */}
                    {showHistory && annotationHistory.length > 0 && (
                      <div className="p-2 bg-dark-900/50 rounded-lg">
                        <h4 className="text-xs font-medium text-dark-400 mb-2 flex items-center gap-1">
                          <History className="w-3 h-3" /> Lịch sử gán nhãn ({annotationHistory.length})
                        </h4>
                        <div className="max-h-32 overflow-y-auto space-y-2">
                          {annotationHistory.map((ann) => (
                            <div key={ann.id} className="p-2 bg-dark-800/50 rounded text-[10px]">
                              <div className="flex items-center justify-between mb-1">
                                <span className="font-medium text-brand-400">v{ann.version}</span>
                                <span className="text-dark-500">{formatDateTime(ann.created_at)}</span>
                              </div>
                              <div className="text-dark-400">
                                <span className="text-dark-500">Bởi:</span> {ann.expert_name || 'Unknown'}
                              </div>
                              {ann.final_text && (
                                <p className="text-dark-300 mt-1 line-clamp-1">{ann.final_text}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-dark-400 mb-1">Start (giây)</label>
                        <input
                          type="number"
                          step="0.001"
                          value={startTime}
                          onChange={(e) => setStartTime(parseFloat(e.target.value))}
                          disabled={isAdmin}
                          className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-sm text-white font-mono focus:border-brand-500 disabled:opacity-60"
                        />
                        <p className="mt-0.5 text-[10px] text-dark-500">Gốc: {currentSegment.start_time}s</p>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-dark-400 mb-1">End (giây)</label>
                        <input
                          type="number"
                          step="0.001"
                          value={endTime}
                          onChange={(e) => setEndTime(parseFloat(e.target.value))}
                          disabled={isAdmin}
                          className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-sm text-white font-mono focus:border-brand-500 disabled:opacity-60"
                        />
                        <p className="mt-0.5 text-[10px] text-dark-500">Gốc: {currentSegment.end_time}s</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-dark-400 mb-1">Chuỗi Gloss (tùy chọn)</label>
                        <input
                          type="text"
                          value={glossSequence}
                          onChange={(e) => setGlossSequence(e.target.value)}
                          disabled={isAdmin}
                          className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-sm text-white font-mono focus:border-brand-500 disabled:opacity-60"
                          placeholder="VD: TÔI|ĐI|HỌC"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-dark-400 mb-1">Ghi chú (tùy chọn)</label>
                        <input
                          type="text"
                          value={comment}
                          onChange={(e) => setComment(e.target.value)}
                          disabled={isAdmin}
                          className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-sm text-white focus:border-brand-500 disabled:opacity-60"
                          placeholder="Thêm ghi chú nếu cần..."
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-dark-400 mb-1">
                        Câu tiếng Việt (final_text)
                      </label>
                      <textarea
                        value={finalText}
                        onChange={(e) => setFinalText(e.target.value)}
                        rows={4}
                        disabled={isAdmin}
                        className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-sm text-white resize-none focus:border-brand-500 disabled:opacity-60"
                        placeholder="Nhập câu tiếng Việt đã căn chỉnh..."
                      />
                    </div>
                  </div>
                  
                  {/* Actions */}
                  <div className="mt-3 pt-3 border-t border-dark-800 flex items-center justify-between flex-shrink-0">
                    <div className="flex gap-2">
                      {!isAdmin && (
                        <button
                          onClick={resetToOriginal}
                          className="px-3 py-1.5 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 rounded-lg text-sm flex items-center gap-1"
                        >
                          <RefreshCw className="w-3.5 h-3.5" /> Reset
                        </button>
                      )}
                      <button
                        onClick={goToPrevious}
                        disabled={currentIndex === 0 && page === 1}
                        className="px-3 py-1.5 bg-dark-800 hover:bg-dark-700 rounded-lg text-sm flex items-center gap-1 disabled:opacity-50"
                      >
                        <ChevronLeft className="w-4 h-4" /> Trước
                      </button>
                      <button
                        onClick={goToNext}
                        className="px-3 py-1.5 bg-dark-800 hover:bg-dark-700 rounded-lg text-sm flex items-center gap-1"
                      >
                        Sau <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                    
                    {/* Role-based action buttons */}
                    {isAdmin ? (
                      /* Admin: Review buttons */
                      <div className="flex gap-2">
                        {canReview ? (
                          <>
                            <button
                              onClick={() => setShowRejectModal(true)}
                              disabled={saving}
                              className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg text-sm flex items-center gap-2 font-medium"
                            >
                              <X className="w-4 h-4" /> Trả về sửa
                            </button>
                            <button
                              onClick={approveSegment}
                              disabled={saving}
                              className="px-5 py-2 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 rounded-lg text-sm flex items-center gap-2 font-medium shadow-lg shadow-green-500/20 disabled:opacity-50"
                            >
                              {saving ? (
                                <><RefreshCw className="w-4 h-4 animate-spin" /> Đang duyệt...</>
                              ) : (
                                <><Check className="w-4 h-4" /> Duyệt</>
                              )}
                            </button>
                          </>
                        ) : (
                          <div className="px-4 py-2 text-xs text-dark-500">
                            {currentSegment.status === 'raw' && '⚠️ Segment chưa được gán nhãn'}
                            {currentSegment.status === 'needs_fix' && '⏳ Đang chờ annotator sửa'}
                            {currentSegment.status === 'reviewed' && '✅ Đã duyệt xong'}
                          </div>
                        )}
                      </div>
                    ) : (
                      /* Annotator: Save button */
                      <button
                        onClick={saveAnnotation}
                        disabled={saving || !canLabel}
                        className="px-5 py-2 bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 rounded-lg text-sm flex items-center gap-2 font-medium shadow-lg shadow-brand-500/20 disabled:opacity-50"
                      >
                        {saving ? (
                          <><RefreshCw className="w-4 h-4 animate-spin" /> Đang lưu...</>
                        ) : (
                          <><Save className="w-4 h-4" /> Lưu & Tiếp tục</>
                        )}
                      </button>
                    )}
                  </div>

                  {/* Login reminder */}
                  {!isLoggedIn && (
                    <div className="mt-2 p-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-xs text-yellow-400 text-center">
                      💡 <Link href="/login" className="underline hover:text-yellow-300">Đăng nhập</Link> để gán nhãn và lưu tiến trình
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-dark-950 border border-dark-800 rounded-xl p-8 flex flex-col items-center justify-center h-[calc(100vh-140px)]">
                <div className="w-16 h-16 bg-dark-900 rounded-full flex items-center justify-center mb-4">
                  <FileText className="w-8 h-8 text-dark-600" />
                </div>
                <h3 className="text-lg font-semibold text-dark-300 mb-1">
                  {loading ? 'Đang tải dữ liệu...' : 'Không có mẫu nào'}
                </h3>
                <p className="text-sm text-dark-500 text-center max-w-sm">
                  {loading 
                    ? 'Vui lòng chờ trong giây lát'
                    : 'Chọn một dataset hoặc thay đổi bộ lọc để xem các segment.'
                  }
                </p>
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-dark-900 border border-dark-700 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-400" />
              Trả về để sửa
            </h3>
            <p className="text-sm text-dark-400 mb-4">
              Nhập lý do trả về để annotator biết cần sửa gì:
            </p>
            <textarea
              value={reviewComment}
              onChange={(e) => setReviewComment(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-sm text-white resize-none focus:border-red-500"
              placeholder="VD: Thời gian chưa chính xác, cần điều chỉnh lại start time..."
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => { setShowRejectModal(false); setReviewComment(''); }}
                className="px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg text-sm"
              >
                Hủy
              </button>
              <button
                onClick={rejectSegment}
                disabled={saving || !reviewComment.trim()}
                className="px-4 py-2 bg-red-500 hover:bg-red-600 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {saving ? 'Đang xử lý...' : 'Xác nhận trả về'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Dataset Modal */}
      {showDeleteDatasetModal && selectedDataset && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-dark-900 border border-dark-700 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Trash2 className="w-5 h-5 text-red-400" />
              Xóa Dataset
            </h3>
            <p className="text-sm text-dark-300 mb-4">
              Bạn có chắc chắn muốn xóa dataset <span className="font-semibold text-white">
                {datasets.find(d => d.id === selectedDataset)?.name}
              </span>?
            </p>
            <p className="text-xs text-dark-400 mb-4">
              Thao tác này sẽ xóa tất cả segments và annotations trong dataset.
            </p>
            
            {/* Delete files checkbox */}
            <label className="flex items-center gap-2 mb-4 cursor-pointer">
              <input
                type="checkbox"
                checked={deleteWithFiles}
                onChange={(e) => setDeleteWithFiles(e.target.checked)}
                className="w-4 h-4 rounded border-dark-600 bg-dark-800 text-red-500 focus:ring-red-500"
              />
              <span className="text-sm text-dark-300">Xóa cả video files trên disk</span>
            </label>
            
            {deleteWithFiles && (
              <div className="p-2 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400 mb-4">
                ⚠️ Các file video trong sentence_clips và signer_clips sẽ bị xóa vĩnh viễn
              </div>
            )}
            
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowDeleteDatasetModal(false); setDeleteWithFiles(false); }}
                className="px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg text-sm"
              >
                Hủy
              </button>
              <button
                onClick={deleteDataset}
                disabled={isDeleting}
                className="px-4 py-2 bg-red-500 hover:bg-red-600 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2"
              >
                {isDeleting ? (
                  <><RefreshCw className="w-4 h-4 animate-spin" /> Đang xóa...</>
                ) : (
                  <><Trash2 className="w-4 h-4" /> Xóa dataset</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-6 right-6 px-6 py-4 rounded-xl shadow-2xl toast-enter flex items-center gap-3 ${
          toast.type === 'success' ? 'bg-green-500 text-white' : 
          toast.type === 'warning' ? 'bg-yellow-500 text-white' :
          'bg-red-500 text-white'
        }`}>
          {toast.type === 'success' ? <CheckCircle className="w-5 h-5" /> : 
           toast.type === 'warning' ? <AlertTriangle className="w-5 h-5" /> :
           <AlertCircle className="w-5 h-5" />}
          {toast.message}
        </div>
      )}
    </div>
  )
}
