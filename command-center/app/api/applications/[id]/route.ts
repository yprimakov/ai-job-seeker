import { NextRequest, NextResponse } from 'next/server'
import { readTracker, writeTracker } from '@/lib/csv'
import type { TrackerRow } from '@/lib/utils'

export const dynamic = 'force-dynamic'

// PATCH /api/applications/[id]  — update any fields on a tracker row
export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const idx = parseInt(params.id, 10)
  if (isNaN(idx)) {
    return NextResponse.json({ error: 'Invalid id' }, { status: 400 })
  }

  const body = await req.json().catch(() => ({})) as Partial<TrackerRow>
  const rows = readTracker()

  if (idx < 0 || idx >= rows.length) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 })
  }

  rows[idx] = { ...rows[idx], ...body, _id: idx }
  writeTracker(rows)

  return NextResponse.json(rows[idx])
}

// POST /api/applications/[id]/response  — handled in the sub-route file
// (kept here as a no-op to avoid 404 on the base path)
