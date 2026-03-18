import { NextRequest } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'
import fs from 'fs'
import { APPS_DIR } from '@/lib/csv'

export const dynamic = 'force-dynamic'

const PIPELINE_DIR = path.resolve(APPS_DIR, '..', 'pipeline')

function norm(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]/g, '')
}

function findAppFolder(company: string, title: string): string | null {
  if (!fs.existsSync(APPS_DIR)) return null
  const co = norm(company)
  if (!co) return null
  const titleWords = norm(title).match(/[a-z0-9]{3,}/g) ?? []
  let best: string | null = null
  let bestScore = -1
  for (const folder of fs.readdirSync(APPS_DIR)) {
    if (!fs.existsSync(path.join(APPS_DIR, folder, 'analysis.json'))) continue
    const body = norm(folder.replace(/^\d{8}_/, ''))
    const firstSeg = norm(folder.replace(/^\d{8}_/, '').split('_')[0])
    if (!body.startsWith(co) && !co.startsWith(firstSeg)) continue
    const score = titleWords.filter(w => body.includes(w)).length
    if (score > bestScore) { bestScore = score; best = path.join(APPS_DIR, folder) }
  }
  return best
}

// POST /api/pipeline/stream
// Body: { action: 'tailor' | 'cover-letter' | 'followup', company: string, title: string }
// Returns: streaming plain-text response (stdout + stderr from the spawned script)
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({})) as {
    action?: string
    company?: string
    title?: string
  }

  const { action, company = '', title = '' } = body

  if (!action || !company || !title) {
    return new Response('Missing action, company, or title', { status: 400 })
  }

  let args: string[]

  if (action === 'tailor') {
    const folder = findAppFolder(company, title)
    const jdPath = folder ? path.join(folder, 'job_description.txt') : null
    if (!jdPath || !fs.existsSync(jdPath)) {
      return new Response(
        `Could not locate job_description.txt for "${company} / ${title}".\n` +
        `Ensure the application folder exists and contains a job_description.txt file.`,
        { status: 422 },
      )
    }
    args = ['tailor_resume.py', '--jd', jdPath]
  } else if (action === 'cover-letter') {
    args = ['cover_letter.py', '--company', company, '--title', title]
  } else if (action === 'followup') {
    args = ['followup.py', '--dry-run']
  } else {
    return new Response(`Unknown action: ${action}`, { status: 400 })
  }

  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    start(controller) {
      const proc = spawn('python', args, {
        cwd: PIPELINE_DIR,
        shell: process.platform === 'win32',
      })

      const send = (text: string) => {
        try { controller.enqueue(encoder.encode(text)) } catch { /* closed */ }
      }

      proc.stdout.on('data', (d: Buffer) => send(d.toString()))
      proc.stderr.on('data', (d: Buffer) => send(d.toString()))

      proc.on('close', (code: number | null) => {
        send(`\n--- Finished (exit code ${code ?? 0}) ---\n`)
        try { controller.close() } catch { /* already closed */ }
      })

      proc.on('error', (err: Error) => {
        send(`\nFailed to start process: ${err.message}\n`)
        try { controller.close() } catch { /* already closed */ }
      })
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'no-cache',
      'X-Content-Type-Options': 'nosniff',
    },
  })
}
