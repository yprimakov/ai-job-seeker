'use client'

import { useState, useCallback } from 'react'
import useSWR from 'swr'
import {
  Briefcase, TrendingUp, Activity, Clock, HelpCircle,
  Plus, Search, RefreshCw, Loader2, CheckCircle, AlertCircle,
} from 'lucide-react'
import { MetricCard } from '@/components/MetricCard'
import { SpotlightCard } from '@/components/SpotlightCard'
import { StatusBadge } from '@/components/StatusBadge'
import { useWS } from '@/lib/ws-client'
import { formatDate } from '@/lib/utils'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

const fetcher = (url: string) => fetch(url).then(r => r.json())

const STATUS_COLORS: Record<string, string> = {
  Applied: '#3b82f6',
  'Phone Screen': '#38bdf8',
  Interview: '#a855f7',
  Assessment: '#fb923c',
  Offer: '#22c55e',
  Rejected: '#ef4444',
  Ghosted: '#64748b',
}

export default function Dashboard() {
  const { data: analytics, mutate: mutateAnalytics } = useSWR('/api/analytics', fetcher, { refreshInterval: 0 })
  const { data: activity, mutate: mutateActivity } = useSWR('/api/activity', fetcher, { refreshInterval: 0 })
  const [jobUrlModal, setJobUrlModal] = useState(false)
  const [jobUrl, setJobUrl] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitResult, setSubmitResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [scraperRunning, setScraperRunning] = useState(false)
  const [followupRunning, setFollowupRunning] = useState(false)

  const refresh = useCallback(() => {
    mutateAnalytics()
    mutateActivity()
  }, [mutateAnalytics, mutateActivity])

  useWS('tracker_updated', refresh)
  useWS('qa_updated', refresh)

  async function submitJob() {
    if (!jobUrl.trim()) return
    setSubmitting(true)
    const res = await fetch('/api/jobs/queue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: jobUrl }),
    })
    const data = await res.json()
    setSubmitResult({ ok: res.ok, msg: res.ok ? `Added to queue: ${data.id}` : 'Failed to add.' })
    setSubmitting(false)
    setJobUrl('')
  }

  async function runScraper() {
    setScraperRunning(true)
    await fetch('/api/pipeline/scrape', { method: 'POST' })
    setScraperRunning(false)
    refresh()
  }

  async function runFollowup() {
    setFollowupRunning(true)
    await fetch('/api/pipeline/followup', { method: 'POST' })
    setFollowupRunning(false)
  }

  const funnelData = analytics?.byStatus ?? []
  const a = analytics ?? {}

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Job search pipeline overview</p>
        </div>
        <button onClick={refresh} className="p-2 rounded-lg hover:bg-secondary/60 transition-colors">
          <RefreshCw size={15} className="text-muted-foreground" />
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <MetricCard label="Total Apps" value={a.total ?? 0} icon={Briefcase}
          sub="all time" />
        <MetricCard label="Response Rate" value={`${a.responseRate ?? 0}%`} icon={TrendingUp}
          accent sub={`${a.responded ?? 0} of ${a.total ?? 0}`} />
        <MetricCard label="Active Pipeline" value={a.active ?? 0} icon={Activity}
          sub="not rejected/ghosted" />
        <MetricCard label="Follow-ups Due" value={a.followUpDue ?? 0} icon={Clock}
          warning={!!a.followUpDue} sub="today or overdue"
          href="/applications?due=1" />
        <MetricCard label="Unanswered Q&A" value={a.unansweredQA ?? 0} icon={HelpCircle}
          warning={!!a.unansweredQA} sub="needs your input"
          href="/qa" />
      </div>

      {/* Charts + Activity row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Pipeline funnel */}
        <div className="lg:col-span-2">
          <SpotlightCard>
            <div className="p-5">
              <h2 className="text-sm font-semibold mb-4">Pipeline Funnel</h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={funnelData} layout="vertical" barCategoryGap="30%">
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="status" width={96}
                    tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(2,6,23,0.9)', border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 8, fontSize: 12,
                    }}
                  />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {funnelData.map((entry: { status: string }) => (
                      <Cell key={entry.status}
                        fill={STATUS_COLORS[entry.status] ?? '#3b82f6'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </SpotlightCard>
        </div>

        {/* Activity feed */}
        <SpotlightCard>
          <div className="p-5">
            <h2 className="text-sm font-semibold mb-3">Recent Activity</h2>
            <div className="space-y-0">
              {(activity ?? []).slice(0, 8).map((ev: {
                type: string; label: string; date: string; sub?: string
              }, i: number) => (
                <div key={i} className="activity-item">
                  <div className={`mt-0.5 w-1.5 h-1.5 rounded-full shrink-0 ${
                    ev.type === 'applied' ? 'bg-blue-400'
                    : ev.type === 'response' ? 'bg-green-400' : 'bg-purple-400'
                  }`} />
                  <div className="min-w-0">
                    <p className="text-xs font-medium truncate">{ev.label}</p>
                    {ev.sub && <p className="text-xs text-muted-foreground truncate">{ev.sub}</p>}
                    <p className="text-xs text-muted-foreground/60">{formatDate(ev.date)}</p>
                  </div>
                </div>
              ))}
              {!activity?.length && (
                <p className="text-xs text-muted-foreground text-center py-4">No activity yet</p>
              )}
            </div>
          </div>
        </SpotlightCard>
      </div>

      {/* Quick actions */}
      <SpotlightCard>
        <div className="p-5">
          <h2 className="text-sm font-semibold mb-4">Quick Actions</h2>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => setJobUrlModal(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white
                bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600
                hover:brightness-110 transition-all duration-150"
            >
              <Plus size={14} /> Submit Job URL
            </button>
            <button
              onClick={runScraper}
              disabled={scraperRunning}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                bg-secondary/60 hover:bg-secondary border border-border/60
                transition-all duration-150 disabled:opacity-50"
            >
              {scraperRunning ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              Find New Jobs
            </button>
            <button
              onClick={runFollowup}
              disabled={followupRunning}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                bg-secondary/60 hover:bg-secondary border border-border/60
                transition-all duration-150 disabled:opacity-50"
            >
              {followupRunning ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
              Run Follow-up Check
            </button>
          </div>
        </div>
      </SpotlightCard>

      {/* Job URL modal */}
      {jobUrlModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <SpotlightCard className="w-full max-w-md mx-4">
            <div className="p-6 space-y-4">
              <h3 className="font-semibold">Submit Job URL</h3>
              <p className="text-sm text-muted-foreground">
                Paste a job posting URL. It will be added to the processing queue
                where the pipeline will tailor your resume automatically.
              </p>
              <input
                type="url"
                value={jobUrl}
                onChange={e => setJobUrl(e.target.value)}
                placeholder="https://boards.greenhouse.io/..."
                className="w-full px-3 py-2.5 rounded-lg bg-secondary/60 border border-border
                  text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                autoFocus
              />
              {submitResult && (
                <div className={`flex items-center gap-2 text-xs ${submitResult.ok ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {submitResult.ok ? <CheckCircle size={12} /> : <AlertCircle size={12} />}
                  {submitResult.msg}
                </div>
              )}
              <div className="flex gap-2 justify-end">
                <button onClick={() => { setJobUrlModal(false); setSubmitResult(null) }}
                  className="px-4 py-2 rounded-lg text-sm bg-secondary/60 hover:bg-secondary border border-border/60">
                  Cancel
                </button>
                <button onClick={submitJob} disabled={submitting || !jobUrl.trim()}
                  className="px-4 py-2 rounded-lg text-sm text-white
                    bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600
                    hover:brightness-110 disabled:opacity-50 flex items-center gap-2">
                  {submitting && <Loader2 size={12} className="animate-spin" />}
                  Add to Queue
                </button>
              </div>
            </div>
          </SpotlightCard>
        </div>
      )}
    </div>
  )
}
