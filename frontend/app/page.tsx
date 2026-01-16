'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { 
  Video, 
  Tag, 
  BarChart3,
  ArrowRight,
  Zap,
  Download,
  FileText,
  Users,
  LogOut
} from 'lucide-react'

export default function HomePage() {
  const router = useRouter()
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [userName, setUserName] = useState('')
  const [userRole, setUserRole] = useState('')

  useEffect(() => {
    // Check login status on mount
    const token = localStorage.getItem('access_token')
    const user = localStorage.getItem('user')
    if (token) {
      setIsLoggedIn(true)
      if (user) {
        try {
          const userData = JSON.parse(user)
          setUserName(userData.full_name || userData.email || '')
          setUserRole(userData.role || 'annotator')
        } catch {}
      }
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    setIsLoggedIn(false)
    setUserName('')
    setUserRole('')
    router.push('/')
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
              {/* Admin only: Thu thập */}
              {(!isLoggedIn || userRole === 'admin') && (
                <Link href="/collecting" className="px-4 py-2 text-sm text-dark-300 hover:text-white transition-colors">
                  Thu thập
                </Link>
              )}
              <Link href="/labeling" className="px-4 py-2 text-sm text-dark-300 hover:text-white transition-colors">
                Gán nhãn
              </Link>
              {isLoggedIn ? (
                <div className="flex items-center gap-3">
                  <div className="text-sm text-dark-400">
                    <span className="text-brand-400">{userName}</span>
                    <span className={`ml-2 px-2 py-0.5 text-xs rounded ${
                      userRole === 'admin' 
                        ? 'bg-red-500/20 text-red-400' 
                        : 'bg-blue-500/20 text-blue-400'
                    }`}>
                      {userRole === 'admin' ? 'Admin' : 'Annotator'}
                    </span>
                </div>
                  <button 
                    onClick={handleLogout}
                    className="px-4 py-2 text-sm bg-dark-800 hover:bg-dark-700 text-dark-300 hover:text-white rounded-lg transition-colors flex items-center gap-2"
                  >
                    <LogOut className="w-4 h-4" />
                    Đăng xuất
                  </button>
                </div>
              ) : (
                <Link href="/login" className="px-4 py-2 text-sm bg-brand-500 hover:bg-brand-600 text-white rounded-lg transition-colors">
                  Đăng nhập
                </Link>
            )}
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
            {/* Admin only or not logged in */}
            {(!isLoggedIn || userRole === 'admin') && (
              <Link 
                href="/collecting"
                className="px-6 py-3 bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 text-white rounded-xl font-medium flex items-center gap-2 shadow-lg shadow-brand-500/25 transition-all hover:scale-105"
              >
                <Video className="w-5 h-5" />
                Bắt đầu thu thập
                <ArrowRight className="w-4 h-4" />
              </Link>
            )}
            <Link 
              href="/labeling"
              className={`px-6 py-3 text-white rounded-xl font-medium flex items-center gap-2 transition-all hover:scale-105 ${
                isLoggedIn && userRole === 'annotator'
                  ? 'bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 shadow-lg shadow-brand-500/25'
                  : 'bg-dark-800 hover:bg-dark-700'
              }`}
            >
              <Tag className="w-5 h-5" />
              Gán nhãn dữ liệu
              {isLoggedIn && userRole === 'annotator' && <ArrowRight className="w-4 h-4" />}
            </Link>
              </div>
            </div>
      </section>

      {/* Features Section */}
      <section className="py-12 px-6 border-t border-dark-800">
        <div className="max-w-6xl mx-auto">
          <h3 className="text-2xl font-bold text-white text-center mb-12">Các tính năng chính</h3>
          
          <div className={`grid gap-8 ${(!isLoggedIn || userRole === 'admin') ? 'md:grid-cols-2' : 'md:grid-cols-1 max-w-xl mx-auto'}`}>
            {/* Collecting Tool - Admin only */}
            {(!isLoggedIn || userRole === 'admin') && (
              <Link href="/collecting" className="group">
                <div className="bg-dark-950 border border-dark-800 rounded-2xl p-8 h-full hover:border-brand-500/50 transition-all hover:shadow-lg hover:shadow-brand-500/10">
                  <div className="flex items-start justify-between mb-6">
                    <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
                      <Video className="w-7 h-7 text-white" />
                    </div>
                    <span className="px-2 py-1 bg-red-500/20 text-red-400 text-xs rounded-lg">Admin</span>
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
            )}

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
