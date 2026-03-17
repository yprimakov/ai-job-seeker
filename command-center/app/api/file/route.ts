import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

export const dynamic = 'force-dynamic'

// Project root is one level above command-center/
const ROOT = path.resolve(process.cwd(), '..')

const ALLOWED_ROOTS = [
  path.resolve(ROOT, 'applications'),
  path.resolve(ROOT, 'resume'),
]

export async function GET(req: NextRequest) {
  const filePath = req.nextUrl.searchParams.get('path')
  if (!filePath) {
    return new NextResponse('Missing path parameter', { status: 400 })
  }

  // Resolve relative paths against project ROOT, not command-center CWD
  const resolved = path.isAbsolute(filePath)
    ? path.resolve(filePath)
    : path.resolve(ROOT, filePath)

  // Case-insensitive startsWith for Windows path comparison
  const resolvedLower = resolved.toLowerCase()
  const allowed = ALLOWED_ROOTS.some(root =>
    resolvedLower.startsWith(root.toLowerCase() + path.sep) ||
    resolvedLower === root.toLowerCase()
  )

  if (!allowed) {
    return new NextResponse('Forbidden', { status: 403 })
  }

  if (!fs.existsSync(resolved)) {
    return new NextResponse('File not found', { status: 404 })
  }

  const stat = fs.statSync(resolved)
  if (stat.isDirectory()) {
    return new NextResponse('Is a directory', { status: 400 })
  }

  const ext = path.extname(resolved).toLowerCase()
  const mimeTypes: Record<string, string> = {
    '.pdf':  'application/pdf',
    '.md':   'text/markdown; charset=utf-8',
    '.txt':  'text/plain; charset=utf-8',
    '.json': 'application/json',
    '.html': 'text/html; charset=utf-8',
  }

  const contentType = mimeTypes[ext] ?? 'application/octet-stream'
  const buffer = fs.readFileSync(resolved)

  return new NextResponse(buffer, {
    headers: {
      'Content-Type': contentType,
      'Content-Length': String(buffer.length),
      'Content-Disposition': 'inline',
      'Cache-Control': 'private, max-age=60',
    },
  })
}
