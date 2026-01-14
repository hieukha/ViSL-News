import { NextRequest, NextResponse } from 'next/server'
import { createReadStream, statSync, existsSync } from 'fs'
import { join } from 'path'

// Base directory cho video files
const DATA_DIR = '/workspace/khanh/ViSL-News/data'

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  try {
    const pathSegments = params.path
    const filePath = join(DATA_DIR, ...pathSegments)
    
    // Security check: prevent directory traversal
    if (!filePath.startsWith(DATA_DIR)) {
      return new NextResponse('Forbidden', { status: 403 })
    }
    
    // Check if file exists
    if (!existsSync(filePath)) {
      return new NextResponse('File not found', { status: 404 })
    }
    
    const stat = statSync(filePath)
    const fileSize = stat.size
    
    // Handle range requests for video streaming
    const range = request.headers.get('range')
    
    if (range) {
      const parts = range.replace(/bytes=/, '').split('-')
      const start = parseInt(parts[0], 10)
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1
      const chunkSize = end - start + 1
      
      const headers = new Headers({
        'Content-Range': `bytes ${start}-${end}/${fileSize}`,
        'Accept-Ranges': 'bytes',
        'Content-Length': chunkSize.toString(),
        'Content-Type': 'video/mp4',
      })
      
      // Read the specific chunk
      const { Readable } = await import('stream')
      const fs = await import('fs')
      const stream = fs.createReadStream(filePath, { start, end })
      
      // Convert Node stream to Web stream
      const webStream = new ReadableStream({
        start(controller) {
          stream.on('data', (chunk) => controller.enqueue(chunk))
          stream.on('end', () => controller.close())
          stream.on('error', (err) => controller.error(err))
        },
      })
      
      return new NextResponse(webStream, { status: 206, headers })
    }
    
    // No range request - serve entire file
    const fs = await import('fs')
    const stream = fs.createReadStream(filePath)
    
    const webStream = new ReadableStream({
      start(controller) {
        stream.on('data', (chunk) => controller.enqueue(chunk))
        stream.on('end', () => controller.close())
        stream.on('error', (err) => controller.error(err))
      },
    })
    
    const headers = new Headers({
      'Content-Length': fileSize.toString(),
      'Content-Type': 'video/mp4',
      'Accept-Ranges': 'bytes',
    })
    
    return new NextResponse(webStream, { status: 200, headers })
    
  } catch (error) {
    console.error('Error serving video:', error)
    return new NextResponse('Internal Server Error', { status: 500 })
  }
}

