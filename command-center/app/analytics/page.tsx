'use client'

import useSWR from 'swr'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, CartesianGrid, PieChart, Pie, Legend,
  ScatterChart, Scatter, ZAxis,
} from 'recharts'
import { SpotlightCard } from '@/components/SpotlightCard'
import { TrendingUp, Activity, Clock, Mail } from 'lucide-react'

const fetcher = (url: string) => fetch(url).then(r => r.json())

const CHART_TOOLTIP_STYLE = {
  contentStyle: {
    background: 'rgba(2,6,23,0.9)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8,
    fontSize: 12,
  },
}

const STATUS_COLORS: Record<string, string> = {
  Applied: '#3b82f6',
  'Phone Screen': '#38bdf8',
  Interview: '#a855f7',
  Assessment: '#fb923c',
  Offer: '#22c55e',
  Rejected: '#ef4444',
  Ghosted: '#64748b',
}

const MODE_COLORS: Record<string, string> = {
  Remote: '#3b82f6',
  Hybrid: '#a855f7',
  'On-site': '#fb923c',
}

function ChartCard({ title, children, className = '' }: {
  title: string; children: React.ReactNode; className?: string
}) {
  return (
    <SpotlightCard className={className}>
      <div className="p-5">
        <h3 className="text-sm font-semibold mb-4">{title}</h3>
        {children}
      </div>
    </SpotlightCard>
  )
}

function StatChip({ label, value, icon: Icon, accent }: {
  label: string; value: string | number; icon: React.ElementType; accent?: boolean
}) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl bg-secondary/40 border border-border/40">
      <div className={`p-2 rounded-lg ${accent ? 'bg-blue-500/20 text-blue-600 dark:text-blue-400' : 'bg-secondary text-muted-foreground'}`}>
        <Icon size={14} />
      </div>
      <div>
        <p className="text-lg font-bold leading-none">{value}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
      </div>
    </div>
  )
}

