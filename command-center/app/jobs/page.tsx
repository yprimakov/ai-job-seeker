'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import useSWR from 'swr'
import {
  Plus, Trash2, RefreshCw, Loader2, ExternalLink, Star, Sparkles,
  X, Check, AlertTriangle, Play, Square, ChevronDown, ChevronUp, StopCircle,
} from 'lucide-react'
import { SpotlightCard } from '@/components/SpotlightCard'
import { useWS } from '@/lib/ws-client'
import { formatDate } from '@/lib/utils'

const fetcher = (url: string) => fetch(url).then(r => r.json())

const LS_SELECTED = 'scraper_selected_titles'

type QueueItem = {
  id: string
  url: string
  company?: string
  title?: string
  status: 'pending' | 'processing' | 'ready' | 'failed'
  submittedAt: string
  error?: string
}

type LinkedInJob = {
  title: string
  company: string
  location: string
  salary?: string
  easyApply?: boolean
  url: string
  score?: number
  fit_reason?: string
}

const STATUS_COLORS: Record<string, string> = {
  pending:    'text-yellow-600 dark:text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
  processing: 'text-blue-600 dark:text-blue-400 bg-blue-400/10 border-blue-400/20 animate-pulse',
  ready:      'text-green-600 dark:text-green-400 bg-green-400/10 border-green-400/20',
  failed:     'text-red-600 dark:text-red-400 bg-red-400/10 border-red-400/20',
}

function ScoreBadge({ score }: { score?: number }) {
  if (score == null) return <span className="text-xs text-muted-foreground/40">-</span>
  const color =
    score >= 4 ? 'text-green-600 dark:text-green-400' :
    score >= 3 ? 'text-yellow-600 dark:text-yellow-400' :
    score >= 1 ? 'text-muted-foreground' :
    'text-muted-foreground/40'
  return (
    <span className={`flex items-center gap-1 text-xs font-medium ${color}`}>
      <Star size={10} fill="currentColor" /> {score}
    </span>
  )
}

function StepBadge({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <div className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-500/20 border border-blue-500/40 text-blue-600 dark:text-blue-400 text-xs font-bold shrink-0">
        {n}
      </div>
      <span className="text-sm font-semibold">{label}</span>
    </div>
  )
}

