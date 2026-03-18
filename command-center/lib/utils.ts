import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

function parseLocalDate(dateStr: string): Date | null {
  const m = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (m) return new Date(parseInt(m[1]), parseInt(m[2]) - 1, parseInt(m[3]))
  const d = new Date(dateStr)
  return isNaN(d.getTime()) ? null : d
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  try {
    const d = parseLocalDate(dateStr)
    if (!d) return dateStr
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch { return dateStr }
}

export function formatShortDate(dateStr: string): string {
  if (!dateStr) return ''
  try {
    const d = parseLocalDate(dateStr)
    if (!d) return dateStr
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch { return dateStr }
}

export function isFollowUpDue(dateStr: string): boolean {
  if (!dateStr) return false
  try {
    return new Date(dateStr) <= new Date()
  } catch { return false }
}

export function responseRate(rows: TrackerRow[]): number {
  if (!rows.length) return 0
  const responded = rows.filter(r => r['Date Response Received']?.trim())
  return Math.round((responded.length / rows.length) * 100)
}

export interface TrackerRow {
  'Date Applied': string
  'Company': string
  'Job Title': string
  'LinkedIn URL': string
  'Work Mode': string
  'Salary Range': string
  'Easy Apply': string
  'Application Status': string
  'Notes': string
  'Tailored Resume File': string
  'Follow Up Date': string
  'Date Response Received': string
  'Response Type': string
  _id?: number
  // Enriched server-side (not stored in CSV)
  _slug?: string                // application folder name — stable URL identifier
  match_score?: number
  ats_coverage_before?: number  // keywords found in base resume
  ats_coverage_after?: number   // keywords found in tailored resume
}

export interface QARow {
  'Question ID': string
  'Question': string
  'Context (where it appeared)': string
  'Answer': string
  'Date Answered': string
  'Notes': string
  _id?: number
}

export const STATUS_ORDER = [
  'Applied', 'Phone Screen', 'Interview', 'Assessment', 'Offer', 'Rejected', 'Ghosted',
]

export function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    'Applied': 'badge-applied',
    'Phone Screen': 'badge-phone-screen',
    'Interview': 'badge-interview',
    'Assessment': 'badge-assessment',
    'Offer': 'badge-offer',
    'Rejected': 'badge-rejected',
    'Ghosted': 'badge-ghosted',
  }
  return map[status] ?? 'badge-applied'
}
