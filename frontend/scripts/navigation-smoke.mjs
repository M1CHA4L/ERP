import { readFile } from 'node:fs/promises'

const navText = await readFile('src/data/navigation.ts', 'utf8')
const routerText = await readFile('src/router/index.ts', 'utf8')

function parseRoles(rawRoles) {
  if (!rawRoles) return []
  return rawRoles
    .split(',')
    .map((role) => role.trim().replace(/^['"]|['"]$/g, ''))
    .filter(Boolean)
    .sort()
}

function parseNavItems(text) {
  const items = []
  const itemPattern =
    /\{\s*label:[\s\S]*?path:\s*'([^']+)'[\s\S]*?permission:\s*'([^']+)'[\s\S]*?group:\s*'[^']+'(?:,\s*roles:\s*\[([^\]]*)\])?[\s\S]*?\}/g
  let match = itemPattern.exec(text)
  while (match) {
    items.push({
      path: match[1],
      permission: match[2],
      roles: parseRoles(match[3])
    })
    match = itemPattern.exec(text)
  }
  return items
}

function parseRoutes(text) {
  const routes = new Map()
  const routePattern =
    /\{\s*path:\s*'([^']+)'[\s\S]*?meta:\s*\{\s*permission:\s*'([^']+)'(?:,\s*roles:\s*\[([^\]]*)\])?/g
  let match = routePattern.exec(text)
  while (match) {
    if (match[1].includes(':')) {
      match = routePattern.exec(text)
      continue
    }
    routes.set(`/${match[1]}`.replace(/\/+/g, '/'), {
      permission: match[2],
      roles: parseRoles(match[3])
    })
    match = routePattern.exec(text)
  }
  return routes
}

const navItems = parseNavItems(navText)
const routes = parseRoutes(routerText)
const failures = []

for (const item of navItems) {
  const route = routes.get(item.path)
  if (!route) continue
  if (item.permission !== route.permission) {
    failures.push(`${item.path}: permission mismatch nav=${item.permission} route=${route.permission}`)
  }
  if (item.roles.join('|') !== route.roles.join('|')) {
    failures.push(
      `${item.path}: role mismatch nav=[${item.roles.join(', ')}] route=[${route.roles.join(', ')}]`
    )
  }
}

if (failures.length) {
  console.error('[FAIL] navigation and router permissions are out of sync')
  failures.forEach((failure) => console.error(`  - ${failure}`))
  process.exit(1)
}

console.log('[PASS] navigation and router permissions are aligned')
