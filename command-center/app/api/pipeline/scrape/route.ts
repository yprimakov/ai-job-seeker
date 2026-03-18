import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'
import fs from 'fs'

export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({})) as {
    queries?: string[]   // multi-title run
    query?: string       // single query (legacy)
    remote?: boolean
    easyApply?: boolean
    pages?: number
  }

  // Resolve list of queries
  const queries: string[] = []
  if (body.queries?.length) {
    queries.push(...body.queries.filter(q => q.trim()))
  } else if (body.query?.trim()) {
    queries.push(body.query.trim())
  }

  if (queries.length === 0) {
    return NextResponse.json({ ok: false, error: 'At least one search query is required.' }, { status: 400 })
  }

  const rootDir  = path.resolve(process.cwd(), '..')
  const script   = path.join(rootDir, 'pipeline', 'linkedin_scraper.py')
  const merger   = path.join(rootDir, 'pipeline', 'merge_linkedin_results.py')

  const flags: string[] = []
  if (body.remote !== false)   flags.push('--remote')
  if (body.easyApply !== false) flags.push('--easy-apply')
  if (body.pages)               flags.push(`--pages ${body.pages}`)

  const batLines: string[] = ['@echo off', `cd /d "${rootDir}"`, 'echo Running LinkedIn scraper...', 'echo.']

  if (queries.length === 1) {
    // Single query — write straight to linkedin_results.md
    batLines.push(`python "${script}" --query "${queries[0]}" ${flags.join(' ')}`)
  } else {
    // Multiple queries — write to temp files then merge
    queries.forEach((q, i) => {
      const tmpOut = path.join(rootDir, 'jobs', `.tmp_results_${i}.md`)
      batLines.push(`echo Searching: ${q}`)
      batLines.push(`python "${script}" --query "${q}" ${flags.join(' ')} --output "${tmpOut}"`)
      batLines.push('echo.')
    })
    // Merge with query list as args (used in the results header)
    const queryArgs = queries.map(q => `"${q}"`).join(' ')
    batLines.push(`python "${merger}" ${queryArgs}`)
  }

  batLines.push('echo.', 'echo Done! Results saved to jobs/linkedin_results.md.', '')

  const batPath = path.join(rootDir, '.scraper_launch.bat')
  fs.writeFileSync(batPath, batLines.join('\r\n'))

  const proc = spawn(
    'cmd.exe',
    ['/c', 'start', 'cmd', '/k', batPath],
    { detached: true, stdio: 'ignore', shell: false }
  )
  proc.unref()

  const label = queries.length === 1
    ? `"${queries[0]}"`
    : `${queries.length} queries (${queries.join(', ')})`

  return NextResponse.json({
    ok: true,
    message: `Scraper launched for ${label}. A Chrome window will open. Results will appear automatically when complete.`,
  })
}
