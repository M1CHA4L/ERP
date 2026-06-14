import type { UserProfile } from '../api/types'

export interface NavGroup {
  key: 'order' | 'manufacturing' | 'inventory' | 'finance' | 'management'
  label: string
}

export interface NavItem {
  label: string
  labelKey: string
  path: string
  icon: string
  permission: string
  group: NavGroup['key']
  roles?: string[]
}

export const navGroups: NavGroup[] = [
  { key: 'order', label: '下单' },
  { key: 'manufacturing', label: '制造' },
  { key: 'inventory', label: '库存' },
  { key: 'finance', label: '财务' },
  { key: 'management', label: '管理' }
]

export const navItems: NavItem[] = [
  { label: '工作台', labelKey: 'nav.dashboard', path: '/dashboard', icon: 'DataBoard', permission: 'dashboard:view', group: 'management' },
  { label: '制版下单', labelKey: 'nav.orders', path: '/orders', icon: 'Tickets', permission: 'order:view', group: 'order' },
  { label: '客户管理', labelKey: 'nav.customers', path: '/customers', icon: 'OfficeBuilding', permission: 'customer:view', group: 'order' },
  { label: '版号追踪', labelKey: 'nav.cylinders', path: '/cylinders', icon: 'Memo', permission: 'cylinder:view', group: 'order' },
  {
    label: '生产工单',
    labelKey: 'nav.workOrders',
    path: '/work-orders',
    icon: 'SetUp',
    permission: 'work_order:view',
    group: 'manufacturing',
    roles: ['admin', 'boss', 'sales', 'designer', 'production_manager', 'inspector']
  },
  {
    label: '工序看板',
    labelKey: 'nav.productionBoard',
    path: '/production-board',
    icon: 'Grid',
    permission: 'work_order:view',
    group: 'manufacturing',
    roles: ['admin', 'boss', 'production_manager']
  },
  {
    label: '订单进度',
    labelKey: 'nav.workflowV2',
    path: '/workflows',
    icon: 'Share',
    permission: 'workflow_v2:view',
    group: 'manufacturing'
  },
  {
    label: '工序任务',
    labelKey: 'nav.myTasks',
    path: '/my-tasks',
    icon: 'Finished',
    permission: 'step:report',
    group: 'manufacturing',
    roles: ['admin', 'production_manager', 'operator']
  },
  { label: '质检返工', labelKey: 'nav.inspections', path: '/inspections', icon: 'CircleCheck', permission: 'inspection:view', group: 'manufacturing' },
  { label: '送货管理', labelKey: 'nav.deliveries', path: '/deliveries', icon: 'Van', permission: 'delivery:view', group: 'manufacturing' },
  { label: '库存来料', labelKey: 'nav.inventory', path: '/inventory', icon: 'Box', permission: 'inventory:view', group: 'inventory' },
  {
    label: '财务应收',
    labelKey: 'nav.finance',
    path: '/finance',
    icon: 'Wallet',
    permission: 'finance:receivable:view',
    group: 'finance',
    roles: ['admin', 'boss', 'finance']
  },
  {
    label: '日收入月结',
    labelKey: 'nav.receipts',
    path: '/receipts',
    icon: 'Money',
    permission: 'finance:receivable:view',
    group: 'finance',
    roles: ['admin', 'boss', 'finance']
  },
  {
    label: '打印记录',
    labelKey: 'nav.printJobs',
    path: '/print-jobs',
    icon: 'Printer',
    permission: 'report:view',
    group: 'finance',
    roles: ['admin', 'boss', 'finance', 'production_manager']
  },
  {
    label: '销售报表',
    labelKey: 'nav.salesReports',
    path: '/sales-reports',
    icon: 'TrendCharts',
    permission: 'report:view',
    group: 'finance',
    roles: ['admin', 'boss', 'finance', 'sales']
  },
  { label: '成本利润', labelKey: 'nav.costs', path: '/costs', icon: 'TrendCharts', permission: 'cost:view', group: 'finance' },
  { label: '基础数据清理', labelKey: 'nav.maintenance', path: '/maintenance', icon: 'Tools', permission: 'master_data:cleanup', group: 'management' },
  { label: '操作日志', labelKey: 'nav.logs', path: '/logs', icon: 'Document', permission: 'log:view', group: 'management' },
  { label: '用户权限', labelKey: 'nav.users', path: '/users', icon: 'User', permission: 'system:permission', group: 'management' }
]

export function canSeeNavItem(item: NavItem, user: UserProfile | null) {
  const permissions = user?.permissions || []
  const roles = user?.roles || []
  if (!permissions.includes(item.permission)) return false
  if (!item.roles?.length) return true
  return item.roles.some((role) => roles.includes(role))
}

export function visibleNavItems(user: UserProfile | null) {
  return navItems.filter((item) => canSeeNavItem(item, user))
}

export function visibleNavGroups(user: UserProfile | null) {
  const visibleItems = visibleNavItems(user)
  return navGroups
    .map((group) => ({
      ...group,
      items: visibleItems.filter((item) => item.group === group.key)
    }))
    .filter((group) => group.items.length > 0)
}

export function canSeePath(path: string, user: UserProfile | null) {
  const item = navItems.find((navItem) => navItem.path === path)
  return item ? canSeeNavItem(item, user) : true
}

export function preferredHomePath(user: UserProfile | null) {
  const byRole: Array<[string, string]> = [
    ['operator', '/my-tasks'],
    ['production_manager', '/production-board'],
    ['inspector', '/inspections'],
    ['delivery', '/inventory'],
    ['finance', '/receipts'],
    ['sales', '/orders'],
    ['designer', '/work-orders']
  ]
  const visible = visibleNavItems(user)
  const roles = user?.roles || []
  for (const [role, path] of byRole) {
    if (roles.includes(role) && visible.some((item) => item.path === path)) {
      return path
    }
  }
  return visible[0]?.path || '/dashboard'
}
