import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ViSL Tool - Công cụ xử lý ngôn ngữ ký hiệu Việt Nam',
  description: 'Công cụ tích hợp: Thu thập video, xử lý và gán nhãn ngôn ngữ ký hiệu Việt Nam',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="vi">
      <body className="antialiased">
        {children}
      </body>
    </html>
  )
}
