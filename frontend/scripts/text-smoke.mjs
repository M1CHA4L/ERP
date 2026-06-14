import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'

const roots = ['src', 'index.html']
const sourceExtensions = new Set(['.vue', '.ts', '.js', '.mjs', '.html', '.json'])
const badPatterns = ['�', '锟', 'Ã', 'Â', 'Î', 'Ð', 'Ë', '£', '谷旋', '隆辺', '住豚', '人薩']

async function* walk(target) {
  const stats = await readdir(target, { withFileTypes: true }).catch(() => null)
  if (!stats) {
    yield target
    return
  }

  for (const entry of stats) {
    const next = path.join(target, entry.name)
    if (entry.isDirectory()) {
      if (['node_modules', 'dist', '.vite'].includes(entry.name)) continue
      yield* walk(next)
    } else {
      yield next
    }
  }
}

function shouldScan(filePath) {
  return sourceExtensions.has(path.extname(filePath))
}

const failures = []

for (const root of roots) {
  for await (const filePath of walk(root)) {
    if (!shouldScan(filePath)) continue
    const text = await readFile(filePath, 'utf8')
    const lines = text.split(/\r?\n/)
    lines.forEach((line, index) => {
      const matches = badPatterns.filter((pattern) => line.includes(pattern))
      if (matches.length) {
        failures.push(`${filePath}:${index + 1}: suspicious text ${matches.join(', ')}: ${line.trim()}`)
      }
    })
  }
}

if (failures.length) {
  console.error('[FAIL] suspicious frontend text found')
  failures.forEach((failure) => console.error(`  - ${failure}`))
  process.exit(1)
}

console.log('[PASS] frontend text smoke scanned src and index.html')
