import { SpotlightCard } from './SpotlightCard'
import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

interface MetricCardProps {
  label: string
  value: string | number
  sub?: string
  icon: LucideIcon
  accent?: boolean
  warning?: boolean
}

export function MetricCard({ label, value, sub, icon: Icon, accent, warning }: MetricCardProps) {
  return (
    <SpotlightCard hover>
      <div className="p-5">
        <div className="flex items-start justify-between mb-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {label}
          </p>
          <div className={cn(
            'p-1.5 rounded-lg',
            accent ? 'bg-blue-500/10' : warning ? 'bg-orange-500/10' : 'bg-secondary/60',
          )}>
            <Icon size={14} className={cn(
              accent ? 'text-blue-600 dark:text-blue-400' : warning ? 'text-orange-600 dark:text-orange-400' : 'text-muted-foreground',
            )} />
          </div>
        </div>
        <p className={cn(
          'text-3xl font-bold tracking-tight',
          accent && 'text-blue-600 dark:text-blue-400',
          warning && 'text-orange-600 dark:text-orange-400',
        )}>
          {value}
        </p>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </div>
    </SpotlightCard>
  )
}
