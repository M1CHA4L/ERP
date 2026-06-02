import { nextTick, watch } from 'vue'
import { locale } from '../stores/language'

const translatedTextNodes = new WeakMap<Text, string>()
const translatedAttributes = new WeakMap<Element, Record<string, string>>()

const exactTranslations: Record<string, string> = {
  孟加拉上海制版: 'Bangladesh Shanghai Plate',
  系统管理员: 'System Admin',
  管理员: 'Admin',
  老板: 'Owner',
  销售跟单: 'Sales Follow-up',
  生产主管: 'Production Manager',
  雕刻操作员: 'Engraving Operator',
  镀铬操作员: 'Chrome Plating Operator',
  质检员: 'Inspector',
  送货人员: 'Delivery Staff',
  财务人员: 'Finance Staff',
  管理: 'Management',
  工作台: 'Dashboard',
  设计部: 'Design',
  生产部: 'Production',
  质量部: 'Quality',
  销售部: 'Sales',
  仓储物流: 'Warehouse Logistics',
  财务部: 'Finance',
  刷新: 'Refresh',
  新增: 'New',
  新建: 'New',
  保存: 'Save',
  保存草稿: 'Save Draft',
  保存成本: 'Save Cost',
  取消: 'Cancel',
  删除: 'Delete',
  编辑: 'Edit',
  详情: 'Details',
  操作: 'Actions',
  查看: 'View',
  开始: 'Start',
  完成: 'Complete',
  报工: 'Report',
  完成报工: 'Complete Report',
  派工: 'Dispatch',
  保存派工: 'Save Dispatch',
  复制: 'Copy',
  提交: 'Submit',
  上传: 'Upload',
  下载: 'Download',
  导出: 'Export',
  '导出 Excel': 'Export Excel',
  新增客户: 'New Customer',
  新增产品: 'New Product',
  新建订单: 'New Order',
  新增明细: 'Add Line',
  新增用户: 'New User',
  新增工艺路线: 'New Process Route',
  新增工序模板: 'New Process Template',
  编辑产品: 'Edit Product',
  编辑用户: 'Edit User',
  编辑工序模板: 'Edit Process Template',
  客户: 'Customer',
  客户编号: 'Customer Code',
  客户名称: 'Customer Name',
  客户详情: 'Customer Details',
  联系人: 'Contact',
  电话: 'Phone',
  地址: 'Address',
  账期: 'Payment Terms',
  账期天数: 'Payment Terms Days',
  当前订单: 'Current Orders',
  历史订单: 'Order History',
  产品: 'Product',
  产品编码: 'Product Code',
  产品名称: 'Product Name',
  产品模板: 'Product Template',
  产品摘要: 'Product Summary',
  规格: 'Specification',
  单位: 'Unit',
  数量: 'Quantity',
  单价: 'Unit Price',
  参考价: 'Reference Price',
  金额: 'Amount',
  合计: 'Total',
  订单: 'Order',
  订单中控台: 'Order Control Center',
  订单概览: 'Order Overview',
  订单编号: 'Order No.',
  订单信息: 'Order Info',
  订单明细: 'Order Lines',
  订单金额: 'Order Amount',
  订单状态: 'Order Status',
  下单日期: 'Order Date',
  交期: 'Due Date',
  交期正常: 'Due Date Normal',
  已结束: 'Closed',
  优先级: 'Priority',
  备注: 'Remark',
  工艺路线: 'Process Route',
  路线: 'Route',
  路线名称: 'Route Name',
  路线编码: 'Route Code',
  默认路线: 'Default Route',
  默认工艺路线: 'Default Process Route',
  整单默认工艺路线: 'Default Route for Order',
  工序: 'Process Step',
  工序编码: 'Step Code',
  工序名称: 'Step Name',
  工序模板: 'Step Template',
  工序流转: 'Step Flow',
  工序数量: 'Step Count',
  当前工序: 'Current Step',
  工单: 'Work Order',
  工单编号: 'Work Order No.',
  工单详情: 'Work Order Details',
  工单信息: 'Work Order Info',
  工单状态: 'Work Order Status',
  工单数量: 'Work Order Count',
  生产工单: 'Work Orders',
  生产看板: 'Production Board',
  我的任务: 'My Tasks',
  任务状态: 'Task Status',
  当前推进: 'Current Action',
  闭环进度: 'Closed-loop Progress',
  接单确认: 'Order Confirmation',
  生产流转: 'Production Flow',
  质检通过: 'QC Passed',
  送货签收: 'Delivery Sign-off',
  财务结清: 'Financial Settlement',
  生产进度: 'Production Progress',
  已完成工序: 'Completed Steps',
  工序总数: 'Total Steps',
  待检工序: 'Pending QC Steps',
  工序队列: 'Step Queue',
  当前卡点: 'Current Bottleneck',
  可开工任务: 'Ready to Start',
  现场进行中: 'In Progress On Site',
  等待质检: 'Waiting for QC',
  返工异常: 'Rework Exceptions',
  需处理: 'Action Needed',
  未派工: 'Unassigned',
  需主管分配: 'Supervisor Assignment Needed',
  逾期风险: 'Overdue Risk',
  负责人: 'Owner',
  计划完成: 'Planned Finish',
  订单交期: 'Order Due Date',
  到期日: 'Due Date',
  计划开始: 'Planned Start',
  实际开始: 'Actual Start',
  实际完成: 'Actual Finish',
  工时: 'Hours',
  加工数量: 'Processed Qty',
  合格数量: 'Qualified Qty',
  不良数量: 'Defective Qty',
  现场照片: 'Site Photos',
  现场附件: 'Site Attachments',
  质检: 'QC',
  质检返工: 'QC & Rework',
  质检编号: 'QC No.',
  质检图片: 'QC Images',
  质检记录: 'QC Records',
  检验: 'Inspection',
  检验结果: 'Inspection Result',
  检验数量: 'Inspected Qty',
  检验时间: 'Inspection Time',
  通过数量: 'Passed Qty',
  最新质检: 'Latest QC',
  原因: 'Reason',
  '原因/备注': 'Reason / Remark',
  返工回到工序: 'Rework To Step',
  提交质检: 'Submit QC',
  待检任务: 'Pending QC Tasks',
  送货: 'Delivery',
  送货管理: 'Deliveries',
  客户与交付: 'Customer & Delivery',
  送货状态: 'Delivery Status',
  送货记录: 'Delivery Records',
  可送货订单: 'Deliverable Orders',
  送货单: 'Delivery Orders',
  送货单号: 'Delivery No.',
  送货地址: 'Delivery Address',
  送货时间: 'Delivery Time',
  司机: 'Driver',
  '司机/物流': 'Driver / Logistics',
  物流单号: 'Logistics No.',
  签收: 'Sign',
  签收人: 'Signed By',
  签收时间: 'Signed At',
  签收确认: 'Sign Confirmation',
  发货: 'Ship',
  已发货: 'Shipped',
  已签收: 'Signed',
  创建: 'Create',
  确认签收: 'Confirm Sign',
  生成送货单: 'Create Delivery Order',
  送货单已创建: 'Delivery order created',
  送货单已发货: 'Delivery order shipped',
  请填写签收人: 'Please enter signer',
  '签收完成，可进入财务应收': 'Signed, ready for receivables',
  已签收待生成应收: 'Signed Deliveries Awaiting Receivables',
  财务: 'Finance',
  财务与成本: 'Finance & Cost',
  财务状态: 'Finance Status',
  财务应收: 'Receivables',
  应收账款: 'Receivables',
  应收编号: 'Receivable No.',
  应收金额: 'Receivable Amount',
  未收款: 'Outstanding',
  已收: 'Received',
  未收: 'Balance',
  收款: 'Payment',
  收款状态: 'Payment Status',
  收款登记: 'Payment Entry',
  收款金额: 'Payment Amount',
  收款日期: 'Payment Date',
  收款方式: 'Payment Method',
  流水号: 'Reference No.',
  生成应收: 'Create Receivable',
  成本利润: 'Costs & Profit',
  销售报表: 'Sales Reports',
  销售月成绩: 'Salesperson Monthly Results',
  客户月销售额: 'Customer Monthly Sales',
  业务员: 'Salesperson',
  新支数: 'New Pcs',
  旧支数: 'Old Pcs',
  销售额: 'Sales Amount',
  平均单价: 'Average Price',
  结算方式: 'Settlement Type',
  开始日期: 'Start Date',
  结束日期: 'End Date',
  选择业务员: 'Select Salesperson',
  生产通知单: 'Production Notice',
  生产单: 'Production Notice',
  打印中心: 'Print Center',
  生产通知单入口: 'Production Notice Entry',
  待打印生产通知单: 'Production Notices To Print',
  打印留痕: 'Print Audit Trail',
  单据类型: 'Document Type',
  订单号: 'Order No.',
  订单号或产品名称: 'Order No. or Product Name',
  '订单号 / 产品 / 客户 / 版号': 'Order No. / Product / Customer / Cylinder No.',
  版号: 'Cylinder No.',
  下单开始: 'Order Date From',
  下单结束: 'Order Date To',
  打印: 'Print',
  打印号: 'Print No.',
  目标类型: 'Target Type',
  目标: 'Target',
  目标ID: 'Target ID',
  '目标 ID': 'Target ID',
  打印时间: 'Printed At',
  快照: 'Snapshot',
  车间任务单: 'Workshop Task Sheet',
  委托书打印版式: 'Entrust Sheet Layout',
  保存版式: 'Save Layout',
  委托书版式已保存: 'Entrust Sheet Layout Saved',
  版式已保存: 'Layout Saved',
  标题类型: 'Title Type',
  'Layout 样式': 'Layout Style',
  颜色列数: 'Color Columns',
  左侧标注: 'Left Label',
  中间标注: 'Center Label',
  右侧标注: 'Right Label',
  上方说明: 'Top Note',
  下方说明: 'Bottom Note',
  '宽度/雕刻说明': 'Width / Engraving Note',
  '自定义 Layout 要求': 'Custom Layout Requirement',
  显示主信息: 'Show Main Info',
  显示颜色表: 'Show Color Table',
  '显示 Layout': 'Show Layout',
  显示要求: 'Show Requirements',
  三段式版面: 'Three-section Layout',
  整版窗口: 'Single Window',
  只显示文字要求: 'Text Only',
  统计全部: 'Include All',
  只统计返工: 'Only Rework',
  不统计返工: 'Exclude Rework',
  导出销售月绩: 'Export Sales Results',
  导出客户月销售额: 'Export Customer Monthly Sales',
  按当前日期和返工口径汇总: 'Summarized by current date range and rework mode',
  '退镀、返工、旧版归为旧支数': 'Dechrome, rework, and old cylinder orders count as old pcs',
  来自订单总金额: 'From order total amount',
  工艺与生产: 'Process & Production',
  录入成本: 'Add Cost',
  成本记录: 'Cost Records',
  成本类型: 'Cost Type',
  成本日期: 'Cost Date',
  当前报表总收入: 'Current Report Revenue',
  '人工/材料/外协/加工等': 'Labor / Materials / Outsourcing / Processing',
  '订单金额 - 总成本': 'Order Amount - Total Cost',
  '毛利 / 订单金额': 'Gross Profit / Order Amount',
  '订单 ID': 'Order ID',
  总成本: 'Total Cost',
  毛利: 'Gross Profit',
  毛利率: 'Gross Margin',
  利润报表: 'Profit Report',
  类型: 'Type',
  日期: 'Date',
  销售订单: 'Sales Order',
  人工成本: 'Labor Cost',
  材料成本: 'Material Cost',
  外协成本: 'Outsourcing Cost',
  加工费用: 'Processing Fee',
  其他: 'Other',
  基础数据清理: 'Master Data Cleanup',
  '停用、未引用、可恢复资料': 'Disabled, unused, and recoverable data',
  停用工序: 'Disabled Steps',
  '可重新启用或删除未引用项': 'Re-enable or delete unused items',
  未用工序: 'Unused Steps',
  '尚未进入路线/工单': 'Not used in routes/work orders',
  异常路线: 'Route Issues',
  草稿或已禁用路线: 'Draft or disabled routes',
  未用产品: 'Unused Products',
  尚未被订单引用: 'Not referenced by orders',
  停用产品: 'Disabled Products',
  可从这里恢复误删档案: 'Recover mistakenly deleted records here',
  重新启用: 'Re-enable',
  删除未引用: 'Delete Unused',
  恢复草稿: 'Restore Draft',
  恢复: 'Restore',
  已删除: 'Deleted',
  工序模板已重新启用: 'Step template re-enabled',
  工艺路线已恢复为草稿: 'Process route restored to draft',
  产品档案已恢复: 'Product record restored',
  工序模板已删除: 'Step template deleted',
  工艺路线已禁用: 'Process route disabled',
  删除确认: 'Delete Confirmation',
  禁用确认: 'Disable Confirmation',
  '确定删除这个未引用的工序模板吗？删除后不能被路线选择。': 'Delete this unused step template? It will no longer be available for routes.',
  '确定禁用这条工艺路线吗？已被引用的历史订单和工单不会被删除。': 'Disable this process route? Referenced historical orders and work orders will be kept.',
  产品档案: 'Product Master',
  清理原因: 'Cleanup Reason',
  引用: 'References',
  状态: 'Status',
  编码: 'Code',
  名称: 'Name',
  分类: 'Category',
  启用: 'Active',
  禁用: 'Disabled',
  草稿: 'Draft',
  已确认: 'Confirmed',
  生产中: 'In Production',
  待送货: 'Pending Delivery',
  已送货: 'Delivered',
  待收款: 'Pending Payment',
  已结清: 'Closed',
  已取消: 'Cancelled',
  已暂停: 'Paused',
  返工中: 'Reworking',
  待排产: 'Pending Schedule',
  已排产: 'Scheduled',
  部分完成: 'Partially Completed',
  已完成: 'Completed',
  未开始: 'Not Started',
  待加工: 'Pending',
  加工中: 'Processing',
  待检验: 'Pending QC',
  检验通过: 'QC Passed',
  检验失败: 'QC Failed',
  已跳过: 'Skipped',
  待检: 'Pending QC',
  返工: 'Rework',
  待开票: 'Pending Invoice',
  已开票: 'Invoiced',
  部分收款: 'Partially Paid',
  已收款: 'Paid',
  逾期: 'Overdue',
  普通: 'Normal',
  加急: 'Urgent',
  需要: 'Required',
  否: 'No',
  是: 'Yes',
  银行转账: 'Bank Transfer',
  现金: 'Cash',
  微信: 'WeChat',
  支付宝: 'Alipay',
  用户权限: 'Users & Roles',
  显示已禁用: 'Show Disabled',
  权限测试账号: 'Permission Test Accounts',
  演示环境: 'Demo Environment',
  岗位: 'Position',
  用户名: 'Username',
  密码: 'Password',
  默认入口: 'Default Entry',
  适合验证: 'Suggested Test Scope',
  姓名: 'Name',
  部门: 'Department',
  邮箱: 'Email',
  角色: 'Roles',
  操作日志: 'Operation Logs',
  模块: 'Module',
  成本: 'Cost',
  报表: 'Reports',
  动作: 'Action',
  对象: 'Target',
  对象ID: 'Target ID',
  '对象 ID': 'Target ID',
  内容: 'Content',
  时间: 'Time',
  操作人: 'Operator',
  选择客户: 'Select Customer',
  选择交期: 'Select Due Date',
  选择路线: 'Select Route',
  选择方式: 'Select Method',
  选择订单: 'Select Order',
  选择角色: 'Select Roles',
  '新密码（不填则不修改）': 'New password (leave blank to keep unchanged)',
  '完整菜单、用户权限、基础数据清理、所有业务操作': 'Full menu, user permissions, master data cleanup, and all business actions',
  '经营看板、业务全流程查看，不进入用户权限管理': 'Business dashboard and full-flow viewing, without user permission management',
  '销售/跟单': 'Sales / Follow-up',
  老板账号: 'Owner Account',
  '老板/管理员': 'Owner / Admin',
  '仓库/送货人员': 'Warehouse / Delivery Staff',
  工序操作员: 'Process Operator',
  订单管理: 'Order Management',
  '客户、产品、订单创建与确认，查看送货/应收': 'Customers, products, order creation and confirmation, plus delivery and receivables viewing',
  设计人员: 'Designer',
  '查看订单、产品、工艺路线和工单': 'View orders, products, process routes, and work orders',
  '工艺维护、生成工单、派工、生产看板': 'Process maintenance, work order creation, dispatching, and production board',
  操作员: 'Operator',
  '只看本人任务，开始加工和报工': 'Only own tasks, start processing, and submit reports',
  '查看待检任务、提交质检、发起返工': 'View pending QC tasks, submit QC, and start rework',
  '可送货、签收，不看财务和系统设置': 'Handle delivery and sign-off, without finance or system settings',
  '应收、收款、成本利润和导出': 'Receivables, payments, cost/profit, and exports',
  '请填写用户名、姓名和密码': 'Please enter username, name, and password',
  用户已更新: 'User updated',
  用户已创建: 'User created',
  删除用户: 'Delete User',
  用户已删除: 'User deleted',
  搜索客户名称或编号: 'Search customer name or code',
  搜索产品名称或编码: 'Search product name or code',
  可选模板: 'Optional template',
  可手动填写: 'Manual input',
  可选: 'Optional',
  不填则自动生成: 'Auto-generate if empty',
  暂无附件: 'No attachments',
  暂无: 'None',
  暂无工单: 'No work orders',
  暂无质检记录: 'No QC records',
  暂无送货单: 'No delivery orders',
  暂无应收: 'No receivables',
  暂无成本记录: 'No cost records',
  未选择路线: 'No route selected',
  已选择路线: 'Route selected',
  未生成应收: 'No receivable created',
  暂无进度记录: 'No timeline records',
  暂无任务: 'No tasks',
  暂无需要清理的工序模板: 'No step templates to clean',
  暂无需要清理的工艺路线: 'No process routes to clean',
  暂无需要清理的产品档案: 'No products to clean',
  返回订单: 'Back to Orders',
  返回工单: 'Back to Work Orders',
  确认订单: 'Confirm Order',
  生成工单: 'Create Work Orders',
  查看生产: 'View Production',
  查看送货: 'View Delivery',
  查看应收: 'View Receivables',
  查看工单: 'View Work Order',
  订单附件: 'Order Attachments',
  '订单附件 / 图纸 / 样品图': 'Order Attachments / Drawings / Sample Images',
  图纸: 'Drawings',
  样品图: 'Sample Images',
  工单附件: 'Work Order Attachments',
  订单进度时间线: 'Order Timeline',
  工单进度时间线: 'Work Order Timeline',
  订单创建: 'Order Created',
  '从接单、生产、质检、送货到财务收款的完整记录': 'Complete record from order intake, production, QC, delivery, to payment',
  等待确认订单: 'Waiting for Order Confirmation',
  '选择工艺路线后确认订单，确认后才能生成生产工单。': 'Select a process route and confirm the order before creating work orders.',
  等待生成工单: 'Waiting for Work Orders',
  '按订单明细和工艺路线生成工单，之后进入工序派工。': 'Create work orders from order lines and routes, then dispatch process steps.',
  生产与质检推进中: 'Production and QC in Progress',
  '关注当前卡点、待检任务和返工异常，保证工序按顺序流转。': 'Watch bottlenecks, pending QC, and rework exceptions to keep steps flowing in order.',
  等待送货: 'Waiting for Delivery',
  '检验通过后可生成送货单并完成客户签收。': 'After QC passes, create a delivery order and complete customer sign-off.',
  等待生成应收: 'Waiting for Receivable',
  '送货签收后由财务生成应收账款。': 'Finance creates receivables after delivery sign-off.',
  等待收款: 'Waiting for Payment',
  '跟进账期、部分收款和尾款结清。': 'Track payment terms, partial payments, and final settlement.',
  订单已进入收尾: 'Order Is Closing',
  '订单闭环数据已沉淀，可用于利润和客户复盘。': 'Closed-loop order data is ready for profit and customer review.'
}

