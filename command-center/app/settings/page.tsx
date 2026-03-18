'use client'

import { useState, useEffect } from 'react'
import useSWR from 'swr'
import { Save, Loader2, CheckCircle, XCircle, ExternalLink, Link2 } from 'lucide-react'
import { SpotlightCard } from '@/components/SpotlightCard'

const fetcher = (url: string) => fetch(url).then(r => r.json())

type Settings = {
  CANDIDATE_NAME?: string
  CANDIDATE_TITLE?: string
  CANDIDATE_EMAIL?: string
  CANDIDATE_PHONE?: string
  CANDIDATE_LOCATION?: string
  CANDIDATE_WEBSITE?: string
  DEFAULT_WORK_MODE?: string
  FOLLOWUP_DAYS?: string
  SCRAPER_REMOTE?: string
  SCRAPER_EASY_APPLY?: string
  integrations?: {
    gmail: boolean
    anthropic: boolean
    herenow: boolean
  }
}

function IntegrationStatus({ label, ok, link }: { label: string; ok: boolean; link?: string }) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30 border border-border/40">
      <div className="flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full ${ok ? 'bg-green-400' : 'bg-red-400'} shadow-[0_0_6px_currentColor]`} />
        <span className="text-sm">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className={`text-xs ${ok ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
          {ok ? 'Connected' : 'Not configured'}
        </span>
        {link && !ok && (
          <a href={link} target="_blank" rel="noopener noreferrer"
            className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-500 dark:hover:text-blue-300 flex items-center gap-1">
            Setup <ExternalLink size={10} />
          </a>
        )}
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { data: settings, mutate } = useSWR<Settings>('/api/settings', fetcher)
  const [form, setForm] = useState<Settings>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [tunnelUrl, setTunnelUrl] = useState('')
  const [tunneling, setTunneling] = useState(false)

  useEffect(() => {
    if (settings) setForm(settings)
  }, [settings])

  function field(key: keyof Settings) {
    return {
      value: (form[key] as string) ?? '',
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
        setForm(f => ({ ...f, [key]: e.target.value })),
    }
  }

  async function save() {
    setSaving(true)
    await fetch('/api/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
    mutate()
  }

  async function startTunnel() {
    setTunneling(true)
    const res = await fetch('/api/tunnel', { method: 'POST' })
    const data = await res.json()
    setTunnelUrl(data.url ?? '')
    setTunneling(false)
  }

  const integrations = settings?.integrations ?? { gmail: false, anthropic: false, herenow: false }

  const inputClass = "w-full px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60 focus:outline-none focus:ring-1 focus:ring-blue-500"
  const labelClass = "text-xs text-muted-foreground mb-1.5 block"

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Candidate profile and pipeline configuration</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Candidate profile */}
        <SpotlightCard>
          <div className="p-5 space-y-4">
            <h2 className="text-sm font-semibold">Candidate Profile</h2>
            <div className="space-y-3">
              <div>
                <label className={labelClass}>Full Name</label>
                <input className={inputClass} {...field('CANDIDATE_NAME')} placeholder="Yury Primakov" />
              </div>
              <div>
                <label className={labelClass}>Job Title</label>
                <input className={inputClass} {...field('CANDIDATE_TITLE')} placeholder="Principal AI Engineer" />
              </div>
              <div>
                <label className={labelClass}>Email</label>
                <input className={inputClass} type="email" {...field('CANDIDATE_EMAIL')} placeholder="you@example.com" />
              </div>
              <div>
                <label className={labelClass}>Phone</label>
                <input className={inputClass} {...field('CANDIDATE_PHONE')} placeholder="555-555-5555" />
              </div>
              <div>
                <label className={labelClass}>Location</label>
                <input className={inputClass} {...field('CANDIDATE_LOCATION')} placeholder="Holmdel, NJ" />
              </div>
              <div>
                <label className={labelClass}>Website</label>
                <input className={inputClass} {...field('CANDIDATE_WEBSITE')} placeholder="yuryprimakov.com" />
              </div>
            </div>
          </div>
        </SpotlightCard>

        {/* Pipeline config */}
        <SpotlightCard>
          <div className="p-5 space-y-4">
            <h2 className="text-sm font-semibold">Pipeline Configuration</h2>
            <div className="space-y-3">
              <div>
                <label className={labelClass}>Default Work Mode</label>
                <select className={inputClass} {...field('DEFAULT_WORK_MODE')}>
                  <option value="">Any</option>
                  <option>Remote</option>
                  <option>Hybrid</option>
                  <option>On-site</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Follow-up Days (after applying)</label>
                <input className={inputClass} type="number" min="1" max="30" {...field('FOLLOWUP_DAYS')} placeholder="7" />
              </div>
              <div>
                <label className={labelClass}>Scraper: Default to Remote</label>
                <select className={inputClass} {...field('SCRAPER_REMOTE')}>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Scraper: Default to Easy Apply</label>
                <select className={inputClass} {...field('SCRAPER_EASY_APPLY')}>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </div>
            </div>

            <button onClick={save} disabled={saving}
              className="w-full py-2 rounded-lg text-sm font-medium text-white
                bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600
                hover:brightness-110 transition-all disabled:opacity-50
                flex items-center justify-center gap-2">
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
              {saved ? 'Saved!' : 'Save Settings'}
            </button>
          </div>
        </SpotlightCard>
      </div>

      {/* Integrations */}
      <SpotlightCard>
        <div className="p-5 space-y-3">
          <h2 className="text-sm font-semibold">Integration Status</h2>
          <IntegrationStatus label="Anthropic API" ok={integrations.anthropic} />
          <IntegrationStatus label="Gmail OAuth" ok={integrations.gmail} />
          <IntegrationStatus label="here.now" ok={integrations.herenow} />
        </div>
      </SpotlightCard>

      {/* Tunneling */}
      <SpotlightCard>
        <div className="p-5 space-y-3">
          <h2 className="text-sm font-semibold">Public Access</h2>
          <p className="text-xs text-muted-foreground">
            Share this Command Center publicly via a temporary here.now tunnel (24hr TTL).
          </p>
          <button onClick={startTunnel} disabled={tunneling}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
              bg-secondary/60 hover:bg-secondary border border-border/60 transition-colors disabled:opacity-50">
            {tunneling ? <Loader2 size={13} className="animate-spin" /> : <Link2 size={13} />}
            {tunneling ? 'Starting tunnel...' : 'Share Publicly'}
          </button>
          {tunnelUrl && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-green-400/10 border border-green-400/20">
              <CheckCircle size={13} className="text-green-600 dark:text-green-400 shrink-0" />
              <a href={tunnelUrl} target="_blank" rel="noopener noreferrer"
                className="text-sm text-green-600 dark:text-green-400 hover:text-green-500 dark:hover:text-green-300 font-mono truncate">
                {tunnelUrl}
              </a>
              <ExternalLink size={11} className="text-green-600 dark:text-green-400 shrink-0" />
            </div>
          )}
        </div>
      </SpotlightCard>
    </div>
  )
}
