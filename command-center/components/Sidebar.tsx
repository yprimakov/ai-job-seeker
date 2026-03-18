'use client'

import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Briefcase, Zap, HelpCircle,
  BarChart3, Settings, ChevronLeft, ChevronRight, Wifi, WifiOff, BookOpen,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ThemeToggle } from './ThemeToggle'

const NAV = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/applications', label: 'Applications', icon: Briefcase },
  { href: '/jobs', label: 'Job Queue', icon: Zap },
  { href: '/qa', label: 'Q&A Base', icon: HelpCircle },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/documentation', label: 'Documentation', icon: BookOpen },
]

export function Sidebar({
  wsConnected = true,
  collapsed,
  onCollapse,
}: {
  wsConnected?: boolean
  collapsed: boolean
  onCollapse: (v: boolean) => void
}) {
  const pathname = usePathname()

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 bottom-0 z-50 flex flex-col',
        'border-r border-border/40 backdrop-blur-xl',
        'bg-background/60 dark:bg-background/40',
        'transition-all duration-300 ease-in-out',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      {/* Logo / brand */}
      <div className={cn(
        'flex items-center border-b border-border/40 shrink-0',
        collapsed ? 'justify-center p-3' : 'px-4 py-3',
      )}>
        {!collapsed ? (
          <div className="min-w-0">
            {/* iMadeFire brand logo */}
            <Image
              src="/logo-dark.svg"
              alt="iMadeFire"
              width={96}
              height={20}
              className="hidden dark:block object-contain mb-1"
              priority
            />
            <Image
              src="/logo-light.svg"
              alt="iMadeFire"
              width={96}
              height={20}
              className="block dark:hidden object-contain mb-1"
              priority
            />
            {/* App + interface name */}
            <div className="leading-none">
              <span className="text-sm font-bold tracking-tight">Job Seeker</span>
              <span className="text-xs text-muted-foreground ml-1.5">Command Center</span>
            </div>
          </div>
        ) : (
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-orange-500/20 to-red-500/10 border border-orange-500/20 flex items-center justify-center">
            <Image
              src="/icon-fire.svg"
              alt="Job Seeker"
              width={18}
              height={18}
              className="object-contain"
              priority
            />
          </div>
        )}
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => onCollapse(!collapsed)}
        className={cn(
          'absolute top-14 -right-3 w-6 h-6 rounded-full border border-border/60',
          'bg-background flex items-center justify-center',
          'hover:bg-secondary transition-colors duration-150',
          'shadow-sm z-10',
        )}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed
          ? <ChevronRight size={12} className="text-muted-foreground" />
          : <ChevronLeft size={12} className="text-muted-foreground" />
        }
      </button>

      {/* Nav items */}
      <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium',
                'transition-all duration-150',
                collapsed && 'justify-center px-2',
                active
                  ? 'bg-background/80 shadow-sm text-blue-600 dark:text-blue-400'
                  : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50',
              )}
              title={collapsed ? label : undefined}
            >
              <Icon size={16} className={active ? 'text-blue-600 dark:text-blue-400' : ''} />
              {!collapsed && <span>{label}</span>}
            </Link>
          )
        })}
      </nav>

      {/* Bottom controls */}
      <div className="border-t border-border/40 p-2 space-y-1 shrink-0">
        {/* Settings link */}
        {(() => {
          const active = pathname.startsWith('/settings')
          return (
            <Link
              href="/settings"
              className={cn(
                'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium',
                'transition-all duration-150',
                collapsed && 'justify-center px-2',
                active
                  ? 'bg-background/80 shadow-sm text-blue-600 dark:text-blue-400'
                  : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50',
              )}
              title={collapsed ? 'Settings' : undefined}
            >
              <Settings size={16} className={active ? 'text-blue-600 dark:text-blue-400' : ''} />
              {!collapsed && <span>Settings</span>}
            </Link>
          )
        })()}

        {/* WS status */}
        <div className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg',
          collapsed && 'justify-center px-2',
        )}>
          {wsConnected
            ? <Wifi size={14} className="text-green-600 dark:text-green-400 shrink-0" />
            : <WifiOff size={14} className="text-red-600 dark:text-red-400 shrink-0" />
          }
          {!collapsed && (
            <span className={cn('text-xs', wsConnected ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400')}>
              {wsConnected ? 'Live' : 'Offline'}
            </span>
          )}
        </div>

        <ThemeToggle collapsed={collapsed} />
      </div>
    </aside>
  )
}