const textPatterns: Array<[RegExp, (match: RegExpMatchArray) => string]> = [
  [/^共\s*(\d+)\s*项$/, (match) => `${match[1]} items`],
  [/^(\d+)\s*天$/, (match) => `${match[1]} days`],
  [/^逾期\s*(\d+)\s*天$/, (match) => `${match[1]} days overdue`],
  [/^(\d+)\s*天内到期$/, (match) => `Due in ${match[1]} days`],
  [/^(\d+)\s*单$/, (match) => `${match[1]} orders`],
  [/^(\d+)\s*张工单$/, (match) => `${match[1]} work orders`],
  [/^(\d+)\s*个工序$/, (match) => `${match[1]} steps`],
  [/^(\d+)\s*条$/, (match) => `${match[1]} records`],
  [/^(\d+)\s*条记录$/, (match) => `${match[1]} records`],
  [/^(\d+)\s*笔$/, (match) => `${match[1]} records`],
  [/^(\d+)\s*项明细$/, (match) => `${match[1]} line items`],
  [/^(\d+)\s*张$/, (match) => `${match[1]} sheets`],
  [/^(\d+)\s*个文件$/, (match) => `${match[1]} files`],
  [/^(\d+)\s*道工序$/, (match) => `${match[1]} steps`],
  [/^(\d+)\s*项$/, (match) => `${match[1]} items`],
  [/^订单\s*(\d+)$/, (match) => `Order ${match[1]}`],
  [/^订单\s+(.+)\s+已建立，金额\s+(.+)$/, (match) => `Order ${match[1]} created, amount ${match[2]}`],
  [/^计划交期\s+(.+)$/, (match) => `Planned due date ${match[1]}`],
  [/^合计\s+(.+)$/, (match) => `Total ${match[1]}`],
  [/^客户详情：(.+)$/, (match) => `Customer Details: ${match[1]}`],
  [/^确定删除用户「(.+)」吗？系统会禁用该账号并保留历史业务记录。$/, (match) => `Delete user "${match[1]}"? The account will be disabled and historical business records will be kept.`],
  [/^(\d+)\.\s*(.+)$/, (match) => `${match[1]}. ${translateText(match[2])}`],
]

