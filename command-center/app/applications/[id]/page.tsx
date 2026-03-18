'use client'

import { useState, useEffect, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import dynamic from 'next/dynamic'

const PdfModal = dynamic(
  () => import('@/components/PdfModal').then(m => m.PdfModal),
  { ssr: false }
)
import useSWR from 'swr'
import {
  ArrowLeft, Save, Loader2, FileText, BarChart2, Mail, Zap, ExternalLink, Eye,
  Target, AlertTriangle, Lightbulb, Tag, ChevronDown, ChevronUp, CheckCircle, XCircle,
} from 'lucide-react'
import { SpotlightCard } from '@/components/SpotlightCard'
import { StatusBadge } from '@/components/StatusBadge'
import { formatDate, STATUS_ORDER, type TrackerRow } from '@/lib/utils'

const fetcher = (url: string) => fetch(url).then(r => r.json())

const RESPONSE_TYPES = ['Phone Screen', 'Interview', 'Take-Home Assessment', 'Offer', 'Rejected', 'Recruiter Outreach', 'Other']

type AnalysisData = {
  // Scores
  match_score?: number
  // Role metadata
  job_title?: string
  company?: string
  role_type?: string
  seniority?: string
  work_mode?: string
  domain?: string
  // Lists — actual field names from tailor_resume.py output
  keywords_ats?: string[]
  tech_stack?: string[]
  key_requirements?: string[]
  preferred_requirements?: string[]
  core_responsibilities?: string[]
  match_gaps?: string[]
  resume_angles?: string[]
  // Legacy / fallback field names
  ats_keywords?: string[]
  gaps?: string[]
  angles?: string[]
  summary?: string
  company_intel?: string
  [key: string]: unknown
}

function Section({ icon, label, color, children }: {
  icon: React.ReactNode; label: string; color?: string; children: React.ReactNode
}) {
  return (
    <div className="space-y-2">
      <h4 className={`text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5 ${color ?? 'text-muted-foreground'}`}>
        {icon} {label}
      </h4>
      {children}
    </div>
  )
}

function Chips({ items, className }: { items: string[]; className: string }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item, i) => (
        <span key={i} className={`text-xs px-2 py-0.5 rounded-full border ${className}`}>{item}</span>
      ))}
    </div>
  )
}

function BulletList({ items, prefix, prefixColor }: { items: string[]; prefix: string; prefixColor: string }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="text-sm text-foreground/80 flex items-start gap-2 leading-snug">
          <span className={`${prefixColor} mt-0.5 shrink-0 font-bold`}>{prefix}</span> {item}
        </li>
      ))}
    </ul>
  )
}

