import { NextResponse } from 'next/server'
import { readTracker, writeTracker, readQueue, APPS_DIR } from '@/lib/csv'
import type { TrackerRow } from '@/lib/utils'
import fs from 'fs'
import path from 'path'

export const dynamic = 'force-dynamic'

function norm(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]/g, '')
}

// Find the best application folder for a company + title
function findFolder(company: string, title: string): string | null {
  if (!fs.existsSync(APPS_DIR)) return null
  let folders: string[]
  try { folders = fs.readdirSync(APPS_DIR) } catch { return null }

  const co = norm(company)
  const titleWords = norm(title).match(/[a-z0-9]{3,}/g) ?? []

  let best: string | null = null
  let bestScore = -1

  for (const folder of folders) {
    if (!fs.existsSync(path.join(APPS_DIR, folder, 'analysis.json'))) continue
    const body = norm(folder.replace(/^\d{8}_/, ''))
    const firstSeg = norm(folder.replace(/^\d{8}_/, '').split('_')[0])
    const coMatch = body.startsWith(co) || co.startsWith(firstSeg) || firstSeg.startsWith(co.slice(0, 4))
    if (!coMatch) continue
    const score = titleWords.filter(w => body.includes(w)).length
    if (score > bestScore) { bestScore = score; best = path.join(APPS_DIR, folder) }
  }
  return best
}

// POST /api/jobs/queue/sync
// Creates "Tailored" tracker entries for all ready queue items that don't
// already have a tracker entry. Also scans application folders directly.
export async function POST() {
  const queue = readQueue()
  const readyItems = queue.filter(i => i.status === 'ready')
  const tracker = readTracker()
  let synced = 0

  // Track company+title combos we've already synced this batch to avoid queue duplicates
  const syncedKeys = new Set<string>()

  // Pre-populate with existing tracker entries
  for (const row of tracker) {
    syncedKeys.add(`${norm(row.Company ?? '')}|${norm(row['Job Title'] ?? '').slice(0, 20)}`)
  }

  for (const item of readyItems) {
    const company = item.company ?? ''
    const title = item.title ?? ''
    if (!company && !title) continue

    const key = `${norm(company)}|${norm(title).slice(0, 20)}`
    if (syncedKeys.has(key)) continue
    syncedKeys.add(key)

    const folder = findFolder(company, title)
    let analysis: Record<string, unknown> = {}
    let resumeFile = ''

    if (folder && fs.existsSync(path.join(folder, 'analysis.json'))) {
      try {
        analysis = JSON.parse(fs.readFileSync(path.join(folder, 'analysis.json'), 'utf-8'))
      } catch { /* ignore */ }
      const resumePdf = path.join(folder, 'resume.pdf')
      if (fs.existsSync(resumePdf)) resumeFile = resumePdf
    }

    const workMode = (analysis.work_mode as string) ?? ''
    const cleanCompany = (analysis.company as string) || company
    const cleanTitle = (analysis.job_title as string) || title

    const newRow: TrackerRow = {
      'Date Applied': new Date().toISOString().slice(0, 10),
      'Company': cleanCompany,
      'Job Title': cleanTitle,
      'LinkedIn URL': item.url ?? '',
      'Work Mode': workMode,
      'Salary Range': '',
      'Easy Apply': item.url?.includes('linkedin.com') ? 'Yes' : '',
      'Application Status': 'Tailored',
      'Notes': '',
      'Tailored Resume File': resumeFile,
      'Follow Up Date': '',
      'Date Response Received': '',
      'Response Type': '',
    }
    tracker.push(newRow)
    synced++
  }

  if (synced > 0) {
    writeTracker(tracker)
  }

  return NextResponse.json({ synced, total: readyItems.length })
}