const attributeNames = ['placeholder', 'title', 'aria-label']

function hasHanText(value: string) {
  return /[\u3400-\u9fff]/.test(value)
}

function preserveWhitespace(original: string, translated: string) {
  const leading = original.match(/^\s*/)?.[0] || ''
  const trailing = original.match(/\s*$/)?.[0] || ''
  return `${leading}${translated}${trailing}`
}

export function translateText(original: string) {
  const trimmed = original.trim()
  if (!trimmed) return original
  const exact = exactTranslations[trimmed]
  if (exact) return preserveWhitespace(original, exact)
  for (const [pattern, formatter] of textPatterns) {
    const match = trimmed.match(pattern)
    if (match) return preserveWhitespace(original, formatter(match))
  }
  return original
}

function shouldSkipElement(element: Element) {
  return ['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA'].includes(element.tagName)
}

function translateTextNode(node: Text) {
  if (!node.textContent || !node.textContent.trim()) return
  let original = translatedTextNodes.get(node)
  if (locale.value === 'en') {
    if (!original) {
      if (!hasHanText(node.textContent)) return
      original = node.textContent
      translatedTextNodes.set(node, original)
    }
  } else if (!original) {
    return
  }
  const nextValue = locale.value === 'en' ? translateText(original) : original
  if (node.textContent !== nextValue) {
    node.textContent = nextValue
  }
}