function AnalysisView({ analysisPath }: { analysisPath: string }) {
  const [data, setData] = useState<AnalysisData | null>(null)
  const [resumeText, setResumeText] = useState<string | null>(null)
  const [baseResumeText, setBaseResumeText] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activePanel, setActivePanel] = useState<'score' | 'ats' | null>(null)

  useEffect(() => {
    fetch(`/api/file?path=${encodeURIComponent(analysisPath)}`)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json()
      })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))

    // Tailored resume.md (same folder as analysis.json)
    const resumePath = analysisPath.replace(/analysis\.json$/, 'resume.md')
    fetch(`/api/file?path=${encodeURIComponent(resumePath)}`)
      .then(r => r.ok ? r.text() : null)
      .then(text => { if (text) setResumeText(text.toLowerCase()) })
      .catch(() => null)

    // Base (un-tailored) resume for before/after comparison
    fetch(`/api/file?path=${encodeURIComponent('pipeline/resume_base.md')}`)
      .then(r => r.ok ? r.text() : null)
      .then(text => { if (text) setBaseResumeText(text.toLowerCase()) })
      .catch(() => null)
  }, [analysisPath])

  if (loading) return (
    <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center">
      <Loader2 size={14} className="animate-spin" /> Loading analysis...
    </div>
  )
  if (error) return <p className="text-sm text-red-600 dark:text-red-400 py-4">Could not load analysis: {error}</p>
  if (!data) return <p className="text-sm text-muted-foreground py-4">No analysis data found.</p>

  const score = data.match_score
  const scoreColor = score == null ? 'text-muted-foreground' : score >= 80 ? 'text-green-600 dark:text-green-400' : score >= 60 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'
  const scoreBg   = score == null ? '' : score >= 80 ? 'bg-green-500/10 border-green-500/20' : score >= 60 ? 'bg-yellow-500/10 border-yellow-500/20' : 'bg-red-500/10 border-red-500/20'

  // Normalise field names
  const atsKeywords      = data.keywords_ats ?? data.ats_keywords ?? []
  const techStack        = data.tech_stack ?? []
  const keyReqs          = data.key_requirements ?? []
  const preferredReqs    = data.preferred_requirements ?? []
  const responsibilities = data.core_responsibilities ?? []
  const gaps             = data.match_gaps ?? data.gaps ?? []
  const angles           = data.resume_angles ?? data.angles ?? []

  // ATS coverage — before (base resume) and after (tailored resume)
  function splitKeywords(text: string | null) {
    const src = text ?? angles.join(' ').toLowerCase()
    const found   = atsKeywords.filter(kw => src.includes(kw.toLowerCase()))
    const missing = atsKeywords.filter(kw => !src.includes(kw.toLowerCase()))
    const pct     = atsKeywords.length > 0 ? Math.round(found.length / atsKeywords.length * 100) : null
    return { found, missing, pct }
  }

  const beforeAts = splitKeywords(baseResumeText)
  const afterAts  = splitKeywords(resumeText)
  const atsConfidence = afterAts.pct  // "after" is the headline number

  // Keywords that tailoring moved from missing → found
  const newlyCovered = afterAts.found.filter(kw => beforeAts.missing.some(m => m === kw))
  const stillMissing = afterAts.missing

  const meta = [
    data.role_type && { label: 'Role Type', value: data.role_type },
    data.seniority && { label: 'Seniority', value: data.seniority },
    data.work_mode && { label: 'Mode', value: data.work_mode },
    data.domain    && { label: 'Domain', value: data.domain },
  ].filter(Boolean) as { label: string; value: string }[]

  function togglePanel(panel: 'score' | 'ats') {
    setActivePanel(p => p === panel ? null : panel)
  }

  return (
    <div className="space-y-5">
      {/* Score strip — clickable, shared explanation panel below */}
      <div className="space-y-2">
        <div className="grid grid-cols-2 gap-3">
          {score != null && (
            <button
              onClick={() => togglePanel('score')}
              className={`flex items-center gap-3 p-3 rounded-xl border text-left transition-all hover:brightness-105 ${scoreBg} ${activePanel === 'score' ? 'ring-1 ring-current/30' : ''}`}
            >
              <Target size={16} className={scoreColor} />
              <div className="flex-1">
                <p className="text-xs text-muted-foreground">Match Score</p>
                <p className={`text-2xl font-bold ${scoreColor}`}>
                  {score}<span className="text-sm font-normal text-muted-foreground">/100</span>
                </p>
              </div>
              {activePanel === 'score'
                ? <ChevronUp size={12} className="text-muted-foreground shrink-0" />
                : <ChevronDown size={12} className="text-muted-foreground shrink-0" />}
            </button>
          )}
          {atsConfidence != null && (
            <button
              onClick={() => togglePanel('ats')}
              className={`flex items-center gap-3 p-3 rounded-xl border text-left transition-all hover:brightness-105 ${atsConfidence >= 50 ? 'bg-blue-500/10 border-blue-500/20' : 'bg-secondary/40 border-border/40'} ${activePanel === 'ats' ? 'ring-1 ring-blue-500/30' : ''}`}
            >
              <Tag size={16} className={atsConfidence >= 50 ? 'text-blue-600 dark:text-blue-400' : 'text-muted-foreground'} />
              <div className="flex-1">
                <p className="text-xs text-muted-foreground">ATS Coverage</p>
                <div className="flex items-baseline gap-1.5">
                  {beforeAts.pct != null && (
                    <span className="text-sm text-muted-foreground tabular-nums">{beforeAts.pct}%</span>
                  )}
                  {beforeAts.pct != null && <span className="text-muted-foreground/40 text-xs">→</span>}
                  <p className={`text-2xl font-bold ${atsConfidence >= 50 ? 'text-blue-600 dark:text-blue-400' : 'text-muted-foreground'}`}>
                    {atsConfidence}<span className="text-sm font-normal text-muted-foreground">%</span>
                  </p>
                </div>
              </div>
              {activePanel === 'ats'
                ? <ChevronUp size={12} className="text-muted-foreground shrink-0" />
                : <ChevronDown size={12} className="text-muted-foreground shrink-0" />}
            </button>
          )}
        </div>

        {/* Shared explanation panel */}
        {activePanel === 'score' && (
          <div className="rounded-xl border border-border/40 bg-secondary/30 p-4 space-y-4">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Match Score Breakdown</p>
            {gaps.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-orange-600 dark:text-orange-400 mb-2 flex items-center gap-1.5"><AlertTriangle size={11} /> Why the score is lower</p>
                <ul className="space-y-1.5">
                  {gaps.map((g, i) => (
                    <li key={i} className="text-xs text-foreground/80 flex gap-2 leading-snug">
                      <span className="text-orange-600 dark:text-orange-400 shrink-0 font-bold mt-0.5">!</span>{g}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {angles.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-yellow-600 dark:text-yellow-400 mb-2 flex items-center gap-1.5"><Lightbulb size={11} /> What scored positively</p>
                <ul className="space-y-1.5">
                  {angles.map((a, i) => (
                    <li key={i} className="text-xs text-foreground/80 flex gap-2 leading-snug">
                      <span className="text-yellow-600 dark:text-yellow-400 shrink-0 font-bold mt-0.5">+</span>{a}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {gaps.length === 0 && angles.length === 0 && (
              <p className="text-xs text-muted-foreground">No detailed breakdown available.</p>
            )}
          </div>
        )}

        {activePanel === 'ats' && (
          <div className="rounded-xl border border-border/40 bg-secondary/30 p-4 space-y-4">
            {/* Before / After headline */}
            <div className="flex items-center gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Base Resume</p>
                <p className="text-xl font-bold text-muted-foreground">
                  {beforeAts.pct ?? '?'}<span className="text-xs font-normal">%</span>
                </p>
              </div>
              <div className="text-muted-foreground/40 text-lg">→</div>
              <div>
                <p className="text-xs text-muted-foreground">Tailored Resume</p>
                <p className={`text-xl font-bold ${afterAts.pct != null ? (afterAts.pct >= 70 ? 'text-green-600 dark:text-green-400' : afterAts.pct >= 50 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400') : 'text-muted-foreground'}`}>
                  {afterAts.pct ?? '?'}<span className="text-xs font-normal">%</span>
                </p>
              </div>
              {beforeAts.pct != null && afterAts.pct != null && (
                <div className="ml-auto text-right">
                  <p className="text-xs text-muted-foreground">Improvement</p>
                  <p className={`text-sm font-semibold ${afterAts.pct - beforeAts.pct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    {afterAts.pct - beforeAts.pct >= 0 ? '+' : ''}{afterAts.pct - beforeAts.pct}%
                  </p>
                </div>
              )}
            </div>

            {/* Newly covered by tailoring */}
            {newlyCovered.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-green-600 dark:text-green-400 mb-2 flex items-center gap-1.5"><CheckCircle size={11} /> Added by tailoring</p>
                <div className="flex flex-wrap gap-1.5">
                  {newlyCovered.map((kw, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-green-500/10 text-green-700 dark:text-green-400 border border-green-500/20">{kw}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Already present in base */}
            {beforeAts.found.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-blue-600 dark:text-blue-400 mb-2 flex items-center gap-1.5"><CheckCircle size={11} /> Already in base resume</p>
                <div className="flex flex-wrap gap-1.5">
                  {beforeAts.found.map((kw, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-500/20">{kw}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Still missing after tailoring */}
            {stillMissing.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-red-600 dark:text-red-400 mb-2 flex items-center gap-1.5"><XCircle size={11} /> Still missing after tailoring</p>
                <div className="flex flex-wrap gap-1.5">
                  {stillMissing.map((kw, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-red-500/10 text-red-700 dark:text-red-400 border border-red-500/20">{kw}</span>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  These ATS-critical keywords were not incorporated during tailoring. Re-tailoring or manually adding them may improve screening pass rate.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Role metadata pills */}
      {meta.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {meta.map(({ label, value }) => (
            <span key={label} className="text-xs px-2.5 py-1 rounded-lg bg-secondary/60 border border-border/40">
              <span className="text-muted-foreground">{label}: </span>
              <span className="font-medium">{value}</span>
            </span>
          ))}
        </div>
      )}

      {/* Gaps */}
      {gaps.length > 0 && (
        <Section icon={<AlertTriangle size={11} />} label="Gaps to Address" color="text-orange-600 dark:text-orange-400">
          <BulletList items={gaps} prefix="!" prefixColor="text-orange-600 dark:text-orange-400" />
        </Section>
      )}

      {/* Resume angles */}
      {angles.length > 0 && (
        <Section icon={<Lightbulb size={11} />} label="Resume Angles" color="text-yellow-600 dark:text-yellow-400">
          <BulletList items={angles} prefix="+" prefixColor="text-yellow-600 dark:text-yellow-400" />
        </Section>
      )}

      {/* ATS Keywords */}
      {atsKeywords.length > 0 && (
        <Section icon={<Tag size={11} />} label={`ATS Keywords (${atsKeywords.length})`}>
          <Chips items={atsKeywords} className="bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20" />
        </Section>
      )}

      {/* Tech stack */}
      {techStack.length > 0 && (
        <Section icon={<BarChart2 size={11} />} label="Tech Stack">
          <Chips items={techStack} className="bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/20" />
        </Section>
      )}

      {/* Key requirements */}
      {keyReqs.length > 0 && (
        <Section icon={<Target size={11} />} label="Key Requirements">
          <BulletList items={keyReqs} prefix="·" prefixColor="text-muted-foreground" />
        </Section>
      )}

      {/* Preferred */}
      {preferredReqs.length > 0 && (
        <Section icon={<Target size={11} />} label="Preferred Requirements" color="text-muted-foreground">
          <BulletList items={preferredReqs} prefix="·" prefixColor="text-muted-foreground" />
        </Section>
      )}

      {/* Core responsibilities */}
      {responsibilities.length > 0 && (
        <Section icon={<Zap size={11} />} label="Core Responsibilities">
          <BulletList items={responsibilities} prefix="·" prefixColor="text-muted-foreground" />
        </Section>
      )}

      {/* Legacy: summary / company_intel */}
      {data.summary && (
        <Section icon={<FileText size={11} />} label="Summary">
          <p className="text-sm text-foreground/80 leading-relaxed">{data.summary}</p>
        </Section>
      )}
      {data.company_intel && (
        <Section icon={<FileText size={11} />} label="Company Intel">
          <p className="text-sm text-foreground/80 leading-relaxed">{data.company_intel}</p>
        </Section>
      )}
    </div>
  )
}

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const { data: rows = [] } = useSWR<TrackerRow[]>('/api/applications', fetcher)

  // Support both stable slug IDs (20260315_Company_Title) and legacy numeric IDs
  const isNumeric = /^\d+$/.test(id)
  const row = isNumeric
    ? rows[parseInt(id)]
    : rows.find(r => r._slug === id)

  const [form, setForm] = useState<Partial<TrackerRow>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [activeTab, setActiveTab] = useState<'resume' | 'analysis'>('resume')
  const [pipelineOutput, setPipelineOutput] = useState('')
  const [pipelineRunning, setPipelineRunning] = useState(false)
  const [responseForm, setResponseForm] = useState({ type: '', date: '', notes: '' })
  const [logginResponse, setLoggingResponse] = useState(false)
  const [pdfOpen, setPdfOpen] = useState(false)
  const outputRef = useRef<HTMLPreElement>(null)

  useEffect(() => {
    if (row) setForm({
      'Application Status': row['Application Status'],
      'Work Mode': row['Work Mode'],
      'Salary Range': row['Salary Range'],
      'Notes': row['Notes'],
    })
  }, [row])

  // Auto-scroll output panel as new lines arrive
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [pipelineOutput])

  async function save() {
    setSaving(true)
    await fetch(`/api/applications/${row?._id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  async function logResponse() {
    if (!responseForm.type) return
    setLoggingResponse(true)
    await fetch(`/api/applications/${row?._id}/response`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(responseForm),
    })
    setLoggingResponse(false)
  }

  async function runPipeline(action: 'tailor' | 'cover-letter' | 'followup') {
    setPipelineRunning(true)
    setPipelineOutput('')
    try {
      const res = await fetch('/api/pipeline/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, company: row?.Company, title: row?.['Job Title'] }),
      })
      if (!res.ok || !res.body) {
        setPipelineOutput(await res.text())
        return
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        setPipelineOutput(prev => prev + decoder.decode(value, { stream: true }))
      }
    } catch (err) {
      setPipelineOutput(`Error: ${String(err)}`)
    } finally {
      setPipelineRunning(false)
    }
  }

  if (!row) return (
    <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
      Application not found.
    </div>
  )

  const resumePath = row['Tailored Resume File']
  const analysisPath = resumePath?.replace(/resume\.pdf$/i, 'analysis.json')
  const pdfUrl = resumePath ? `/api/file?path=${encodeURIComponent(resumePath)}` : null

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => router.back()}
          className="p-2 rounded-lg hover:bg-secondary/60 transition-colors text-muted-foreground hover:text-foreground">
          <ArrowLeft size={16} />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold tracking-tight truncate">{row['Job Title']}</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-sm text-muted-foreground">{row.Company}</span>
            <span className="text-muted-foreground/40">·</span>
            <StatusBadge status={row['Application Status']} />
            {row['LinkedIn URL'] && (
              <a href={row['LinkedIn URL']} target="_blank" rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors">
                <ExternalLink size={11} />
              </a>
            )}
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs text-muted-foreground">Applied</p>
          <p className="text-sm font-medium">{formatDate(row['Date Applied'])}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Left: edit form */}
        <div className="lg:col-span-2 space-y-4">
          <SpotlightCard>
            <div className="p-5 space-y-4">
              <h2 className="text-sm font-semibold">Edit Application</h2>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Status</label>
                  <select
                    value={form['Application Status'] ?? ''}
                    onChange={e => setForm(f => ({ ...f, 'Application Status': e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    {STATUS_ORDER.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Work Mode</label>
                  <select
                    value={form['Work Mode'] ?? ''}
                    onChange={e => setForm(f => ({ ...f, 'Work Mode': e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60 focus:outline-none"
                  >
                    {['Remote', 'Hybrid', 'On-site'].map(m => <option key={m}>{m}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Salary Range</label>
                  <input
                    value={form['Salary Range'] ?? ''}
                    onChange={e => setForm(f => ({ ...f, 'Salary Range': e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Notes</label>
                  <textarea
                    value={form['Notes'] ?? ''}
                    onChange={e => setForm(f => ({ ...f, 'Notes': e.target.value }))}
                    rows={3}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                  />
                </div>
              </div>
              <button onClick={save} disabled={saving}
                className="w-full py-2 rounded-lg text-sm font-medium text-white
                  bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600
                  hover:brightness-110 transition-all disabled:opacity-50
                  flex items-center justify-center gap-2">
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                {saved ? 'Saved!' : 'Save Changes'}
              </button>
            </div>
          </SpotlightCard>

          {/* Log response */}
          <SpotlightCard>
            <div className="p-5 space-y-3">
              <h2 className="text-sm font-semibold">Log Response</h2>
              {row['Response Type'] && (
                <div className="text-xs text-muted-foreground p-2 bg-secondary/40 rounded-lg">
                  Last: <span className="text-foreground">{row['Response Type']}</span> on {formatDate(row['Date Response Received'])}
                </div>
              )}
              <select value={responseForm.type}
                onChange={e => setResponseForm(f => ({ ...f, type: e.target.value }))}
                className="w-full px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60 focus:outline-none">
                <option value="">Select response type...</option>
                {RESPONSE_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
              <input type="date" value={responseForm.date}
                onChange={e => setResponseForm(f => ({ ...f, date: e.target.value }))}
                className="w-full px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60 focus:outline-none" />
              <button onClick={logResponse} disabled={logginResponse || !responseForm.type}
                className="w-full py-2 rounded-lg text-sm font-medium bg-secondary/60 hover:bg-secondary
                  border border-border/60 transition-colors disabled:opacity-50
                  flex items-center justify-center gap-2">
                {logginResponse && <Loader2 size={12} className="animate-spin" />}
                <Mail size={12} /> Log Response
              </button>
            </div>
          </SpotlightCard>

          {/* Timeline */}
          <SpotlightCard>
            <div className="p-5 space-y-1">
              <h2 className="text-sm font-semibold mb-3">Timeline</h2>
              <div className="relative pl-4 space-y-0">
                {[
                  row['Date Applied'] && {
                    date: row['Date Applied'],
                    label: 'Applied',
                    sub: row['Work Mode'] ? `${row['Work Mode']}${row['Easy Apply'] === 'Yes' ? ' · Easy Apply' : ''}` : undefined,
                    color: 'bg-blue-400',
                  },
                  row['Date Response Received'] && {
                    date: row['Date Response Received'],
                    label: row['Response Type'] || 'Response received',
                    sub: undefined,
                    color: row['Response Type'] === 'Rejected' ? 'bg-red-400'
                      : row['Response Type'] === 'Offer' ? 'bg-green-400'
                      : 'bg-purple-400',
                  },
                  !['Applied', 'Rejected', 'Ghosted', 'Offer'].includes(row['Application Status'] ?? '') && {
                    date: null,
                    label: row['Application Status'] ?? 'Unknown status',
                    sub: 'current status',
                    color: 'bg-yellow-400',
                  },
                  row['Application Status'] === 'Ghosted' && {
                    date: null,
                    label: 'Ghosted',
                    sub: 'no response',
                    color: 'bg-slate-400',
                  },
                  row['Application Status'] === 'Rejected' && !row['Date Response Received'] && {
                    date: null,
                    label: 'Rejected',
                    sub: undefined,
                    color: 'bg-red-400',
                  },
                  row['Application Status'] === 'Offer' && !row['Date Response Received'] && {
                    date: null,
                    label: 'Offer received',
                    sub: undefined,
                    color: 'bg-green-400',
                  },
                ].filter(Boolean).map((ev, i, arr) => {
                  if (!ev) return null
                  return (
                    <div key={i} className="relative flex gap-3 pb-4 last:pb-0">
                      {/* Connector line */}
                      {i < arr.length - 1 && (
                        <div className="absolute left-[5px] top-3 bottom-0 w-px bg-border/50" />
                      )}
                      <div className={`mt-1 w-2.5 h-2.5 rounded-full shrink-0 ${ev.color}`} />
                      <div className="min-w-0">
                        <p className="text-xs font-medium leading-snug">{ev.label}</p>
                        {ev.sub && <p className="text-xs text-muted-foreground">{ev.sub}</p>}
                        {ev.date && <p className="text-xs text-muted-foreground/60">{formatDate(ev.date)}</p>}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </SpotlightCard>

          {/* Pipeline actions */}
          <SpotlightCard>
            <div className="p-5 space-y-2">
              <h2 className="text-sm font-semibold mb-3">Pipeline Actions</h2>
              {[
                { label: 'Re-tailor Resume', action: 'tailor' as const, icon: FileText },
                { label: 'Generate Cover Letter', action: 'cover-letter' as const, icon: FileText },
                { label: 'Generate Follow-up Draft', action: 'followup' as const, icon: Mail },
              ].map(({ label, action, icon: Icon }) => (
                <button key={action} onClick={() => runPipeline(action)}
                  disabled={pipelineRunning}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm
                    bg-secondary/60 hover:bg-secondary border border-border/60
                    transition-colors disabled:opacity-50">
                  {pipelineRunning ? <Loader2 size={12} className="animate-spin" /> : <Icon size={12} />}
                  {label}
                </button>
              ))}
            </div>
          </SpotlightCard>
        </div>

        {/* Right: content tabs */}
        <div className="lg:col-span-3 space-y-4">
          <SpotlightCard>
            <div>
              {/* Tab bar */}
              <div className="flex border-b border-border/40">
                {[
                  { key: 'resume', label: 'Resume', icon: FileText },
                  { key: 'analysis', label: 'Analysis', icon: BarChart2 },
                ].map(({ key, label, icon: Icon }) => (
                  <button key={key}
                    onClick={() => setActiveTab(key as 'resume' | 'analysis')}
                    className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors
                      ${activeTab === key
                        ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                        : 'border-transparent text-muted-foreground hover:text-foreground'}`}>
                    <Icon size={13} /> {label}
                  </button>
                ))}
              </div>

              <div className="p-5">
                {activeTab === 'resume' && (
                  <div>
                    {resumePath && pdfUrl ? (
                      <div className="space-y-4">
                        {/* Thumbnail — scaled-down iframe of page 1 */}
                        <button
                          onClick={() => setPdfOpen(true)}
                          className="group relative block w-full overflow-hidden rounded-xl border border-border/40
                            hover:border-blue-500/40 transition-colors cursor-pointer"
                          title="Click to preview"
                          style={{ aspectRatio: '9.5 / 11' }}
                        >
                          {/* iframe renders at 900px wide, scaled to fit container */}
                          <iframe
                            src={`${pdfUrl}#toolbar=0&navpanes=0&scrollbar=0&page=1&zoom=75`}
                            className="absolute inset-0 w-full h-full border-0 pointer-events-none"
                            title="Resume thumbnail"
                            tabIndex={-1}
                          />
                          {/* Hover overlay */}
                          <div className="absolute inset-0 flex items-center justify-center
                            opacity-0 group-hover:opacity-100 transition-opacity
                            bg-black/40 backdrop-blur-[1px]">
                            <div className="flex items-center gap-2 px-4 py-2 rounded-lg
                              bg-blue-500/90 text-white text-sm font-medium shadow-lg">
                              <Eye size={14} /> Click to expand
                            </div>
                          </div>
                        </button>

                        {/* Path + open link */}
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-xs text-muted-foreground font-mono truncate flex-1 min-w-0">
                            {resumePath}
                          </p>
                          <a href={pdfUrl} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-muted-foreground
                              hover:text-foreground transition-colors shrink-0">
                            <ExternalLink size={11} /> Open
                          </a>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No tailored resume yet. Use "Re-tailor Resume" to generate one.
                      </p>
                    )}
                  </div>
                )}

                {activeTab === 'analysis' && (
                  <div>
                    {analysisPath ? (
                      <AnalysisView analysisPath={analysisPath} />
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No analysis available. Tailor the resume first to generate analysis data.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </SpotlightCard>

          {/* Pipeline output — visible while running or when output exists */}
          {(pipelineRunning || pipelineOutput) && (
            <SpotlightCard>
              <div className="p-5">
                <div className="flex items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    {pipelineRunning
                      ? <Loader2 size={13} className="text-blue-600 dark:text-blue-400 animate-spin" />
                      : <Zap size={13} className="text-blue-600 dark:text-blue-400" />}
                    <h3 className="text-sm font-semibold">Pipeline Output</h3>
                  </div>
                  {pipelineRunning && (
                    <span className="text-xs text-blue-600 dark:text-blue-400 animate-pulse">Running...</span>
                  )}
                </div>
                <pre
                  ref={outputRef}
                  className="stream-output text-xs overflow-auto whitespace-pre-wrap max-h-72 scroll-smooth"
                >
                  {pipelineOutput || 'Starting process...'}
                </pre>
              </div>
            </SpotlightCard>
          )}
        </div>
      </div>

      {/* PDF Modal */}
      {pdfOpen && pdfUrl && (
        <PdfModal url={pdfUrl} onClose={() => setPdfOpen(false)} />
      )}
    </div>
  )
}
