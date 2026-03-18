'use client'

import { useState } from 'react'
import { Sidebar } from './Sidebar'

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="relative z-10 flex min-h-screen">
      <Sidebar collapsed={collapsed} onCollapse={setCollapsed} />
      <main
        className="flex-1 min-h-screen transition-all duration-300 ease-in-out"
        style={{ marginLeft: collapsed ? '4rem' : '15rem' }}
      >
        <div className="px-6 py-8">
          {children}
        </div>
      </main>
    </div>
  )
}
