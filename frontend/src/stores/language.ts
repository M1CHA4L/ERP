import { computed, ref } from 'vue'

export type Locale = 'zh' | 'en'

const rawLocale = localStorage.getItem('erp_locale')

export const locale = ref<Locale>(rawLocale === 'en' ? 'en' : 'zh')

type TranslationValue = {
  zh: string
  en: string
}

const dictionary: Record<string, TranslationValue> = {
  'app.subtitle': {
    zh: '版号、生产、库存、收款、客户账单闭环',
    en: 'Cylinder, production, inventory, receipt and statement loop'
  },
  'app.logout': { zh: '退出', en: 'Logout' },
  'app.language': { zh: 'EN', en: '中文' },
  'brand.short': { zh: '孟加拉上海制版', en: 'Bangladesh Shanghai Plate' },
  'brand.full': {
    zh: '孟加拉上海制版有限公司',
    en: 'Bangladesh Shanghai Plate Making Co., Ltd.'
  },
  'login.title': { zh: '制版 ERP', en: 'Plate Making ERP' },
  'login.username': { zh: '用户名', en: 'Username' },
  'login.password': { zh: '密码', en: 'Password' },
  'login.submit': { zh: '登录', en: 'Sign in' },
  'login.success': { zh: '登录成功', en: 'Signed in' },
  'login.failure': { zh: '登录失败，请检查账号或后端服务', en: 'Sign-in failed. Check your account or backend service.' },
  'nav.dashboard': { zh: '工作台', en: 'Dashboard' },
  'nav.customers': { zh: '客户管理', en: 'Customers' },
  'nav.cylinders': { zh: '版号追踪', en: 'Cylinder Ledger' },
  'nav.products': { zh: '产品管理', en: 'Products' },
  'nav.orders': { zh: '制版下单', en: 'Plate Orders' },
  'nav.processRoutes': { zh: '工艺路线', en: 'Process Routes' },
  'nav.workOrders': { zh: '生产工单', en: 'Work Orders' },
  'nav.productionBoard': { zh: '生产看板', en: 'Production Board' },
  'nav.myTasks': { zh: '我的任务', en: 'My Tasks' },
  'nav.inspections': { zh: '质检返工', en: 'QC & Rework' },
  'nav.deliveries': { zh: '送货管理', en: 'Deliveries' },
  'nav.finance': { zh: '财务应收', en: 'Receivables' },
  'nav.receipts': { zh: '日收入月结', en: 'Receipts & Month Close' },
  'nav.productionNotices': { zh: '生产通知单', en: 'Production Notices' },
  'nav.printJobs': { zh: '打印中心', en: 'Print Center' },
  'nav.salesReports': { zh: '销售报表', en: 'Sales Reports' },
  'nav.inventory': { zh: '库存来料', en: 'Inventory & Materials' },
  'nav.costs': { zh: '成本利润', en: 'Costs & Profit' },
  'nav.maintenance': { zh: '基础数据清理', en: 'Master Data Cleanup' },
  'nav.logs': { zh: '操作日志', en: 'Operation Logs' },
  'nav.users': { zh: '用户权限', en: 'Users & Roles' },
  'role.admin': { zh: '管理员', en: 'Admin' },
  'role.boss': { zh: '老板', en: 'Owner' },
  'role.sales': { zh: '销售/跟单', en: 'Sales' },
  'role.designer': { zh: '设计', en: 'Designer' },
  'role.production_manager': { zh: '生产主管', en: 'Production Manager' },
  'role.operator': { zh: '操作员', en: 'Operator' },
  'role.inspector': { zh: '质检', en: 'Inspector' },
  'role.delivery': { zh: '仓库/送货', en: 'Warehouse/Delivery' },
  'role.finance': { zh: '财务', en: 'Finance' },
  'common.refresh': { zh: '刷新', en: 'Refresh' },
  'common.exportExcel': { zh: '导出 Excel', en: 'Export Excel' },
  'common.noFlowAccess': { zh: '当前岗位没有流程看板入口', en: 'No flow entry for this role' },
  'common.noAttentionAccess': { zh: '当前岗位暂无异常入口', en: 'No exception entry for this role' },
  'dashboard.quickEntries': { zh: '我的入口', en: 'My Shortcuts' },
  'dashboard.quickHint': { zh: '按当前账号权限显示', en: 'Shown by current account permissions' },
  'dashboard.flowTitle': { zh: '订单闭环工作台', en: 'Order-to-Cash Workspace' },
  'dashboard.flowHint': { zh: '接单到收款', en: 'Order to cash' },
  'dashboard.metric.draft': { zh: '待确认订单', en: 'Orders to Confirm' },
  'dashboard.metric.draftHint': { zh: '销售接单后待确认', en: 'Draft orders awaiting confirmation' },
  'dashboard.metric.confirmed': { zh: '待生成工单', en: 'Work Orders Needed' },
  'dashboard.metric.confirmedHint': { zh: '已确认未投产', en: 'Confirmed but not released' },
  'dashboard.metric.production': { zh: '生产中订单', en: 'In Production' },
  'dashboard.metric.productionHint': { zh: '正在工序流转', en: 'Moving through production steps' },
  'dashboard.metric.delivery': { zh: '待送货订单', en: 'Pending Delivery' },
  'dashboard.metric.deliveryHint': { zh: '检验通过待发货', en: 'QC passed, awaiting delivery' },
  'dashboard.metric.payment': { zh: '待收款订单', en: 'Pending Payment' },
  'dashboard.metric.paymentHint': { zh: '送货后待结算', en: 'Delivered and awaiting settlement' },
  'dashboard.stage.sales': { zh: '接单确认', en: 'Order Confirm' },
  'dashboard.stage.production': { zh: '生产流转', en: 'Production Flow' },
  'dashboard.stage.qc': { zh: '质检返工', en: 'QC & Rework' },
  'dashboard.stage.delivery': { zh: '送货签收', en: 'Delivery Sign-off' },
  'dashboard.stage.finance': { zh: '财务收款', en: 'Finance Collection' },
  'dashboard.stage.salesSubtitle': { zh: '{draft} 草稿 / {confirmed} 已确认', en: '{draft} draft / {confirmed} confirmed' },
  'dashboard.stage.productionSubtitle': { zh: '{steps} 道现场工序', en: '{steps} active steps' },
  'dashboard.stage.qcSubtitle': { zh: '{pending} 道待检 / {rework} 道返工', en: '{pending} pending QC / {rework} rework' },
  'dashboard.stage.deliverySubtitle': { zh: '{pending} 待送 / {delivered} 已送', en: '{pending} pending / {delivered} delivered' },
  'dashboard.stage.financeSubtitle': { zh: '{pending} 待收 / {paid} 结清', en: '{pending} pending / {paid} closed' },
  'dashboard.queue': { zh: '生产队列', en: 'Production Queue' },
  'dashboard.queueSteps': { zh: '{count} 道工序', en: '{count} steps' },
  'dashboard.pending': { zh: '待加工', en: 'Pending' },
  'dashboard.processing': { zh: '加工中', en: 'Processing' },
  'dashboard.pendingInspection': { zh: '待检验', en: 'Pending QC' },
  'dashboard.reworking': { zh: '返工中', en: 'Reworking' },
  'dashboard.attention': { zh: '异常关注', en: 'Exceptions' },
  'dashboard.attentionCount': { zh: '{count} 项', en: '{count} items' },
  'dashboard.overdueOrders': { zh: '逾期订单', en: 'Overdue Orders' },
  'dashboard.reworkOrders': { zh: '返工订单', en: 'Rework Orders' },
  'dashboard.reworkSteps': { zh: '返工工序', en: 'Rework Steps' }
}

export const languageButtonLabel = computed(() => dictionary['app.language'][locale.value])

export function setLocale(nextLocale: Locale) {
  locale.value = nextLocale
  localStorage.setItem('erp_locale', nextLocale)
}

export function toggleLocale() {
  setLocale(locale.value === 'zh' ? 'en' : 'zh')
}

export function t(key: string, params?: Record<string, string | number>) {
  let value = dictionary[key]?.[locale.value] || dictionary[key]?.zh || key
  if (params) {
    for (const [name, paramValue] of Object.entries(params)) {
      value = value.split(`{${name}}`).join(String(paramValue))
    }
  }
  return value
}
