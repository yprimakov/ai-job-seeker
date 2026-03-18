// Custom Node.js server: Next.js + WebSocket + chokidar
const { createServer } = require('http')
const { parse } = require('url')
const next = require('next')
const { WebSocketServer } = require('ws')
const chokidar = require('chokidar')
const path = require('path')
const fs = require('fs')
const { spawn } = require('child_process')

const dev = process.env.NODE_ENV !== 'production'
const port = parseInt(process.env.PORT || '3051', 10)

const ROOT = path.join(__dirname, '..')
const QUEUE_PATH = path.join(ROOT, 'jobs', 'queue.json')
const PIPELINE_DIR = path.join(ROOT, 'pipeline')

// ── Queue auto-processor ──────────────────────────────────────────────────────

let queueProcessing = false

function readQueue() {
  try {
    if (!fs.existsSync(QUEUE_PATH)) return []
    return JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'))
  } catch { return [] }
}

function writeQueue(items) {
  try { fs.writeFileSync(QUEUE_PATH, JSON.stringify(items, null, 2), 'utf-8') } catch (e) {
    console.error('[Queue] Failed to write queue.json:', e.message)
  }
}

async function fetchJDText(url) {
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
    signal: AbortSignal.timeout(20000),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status} from ${url}`)
  const html = await res.text()
  const text = html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ').trim()
  if (text.length < 200) throw new Error('Page content too short — may require authentication or JavaScript rendering')
  return text
}

function runScript(args, cwd) {
  return new Promise((resolve, reject) => {
    const proc = spawn('python', args, { cwd, shell: process.platform === 'win32', stdio: 'inherit' })
    proc.on('close', code => code === 0 ? resolve() : reject(new Error(`Process exited with code ${code}`)))
    proc.on('error', reject)
  })
}

async function processQueue() {
  if (queueProcessing) return
  queueProcessing = true
  try {
    const items = readQueue()
    const pending = items.filter(i => i.status === 'pending')
    if (!pending.length) return

    for (const item of pending) {
      console.log(`[Queue] Processing ${item.id}: ${item.url}`)
      item.status = 'processing'
      writeQueue(items)

      try {
        const jdText = await fetchJDText(item.url)
        const tmpPath = path.join(ROOT, 'jobs', `queue_jd_${item.id}.txt`)
        fs.writeFileSync(tmpPath, jdText, 'utf-8')

        await runScript(['tailor_resume.py', '--jd', tmpPath], PIPELINE_DIR)

        try { fs.unlinkSync(tmpPath) } catch { /* ok */ }

        item.status = 'ready'
        item.completedAt = new Date().toISOString()
        console.log(`[Queue] Completed ${item.id}`)
      } catch (err) {
        item.status = 'failed'
        item.error = String(err.message ?? err)
        console.error(`[Queue] Failed ${item.id}:`, item.error)
      }

      writeQueue(items)
    }
  } catch (err) {
    console.error('[Queue] Worker error:', err)
  } finally {
    queueProcessing = false
  }
}

// ─────────────────────────────────────────────────────────────────────────────

const WATCH_PATHS = [
  path.join(ROOT, 'jobs', 'application_tracker.csv'),
  path.join(ROOT, 'jobs', 'application_qa.csv'),
  path.join(ROOT, 'jobs', 'linkedin_results.md'),
  path.join(ROOT, 'jobs', 'queue.json'),
]

const app = next({ dev, dir: __dirname })
const handle = app.getRequestHandler()

// Track connected WebSocket clients
const clients = new Set()

function broadcast(payload) {
  const msg = JSON.stringify(payload)
  for (const ws of clients) {
    if (ws.readyState === 1 /* OPEN */) {
      ws.send(msg)
    }
  }
}

app.prepare().then(() => {
  const server = createServer((req, res) => {
    const parsedUrl = parse(req.url, true)
    handle(req, res, parsedUrl)
  })

  // WebSocket server attached to the same HTTP server
  const wss = new WebSocketServer({ noServer: true })

  // Next.js upgrade handler (HMR in dev mode)
  const nextUpgrade = app.getUpgradeHandler ? app.getUpgradeHandler() : null

  server.on('upgrade', (req, socket, head) => {
    const { pathname } = parse(req.url)
    if (pathname === '/ws') {
      wss.handleUpgrade(req, socket, head, ws => {
        wss.emit('connection', ws, req)
      })
    } else if (nextUpgrade) {
      // Forward HMR and other Next.js websocket connections
      nextUpgrade(req, socket, head)
    } else {
      socket.destroy()
    }
  })

  wss.on('connection', ws => {
    clients.add(ws)
    ws.on('close', () => clients.delete(ws))
    ws.on('error', () => clients.delete(ws))
    // Send a ping to confirm connection
    ws.send(JSON.stringify({ type: 'connected' }))
  })

  // File watchers
  const watcher = chokidar.watch(WATCH_PATHS, {
    persistent: true,
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 300, pollInterval: 50 },
  })

  watcher.on('change', filePath => {
    const name = path.basename(filePath)
    if (name === 'application_tracker.csv') {
      broadcast({ type: 'tracker_updated' })
    } else if (name === 'application_qa.csv') {
      broadcast({ type: 'qa_updated' })
    } else if (name === 'linkedin_results.md') {
      broadcast({ type: 'results_updated' })
    } else if (name === 'queue.json') {
      broadcast({ type: 'results_updated' })
      processQueue()
    }
  })

  server.listen(port, () => {
    console.log(`> Command Center ready on http://localhost:${port}`)
    console.log(`> WebSocket server on ws://localhost:${port}/ws`)
    console.log(`> Watching ${WATCH_PATHS.length} files for changes`)
    if (!dev) console.log('> Running in production mode')
    // Process any pending queue items on startup
    setTimeout(() => processQueue(), 2000)
  })
})