function translateAttributes(element: Element) {
  let originals = translatedAttributes.get(element)
  for (const attributeName of attributeNames) {
    const value = element.getAttribute(attributeName)
    if (!value) continue
    if (locale.value === 'en' && !originals?.[attributeName] && !hasHanText(value)) continue
    if (!originals) {
      originals = {}
      translatedAttributes.set(element, originals)
    }
    if (!originals[attributeName]) {
      originals[attributeName] = value
    }
    const original = originals[attributeName]
    const nextValue = locale.value === 'en' ? translateText(original) : original
    if (value !== nextValue) {
      element.setAttribute(attributeName, nextValue)
    }
  }
}

function translateTree(root: ParentNode) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT)
  let current = walker.nextNode()
  while (current) {
    if (current.nodeType === Node.ELEMENT_NODE) {
      const element = current as Element
      if (shouldSkipElement(element)) {
        current = walker.nextSibling()
        continue
      }
      translateAttributes(element)
    } else if (current.nodeType === Node.TEXT_NODE) {
      translateTextNode(current as Text)
    }
    current = walker.nextNode()
  }
}

export function useDomTranslator() {
  let observer: MutationObserver | null = null
  let scheduled = false

  function scheduleTranslate() {
    if (scheduled) return
    scheduled = true
    window.requestAnimationFrame(() => {
      scheduled = false
      translateTree(document.body)
    })
  }

  nextTick(() => {
    translateTree(document.body)
    observer = new MutationObserver(scheduleTranslate)
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: attributeNames,
    })
  })

  watch(locale, () => {
    nextTick(scheduleTranslate)
  })

  return () => observer?.disconnect()
}
