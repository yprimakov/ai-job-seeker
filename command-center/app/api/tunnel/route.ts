import { NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'
import os from 'os'

export const dynamic = 'force-dynamic'

export async function POST() {
  const scriptPath = path.join(os.homedir(), '.agents', 'skills', 'here-now', 'scripts', 'publish.sh')
  const port = process.env.PORT || '3051'

  // Publish the local server URL via here.now
  return new Promise<NextResponse>(resolve => {
    const proc = spawn('bash', [scriptPath, `http://localhost:${port}`, '--ttl', '86400', '--client', 'claude-code'], {
      timeout: 30_000,
    })

    let output = ''
    proc.stdout.on('data', (d: Buffer) => { output += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { output += d.toString() })

    proc.on('close', code => {
      // Try to extract URL from output
      const urlMatch = output.match(/https?:\/\/[^\s]+\.here\.now[^\s]*/i)
      if (urlMatch) {
        resolve(NextResponse.json({ url: urlMatch[0] }))
      } else if (code !== 0) {
        resolve(NextResponse.json({ error: output || 'Tunnel failed' }, { status: 500 }))
      } else {
        resolve(NextResponse.json({ url: null, output }))
      }
    })

    proc.on('error', err => {
      resolve(NextResponse.json({ error: err.message }, { status: 500 }))
    })
  })
}
