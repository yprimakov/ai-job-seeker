'use client'

import { useState, useMemo, useCallback, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import useSWR from 'swr'
import Link from 'next/link'
import {
  ArrowUpDown, ExternalLink, ChevronUp, ChevronDown, Search, Filter,
  Download, Ghost, X, CheckSquare,
} from 'lucide-react'
import { SpotlightCard } from '@/components/SpotlightCard'
import { StatusBadge } from '@/components/StatusBadge'
import { useWS } from '@/lib/ws-client'
import { formatShortDate, isFollowUpDue, type TrackerRow, STATUS_ORDER } from '@/lib/utils'

const fetcher = (url: string) => fetch(url).then(r => r.json())

type SortField = keyof TrackerRow
type SortDir = 'asc' | 'desc'

export default function ApplicationsPage() {
  const { data: rows = [], mutate } = useSWR<TrackerRow[]>('/api/applications', fetcher)
  useWS('tracker_updated', useCallback(() => mutate(), [mutate]))

  const searchParams = useSearchParams()

  const [search, setSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterMode, setFilterMode] = useState('')
  const [filterEA, setFilterEA] = useState(false)
  const [filterDue, setFilterDue] = useState(false)
  const [sort, setSort] = useState<{ field: SortField; dir: SortDir }>({
    field: 'Date Applied', dir: 'desc',
  })
  const [updatingId, setUpdatingId] = useState<number | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [bulkUpdating, setBulkUpdating] = useState(false)

  // Read ?due=1 from URL on mount
  useEffect(() => {
    if (searchParams.get('due') === '1') setFilterDue(true)
  }, [searchParams])

  const filtered = useMemo(() => {
    let r = [...rows]
    if (search) {
      const q = search.toLowerCase()
      r = r.filter(row =>
        row.Company?.toLowerCase().includes(q) ||
        row['Job Title']?.toLowerCase().includes(q)
      )
    }
    if (filterStatus) r = r.filter(row => row['Application Status'] === filterStatus)
    if (filterMode) r = r.filter(row => row['Work Mode'] === filterMode)
    if (filterEA) r = r.filter(row => row['Easy Apply'] === 'Yes')
    if (filterDue) r = r.filter(row => isFollowUpDue(row['Follow Up Date']))

    r.sort((a, b) => {
      const av = (a[sort.field] ?? '') as string
      const bv = (b[sort.field] ?? '') as string
      return sort.dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
    })
    return r
  }, [rows, search, filterStatus, filterMode, filterEA, filterDue, sort])

  function toggleSort(field: SortField) {
    setSort(s => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'desc' }
    )
  }

  function SortIcon({ field }: { field: SortField }) {
    if (sort.field !== field) return <ArrowUpDown size={12} className="opacity-30" />
    return sort.dir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
  }

  async function updateStatus(row: TrackerRow, status: string) {
    setUpdatingId(row._id ?? null)
    await fetch(`/api/applications/${row._id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 'Application Status': status }),
    })
    mutate()
    setUpdatingId(null)
  }

  function toggleSelect(id: number) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    if (selected.size === filtered.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(filtered.map(r => r._id!).filter(id => id != null)))
    }
  }

  async function bulkGhost() {
    setBulkUpdating(true)
    await Promise.all([...selected].map(id =>
      fetch(`/api/applications/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 'Application Status': 'Ghosted' }),
      })
    ))
    setSelected(new Set())
    setBulkUpdating(false)
    mutate()
  }

  function exportCSV() {
    const toExport = filtered.filter(r => selected.size === 0 || selected.has(r._id!))
    const headers = ['Date Applied', 'Company', 'Job Title', 'Work Mode', 'Easy Apply',
      'Application Status', 'Match Score', 'ATS Before', 'ATS After', 'Response Type', 'Follow Up Date', 'LinkedIn URL']
    const rows = toExport.map(r => [
      r['Date Applied'] ?? '',
      r.Company ?? '',
      r['Job Title'] ?? '',
      r['Work Mode'] ?? '',
      r['Easy Apply'] ?? '',
      r['Application Status'] ?? '',
      r.match_score ?? '',
      r.ats_coverage_before ?? '',
      r.ats_coverage_after ?? '',
      r['Response Type'] ?? '',
      r['Follow Up Date'] ?? '',
      r['LinkedIn URL'] ?? '',
    ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))

    const csv = [headers.join(','), ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `applications_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const allStatuses = STATUS_ORDER
  const allModes = ['Remote', 'Hybrid', 'On-site']
  const allSelected = filtered.length > 0 && selected.size === filtered.length
  const someSelected = selected.size > 0

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Applications</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {filtered.length} of {rows.length} shown
          </p>
        </div>
        <button onClick={exportCSV}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-secondary/60
            hover:bg-secondary border border-border/60 transition-colors text-muted-foreground hover:text-foreground">
          <Download size={13} />
          Export CSV
        </button>
      </div>

      {/* Filters */}
      <SpotlightCard>
        <div className="p-4 flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-48">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search company or title..."
              className="w-full pl-8 pr-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60
                focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
            className="px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60 focus:outline-none">
            <option value="">All Statuses</option>
            {allStatuses.map(s => <option key={s}>{s}</option>)}
          </select>

          <select value={filterMode} onChange={e => setFilterMode(e.target.value)}
            className="px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60 focus:outline-none">
            <option value="">All Modes</option>
            {allModes.map(m => <option key={m}>{m}</option>)}
          </select>

          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={filterEA}
              onChange={e => setFilterEA(e.target.checked)}
              className="rounded" />
            Easy Apply
          </label>

          <label className="flex items-center gap-2 text-sm cursor-pointer text-orange-600 dark:text-orange-400">
            <input type="checkbox" checked={filterDue}
              onChange={e => setFilterDue(e.target.checked)}
              className="rounded" />
            Follow-up Due
          </label>
        </div>
      </SpotlightCard>

      {/* Bulk action bar */}
      {someSelected && (
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-sm">
          <span className="font-medium text-blue-600 dark:text-blue-400">{selected.size} selected</span>
          <div className="flex-1" />
          <button onClick={bulkGhost} disabled={bulkUpdating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
              bg-slate-500/20 hover:bg-slate-500/30 border border-slate-500/30 transition-colors
              text-slate-600 dark:text-slate-400 disabled:opacity-50">
            <Ghost size={12} /> Mark as Ghosted
          </button>
          <button onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
              bg-secondary/60 hover:bg-secondary border border-border/60 transition-colors">
            <Download size={12} /> Export Selected
          </button>
          <button onClick={() => setSelected(new Set())}
            className="p-1.5 rounded-lg hover:bg-secondary/60 transition-colors text-muted-foreground">
            <X size={13} />
          </button>
        </div>
      )}

      {/* Table */}
      <SpotlightCard>
        <div className="overflow-x-auto">
          <table className="data-table w-full">
            <thead>
              <tr className="border-b border-border/60">
                <th className="w-8 px-3">
                  <button onClick={toggleSelectAll} className="text-muted-foreground hover:text-foreground transition-colors">
                    {allSelected
                      ? <CheckSquare size={14} className="text-blue-600 dark:text-blue-400" />
                      : <div className="w-3.5 h-3.5 rounded border border-border/60" />
                    }
                  </button>
                </th>
                <th className="sortable" onClick={() => toggleSort('Date Applied')}>
                  <span className="flex items-center gap-1">Date <SortIcon field="Date Applied" /></span>
                </th>
                <th className="sortable" onClick={() => toggleSort('Company')}>
                  <span className="flex items-center gap-1">Company <SortIcon field="Company" /></span>
                </th>
                <th className="sortable" onClick={() => toggleSort('Job Title')}>
                  <span className="flex items-center gap-1">Title <SortIcon field="Job Title" /></span>
                </th>
                <th>Mode</th>
                <th>EA</th>
                <th className="sortable" onClick={() => toggleSort('Application Status')}>
                  <span className="flex items-center gap-1">Status <SortIcon field="Application Status" /></span>
                </th>
                <th title="Match score from JD analysis">Score</th>
                <th title="ATS keyword coverage: base resume → tailored resume">ATS</th>
                <th>Response</th>
                <th className="sortable" onClick={() => toggleSort('Follow Up Date')}>
                  <span className="flex items-center gap-1">Follow-up <SortIcon field="Follow Up Date" /></span>
                </th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(row => {
                const due = isFollowUpDue(row['Follow Up Date']) && row['Application Status'] === 'Applied'
                const score = row.match_score
                const scoreColor = score == null ? '' : score >= 80 ? 'text-green-600 dark:text-green-400' : score >= 60 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'
                const before = row.ats_coverage_before
                const after = row.ats_coverage_after
                const isSelected = row._id != null && selected.has(row._id)
                return (
                  <tr key={row._id} className={`${due ? 'bg-orange-500/5' : ''} ${isSelected ? 'bg-blue-500/5' : ''}`}>
                    <td className="px-3">
                      <button onClick={() => row._id != null && toggleSelect(row._id)}
                        className="text-muted-foreground hover:text-foreground transition-colors">
                        {isSelected
                          ? <CheckSquare size={14} className="text-blue-600 dark:text-blue-400" />
                          : <div className="w-3.5 h-3.5 rounded border border-border/60" />
                        }
                      </button>
                    </td>
                    <td className="text-muted-foreground text-xs whitespace-nowrap">
                      {formatShortDate(row['Date Applied'])}
                    </td>
                    <td className="font-medium max-w-[120px] truncate">{row.Company}</td>
                    <td className="max-w-[180px] truncate text-muted-foreground">{row['Job Title']}</td>
                    <td>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-secondary/60 text-muted-foreground">
                        {row['Work Mode'] || '-'}
                      </span>
                    </td>
                    <td className="text-center">
                      {row['Easy Apply'] === 'Yes'
                        ? <span className="text-xs text-blue-600 dark:text-blue-400">EA</span>
                        : <span className="text-xs text-muted-foreground">-</span>
                      }
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={row['Application Status']} />
                        <div className="relative group">
                          <button className="text-xs text-muted-foreground hover:text-foreground transition-colors p-0.5">
                            <Filter size={10} />
                          </button>
                          <div className="absolute left-0 top-full mt-1 bg-background/95 backdrop-blur-md border border-border
                            rounded-lg shadow-xl z-30 py-1 hidden group-hover:block min-w-[140px]">
                            {STATUS_ORDER.map(s => (
                              <button key={s} onClick={() => updateStatus(row, s)}
                                className="w-full text-left px-3 py-1.5 text-xs hover:bg-secondary/60 transition-colors">
                                {s}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className={`text-xs font-semibold tabular-nums ${scoreColor}`}>
                      {score != null ? score : <span className="text-muted-foreground font-normal">-</span>}
                    </td>
                    <td className="text-xs tabular-nums">
                      {before != null || after != null ? (
                        <span className="flex items-center gap-1">
                          <span className="text-muted-foreground">{before ?? '?'}%</span>
                          <span className="text-muted-foreground/40">→</span>
                          <span className={after != null ? (after >= 70 ? 'text-green-600 dark:text-green-400' : after >= 50 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400') : 'text-muted-foreground'}>
                            {after ?? '?'}%
                          </span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="text-xs text-muted-foreground">
                      {row['Response Type'] || '-'}
                    </td>
                    <td className={`text-xs whitespace-nowrap ${due ? 'text-orange-600 dark:text-orange-400 font-medium' : 'text-muted-foreground'}`}>
                      {formatShortDate(row['Follow Up Date'])}
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <Link href={`/applications/${row._slug ?? row._id}`}
                          className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-500 dark:hover:text-blue-300 transition-colors">
                          View
                        </Link>
                        {row['LinkedIn URL'] && (
                          <a href={row['LinkedIn URL']} target="_blank" rel="noopener noreferrer"
                            className="text-muted-foreground hover:text-foreground transition-colors">
                            <ExternalLink size={11} />
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {!filtered.length && (
            <div className="py-12 text-center text-muted-foreground text-sm">
              No applications match your filters.
            </div>
          )}
        </div>
      </SpotlightCard>
    </div>
  )
}
