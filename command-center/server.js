// Custom Node.js server: Next.js + WebSocket + chokidar
const { createServer } = require('http')
const { parse } = require('url')
const next = require('next')
const { WebSocketServer } = require('ws')
const chokidar = require('chokidar')
const path = require('path')

const dev = process.env.NODE_ENV !== 'production'
const port = parseInt(process.env.PORT || '3000', 10)

const ROOT = path.join(__dirname, '..')
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
    } else if (name === 'linkedin_results.md' || name === 'queue.json') {
      broadcast({ type: 'results_updated' })
    }
  })

  server.listen(port, () => {
    console.log(`> Command Center ready on http://localhost:${port}`)
    console.log(`> WebSocket server on ws://localhost:${port}/ws`)
    console.log(`> Watching ${WATCH_PATHS.length} files for changes`)
    if (!dev) console.log('> Running in production mode')
  })
})
