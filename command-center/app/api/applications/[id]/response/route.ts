import { NextRequest, NextResponse } from 'next/server'
import { readTracker, writeTracker } from '@/lib/csv'

export const dynamic = 'force-dynamic'

// POST /api/applications/[id]/response
// Body: { responseType: string, status?: string, date?: string }
export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const idx = parseInt(params.id, 10)
  if (isNaN(idx)) {
    return NextResponse.json({ error: 'Invalid id' }, { status: 400 })
  }

  const body = await req.json().catch(() => ({})) as {
    responseType?: string
    status?: string
    date?: string
  }

  const rows = readTracker()
  if (idx < 0 || idx >= rows.length) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 })
  }

  const today = new Date().toISOString().slice(0, 10)

  rows[idx] = {
    ...rows[idx],
    'Date Response Received': body.date ?? today,
    'Response Type': body.responseType ?? rows[idx]['Response Type'],
    'Application Status': body.status ?? rows[idx]['Application Status'],
    _id: idx,
  }

  writeTracker(rows)
  return NextResponse.json(rows[idx])
}
