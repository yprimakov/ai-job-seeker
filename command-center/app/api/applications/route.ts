import { NextResponse } from 'next/server'
import { readTracker, APPS_DIR } from '@/lib/csv'
import type { TrackerRow } from '@/lib/utils'
import fs from 'fs'
import path from 'path'

export const dynamic = 'force-dynamic'

const ROOT = path.resolve(process.cwd(), '..')
const BASE_RESUME_PATH = path.join(ROOT, 'pipeline', 'resume_base.md')

function norm(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]/g, '')
}

function kwCoverage(keywords: string[], text: string): number | null {
  if (!keywords.length) return null
  const t = text.toLowerCase()
  const found = keywords.filter(kw => t.includes(kw.toLowerCase())).length
  return Math.round((found / keywords.length) * 100)
}

// Find the best-matching application folder for a given company + job title.
// Folders are named YYYYMMDD_CompanyName_JobTitle (underscored, truncated).
// Strategy: filter to company matches first, then rank by title word overlap.
function findAppFolder(company: string, title: string): string | null {
  if (!fs.existsSync(APPS_DIR)) return null
  const co = norm(company)
  if (!co) return null

  let candidates: string[]
  try {
    candidates = fs.readdirSync(APPS_DIR)
  } catch { return null }

  const titleWords = norm(title).match(/[a-z0-9]{3,}/g) ?? []

  let best: string | null = null
  let bestScore = -1

  for (const folder of candidates) {
    // Skip folders that don't have an analysis.json — they're empty placeholders
    if (!fs.existsSync(path.join(APPS_DIR, folder, 'analysis.json'))) continue

    const body = norm(folder.replace(/^\d{8}_/, ''))
    const firstSegment = norm(folder.replace(/^\d{8}_/, '').split('_')[0])

    // Must match on company (first word of folder vs normalized company)
    const coMatch = body.startsWith(co) || co.startsWith(firstSegment)
    if (!coMatch) continue

    // Score by how many title words appear in the full folder body
    const score = titleWords.filter(w => body.includes(w)).length
    if (score > bestScore) {
      bestScore = score
      best = path.join(APPS_DIR, folder)
    }
  }

  return best
}

function enrichRow(row: TrackerRow, baseResumeText: string | null): TrackerRow {
  const folder = findAppFolder(row.Company ?? '', row['Job Title'] ?? '')
  if (!folder) return row

  const analysisPath = path.join(folder, 'analysis.json')
  if (!fs.existsSync(analysisPath)) return row

  let analysis: Record<string, unknown>
  try {
    analysis = JSON.parse(fs.readFileSync(analysisPath, 'utf-8'))
  } catch { return row }

  const keywords: string[] = (analysis.keywords_ats ?? analysis.ats_keywords ?? []) as string[]
  const matchScore = typeof analysis.match_score === 'number' ? analysis.match_score : undefined

  let atsBefore: number | undefined
  let atsAfter: number | undefined

  if (keywords.length > 0) {
    if (baseResumeText) {
      atsBefore = kwCoverage(keywords, baseResumeText) ?? undefined
    }
    const resumeMdPath = path.join(folder, 'resume.md')
    if (fs.existsSync(resumeMdPath)) {
      const tailoredText = fs.readFileSync(resumeMdPath, 'utf-8')
      atsAfter = kwCoverage(keywords, tailoredText) ?? undefined
    }
  }

  return {
    ...row,
    _slug: path.basename(folder),
    match_score: matchScore,
    ats_coverage_before: atsBefore,
    ats_coverage_after: atsAfter,
  }
}

export async function GET() {
  const rows = readTracker()
  const baseResumeText = fs.existsSync(BASE_RESUME_PATH)
    ? fs.readFileSync(BASE_RESUME_PATH, 'utf-8')
    : null
  const enriched = rows.map(r => enrichRow(r, baseResumeText))
  return NextResponse.json(enriched)
}
