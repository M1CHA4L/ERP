import { session, hasPermission } from '../stores/session'

export function hasAnyRole(roles: string[]) {
  return roles.some((role) => session.user?.roles.includes(role))
}

export function canUse(permission?: string, roles?: string[]) {
  const permissionAllowed = hasPermission(permission)
  const roleAllowed = roles?.length ? hasAnyRole(roles) : true
  return permissionAllowed && roleAllowed
}

export const roleGroups = {
  orderOperators: ['admin', 'boss', 'sales'],
  productionOperators: ['admin', 'boss', 'production_manager'],
  deliveryOperators: ['admin', 'boss', 'delivery'],
  financeOperators: ['admin', 'boss', 'finance'],
  costOperators: ['admin', 'boss', 'finance'],
}
