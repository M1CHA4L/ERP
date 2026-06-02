import { reactive } from 'vue'
import type { UserProfile } from '../api/types'

const rawUser = localStorage.getItem('erp_user')
const DEVICE_MAC_KEY = 'erp_device_mac_address'

export const session = reactive<{
  token: string
  user: UserProfile | null
}>({
  token: localStorage.getItem('erp_token') || '',
  user: rawUser ? JSON.parse(rawUser) : null
})

export function setSession(token: string, user: UserProfile) {
  session.token = token
  session.user = user
  localStorage.setItem('erp_token', token)
  localStorage.setItem('erp_user', JSON.stringify(user))
}

export function clearSession() {
  session.token = ''
  session.user = null
  localStorage.removeItem('erp_token')
  localStorage.removeItem('erp_user')
}

export function getDeviceMacAddress() {
  let deviceId = localStorage.getItem(DEVICE_MAC_KEY)
  if (!deviceId) {
    const randomPart =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(16).slice(2)}`
    deviceId = `WEB-${randomPart}`
    localStorage.setItem(DEVICE_MAC_KEY, deviceId)
  }
  return deviceId
}

export function hasPermission(code?: string) {
  if (!code) return true
  return Boolean(session.user?.permissions.includes(code))
}
