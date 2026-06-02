import type { UserProfile } from '../api/types'

export interface NavItem {
  label: string
  labelKey: string
  path: string
  icon: string
  permission: string
  roles?: string[]
}

export const navItems: NavItem[] = [
  { label: '工作台', labelKey: 'nav.dashboard', path: '/dashboard', icon: 'DataBoard', permission: 'dashboard:view' },
  { label: '客户管理', labelKey: 'nav.customers', path: '/customers', icon: 'OfficeBuilding', permission: 'customer:view' },
  { label: '版号追踪', labelKey: 'nav.cylinders', path: '/cylinders', icon: 'Memo', permission: 'cylinder:view' },
  { label: '产品管理', labelKey: 'nav.products', path: '/products', icon: 'Goods', permission: 'product:view' },
  { label: '制版下单', labelKey: 'nav.orders', path: '/orders', icon: 'Tickets', permission: 'order:view' },
  { label: '工艺路线', labelKey: 'nav.processRoutes', path: '/process-routes', icon: 'Connection', permission: 'route:view' },
  {
    label: '生产工单',
    labelKey: 'nav.workOrders',
    path: '/work-orders',
    icon: 'SetUp',
    permission: 'work_order:view',
    roles: ['admin', 'boss', 'sales', 'designer', 'production_manager', 'inspector']
  },
  {
    label: '生产看板',
    labelKey: 'nav.productionBoard',
    path: '/production-board',
    icon: 'Grid',
    permission: 'work_order:view',
    roles: ['admin', 'boss', 'production_manager']
  },
  {
    label: '我的任务',
    labelKey: 'nav.myTasks',
    path: '/my-tasks',
    icon: 'Finished',
    permission: 'step:report',
    roles: ['admin', 'production_manager', 'operator']
  },
  { label: '质检返工', labelKey: 'nav.inspections', path: '/inspections', icon: 'CircleCheck', permission: 'inspection:view' },
  { label: '库存来料', labelKey: 'nav.inventory', path: '/inventory', icon: 'Box', permission: 'inventory:view' },
  { label: '送货管理', labelKey: 'nav.deliveries', path: '/deliveries', icon: 'Van', permission: 'delivery:view' },
  { label: '财务应收', labelKey: 'nav.finance', path: '/finance', icon: 'Wallet', permission: 'finance:receivable:view' },
  { label: '日收入月结', labelKey: 'nav.receipts', path: '/receipts', icon: 'Money', permission: 'finance:receivable:view' },
  {
    label: '生产通知单',
    labelKey: 'nav.productionNotices',
    path: '/production-notices',
    icon: 'Printer',
    permission: 'order:view',
    roles: ['admin', 'boss', 'sales', 'designer', 'production_manager']
  },
  {
    label: '打印中心',
    labelKey: 'nav.printJobs',
    path: '/print-jobs',
    icon: 'Printer',
    permission: 'report:view',
    roles: ['admin', 'boss', 'finance', 'production_manager']
  },
  {
    label: '销售报表',
    labelKey: 'nav.salesReports',
    path: '/sales-reports',
    icon: 'TrendCharts',
    permission: 'report:view',
    roles: ['admin', 'boss', 'finance', 'sales']
  },
  { label: '成本利润', labelKey: 'nav.costs', path: '/costs', icon: 'TrendCharts', permission: 'cost:view' },
  { label: '基础数据清理', labelKey: 'nav.maintenance', path: '/maintenance', icon: 'Tools', permission: 'master_data:cleanup' },
  { label: '操作日志', labelKey: 'nav.logs', path: '/logs', icon: 'Document', permission: 'log:view' },
  { label: '用户权限', labelKey: 'nav.users', path: '/users', icon: 'User', permission: 'system:permission' }
]

export function canSeeNavItem(item: NavItem, user: UserProfile | null) {
  if (!user?.permissions.includes(item.permission)) return false
  if (!item.roles?.length) return true
  return item.roles.some((role) => user.roles.includes(role))
}

export function visibleNavItems(user: UserProfile | null) {
  return navItems.filter((item) => canSeeNavItem(item, user))
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
  for (const [role, path] of byRole) {
    if (user?.roles.includes(role) && visible.some((item) => item.path === path)) {
      return path
    }
  }
  return visible[0]?.path || '/dashboard'
}
