'use client'

import { useState, useCallback } from 'react'
import useSWR from 'swr'
import { Plus, Loader2, CheckCircle, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { SpotlightCard } from '@/components/SpotlightCard'
import { useWS } from '@/lib/ws-client'
import { formatDate, type QARow } from '@/lib/utils'

const fetcher = (url: string) => fetch(url).then(r => r.json())

function QARowItem({ row, onSave }: { row: QARow; onSave: () => void }) {
  const [expanded, setExpanded] = useState(!row.Answer)
  const [answer, setAnswer] = useState(row.Answer ?? '')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  async function save() {
    setSaving(true)
    await fetch(`/api/qa/${row._id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ Answer: answer }),
    })
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
    onSave()
  }

  const unanswered = !row.Answer

  return (
    <div className={`border rounded-xl overflow-hidden transition-colors ${unanswered ? 'border-orange-500/30 bg-orange-500/5' : 'border-border/40'}`}>
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-secondary/30 transition-colors"
      >
        <div className="shrink-0 mt-0.5">
          {unanswered
            ? <AlertCircle size={14} className="text-orange-600 dark:text-orange-400" />
            : <CheckCircle size={14} className="text-green-600 dark:text-green-400" />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-snug">{row.Question}</p>
          {row['Context (where it appeared)'] && (
            <p className="text-xs text-muted-foreground mt-0.5 truncate">{row['Context (where it appeared)']}</p>
          )}
        </div>
        <div className="shrink-0 flex items-center gap-3">
          <span className="text-xs text-muted-foreground">{formatDate(row['Date Answered'])}</span>
          {expanded ? <ChevronUp size={14} className="text-muted-foreground" /> : <ChevronDown size={14} className="text-muted-foreground" />}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-border/30 pt-3">
          {row.Answer && (
            <p className="text-sm text-muted-foreground leading-relaxed">{row.Answer}</p>
          )}
          <textarea
            value={answer}
            onChange={e => setAnswer(e.target.value)}
            rows={3}
            placeholder="Type your answer..."
            className="w-full px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border/60
              focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
          />
          <button onClick={save} disabled={saving || !answer.trim()}
            className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-medium text-white
              bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600
              hover:brightness-110 transition-all disabled:opacity-50">
            {saving ? <Loader2 size={11} className="animate-spin" /> : null}
            {saved ? 'Saved!' : 'Save Answer'}
          </button>
        </div>
      )}
    </div>
  )
}

export default function QAPage() {
  const { data: rows = [], mutate } = useSWR<QARow[]>('/api/qa', fetcher)
  useWS('qa_updated', useCallback(() => mutate(), [mutate]))

  const [showModal, setShowModal] = useState(false)
  const [newQ, setNewQ] = useState('')
  const [newCtx, setNewCtx] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const unanswered = rows.filter(r => !r.Answer)
  const answered = rows.filter(r => !!r.Answer)

  async function addQuestion() {
    if (!newQ.trim()) return
    setSubmitting(true)
    await fetch('/api/qa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: newQ, context: newCtx }),
    })
    setNewQ('')
    setNewCtx('')
    setSubmitting(false)
    setShowModal(false)
    mutate()
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Q&A Knowledge Base</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {unanswered.length} unanswered · {answered.length} answered
          </p>
        </div>
        <button onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white
            bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600
            hover:brightness-110 transition-all">
          <Plus size={14} /> Add Question
        </button>
      </div>

      {/* Unanswered */}
      {unanswered.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-orange-600 dark:text-orange-400 uppercase tracking-wider flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse inline-block" />
            Needs Your Answer ({unanswered.length})
          </h2>
          {unanswered.map(row => (
            <QARowItem key={row._id} row={row} onSave={() => mutate()} />
          ))}
        </div>
      )}

      {/* Answered */}
      {answered.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Answered ({answered.length})
          </h2>
          {answered.map(row => (
            <QARowItem key={row._id} row={row} onSave={() => mutate()} />
          ))}
        </div>
      )}

      {rows.length === 0 && (
        <SpotlightCard>
          <div className="p-12 text-center text-muted-foreground text-sm">
            No questions yet. Questions encountered during applications are saved here automatically.
          </div>
        </SpotlightCard>
      )}

      {/* Add modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <SpotlightCard className="w-full max-w-md mx-4">
            <div className="p-6 space-y-4">
              <h3 className="font-semibold">Add Question</h3>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Question</label>
                  <textarea
                    value={newQ}
                    onChange={e => setNewQ(e.target.value)}
                    rows={3}
                    placeholder="What question did you encounter?"
                    className="w-full px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border
                      focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                    autoFocus
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Context (optional)</label>
                  <input
                    value={newCtx}
                    onChange={e => setNewCtx(e.target.value)}
                    placeholder="e.g. Acme Corp Easy Apply"
                    className="w-full px-3 py-2 text-sm rounded-lg bg-secondary/60 border border-border
                      focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded-lg text-sm bg-secondary/60 hover:bg-secondary border border-border/60">
                  Cancel
                </button>
                <button onClick={addQuestion} disabled={submitting || !newQ.trim()}
                  className="px-4 py-2 rounded-lg text-sm text-white
                    bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600
                    hover:brightness-110 disabled:opacity-50 flex items-center gap-2">
                  {submitting && <Loader2 size={12} className="animate-spin" />}
                  Save
                </button>
              </div>
            </div>
          </SpotlightCard>
        </div>
      )}
    </div>
  )
}