export default function JobsPage() {
  const { data: queue = [], mutate: mutateQueue } = useSWR<QueueItem[]>('/api/jobs/queue', fetcher)
  const { data: results, mutate: mutateResults } = useSWR<{ jobs: LinkedInJob[]; query?: string; date?: string }>(
    '/api/jobs/results', fetcher, { refreshInterval: 0 }
  )
  const { data: titlesData, mutate: mutateTitles } = useSWR<{ titles: string[]; analyzed: boolean }>(
    '/api/jobs/titles', fetcher
  )

  useWS('results_updated', useCallback(() => {
    mutateQueue()
    mutateResults()
    setScraping(false)
    setScrapeOutput(prev => prev ? prev + '\n\nDone. Scroll down to see results.' : '')
  }, [mutateQueue, mutateResults]))

  // Sync scraping state with server sentinel on mount
  useEffect(() => {
    fetch('/api/pipeline/scrape')
      .then(r => r.json())
      .then(d => { if (d.running) setScraping(true) })
      .catch(() => {})
  }, [])

  // ── Scraper state ────────────────────────────────────────────────
  const [selectedTitles, setSelectedTitles] = useState<string[]>([])
  const [addingTitle, setAddingTitle] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [savingTitles, setSavingTitles] = useState(false)
  const [scraping, setScraping] = useState(false)
  const [scrapeRemote, setScrapeRemote] = useState(true)
  const [scrapeEA, setScrapeEA] = useState(true)
  const [scrapeOutput, setScrapeOutput] = useState('')
  const [analyzing, setAnalyzing] = useState(false)

  // ── Results selection state ──────────────────────────────────────
  const [selectedJobs, setSelectedJobs] = useState<Set<number>>(new Set())

  // ── Queue state ──────────────────────────────────────────────────
  const [url, setUrl] = useState('')
  const [adding, setAdding] = useState(false)
  const [showManualAdd, setShowManualAdd] = useState(false)

  // ── Process queue state ──────────────────────────────────────────
  const [processing, setProcessing] = useState(false)
  const [processOutput, setProcessOutput] = useState('')
  const processOutputRef = useRef<HTMLPreElement>(null)

  // Auto-scroll stream output
  useEffect(() => {
    if (processOutputRef.current) {
      processOutputRef.current.scrollTop = processOutputRef.current.scrollHeight
    }
  }, [processOutput])

  // ── Title management ─────────────────────────────────────────────
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LS_SELECTED)
      if (saved) setSelectedTitles(JSON.parse(saved))
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    if (!titlesData?.titles?.length) return
    try {
      const saved = localStorage.getItem(LS_SELECTED)
      if (!saved) {
        setSelectedTitles(titlesData.titles)
        localStorage.setItem(LS_SELECTED, JSON.stringify(titlesData.titles))
      }
    } catch { /* ignore */ }
  }, [titlesData])

  function toggleTitle(title: string) {
    setSelectedTitles(prev => {
      const next = prev.includes(title) ? prev.filter(t => t !== title) : [...prev, title]
      localStorage.setItem(LS_SELECTED, JSON.stringify(next))
      return next
    })
  }

  function selectAll() {
    const all = titlesData?.titles ?? []
    setSelectedTitles(all)
    localStorage.setItem(LS_SELECTED, JSON.stringify(all))
  }

  function selectNone() {
    setSelectedTitles([])
    localStorage.setItem(LS_SELECTED, JSON.stringify([]))
  }

  async function saveTitles(titles: string[]) {
    setSavingTitles(true)
    await fetch('/api/jobs/titles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ titles }),
    })
    mutateTitles({ titles, analyzed: titlesData?.analyzed ?? false }, false)
    setSavingTitles(false)
  }

  async function addTitle() {
    const t = addingTitle.trim()
    if (!t) return
    const current = titlesData?.titles ?? []
    if (current.includes(t)) { setAddingTitle(''); return }
    const next = [...current, t]
    await saveTitles(next)
    setSelectedTitles(prev => {
      const updated = [...prev, t]
      localStorage.setItem(LS_SELECTED, JSON.stringify(updated))
      return updated
    })
    setAddingTitle('')
  }

  async function deleteTitle(title: string) {
    const next = (titlesData?.titles ?? []).filter(t => t !== title)
    await saveTitles(next)
    setSelectedTitles(prev => {
      const updated = prev.filter(t => t !== title)
      localStorage.setItem(LS_SELECTED, JSON.stringify(updated))
      return updated
    })
    setConfirmDelete(null)
  }

  async function analyzeTitles() {
    setAnalyzing(true)
    setScrapeOutput('')
    const res = await fetch('/api/jobs/titles', { method: 'POST' })
    const data = await res.json()
    if (data.titles) {
      mutateTitles(data, false)
      setSelectedTitles(data.titles)
      localStorage.setItem(LS_SELECTED, JSON.stringify(data.titles))
      setScrapeOutput(`Resume analyzed. ${data.titles.length} job titles suggested.`)
    } else {
      setScrapeOutput(data.error ?? 'Failed to analyze resume.')
    }
    setAnalyzing(false)
  }

  async function runScraper() {
    if (selectedTitles.length === 0) {
      setScrapeOutput('Select at least one job title to search.')
      return
    }
    setScraping(true)
    setScrapeOutput('')
    const res = await fetch('/api/pipeline/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ queries: selectedTitles, remote: scrapeRemote, easyApply: scrapeEA }),
    })
    const data = await res.json()
    if (data.ok) {
      setScrapeOutput(data.message)
    } else {
      setScrapeOutput(data.error ?? 'Failed to launch scraper.')
      setScraping(false)
    }
  }

  async function stopScraper() {
    await fetch('/api/pipeline/scrape/stop', { method: 'POST' })
    setScraping(false)
    setScrapeOutput(prev => prev + '\n\nScraper stopped.')
  }

  async function clearResults() {
    await fetch('/api/jobs/results', { method: 'DELETE' })
    mutateResults()
    setSelectedJobs(new Set())
  }

  // ── Results selection ─────────────────────────────────────────────
  const linkedInJobs = results?.jobs ?? []

  function toggleJobSelect(i: number) {
    setSelectedJobs(prev => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  function selectAllJobs() {
    setSelectedJobs(new Set(linkedInJobs.map((_, i) => i)))
  }

  function selectScore4Plus() {
    setSelectedJobs(new Set(
      linkedInJobs.map((j, i) => ({ j, i }))
        .filter(({ j }) => (j.score ?? 0) >= 4)
        .map(({ i }) => i)
    ))
  }

  function clearJobSelection() {
    setSelectedJobs(new Set())
  }

  async function addSelectedToQueue() {
    const jobs = [...selectedJobs].map(i => linkedInJobs[i]).filter(j => j?.url)
    if (jobs.length === 0) return
    await Promise.all(jobs.map(j =>
      fetch('/api/jobs/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: j.url, company: j.company, title: j.title }),
      })
    ))
    mutateQueue()
    setSelectedJobs(new Set())
  }

  // ── Queue management ─────────────────────────────────────────────
  async function addToQueue() {
    if (!url.trim()) return
    setAdding(true)
    await fetch('/api/jobs/queue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
    setUrl('')
    mutateQueue()
    setAdding(false)
  }

  async function removeFromQueue(id: string) {
    await fetch(`/api/jobs/queue/${id}`, { method: 'DELETE' })
    mutateQueue()
  }

  // ── Process queue ────────────────────────────────────────────────
  async function processQueue() {
    const pending = queue.filter(i => i.status === 'pending')
    if (pending.length === 0) return
    setProcessing(true)
    setProcessOutput('')

    try {
      const res = await fetch('/api/pipeline/process-queue', { method: 'POST' })
      if (!res.body) throw new Error('No response body')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        setProcessOutput(prev => prev + decoder.decode(value))
      }
    } catch (err) {
      setProcessOutput(prev => prev + `\nError: ${err instanceof Error ? err.message : String(err)}`)
    }

    setProcessing(false)
    mutateQueue()
    mutateResults()
  }

  const pendingCount = queue.filter(i => i.status === 'pending' || i.status === 'failed').length
  const availableTitles = titlesData?.titles ?? []

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Jobs</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Find, select, and tailor applications in three steps</p>
      </div>

      {/* ── STEP 1: Find New Jobs ── */}
      <SpotlightCard>
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <StepBadge n={1} label="Find New Jobs" />
            <button
              onClick={analyzeTitles}
              disabled={analyzing}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground
                transition-colors disabled:opacity-50"
              title="Analyze resume_base.md with Claude to suggest job titles"
            >
              {analyzing ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
              {analyzing ? 'Analyzing...' : 'Suggest from Resume'}
            </button>
          </div>

          {/* Title chips */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs text-muted-foreground">Search Titles</label>
              <div className="flex gap-2 text-xs text-muted-foreground">
                <button onClick={selectAll} className="hover:text-foreground transition-colors">All</button>
                <span className="opacity-30">·</span>
                <button onClick={selectNone} className="hover:text-foreground transition-colors">None</button>
                <span className="opacity-30">·</span>
                <span className="text-blue-600 dark:text-blue-400">{selectedTitles.length} selected</span>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5 min-h-[52px] p-2 rounded-lg bg-secondary/30 border border-border/40 overflow-hidden">
              {availableTitles.length === 0 && !addingTitle && (
                <p className="text-xs text-muted-foreground self-center mx-auto">
                  Click &quot;Suggest from Resume&quot; to generate titles, or type one below
                </p>
              )}

              {availableTitles.map(title => {
                const isSelected = selectedTitles.includes(title)
                const isPendingDelete = confirmDelete === title

                if (isPendingDelete) {
                  return (
                    <span key={title}
                      className="flex items-center gap-1 px-2 py-1 rounded-full text-xs border
                        bg-red-500/10 border-red-500/40 text-red-600 dark:text-red-400">
                      <AlertTriangle size={9} />
                      <span>Delete &quot;{title}&quot;?</span>
                      <button onClick={() => deleteTitle(title)}
                        className="ml-1 font-semibold hover:text-red-800 dark:hover:text-red-200 transition-colors">
                        Yes
                      </button>
                      <span className="opacity-40">/</span>
                      <button onClick={() => setConfirmDelete(null)}
                        className="hover:text-foreground transition-colors">
                        No
                      </button>
                    </span>
                  )
                }

                return (
                  <span key={title}
                    className={`
                      flex items-center gap-1 pl-2.5 pr-1 py-1 rounded-full text-xs font-medium
                      transition-all duration-150 border group
                      ${isSelected
                        ? 'bg-blue-500/20 border-blue-500/50 text-blue-700 dark:text-blue-300'
                        : 'bg-secondary/60 border-border/40 text-muted-foreground'
                      }
                    `}
                  >
                    <button onClick={() => toggleTitle(title)}
                      className="flex items-center gap-1.5 hover:opacity-80 transition-opacity">
                      {isSelected && <Check size={9} strokeWidth={3} />}
                      {title}
                    </button>
                    <button
                      onClick={e => { e.stopPropagation(); setConfirmDelete(title) }}
                      className="ml-1 p-0.5 rounded-full opacity-0 group-hover:opacity-60
                        hover:!opacity-100 hover:bg-red-500/20 hover:text-red-500
                        transition-all duration-150"
                      title={`Remove "${title}"`}
                    >
                      <X size={9} strokeWidth={2.5} />
                    </button>
                  </span>
                )
              })}

              <input
                value={addingTitle}
                onChange={e => setAddingTitle(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') { e.preventDefault(); addTitle() }
                  if (e.key === 'Escape') setAddingTitle('')
                }}
                placeholder="+ Add title..."
                disabled={savingTitles}
                className="min-w-[120px] px-2 py-1 text-xs bg-transparent outline-none
                  placeholder:text-muted-foreground/40 text-foreground"
              />
            </div>
            <p className="text-xs text-muted-foreground/50">
              Type a title and press Enter to add · Hover a pill and click X to remove permanently
            </p>
          </div>

          {/* Filters + Run button */}
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={scrapeRemote}
                onChange={e => setScrapeRemote(e.target.checked)} className="rounded" />
              Remote only
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={scrapeEA}
                onChange={e => setScrapeEA(e.target.checked)} className="rounded" />
              Easy Apply
            </label>

            <div className="ml-auto flex items-center gap-2">
              {scraping && (
                <button
                  onClick={stopScraper}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                    bg-red-500/10 border border-red-500/40 text-red-600 dark:text-red-400
                    hover:bg-red-500/20 transition-colors"
                >
                  <StopCircle size={13} /> Stop
                </button>
              )}
              <button
                onClick={runScraper}
                disabled={scraping || selectedTitles.length === 0}
                className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium
                  bg-secondary/60 hover:bg-secondary border border-border/60 transition-colors disabled:opacity-50"
              >
                {scraping
                  ? <><Loader2 size={13} className="animate-spin" /> Scraping...</>
                  : <><RefreshCw size={13} /> Run Scraper ({selectedTitles.length})</>
                }
              </button>
            </div>
          </div>

          {scrapeOutput && (
            <pre className="stream-output text-xs p-3 rounded-lg bg-secondary/30 overflow-x-auto whitespace-pre-wrap">
              {scrapeOutput}
            </pre>
          )}
        </div>
      </SpotlightCard>

      {/* ── STEP 2: Review Results & Select ── */}
      <SpotlightCard>
        <div className="p-5">
          <div className="flex items-center justify-between mb-4">
            <StepBadge n={2} label="Review Results & Select" />
            {linkedInJobs.length > 0 && (
              <div className="flex items-center gap-3">
                <p className="text-xs text-muted-foreground">
                  {results?.date && formatDate(results.date)} · {linkedInJobs.length} jobs
                </p>
                <button
                  onClick={clearResults}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground/60
                    hover:text-red-500 dark:hover:text-red-400 transition-colors"
                  title="Clear results list"
                >
                  <Trash2 size={11} /> Clear
                </button>
              </div>
            )}
          </div>

          {linkedInJobs.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground text-sm">
              <RefreshCw size={24} className="mx-auto mb-3 opacity-30" />
              No results yet. Run the scraper above to find matching jobs.
            </div>
          ) : (
            <>
              {/* Bulk action bar */}
              <div className="flex items-center gap-2 mb-3 flex-wrap">
                <button onClick={selectScore4Plus}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                    bg-green-500/10 border border-green-500/30 text-green-700 dark:text-green-400
                    hover:bg-green-500/20 transition-colors">
                  <Star size={10} fill="currentColor" /> Score 4+
                </button>
                <button onClick={selectAllJobs}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                    bg-secondary/60 border border-border/40 text-muted-foreground
                    hover:text-foreground hover:bg-secondary transition-colors">
                  Select All
                </button>
                {selectedJobs.size > 0 && (
                  <>
                    <button onClick={clearJobSelection}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                        bg-secondary/60 border border-border/40 text-muted-foreground
                        hover:text-foreground hover:bg-secondary transition-colors">
                      <X size={10} /> Clear
                    </button>
                    <button
                      onClick={addSelectedToQueue}
                      className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-semibold
                        bg-gradient-to-r from-blue-500 to-blue-600 text-white
                        hover:brightness-110 transition-all shadow-sm shadow-blue-500/30">
                      <Plus size={13} /> Add {selectedJobs.size} to Queue
                    </button>
                  </>
                )}
                {selectedJobs.size === 0 && (
                  <span className="text-xs text-muted-foreground/50 ml-1">
                    Select jobs to add to queue
                  </span>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="data-table w-full">
                  <thead>
                    <tr className="border-b border-border/60">
                      <th className="w-8">
                        <input
                          type="checkbox"
                          checked={selectedJobs.size === linkedInJobs.length && linkedInJobs.length > 0}
                          onChange={e => e.target.checked ? selectAllJobs() : clearJobSelection()}
                          className="rounded"
                        />
                      </th>
                      <th title="Claude Haiku fit score (1-5)">Score</th>
                      <th>Company</th>
                      <th>Title</th>
                      <th>Location</th>
                      <th>Salary</th>
                      <th title="Easy Apply via LinkedIn">EA</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {linkedInJobs.map((job, i) => (
                      <tr
                        key={i}
                        title={job.fit_reason || undefined}
                        className={selectedJobs.has(i) ? 'bg-blue-500/5' : undefined}
                        onClick={() => toggleJobSelect(i)}
                        style={{ cursor: 'pointer' }}
                      >
                        <td onClick={e => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={selectedJobs.has(i)}
                            onChange={() => toggleJobSelect(i)}
                            className="rounded"
                          />
                        </td>
                        <td><ScoreBadge score={job.score} /></td>
                        <td className="font-medium max-w-[120px] truncate">{job.company}</td>
                        <td className="max-w-[200px] truncate text-muted-foreground">{job.title}</td>
                        <td className="text-xs text-muted-foreground max-w-[120px] truncate">{job.location}</td>
                        <td className="text-xs text-muted-foreground">{job.salary || '-'}</td>
                        <td className="text-center">
                          {job.easyApply
                            ? <span className="text-xs text-blue-600 dark:text-blue-400">EA</span>
                            : <span className="text-xs text-muted-foreground">-</span>}
                        </td>
                        <td onClick={e => e.stopPropagation()}>
                          {job.url && (
                            <a href={job.url} target="_blank" rel="noopener noreferrer"
                              className="text-muted-foreground hover:text-foreground transition-colors"
                              title="Open on LinkedIn">
                              <ExternalLink size={11} />
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </SpotlightCard>

      {/* ── STEP 3: Process Queue ── */}
      <SpotlightCard>
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <StepBadge n={3} label="Process Queue" />
            <div className="flex items-center gap-3">
              {queue.length > 0 && (
                <span className="text-xs text-muted-foreground">
                  {queue.filter(i => i.status === 'pending').length} pending · {queue.filter(i => i.status === 'ready').length} ready · {queue.filter(i => i.status === 'failed').length} failed
                </span>
              )}
              <button
                onClick={processQueue}
                disabled={processing || pendingCount === 0}
                className={`
                  flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold transition-all
                  ${pendingCount > 0 && !processing
                    ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white hover:brightness-110 shadow-sm shadow-green-500/30'
                    : 'bg-secondary/60 border border-border/60 text-muted-foreground cursor-not-allowed opacity-50'
                  }
                `}
              >
                {processing
                  ? <><Square size={13} /> Running...</>
                  : <><Play size={13} /> Process {pendingCount > 0 ? `${pendingCount} Job${pendingCount !== 1 ? 's' : ''}` : 'Queue'}</>
                }
              </button>
            </div>
          </div>

          {/* Queue table */}
          {queue.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-6">
              Queue is empty. Select jobs above and click &quot;Add to Queue&quot;.
            </p>
          ) : (
            <div className="space-y-2">
              {queue.map(item => (
                <div key={item.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-secondary/30 border border-border/40">
                  <div className="min-w-0 flex-1">
                    {item.company ? (
                      <p className="text-xs font-medium">{item.company}{item.title ? ` — ${item.title}` : ''}</p>
                    ) : null}
                    <p className="text-xs font-mono truncate text-muted-foreground/60">{item.url}</p>
                    {item.error && (
                      <p className="text-xs text-red-600 dark:text-red-400 mt-0.5 truncate" title={item.error}>
                        {item.error}
                      </p>
                    )}
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium border shrink-0 ${STATUS_COLORS[item.status]}`}>
                    {item.status}
                  </span>
                  <p className="text-xs text-muted-foreground/50 shrink-0 hidden sm:block">
                    {formatDate(item.submittedAt)}
                  </p>
                  <button onClick={() => removeFromQueue(item.id)}
                    className="text-muted-foreground hover:text-red-600 dark:hover:text-red-400 transition-colors shrink-0">
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Process output stream */}
          {processOutput && (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground font-medium">Output</p>
              <pre ref={processOutputRef}
                className="stream-output text-xs p-3 rounded-lg bg-secondary/30 overflow-auto whitespace-pre-wrap max-h-64">
                {processOutput}
              </pre>
            </div>
          )}

          {/* Manual URL add — collapsed by default */}
          <div className="border-t border-border/40 pt-3">
            <button
              onClick={() => setShowManualAdd(v => !v)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {showManualAdd ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Add job URL manually (Greenhouse, Lever, Workday)
            </button>
            {showManualAdd && (
              <div className="flex gap-2 mt-2">
                <input
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && addToQueue()}
                  placeholder="https://boards.greenhouse.io/..."
                  className="flex-1 px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60
                    focus:outline-none focus:ring-1 focus:ring-blue-500 placeholder:text-muted-foreground/50"
                />
                <button onClick={addToQueue} disabled={adding || !url.trim()}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-white
                    bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600
                    hover:brightness-110 transition-all disabled:opacity-50 flex items-center gap-2">
                  {adding ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                  Add
                </button>
              </div>
            )}
          </div>
        </div>
      </SpotlightCard>
    </div>
  )
}
