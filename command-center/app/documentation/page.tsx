'use client'

import { useState } from 'react'
import { SpotlightCard } from '@/components/SpotlightCard'
import { Book, Terminal, BarChart3, Zap, HelpCircle, ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

type Section = {
  id: string
  title: string
  icon: React.ComponentType<{ size?: number; className?: string }>
  content: React.ReactNode
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="bg-secondary/60 border border-border/60 rounded-lg p-4 text-xs overflow-x-auto font-mono leading-relaxed text-foreground/90 whitespace-pre">
      {children}
    </pre>
  )
}

function Table({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border/60">
            {headers.map(h => (
              <th key={h} className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border/30 last:border-0">
              {row.map((cell, j) => (
                <td key={j} className={cn(
                  'py-2 px-3 text-sm',
                  j === 0 && 'font-mono text-xs text-blue-600 dark:text-blue-400',
                )}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Accordion({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-border/40 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-secondary/40 transition-colors text-left"
      >
        <span>{title}</span>
        {open ? <ChevronDown size={14} className="text-muted-foreground" /> : <ChevronRight size={14} className="text-muted-foreground" />}
      </button>
      {open && (
        <div className="px-4 pb-4 pt-2 space-y-3 border-t border-border/40 text-sm text-muted-foreground leading-relaxed">
          {children}
        </div>
      )}
    </div>
  )
}

const SECTIONS: Section[] = [
  {
    id: 'pipeline',
    title: 'Pipeline Scripts',
    icon: Terminal,
    content: (
      <div className="space-y-6">
        <div>
          <h3 className="font-semibold mb-2">tailor_resume.py</h3>
          <p className="text-sm text-muted-foreground mb-3">
            Analyzes a job description with Claude and produces a tailored resume, cover letter, and full JD analysis.
          </p>
          <CodeBlock>{`# Tailor from a JD file
python pipeline/tailor_resume.py --jd path/to/job_description.txt

# Tailor from pasted text (prints full analysis)
python pipeline/tailor_resume.py --jd-text "full JD here" --show-analysis

# Skip cover letter
python pipeline/tailor_resume.py --jd path/to/jd.txt --no-cover`}
          </CodeBlock>
          <div className="mt-3">
            <Table
              headers={['File', 'Contents']}
              rows={[
                ['resume.md', 'Tailored resume in Markdown'],
                ['resume.html', 'Styled, print-ready HTML'],
                ['resume.pdf', 'PDF generated via Chrome CDP'],
                ['cover_letter.md', '3-paragraph cover letter snippet'],
                ['analysis.json', 'ATS keywords, match score, skill gaps'],
                ['job_description.txt', 'Original JD text'],
              ]}
            />
          </div>
        </div>

        <div>
          <h3 className="font-semibold mb-2">tracker.py</h3>
          <p className="text-sm text-muted-foreground mb-3">
            Manages the application log CSV and the Q&A knowledge base CSV.
          </p>
          <CodeBlock>{`# Log a new application
python pipeline/tracker.py log \\
  --company "Acme Corp" --title "Senior AI Engineer" \\
  --url "https://linkedin.com/jobs/view/..." \\
  --mode Remote --salary '$180K-$200K' --easy-apply

# Record a question encountered mid-application
python pipeline/tracker.py question \\
  --q "What is your salary expectation?" \\
  --context "Acme Corp Easy Apply"

# See all unanswered questions
python pipeline/tracker.py pending

# Answer a question (stored for reuse across all applications)
python pipeline/tracker.py answer --id Q001 --answer "Target is $200K-$250K"

# Look up a previously answered question
python pipeline/tracker.py lookup --q "salary expectations"

# Update application status
python pipeline/tracker.py update-status \\
  --company "Acme Corp" --title "Senior AI Engineer" --status "Phone Screen"

# List all applications
python pipeline/tracker.py list`}
          </CodeBlock>
        </div>

        <div>
          <h3 className="font-semibold mb-2">cover_letter.py</h3>
          <CodeBlock>{`python pipeline/cover_letter.py --company "Acme Corp" --title "Senior AI Engineer"`}</CodeBlock>
        </div>

        <div>
          <h3 className="font-semibold mb-2">followup.py</h3>
          <CodeBlock>{`# Preview follow-up emails (dry run)
python pipeline/followup.py --dry-run

# Send follow-up emails
python pipeline/followup.py`}
          </CodeBlock>
        </div>
      </div>
    ),
  },
  {
    id: 'command-center',
    title: 'Command Center',
    icon: BarChart3,
    content: (
      <div className="space-y-6">
        <div>
          <h3 className="font-semibold mb-2">Starting the server</h3>
          <CodeBlock>{`cd command-center

# Development (with hot reload)
npm run dev

# Production
npm run build && npm start`}
          </CodeBlock>
          <p className="text-sm text-muted-foreground mt-2">
            The custom server integrates Next.js, a WebSocket server on <code className="font-mono text-xs bg-secondary/60 px-1 py-0.5 rounded">/ws</code>, and chokidar file watching. The browser receives live updates when CSVs change.
          </p>
        </div>

        <div>
          <h3 className="font-semibold mb-2">Pages</h3>
          <Table
            headers={['Route', 'Purpose']}
            rows={[
              ['/', 'Dashboard: metrics, pipeline funnel, activity feed'],
              ['/applications', 'Full application table with scores, filters, sort'],
              ['/applications/[slug]', 'Application detail: resume, cover letter, ATS analysis, pipeline actions'],
              ['/jobs', 'Job queue: paste URL to auto-process, LinkedIn results'],
              ['/qa', 'Q&A knowledge base: unanswered at top, inline editing'],
              ['/analytics', 'Charts: volume, funnel, response rates, match score correlation'],
              ['/settings', 'Candidate profile, pipeline config, integration status'],
              ['/documentation', 'This page'],
            ]}
          />
        </div>

        <div>
          <h3 className="font-semibold mb-2">API Routes</h3>
          <Table
            headers={['Endpoint', 'Purpose']}
            rows={[
              ['GET /api/applications', 'All applications, enriched with match score + ATS coverage'],
              ['PATCH /api/applications/[id]', 'Update a single row (status, notes, etc.)'],
              ['GET /api/qa', 'All Q&A entries'],
              ['PATCH /api/qa/[id]', 'Save an answer'],
              ['POST /api/qa', 'Add a new question'],
              ['GET /api/analytics', 'Aggregated stats from CSV'],
              ['GET /api/settings', 'Read candidate profile from .env'],
              ['PATCH /api/settings', 'Write candidate profile to .env'],
              ['POST /api/jobs/queue', 'Add URL to processing queue'],
              ['GET /api/jobs/queue', 'Read queue.json'],
              ['GET /api/activity', 'Recent events derived from CSV timestamps'],
              ['POST /api/pipeline/stream', 'Run pipeline script, stream stdout back'],
              ['GET /api/file', 'Serve files from applications/ and pipeline/'],
            ]}
          />
        </div>

        <div>
          <h3 className="font-semibold mb-2">Environment variables</h3>
          <CodeBlock>{`# Required
ANTHROPIC_API_KEY=sk-ant-...
CANDIDATE_NAME=Yury Primakov
CANDIDATE_EMAIL=you@gmail.com
CANDIDATE_PHONE=555-555-5555
CANDIDATE_LOCATION=City, State
CANDIDATE_TITLE=Principal AI Engineer
CANDIDATE_WEBSITE=yoursite.com

# Optional
COMMAND_CENTER_PASSWORD=your-password  # Enables login page
PORT=3000`}
          </CodeBlock>
        </div>
      </div>
    ),
  },
  {
    id: 'jobs-queue',
    title: 'Job Queue',
    icon: Zap,
    content: (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Paste any job posting URL into the queue on the Jobs page. The server automatically fetches the JD text and runs the tailoring pipeline in the background.
        </p>
        <div>
          <h3 className="font-semibold mb-2">Queue statuses</h3>
          <Table
            headers={['Status', 'Meaning']}
            rows={[
              ['pending', 'URL submitted, waiting to process'],
              ['processing', 'Fetching JD and running tailor_resume.py'],
              ['ready', 'Resume, cover letter, and analysis generated'],
              ['failed', 'Error during processing (see error message)'],
            ]}
          />
        </div>
        <div>
          <h3 className="font-semibold mb-2">Limitations</h3>
          <p className="text-sm text-muted-foreground">
            LinkedIn job URLs require authentication and cannot be fetched headlessly. These will fail with "Page content too short." For LinkedIn postings, copy and paste the JD text into the tailoring form on the Application Detail page instead.
          </p>
        </div>
        <div>
          <h3 className="font-semibold mb-2">Queue file</h3>
          <CodeBlock>{`# jobs/queue.json — auto-created
[
  {
    "id": "1710700000000",
    "url": "https://company.com/jobs/123",
    "status": "ready",
    "completedAt": "2026-03-18T10:30:00.000Z"
  }
]`}
          </CodeBlock>
        </div>
      </div>
    ),
  },
  {
    id: 'ats-scoring',
    title: 'ATS Scoring',
    icon: BarChart3,
    content: (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Each application is scored against two metrics derived from <code className="font-mono text-xs bg-secondary/60 px-1 py-0.5 rounded">analysis.json</code>:
        </p>
        <div>
          <h3 className="font-semibold mb-2">Match Score</h3>
          <p className="text-sm text-muted-foreground">
            Claude&apos;s overall assessment of how well your profile matches the role, on a 0-100 scale. Considers skills, experience level, and stated requirements. Stored as <code className="font-mono text-xs bg-secondary/60 px-1 py-0.5 rounded">match_score</code> in analysis.json.
          </p>
        </div>
        <div>
          <h3 className="font-semibold mb-2">ATS Coverage (Before / After)</h3>
          <p className="text-sm text-muted-foreground">
            Percentage of ATS keywords from the JD that appear in the resume text.
          </p>
          <ul className="mt-2 space-y-1 text-sm text-muted-foreground list-disc list-inside">
            <li><strong>Before</strong>: keyword coverage in <code className="font-mono text-xs bg-secondary/60 px-1 py-0.5 rounded">pipeline/resume_base.md</code> (your base resume, before tailoring)</li>
            <li><strong>After</strong>: keyword coverage in <code className="font-mono text-xs bg-secondary/60 px-1 py-0.5 rounded">applications/[folder]/resume.md</code> (tailored resume)</li>
          </ul>
          <p className="mt-2 text-sm text-muted-foreground">
            A large improvement (e.g. 15% to 85%) indicates the tailoring successfully incorporated missing keywords.
          </p>
        </div>
        <div>
          <h3 className="font-semibold mb-2">Color thresholds</h3>
          <Table
            headers={['Match Score', 'Color']}
            rows={[
              ['80 and above', 'Green'],
              ['60-79', 'Yellow'],
              ['Below 60', 'Red'],
            ]}
          />
          <Table
            headers={['ATS Coverage', 'Color']}
            rows={[
              ['70% and above', 'Green'],
              ['50-69%', 'Yellow'],
              ['Below 50%', 'Red'],
            ]}
          />
        </div>
      </div>
    ),
  },
  {
    id: 'qa',
    title: 'Q&A Knowledge Base',
    icon: HelpCircle,
    content: (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Every question encountered during an application is stored in <code className="font-mono text-xs bg-secondary/60 px-1 py-0.5 rounded">jobs/application_qa.csv</code>. Once answered, the answer is reused for similar questions in all future applications.
        </p>
        <div>
          <h3 className="font-semibold mb-2">CSV columns</h3>
          <Table
            headers={['Column', 'Purpose']}
            rows={[
              ['ID', 'Auto-incremented identifier (Q001, Q002, ...)'],
              ['Question', 'The question text as encountered'],
              ['Context (where it appeared)', 'Company and application context'],
              ['Answer', 'Your stored answer (blank if unanswered)'],
              ['Date Added', 'When the question was first recorded'],
            ]}
          />
        </div>
        <div>
          <h3 className="font-semibold mb-2">Command line usage</h3>
          <CodeBlock>{`# Record a question
python pipeline/tracker.py question \\
  --q "What is your notice period?" \\
  --context "Acme Corp Easy Apply"

# Answer it
python pipeline/tracker.py answer --id Q001 --answer "2 weeks"

# Look up an existing answer
python pipeline/tracker.py lookup --q "notice period"`}
          </CodeBlock>
        </div>
      </div>
    ),
  },
  {
    id: 'resume-formatting',
    title: 'Resume Formatting Rules',
    icon: Book,
    content: (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          The pipeline enforces these rules in every tailored output. Your <code className="font-mono text-xs bg-secondary/60 px-1 py-0.5 rounded">resume_base.md</code> must follow them or the PDF layout will break.
        </p>
        <div className="space-y-3">
          <Accordion title="No em dashes">
            <p>Replace all em dashes (--) with commas, colons, or semicolons. Em dashes render inconsistently across PDF renderers.</p>
          </Accordion>
          <Accordion title="No horizontal rules">
            <p>Do not use <code className="font-mono text-xs bg-secondary/60 px-1 py-0.5 rounded">---</code> between sections. Spacing is controlled by CSS in the HTML template.</p>
          </Accordion>
          <Accordion title="Section headers">
            <p>Wrap all section headers in a centered div:</p>
            <CodeBlock>{`<div align="center">

## Experience

</div>`}
            </CodeBlock>
          </Accordion>
          <Accordion title="Company entries">
            <p>Use this exact format for each company block:</p>
            <CodeBlock>{`**Company Name** <span style="float:right">Month YYYY – Month YYYY</span>
*Job Title*

- Bullet point one
- Bullet point two`}
            </CodeBlock>
          </Accordion>
          <Accordion title="Contact bar">
            <p>Use <code className="font-mono text-xs bg-secondary/60 px-1 py-0.5 rounded">&amp;nbsp;·&amp;nbsp;</code> as the separator, inside a centered div:</p>
            <CodeBlock>{`<div align="center">

Name &nbsp;·&nbsp; email@example.com &nbsp;·&nbsp; 555-555-5555

</div>`}
            </CodeBlock>
          </Accordion>
          <Accordion title="Education and Certifications">
            <p>Use plain text lines with no bullet points. Dates on the same line, right-aligned with a float span.</p>
          </Accordion>
        </div>
      </div>
    ),
  },
]

export default function DocumentationPage() {
  const [activeSection, setActiveSection] = useState<string>(SECTIONS[0].id)

  const section = SECTIONS.find(s => s.id === activeSection) ?? SECTIONS[0]

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Documentation</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Pipeline scripts, Command Center usage, and data formats</p>
      </div>

      <div className="flex gap-6 items-start">
        {/* Sidebar nav */}
        <div className="w-52 shrink-0">
          <SpotlightCard>
            <nav className="p-2 space-y-0.5">
              {SECTIONS.map(s => {
                const Icon = s.icon
                const active = s.id === activeSection
                return (
                  <button
                    key={s.id}
                    onClick={() => setActiveSection(s.id)}
                    className={cn(
                      'w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium text-left',
                      'transition-all duration-150',
                      active
                        ? 'bg-background/80 shadow-sm text-blue-600 dark:text-blue-400'
                        : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50',
                    )}
                  >
                    <Icon size={14} className={active ? 'text-blue-600 dark:text-blue-400' : ''} />
                    <span>{s.title}</span>
                  </button>
                )
              })}
            </nav>
          </SpotlightCard>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <SpotlightCard>
            <div className="p-6">
              <div className="flex items-center gap-3 mb-6 pb-4 border-b border-border/40">
                {(() => {
                  const Icon = section.icon
                  return <Icon size={18} className="text-blue-600 dark:text-blue-400" />
                })()}
                <h2 className="text-lg font-semibold">{section.title}</h2>
              </div>
              {section.content}
            </div>
          </SpotlightCard>
        </div>
      </div>
    </div>
  )
}