export default function AnalyticsPage() {
  const { data: a } = useSWR('/api/analytics', fetcher, { refreshInterval: 0 })

  if (!a) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
        Loading analytics...
      </div>
    )
  }

  const byStatus = a.byStatus ?? []
  const byMode = a.byWorkMode ?? []
  const overtime = a.overTime ?? []
  const responseTypes = a.byResponseType ?? []
  const bySalary = a.bySalary ?? []
  const ea = a.byEasyApply ?? {}
  const eaComparison = ea.eaTotal != null ? [
    { type: 'Easy Apply', count: ea.eaTotal },
    { type: 'Direct', count: ea.directTotal ?? 0 },
  ] : []
  const daysToResponseRaw: number[] = a.daysToResponse ?? []
  const daysToResponse = (() => {
    const buckets: Record<string, number> = {}
    for (const d of daysToResponseRaw) {
      const b = d <= 3 ? '1-3d' : d <= 7 ? '4-7d' : d <= 14 ? '8-14d' : d <= 30 ? '15-30d' : '30d+'
      buckets[b] = (buckets[b] ?? 0) + 1
    }
    return ['1-3d','4-7d','8-14d','15-30d','30d+'].filter(b => buckets[b]).map(b => ({ bucket: b, count: buckets[b] }))
  })()
  const matchScores: unknown[] = []

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Pipeline performance and trends</p>
      </div>

      {/* Summary strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatChip label="Total Applications" value={a.total ?? 0} icon={Activity} accent />
        <StatChip label="Response Rate" value={`${a.responseRate ?? 0}%`} icon={TrendingUp} accent />
        <StatChip label="Avg Days to Response" value={a.avgDaysToResponse ?? '-'} icon={Clock} />
        <StatChip label="Responses Received" value={a.responded ?? 0} icon={Mail} />
      </div>

      {/* Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Applications Over Time">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={overtime}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="rgba(255,255,255,0.2)" />
              <YAxis tick={{ fontSize: 11 }} stroke="rgba(255,255,255,0.2)" />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Line type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2}
                dot={{ fill: '#3b82f6', r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Pipeline Funnel">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={byStatus} layout="vertical" barCategoryGap="30%">
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="status" width={100} tick={{ fontSize: 11 }} />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {byStatus.map((entry: { status: string }) => (
                  <Cell key={entry.status} fill={STATUS_COLORS[entry.status] ?? '#3b82f6'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard title="Response Rate by Work Mode">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={byMode.map((m: { mode: string; total: number; responded: number }) => ({
              mode: m.mode,
              responseRate: m.total > 0 ? Math.round((m.responded / m.total) * 100) : 0,
            }))} barCategoryGap="40%">
              <XAxis dataKey="mode" tick={{ fontSize: 11 }} stroke="rgba(255,255,255,0.2)" />
              <YAxis tick={{ fontSize: 11 }} stroke="rgba(255,255,255,0.2)" unit="%" />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Bar dataKey="responseRate" radius={[4, 4, 0, 0]}>
                {byMode.map((entry: { mode: string }) => (
                  <Cell key={entry.mode} fill={MODE_COLORS[entry.mode] ?? '#3b82f6'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Easy Apply vs Direct">
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={eaComparison} dataKey="count" nameKey="type" cx="50%" cy="50%"
                innerRadius={50} outerRadius={80} paddingAngle={4} label={({ type, percent }) =>
                  `${type}: ${(percent * 100).toFixed(0)}%`}
                labelLine={false}>
                {eaComparison.map((entry: { type: string }, i: number) => (
                  <Cell key={i} fill={i === 0 ? '#3b82f6' : '#a855f7'} />
                ))}
              </Pie>
              <Tooltip {...CHART_TOOLTIP_STYLE} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Response Type Breakdown">
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={responseTypes} dataKey="count" nameKey="type" cx="50%" cy="50%"
                outerRadius={70} paddingAngle={3}>
                {responseTypes.map((_: unknown, i: number) => (
                  <Cell key={i} fill={['#3b82f6', '#38bdf8', '#a855f7', '#22c55e', '#ef4444', '#fb923c', '#64748b'][i % 7]} />
                ))}
              </Pie>
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Row 3 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Days to First Response">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={daysToResponse} barCategoryGap="20%">
              <XAxis dataKey="bucket" tick={{ fontSize: 11 }} stroke="rgba(255,255,255,0.2)" />
              <YAxis tick={{ fontSize: 11 }} stroke="rgba(255,255,255,0.2)" />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Bar dataKey="count" fill="#38bdf8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Applications by Salary Range">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={bySalary} barCategoryGap="20%">
              <XAxis dataKey="range" tick={{ fontSize: 10 }} stroke="rgba(255,255,255,0.2)" />
              <YAxis tick={{ fontSize: 11 }} stroke="rgba(255,255,255,0.2)" />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Bar dataKey="count" fill="#a855f7" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Row 4: scatter */}
      {matchScores.length > 0 && (
        <ChartCard title="Match Score vs Response">
          <ResponsiveContainer width="100%" height={220}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="score" name="Match Score" type="number" domain={[0, 100]}
                tick={{ fontSize: 11 }} stroke="rgba(255,255,255,0.2)" label={{ value: 'Match Score', position: 'insideBottom', offset: -5, fontSize: 11 }} />
              <YAxis dataKey="responded" name="Responded" type="number" domain={[0, 1]}
                tick={{ fontSize: 11 }} stroke="rgba(255,255,255,0.2)"
                tickFormatter={(v) => v === 1 ? 'Yes' : 'No'} />
              <ZAxis range={[60, 60]} />
              <Tooltip {...CHART_TOOLTIP_STYLE}
                formatter={(value, name) => [name === 'responded' ? (value ? 'Yes' : 'No') : value, name]} />
              <Scatter data={matchScores} fill="#3b82f6" fillOpacity={0.7} />
            </ScatterChart>
          </ResponsiveContainer>
        </ChartCard>
      )}
    </div>
  )
}
