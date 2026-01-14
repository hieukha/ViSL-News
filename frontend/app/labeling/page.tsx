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
  BarChart3,
  Clock,
  FileText,
  Users,
  Zap,
  RefreshCw,
  Volume2,
  VolumeX,
  Maximize2,
  AlertCircle,
  ArrowLeft,
  Home,
  Tag
} from 'lucide-react'

interface Segment {
  id: number
  clip_name: string
  clip_path: string
  video_source: string  // Video gốc (signer video)
  start_time: number
  end_time: number
  duration: number
  asr_text: string
  status: string
  split: string
  latest_annotation?: Annotation
}

interface Annotation {
  id: number
  final_text: string
  gloss_sequence: string
  start_time: number
  end_time: number
  comment: string
}

interface Stats {
  total_segments: number
  raw_count: number
  in_progress_count: number
  labeled_count: number
  reviewed_count: number
  train_count: number
  val_count: number
  test_count: number
  total_annotations: number
  avg_duration: number | null
}

const API_BASE = '/backend-api'

// Mock data để test khi chưa có backend
const MOCK_SEGMENTS: Segment[] = [
  {
    id: 1,
    clip_name: 'coca-cola-viet-nam-tiep-tuc-khang-dinh-thuong-hieu-nha-tuyen-dung-cua-minh-0',
    clip_path: 'sentence_clips/coca-cola-viet-nam-tiep-tuc-khang-dinh-thuong-hieu-nha-tuyen-dung-cua-minh-0.mp4',
    video_source: 'signer_clips/signer_coca-cola-viet-nam-tiep-tuc-khang-dinh-thuong-hieu-nha-tuyen-dung-cua-minh.mp4',
    start_time: 0.031,
    end_time: 12.117,
    duration: 14.0,
    asr_text: 'Tự hào là một phần trong cuộc sống của nhiều thế hệ người tiêu dùng Việt Nam, Coca-Cola Việt Nam còn tiếp tục khẳng định thương hiệu nhà tuyển dụng của mình khi trở thành một cái tên tiêu biểu cho văn hóa doanh nghiệp, lấy con người làm trọng tâm.',
    status: 'raw',
    split: 'train'
  },
  {
    id: 2,
    clip_name: 'coca-cola-viet-nam-tiep-tuc-khang-dinh-thuong-hieu-nha-tuyen-dung-cua-minh-1',
    clip_path: 'sentence_clips/coca-cola-viet-nam-tiep-tuc-khang-dinh-thuong-hieu-nha-tuyen-dung-cua-minh-1.mp4',
    video_source: 'signer_clips/signer_coca-cola-viet-nam-tiep-tuc-khang-dinh-thuong-hieu-nha-tuyen-dung-cua-minh.mp4',
    start_time: 14.071,
    end_time: 24.95,
    duration: 12.0,
    asr_text: 'Công ty đã liên tục nhiều năm liền được công nhận với giải thưởng nơi làm việc tốt nhất châu Á.',
    status: 'raw',
    split: 'train'
  }
]

const MOCK_STATS: Stats = {
  total_segments: 78,
  raw_count: 65,
  in_progress_count: 3,
  labeled_count: 8,
  reviewed_count: 2,
  train_count: 60,
  val_count: 10,
  test_count: 8,
  total_annotations: 10,
  avg_duration: 9.5
}

// Set to true to use mock data (when backend is not running)
const USE_MOCK_DATA = false

