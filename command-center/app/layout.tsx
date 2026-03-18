import type { Metadata } from 'next'
import './globals.css'
import { AmbientBackground } from '@/components/AmbientBackground'
import { AppShell } from '@/components/AppShell'
import { WSProvider } from '@/lib/ws-client'

export const metadata: Metadata = {
  title: 'Command Center | iMadeFire',
  description: 'AI Job Search Pipeline Command Center',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{
          __html: `
            (function() {
              try {
                var t = localStorage.getItem('theme');
                if (t === 'light') { document.documentElement.classList.remove('dark'); }
                else if (t === 'system') {
                  if (!window.matchMedia('(prefers-color-scheme: dark)').matches) {
                    document.documentElement.classList.remove('dark');
                  }
                }
                // default: dark stays
              } catch(e) {}
            })();
          `
        }} />
      </head>
      <body className="min-h-screen overflow-x-hidden">
        {/* CSS variables for glass card backgrounds */}
        <style>{`
          :root { --glass-outer: rgba(241,245,249,0.4); }
          .dark { --glass-outer: rgba(15,23,42,0.4); }
          .glass-inner-light { background: rgba(241,245,249,0.6); }
          .dark .glass-inner { background: rgba(2,6,23,0.7); }
          .spotlight-card { background: rgba(241,245,249,0.6); }
          .dark .spotlight-card { background: rgba(2,6,23,0.7); }
        `}</style>

        <AmbientBackground />

        <WSProvider>
          <AppShell>{children}</AppShell>
        </WSProvider>
      </body>
    </html>
  )
}
