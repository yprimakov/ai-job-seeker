'use client'

import { useState, useCallback, useEffect } from 'react'
import useSWR from 'swr'
import { Plus, Trash2, RefreshCw, Loader2, ExternalLink, Star, Sparkles, X, Check, AlertTriangle } from 'lucide-react'
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
  pending:    'text-yellow-600 dark:text-yellow-400 bg-yellow-400/10',
  processing: 'text-blue-600 dark:text-blue-400 bg-blue-400/10',
  ready:      'text-green-600 dark:text-green-400 bg-green-400/10',
  failed:     'text-red-600 dark:text-red-400 bg-red-400/10',
}

function ScoreBadge({ score }: { score?: number }) {
  if (score == null) return null
  const color = score >= 4 ? 'text-green-600 dark:text-green-400' : score >= 3 ? 'text-yellow-600 dark:text-yellow-400' : 'text-muted-foreground'
  return (
    <span className={`flex items-center gap-1 text-xs font-medium ${color}`}>
      <Star size={10} fill="currentColor" /> {score}
    </span>
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
    setScrapeOutput(prev => prev ? prev + '\n\nResults loaded.' : '')
  }, [mutateQueue, mutateResults]))

  const [url, setUrl] = useState('')
  const [adding, setAdding] = useState(false)

  // Multi-select state — persisted in localStorage
  const [selectedTitles, setSelectedTitles] = useState<string[]>([])
  const [addingTitle, setAddingTitle] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [savingTitles, setSavingTitles] = useState(false)
  const [scraping, setScraping] = useState(false)
  const [scrapeRemote, setScrapeRemote] = useState(true)
  const [scrapeEA, setScrapeEA] = useState(true)
  const [scrapeOutput, setScrapeOutput] = useState('')
  const [analyzing, setAnalyzing] = useState(false)

  // Load persisted selection on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LS_SELECTED)
      if (saved) setSelectedTitles(JSON.parse(saved))
    } catch { /* ignore */ }
  }, [])

  // Sync new titlesData — auto-select all if nothing persisted yet
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
    // Auto-select the newly added title
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

  const availableTitles = titlesData?.titles ?? []
  const linkedInJobs = results?.jobs ?? []

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Jobs</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Queue management and LinkedIn results</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* URL submission */}
        <SpotlightCard>
          <div className="p-5 space-y-4">
            <h2 className="text-sm font-semibold">Add Job URL to Queue</h2>
            <div className="flex gap-2">
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

            {/* Queue table */}
            <div className="space-y-2">
              {queue.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-4">Queue is empty</p>
              )}
              {queue.map(item => (
                <div key={item.id} className="flex items-center gap-3 p-3 rounded-lg bg-secondary/30 border border-border/40">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-mono truncate text-muted-foreground">{item.url}</p>
                    {item.company && (
                      <p className="text-xs font-medium mt-0.5">{item.company} — {item.title}</p>
                    )}
                    <p className="text-xs text-muted-foreground/60 mt-0.5">{formatDate(item.submittedAt)}</p>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${STATUS_COLORS[item.status]}`}>
                    {item.status}
                  </span>
                  <button onClick={() => removeFromQueue(item.id)}
                    className="text-muted-foreground hover:text-red-600 dark:hover:text-red-400 transition-colors shrink-0">
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </SpotlightCard>

        {/* LinkedIn scraper */}
        <SpotlightCard>
          <div className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">Find New Jobs</h2>
              <button
                onClick={analyzeTitles}
                disabled={analyzing}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground
                  transition-colors disabled:opacity-50"
                title="Analyze resume_base.md with Claude to suggest job titles"
              >
                {analyzing
                  ? <Loader2 size={11} className="animate-spin" />
                  : <Sparkles size={11} />
                }
                {analyzing ? 'Analyzing...' : 'Analyze Resume'}
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

              <div className="flex flex-wrap gap-1.5 min-h-[60px] p-2 rounded-lg bg-secondary/30 border border-border/40">
                {availableTitles.length === 0 && !addingTitle && (
                  <p className="text-xs text-muted-foreground self-center mx-auto">
                    Click "Analyze Resume" to generate suggestions, or add a title below
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
                        <button
                          onClick={() => deleteTitle(title)}
                          className="ml-1 font-semibold hover:text-red-800 dark:hover:text-red-200 transition-colors">
                          Yes
                        </button>
                        <span className="opacity-40">/</span>
                        <button
                          onClick={() => setConfirmDelete(null)}
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
                      <button
                        onClick={() => toggleTitle(title)}
                        className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
                      >
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

                {/* Inline add-title input */}
                <input
                  value={addingTitle}
                  onChange={e => setAddingTitle(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') { e.preventDefault(); addTitle() }
                    if (e.key === 'Escape') setAddingTitle('')
                  }}
                  placeholder="+ Add title..."
                  disabled={savingTitles}
                  className="flex-1 min-w-[120px] px-2 py-1 text-xs bg-transparent outline-none
                    placeholder:text-muted-foreground/40 text-foreground"
                />
              </div>
              <p className="text-xs text-muted-foreground/50">
                Type a title and press Enter to add · Hover a pill and click X to remove permanently
              </p>
            </div>

            {/* Filters */}
            <div className="flex gap-4">
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
            </div>

            <button
              onClick={runScraper}
              disabled={scraping || selectedTitles.length === 0}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                bg-secondary/60 hover:bg-secondary border border-border/60 transition-colors disabled:opacity-50"
            >
              {scraping
                ? <><Loader2 size={13} className="animate-spin" /> Running in external terminal...</>
                : <>Run LinkedIn Scraper ({selectedTitles.length})</>
              }
            </button>

            {scrapeOutput && (
              <pre className="stream-output text-xs p-3 rounded-lg bg-secondary/30 overflow-x-auto whitespace-pre-wrap">
                {scrapeOutput}
              </pre>
            )}
          </div>
        </SpotlightCard>
      </div>

      {/* LinkedIn results */}
      {linkedInJobs.length > 0 && (
        <SpotlightCard>
          <div className="p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-sm font-semibold">LinkedIn Results</h2>
                {results?.query && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Query: {results.query} {results.date && `· ${formatDate(results.date)}`}
                  </p>
                )}
              </div>
              <span className="text-xs text-muted-foreground">{linkedInJobs.length} jobs</span>
            </div>
            <div className="overflow-x-auto">
              <table className="data-table w-full">
                <thead>
                  <tr className="border-b border-border/60">
                    <th>Score</th>
                    <th>Company</th>
                    <th>Title</th>
                    <th>Location</th>
                    <th>Salary</th>
                    <th>EA</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {linkedInJobs.map((job, i) => (
                    <tr key={i}>
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
                      <td>
                        <div className="flex items-center gap-2">
                          {job.url && (
                            <a href={job.url} target="_blank" rel="noopener noreferrer"
                              className="text-muted-foreground hover:text-foreground transition-colors">
                              <ExternalLink size={11} />
                            </a>
                          )}
                          <button
                            onClick={() => setUrl(job.url)}
                            className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-500 dark:hover:text-blue-300 transition-colors">
                            Queue
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </SpotlightCard>
      )}

      {linkedInJobs.length === 0 && (
        <SpotlightCard>
          <div className="p-10 text-center text-muted-foreground text-sm">
            <RefreshCw size={24} className="mx-auto mb-3 opacity-30" />
            No LinkedIn results yet. Select job titles above and run the scraper.
          </div>
        </SpotlightCard>
      )}
    </div>
  )
}
