'use client'

import { useState, FormEvent, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Image from 'next/image'
import { Lock, Loader2 } from 'lucide-react'
import { SpotlightCard } from '@/components/SpotlightCard'
import { AmbientBackground } from '@/components/AmbientBackground'

function LoginForm() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const params = useSearchParams()
  const from = params.get('from') ?? '/'

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    const res = await fetch('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (res.ok) {
      router.push(from)
    } else {
      setError('Incorrect password.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative">
      <AmbientBackground />
      <div className="relative z-10 w-full max-w-sm px-4">
        <SpotlightCard>
          <div className="p-8 flex flex-col items-center gap-6">
            <Image src="/logo-dark.svg" alt="iMadeFire" width={140} height={28}
              className="hidden dark:block" />
            <Image src="/logo-light.svg" alt="iMadeFire" width={140} height={28}
              className="dark:hidden" />
            <div className="text-center">
              <h1 className="text-lg font-semibold">Command Center</h1>
              <p className="text-sm text-muted-foreground mt-1">Enter your access password</p>
            </div>
            <form onSubmit={handleSubmit} className="w-full space-y-3">
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Password"
                  className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-secondary/60 border border-border
                    text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                  autoFocus
                />
              </div>
              {error && <p className="text-xs text-red-600 dark:text-red-400 text-center">{error}</p>}
              <button
                type="submit"
                disabled={loading || !password}
                className="w-full py-2.5 rounded-lg text-sm font-medium text-white
                  bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600
                  hover:brightness-110 transition-all duration-150
                  disabled:opacity-50 disabled:cursor-not-allowed
                  flex items-center justify-center gap-2"
              >
                {loading && <Loader2 size={14} className="animate-spin" />}
                {loading ? 'Signing in...' : 'Enter'}
              </button>
            </form>
          </div>
        </SpotlightCard>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
