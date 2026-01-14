'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { 
  Video, 
  Tag, 
  BarChart3,
  ArrowRight,
  Zap,
  Download,
  FileText,
  Users,
  CheckCircle,
  Clock
} from 'lucide-react'

interface Stats {
  total_segments: number
  raw_count: number
  labeled_count: number
  reviewed_count: number
}

export default function HomePage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async () => {
    try {
      const res = await fetch('/api/labeling/stats')
      if (res.ok) {
        const data = await res.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Error fetching stats:', error)
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-[#0a0a0b]">
      {/* Header */}
      <header className="border-b border-dark-800 bg-[#0a0a0b]/90 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-brand-500 to-brand-600 rounded-xl flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">ViSL Tool</h1>
                <p className="text-xs text-dark-400">Vietnamese Sign Language Tool</p>
              </div>
            </div>
            
            <nav className="flex items-center gap-4">
              <Link href="/collecting" className="px-4 py-2 text-sm text-dark-300 hover:text-white transition-colors">
                Thu thập
              </Link>
              <Link href="/labeling" className="px-4 py-2 text-sm text-dark-300 hover:text-white transition-colors">
                Gán nhãn
              </Link>
              <Link href="/login" className="px-4 py-2 text-sm bg-brand-500 hover:bg-brand-600 text-white rounded-lg transition-colors">
                Đăng nhập
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-brand-500/10 text-brand-400 rounded-full text-sm mb-6">
            <Zap className="w-4 h-4" />
            <span>Phiên bản 2.0 - Tích hợp hoàn chỉnh</span>
          </div>
          
          <h2 className="text-5xl font-bold text-white mb-6 leading-tight">
            Công cụ xử lý
            <span className="bg-gradient-to-r from-brand-400 to-green-400 bg-clip-text text-transparent"> Ngôn ngữ Ký hiệu </span>
            Việt Nam
          </h2>
          
          <p className="text-xl text-dark-400 mb-10 max-w-2xl mx-auto">
            Thu thập, xử lý và gán nhãn video ngôn ngữ ký hiệu một cách tự động. 
            Tích hợp AI để transcribe và phân đoạn video.
          </p>

          <div className="flex items-center justify-center gap-4">
            <Link 
              href="/collecting"
              className="px-6 py-3 bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 text-white rounded-xl font-medium flex items-center gap-2 shadow-lg shadow-brand-500/25 transition-all hover:scale-105"
            >
              <Video className="w-5 h-5" />
              Bắt đầu thu thập
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link 
              href="/labeling"
              className="px-6 py-3 bg-dark-800 hover:bg-dark-700 text-white rounded-xl font-medium flex items-center gap-2 transition-all hover:scale-105"
            >
              <Tag className="w-5 h-5" />
              Gán nhãn dữ liệu
            </Link>
              </div>
            </div>
      </section>

      {/* Stats Section */}
      {stats && (
        <section className="py-12 px-6 border-t border-dark-800">
          <div className="max-w-5xl mx-auto">
            <div className="grid grid-cols-4 gap-6">
              <div className="bg-dark-950 border border-dark-800 rounded-xl p-6 text-center">
                <FileText className="w-8 h-8 text-brand-400 mx-auto mb-3" />
                <div className="text-3xl font-bold text-white mb-1">{stats.total_segments}</div>
                <div className="text-sm text-dark-400">Tổng segments</div>
              </div>
              <div className="bg-dark-950 border border-dark-800 rounded-xl p-6 text-center">
                <Clock className="w-8 h-8 text-yellow-400 mx-auto mb-3" />
                <div className="text-3xl font-bold text-white mb-1">{stats.raw_count}</div>
                <div className="text-sm text-dark-400">Chờ gán nhãn</div>
              </div>
              <div className="bg-dark-950 border border-dark-800 rounded-xl p-6 text-center">
                <CheckCircle className="w-8 h-8 text-green-400 mx-auto mb-3" />
                <div className="text-3xl font-bold text-white mb-1">{stats.labeled_count}</div>
                <div className="text-sm text-dark-400">Đã gán nhãn</div>
              </div>
              <div className="bg-dark-950 border border-dark-800 rounded-xl p-6 text-center">
                <BarChart3 className="w-8 h-8 text-blue-400 mx-auto mb-3" />
                <div className="text-3xl font-bold text-white mb-1">
                  {stats.total_segments > 0 ? Math.round((stats.labeled_count / stats.total_segments) * 100) : 0}%
                </div>
                <div className="text-sm text-dark-400">Tiến độ</div>
                    </div>
                  </div>
                    </div>
        </section>
      )}

      {/* Features Section */}
      <section className="py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <h3 className="text-2xl font-bold text-white text-center mb-12">Các tính năng chính</h3>
          
          <div className="grid md:grid-cols-2 gap-8">
            {/* Collecting Tool */}
            <Link href="/collecting" className="group">
              <div className="bg-dark-950 border border-dark-800 rounded-2xl p-8 h-full hover:border-brand-500/50 transition-all hover:shadow-lg hover:shadow-brand-500/10">
                <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center mb-6">
                  <Video className="w-7 h-7 text-white" />
                </div>
                <h4 className="text-xl font-semibold text-white mb-3 group-hover:text-brand-400 transition-colors">
                  Thu thập Video
                </h4>
                <p className="text-dark-400 mb-4">
                  Tải video từ YouTube, tự động phát hiện và cắt vùng người ký hiệu, 
                  transcribe bằng AI và chia thành các đoạn câu.
                </p>
                <ul className="space-y-2 text-sm text-dark-500">
                  <li className="flex items-center gap-2">
                    <Download className="w-4 h-4 text-blue-400" />
                    Tải video/playlist từ YouTube
                  </li>
                  <li className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-blue-400" />
                    Tự động crop vùng signer
                  </li>
                  <li className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-blue-400" />
                    Transcribe với WhisperX
                  </li>
                </ul>
              </div>
            </Link>

            {/* Labeling Tool */}
            <Link href="/labeling" className="group">
              <div className="bg-dark-950 border border-dark-800 rounded-2xl p-8 h-full hover:border-brand-500/50 transition-all hover:shadow-lg hover:shadow-brand-500/10">
                <div className="w-14 h-14 bg-gradient-to-br from-brand-500 to-brand-600 rounded-xl flex items-center justify-center mb-6">
                  <Tag className="w-7 h-7 text-white" />
                </div>
                <h4 className="text-xl font-semibold text-white mb-3 group-hover:text-brand-400 transition-colors">
                  Gán nhãn Dữ liệu
                </h4>
                <p className="text-dark-400 mb-4">
                  Giao diện chuyên nghiệp để căn chỉnh video với transcript, 
                  thêm gloss sequence và quản lý annotations.
                </p>
                <ul className="space-y-2 text-sm text-dark-500">
                  <li className="flex items-center gap-2">
                    <Video className="w-4 h-4 text-brand-400" />
                    Video player với timeline
                  </li>
                  <li className="flex items-center gap-2">
                    <Tag className="w-4 h-4 text-brand-400" />
                    Căn chỉnh start/end time
                  </li>
                  <li className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-brand-400" />
                    Thống kê tiến độ real-time
                  </li>
                </ul>
              </div>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-dark-800 py-8 px-6">
        <div className="max-w-6xl mx-auto text-center text-dark-500 text-sm">
          <p>ViSL Tool v2.0 - Vietnamese Sign Language Dataset Builder</p>
        </div>
      </footer>
    </div>
  )
}