export default function LabelingPage() {
  // State
  const [segments, setSegments] = useState<Segment[]>([])
  const [currentSegment, setCurrentSegment] = useState<Segment | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  
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
  
  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>('raw')
  const [splitFilter, setSplitFilter] = useState<string>('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  // Fetch segments
  const fetchSegments = async () => {
    setLoading(true)
    
    if (USE_MOCK_DATA) {
      let filtered = MOCK_SEGMENTS
      if (statusFilter) {
        filtered = filtered.filter(s => s.status === statusFilter)
      }
      if (splitFilter) {
        filtered = filtered.filter(s => s.split === splitFilter)
      }
      
      setSegments(filtered)
      setTotalPages(1)
      
      if (filtered.length > 0 && !currentSegment) {
        selectSegment(filtered[0], 0)
      }
      setLoading(false)
      return
    }
    
    try {
      const params = new URLSearchParams({ page: page.toString(), per_page: '20' })
      if (statusFilter) params.append('status', statusFilter)
      if (splitFilter) params.append('split', splitFilter)
      
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

  // Fetch stats
  const fetchStats = async () => {
    if (USE_MOCK_DATA) {
      setStats(MOCK_STATS)
      return
    }
    
    try {
      const res = await fetch(`${API_BASE}/stats`)
      const data = await res.json()
      setStats(data)
    } catch (error) {
      console.error('Error fetching stats:', error)
    }
  }

  useEffect(() => {
    fetchSegments()
    fetchStats()
  }, [page, statusFilter, splitFilter])

  // Select segment
  const selectSegment = (segment: Segment, index: number) => {
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
    
    setIsPlaying(false)
    setCurrentTime(0)
  }

  // Navigation
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

  // Reset to original values
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

  // Save annotation
  const saveAnnotation = async () => {
    if (!currentSegment) return
    
    setSaving(true)
    
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 500))
      showToast('Đã lưu thành công! (Mock mode)', 'success')
      
      const updatedSegments = [...segments]
      updatedSegments[currentIndex] = {
        ...updatedSegments[currentIndex],
        status: 'expert_labeled'
      }
      setSegments(updatedSegments)
      
      setTimeout(() => {
        goToNext()
      }, 1000)
      setSaving(false)
      return
    }
    
    try {
      const res = await fetch(`${API_BASE}/annotations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
        
        const updatedSegments = [...segments]
        updatedSegments[currentIndex] = {
          ...updatedSegments[currentIndex],
          status: 'expert_labeled'
        }
        setSegments(updatedSegments)
        
        fetchStats()
        
        setTimeout(() => {
          goToNext()
        }, 1000)
      } else {
        showToast('Lỗi khi lưu dữ liệu', 'error')
      }
    } catch (error) {
      showToast('Lỗi kết nối server', 'error')
    }
    setSaving(false)
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
    }
  }

  const seekTo = (time: number) => {
    if (videoRef) {
      videoRef.currentTime = time
      setCurrentTime(time)
    }
  }

  // Change playback speed
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

  // Toast
  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  // Format time
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    const ms = Math.floor((seconds % 1) * 100)
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'raw': return 'bg-dark-700 text-dark-300'
      case 'in_progress': return 'bg-yellow-500/20 text-yellow-400'
      case 'expert_labeled': return 'bg-green-500/20 text-green-400'
      case 'reviewed': return 'bg-blue-500/20 text-blue-400'
      default: return 'bg-dark-700 text-dark-300'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'raw': return 'Chưa label'
      case 'in_progress': return 'Đang xử lý'
      case 'expert_labeled': return 'Đã label'
      case 'reviewed': return 'Đã review'
      default: return status
    }
  }

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
            
            {/* Quick Stats */}
            {stats && (
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                  <span className="text-dark-400">Đã label:</span>
                  <span className="font-semibold text-white">{stats.labeled_count}</span>
                  <span className="text-dark-500">/</span>
                  <span className="text-dark-400">{stats.total_segments}</span>
                </div>
                <div className="h-5 w-px bg-dark-700" />
                <div className="flex items-center gap-1.5">
                  <span className="text-dark-400">Tiến độ:</span>
                  <span className="font-semibold text-brand-400">
                    {stats.total_segments > 0 ? Math.round((stats.labeled_count / stats.total_segments) * 100) : 0}%
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="max-w-[1920px] mx-auto px-4 py-3">
        <div className="grid grid-cols-12 gap-4">
          
          {/* Sidebar - Segment List */}
          <aside className="col-span-3 flex flex-col h-[calc(100vh-140px)]">
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
                  <option value="in_progress">Đang xử lý</option>
                  <option value="expert_labeled">Đã label</option>
                  <option value="reviewed">Đã review</option>
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
                          <span className="text-[10px] font-mono text-dark-500">#{segment.id}</span>
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
                <span className="text-[10px] text-dark-500">{page}/{totalPages}</span>
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
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
                    {/* Video */}
                    <div className="h-[260px] bg-black relative flex-shrink-0">
                      <video
                        ref={(el) => setVideoRef(el)}
                        src={`/api/video/${currentSegment.video_source}`}
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

                {/* Right: Annotation Form */}
                <div className="col-span-3 bg-dark-950 border border-dark-800 rounded-xl p-4 flex flex-col">
                  <div className="flex items-center justify-between mb-3 flex-shrink-0">
                    <h2 className="text-base font-semibold">Căn chỉnh dữ liệu</h2>
                    <div className={`px-2 py-0.5 rounded-full text-xs ${getStatusColor(currentSegment.status)}`}>
                      {getStatusText(currentSegment.status)}
                    </div>
                  </div>
                  
                  <div className="space-y-3 flex-1">
                    <div className="p-2 bg-dark-900/50 rounded-lg text-xs text-dark-500 space-y-1">
                      <div className="flex gap-2"><span className="text-dark-400 flex-shrink-0">ID:</span> <span className="font-mono">#{currentSegment.id}</span></div>
                      <div className="flex gap-2"><span className="text-dark-400 flex-shrink-0">Clip:</span> <span className="font-mono text-dark-300">{currentSegment.clip_name}</span></div>
                      <div className="flex gap-2"><span className="text-dark-400 flex-shrink-0">Duration:</span> <span className="font-mono">{currentSegment.duration?.toFixed(2)}s</span></div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-dark-400 mb-1">Start (giây)</label>
                        <input
                          type="number"
                          step="0.001"
                          value={startTime}
                          onChange={(e) => setStartTime(parseFloat(e.target.value))}
                          className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-sm text-white font-mono focus:border-brand-500"
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
                          className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-sm text-white font-mono focus:border-brand-500"
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
                          className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-sm text-white font-mono focus:border-brand-500"
                          placeholder="VD: TÔI|ĐI|HỌC"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-dark-400 mb-1">Ghi chú (tùy chọn)</label>
                        <input
                          type="text"
                          value={comment}
                          onChange={(e) => setComment(e.target.value)}
                          className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-sm text-white focus:border-brand-500"
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
                        className="w-full px-3 py-2 bg-dark-900 border border-dark-700 rounded-lg text-sm text-white resize-none focus:border-brand-500"
                        placeholder="Nhập câu tiếng Việt đã căn chỉnh..."
                      />
                    </div>
                  </div>
                  
                  {/* Actions */}
                  <div className="mt-3 pt-3 border-t border-dark-800 flex items-center justify-between flex-shrink-0">
                    <div className="flex gap-2">
                      <button
                        onClick={resetToOriginal}
                        className="px-3 py-1.5 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 rounded-lg text-sm flex items-center gap-1"
                      >
                        <RefreshCw className="w-3.5 h-3.5" /> Reset
                      </button>
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
                    
                    <button
                      onClick={saveAnnotation}
                      disabled={saving}
                      className="px-5 py-2 bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 rounded-lg text-sm flex items-center gap-2 font-medium shadow-lg shadow-brand-500/20 disabled:opacity-50"
                    >
                      {saving ? (
                        <><RefreshCw className="w-4 h-4 animate-spin" /> Đang lưu...</>
                      ) : (
                        <><Save className="w-4 h-4" /> Lưu & Tiếp tục</>
                      )}
                    </button>
                  </div>
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
                    : 'Chọn một mẫu từ danh sách bên trái hoặc thay đổi bộ lọc.'
                  }
                </p>
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-6 right-6 px-6 py-4 rounded-xl shadow-2xl toast-enter flex items-center gap-3 ${
          toast.type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
        }`}>
          {toast.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          {toast.message}
        </div>
      )}
    </div>
  )
}

