import type { Customer, UserProfile } from '../api/types'

function normalizeToken(input?: string | null) {
  return String(input || '').trim().toLowerCase().replace(/\s+/g, '')
}

function userTokens(user?: UserProfile | null) {
  const tokens = [
    normalizeToken(user?.username),
    normalizeToken(user?.real_name),
    ...String(user?.real_name || '')
      .split(/\s+/)
      .map((part) => normalizeToken(part))
  ]
  return Array.from(new Set(tokens.filter((token) => token.length >= 2)))
}

function textTokens(customer: Customer) {
  return {
    identity: [customer.name, customer.customer_code, customer.legacy_company_id].map(normalizeToken).filter(Boolean),
    owner: [customer.salesperson_name, customer.lister].map(normalizeToken).filter(Boolean)
  }
}

function fieldScore(fields: string[], tokens: string[], exactScore: number, containsScore: number) {
  for (const field of fields) {
    for (const token of tokens) {
      if (field === token) return exactScore
    }
  }
  for (const field of fields) {
    for (const token of tokens) {
      if (field.includes(token) || (field.length >= 3 && token.includes(field))) return containsScore
    }
  }
  return Number.POSITIVE_INFINITY
}

export function customerUserPriority(customer: Customer, user?: UserProfile | null) {
  const tokens = userTokens(user)
  if (!tokens.length) return Number.POSITIVE_INFINITY
  const fields = textTokens(customer)
  return Math.min(
    fieldScore(fields.identity, tokens, 0, 1),
    fieldScore(fields.owner, tokens, 0, 2)
  )
}

export function sortCustomersForCurrentUser(customers: Customer[], user?: UserProfile | null) {
  return customers
    .map((customer, index) => ({
      customer,
      index,
      priority: Number.isFinite(customerUserPriority(customer, user)) ? customerUserPriority(customer, user) : 999
    }))
    .sort((a, b) => a.priority - b.priority || a.index - b.index)
    .map((entry) => entry.customer)
}
