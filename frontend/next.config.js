/** @type {import('next').NextConfig} */

// Backend port - thay đổi nếu backend chạy trên port khác
const BACKEND_PORT = process.env.BACKEND_PORT || 8536

const nextConfig = {
  async rewrites() {
    return {
      beforeFiles: [],
      afterFiles: [
        // Auth API
        {
          source: '/api/auth/:path*',
          destination: `http://localhost:${BACKEND_PORT}/api/auth/:path*`,
        },
        // Collecting API
        {
          source: '/api/collecting/:path*',
          destination: `http://localhost:${BACKEND_PORT}/api/collecting/:path*`,
        },
        // Labeling API (for backward compatibility with /backend-api)
        {
          source: '/backend-api/:path*',
          destination: `http://localhost:${BACKEND_PORT}/api/labeling/:path*`,
        },
        // Direct labeling API
        {
          source: '/api/labeling/:path*',
          destination: `http://localhost:${BACKEND_PORT}/api/labeling/:path*`,
        },
        // Video files - sentence clips
        {
          source: '/api/video/:path*',
          destination: `http://localhost:${BACKEND_PORT}/videos/:path*`,
        },
        // Signer videos
        {
          source: '/api/signer-video/:path*',
          destination: `http://localhost:${BACKEND_PORT}/signer-videos/:path*`,
        },
        // Health check
        {
          source: '/api/health',
          destination: `http://localhost:${BACKEND_PORT}/api/health`,
        },
      ],
      fallback: [],
    }
  },
}

module.exports = nextConfig
