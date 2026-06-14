export interface UserProfile {
  id: string
  username: string
  real_name: string
  department?: string
  roles: string[]
  permissions: string[]
  device_mac_address?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserProfile
}

export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface Customer {
  id: string
  customer_code: string
  legacy_company_id?: string
  name: string
  customer_type?: string
  is_key_customer: boolean
  salesperson_id?: string
  salesperson_name?: string
  contact_name?: string
  phone?: string
  company_phone?: string
  fax?: string
  address?: string
  payment_terms_days: number
  payment_method?: string
  minimum_price?: number
  vat_enabled?: boolean
  ait_enabled?: boolean
  advance_percent?: number
  lister?: string
  price_rules?: Array<{
    max_cm2?: number
    min_cm2?: number
    min_l?: number
    max_l?: number
    min_c?: number
    max_c?: number
    old_pcs?: number
    repair_chromium_pcs?: number
    special_cyl_price?: number
  }>
  credit_limit?: number
  tax_no?: string
  office?: string
  opening_remark?: string
  bank_name?: string
  bank_account?: string
  delivery_method?: string
  copper_thickness?: number
  chrome_time?: number
  stripping_cost?: number
  reconciliation_cycle?: string
  reconciliation_day?: number
  remark?: string
  status: string
}

export interface SalesOrderItem {
  id: string
  product_id?: string
  product_name: string
  specification?: string
  quantity: number
  unit: string
  unit_price: number
  amount: number
  route_id?: string
}

export type PlateValue = string | number | boolean | null | undefined

export interface PlateDetails {
  order_type?: PlateValue
  customer_text?: PlateValue
  product_name?: PlateValue
  total_qty?: PlateValue
  unit_l?: PlateValue
  straight?: PlateValue
  cylinder_id?: PlateValue
  increase?: PlateValue
  hole?: PlateValue
  flange?: PlateValue
  cylinder_model?: PlateValue
  cylinder_making?: PlateValue
  new_material?: PlateValue
  unit_w?: PlateValue
  crossway?: PlateValue
  order_date?: PlateValue
  order_datetime?: PlateValue
  order_time?: PlateValue
  dynamic_balance?: PlateValue
  slope?: PlateValue
  original_no?: PlateValue
  printing_method?: PlateValue
  self_bring?: PlateValue
  production_time?: PlateValue
  cylinder_cost?: PlateValue
  copper_thickness?: PlateValue
  key_way?: PlateValue
  returns?: PlateValue
  archives?: PlateValue
  inspection_requirement?: PlateValue
  no?: PlateValue
  sample_no?: PlateValue
  printings?: PlateValue
  printing_material?: PlateValue
  new_qty?: PlateValue
  self_bring_qty?: PlateValue
  salesman?: PlateValue
  sign_in_person?: PlateValue
  c_value?: PlateValue
  l_value?: PlateValue
  material_model?: PlateValue
  plate_thickness?: PlateValue
  cylinder_structure?: PlateValue
  address?: PlateValue
  lister?: PlateValue
  bag_type?: PlateValue
  material_new?: PlateValue
  set_type?: PlateValue
  dia?: PlateValue
  width?: PlateValue
  hor_ver?: PlateValue
  mark_line?: PlateValue
  test_line?: PlateValue
  test_spot?: PlateValue
  computer_position?: PlateValue
  production_position?: PlateValue
  common_remarks?: PlateValue
  engraving_requirement?: PlateValue
  proofing_requirement?: PlateValue
  computer_requirement?: PlateValue
  color_separation?: PlateValue
  engraving_note?: PlateValue
  dechrome_plan?: PlateValue
  delivery_time?: PlateValue
  charge?: PlateValue
  total_branch?: PlateValue
  finance_note?: PlateValue
  receiver_name?: PlateValue
  form_filler?: PlateValue
  chrome_requirement?: PlateValue
  polishing_requirement?: PlateValue
  rework_reason?: PlateValue
  rework_source_cylinder_no?: PlateValue
  rework_target_step?: PlateValue
  rework_quantity?: PlateValue
  rework_chargeable?: PlateValue
  reserved_plate_number_id?: PlateValue
  plate_number_kind?: PlateValue
  derivation_type?: PlateValue
  derived_source_cylinder_no?: PlateValue
  entrust_layout?: EntrustLayoutSettings
  engraving_record?: EngravingRecord
  [key: string]: PlateValue | EngravingRecord | EntrustLayoutSettings | undefined
}

export interface EntrustLayoutSettings {
  title_mode?: string
  diagram_style?: string
  color_columns?: number
  show_info_table?: boolean
  show_color_table?: boolean
  show_layout_diagram?: boolean
  show_requirements?: boolean
  left_label?: string
  center_label?: string
  right_label?: string
  top_note?: string
  bottom_note?: string
  width_label?: string
  custom_note?: string
  left_mark?: string
  empty_move?: string
  left_detection?: string
  left_empty?: string
  empty_color_move?: string
  layout_color?: string
  left_color?: string
  right_color?: string
  left_broaden?: string
  middle_broaden?: number
  right_move?: string
  right_mark?: string
  right_empty_move?: string
  right_detection?: string
  right_empty?: string
  right_broaden?: string
  printing_width?: string | number
  printing_margin?: string | number
  continuity?: boolean
  light_spot_horizontal?: number
  light_spot_vertical?: number
  light_spot_width?: number
  pattern_1mm_label?: string
  pattern_20mm_label?: string
  light_spot_upper_left?: boolean
  light_spot_upper_right?: boolean
  light_spot_lower_left?: boolean
  light_spot_lower_right?: boolean
  left_mark_enabled?: boolean
  right_mark_enabled?: boolean
  left_detection_enabled?: boolean
  right_detection_enabled?: boolean
  exclusive_use?: boolean
  mid_mark?: boolean
  left_self_mark?: boolean
  right_self_mark?: boolean
  full_line?: boolean
  full_line_width?: string | number
  layout_items?: Array<Record<string, string | number | boolean>>
  [key: string]: string | number | boolean | Array<Record<string, string | number | boolean>> | undefined
}

export interface ColorRow {
  color_no?: PlateValue
  print_color?: PlateValue
  qty?: PlateValue
  dia?: PlateValue
  real_dia?: PlateValue
  public_no?: PlateValue
  printing_method?: PlateValue
  remarks?: PlateValue
  [key: string]: PlateValue
}

export interface SalesOrder {
  id: string
  order_no: string
  legacy_bussiness_mst_id?: string
  legacy_bussiness_mst_rid?: string
  customer_id: string
  product_summary: string
  order_date: string
  due_date: string
  total_amount: number
  status: string
  priority: string
  route_id?: string
  rework_source_order_id?: string
  rework_source_work_order_id?: string
  rework_source_inspection_id?: string
  plate_details?: PlateDetails
  color_rows?: ColorRow[]
  remark?: string
  items: SalesOrderItem[]
}

export interface PlateNumberReservation {
  id: string
  plate_no: string
  prefix: string
  year_month: string
  sequence_no: number
  status: string
  assigned_user_id?: string
  used_order_id?: string
  used_at?: string
  returned_at?: string
  note?: string
  created_at: string
  updated_at: string
}

export interface EntrustSheet {
  order: SalesOrder
  customer_name?: string
  customer_address?: string
  customer_contact?: string
  customer_phone?: string
  entrust_no: string
}

export interface Product {
  id: string
  product_code: string
  name: string
  specification?: string
  unit: string
  default_route_id?: string
  reference_price?: number
  status?: string
  remark?: string
}

export interface ProcessRoute {
  id: string
  route_code: string
  name: string
  version: number
  source_route_id?: string
  source_route_code?: string
  source_route_name?: string
  description?: string
  is_default: boolean
  status: string
  product_count: number
  sales_order_count: number
  work_order_count: number
  is_used: boolean
  can_edit_steps: boolean
  steps: Array<{
    id: string
    step_no: number
    step_name: string
    process_template_id: string
    is_optional: boolean
    requires_inspection: boolean
    planned_hours?: number
    remark?: string
  }>
}

export interface ProcessTemplate {
  id: string
  code: string
  name: string
  category?: string
  requires_inspection: boolean
  enabled: boolean
}

export interface WorkOrder {
  id: string
  work_order_no: string
  sales_order_id: string
  product_name: string
  quantity: number
  status: string
  priority: string
  steps: Array<{
    id: string
    step_no: number
    step_name: string
    requires_inspection: boolean
    status: string
    assigned_user_id?: string
    planned_start_at?: string
    planned_end_at?: string
    actual_start_at?: string
    actual_end_at?: string
  }>
}

export interface WorkOrderStepTask {
  step_id: string
  work_order_id: string
  work_order_no: string
  sales_order_id: string
  order_no: string
  product_name: string
  quantity: number
  priority: string
  step_no: number
  step_name: string
  status: string
  assigned_user_id?: string
  assigned_user_name?: string
  planned_start_at?: string
  planned_end_at?: string
  actual_start_at?: string
  actual_end_at?: string
  due_date: string
  is_overdue: boolean
}

export interface ProcessQueue {
  step_name: string
  pending_count: number
  processing_count: number
  pending_inspection_count: number
  reworking_count: number
  overdue_count: number
  total_count: number
}

export interface ProductionBoard {
  pending_steps: number
  processing_steps: number
  pending_inspection_steps: number
  reworking_steps: number
  unassigned_steps: number
  overdue_steps: number
  due_today_orders: number
  queues: ProcessQueue[]
  active_tasks: WorkOrderStepTask[]
}

export interface ProductionFlowRow {
  work_order_id: string
  sales_order_id: string
  work_order_no: string
  order_no: string
  cylinder_no: string
  salesman?: string
  order_date: string
  due_date: string
  completed_date?: string
  period?: string
  customer_name: string
  product_name: string
  c_value?: string
  l_value?: string
  total_qty: number
  new_base?: string
  old_base?: string
  production_position?: string
  computer_position?: string
  square?: string
  dia?: string
  hole?: string
  slope?: string
  keyway?: string
  single_double?: string
  order_status: string
  work_order_status: string
  current_step_status?: string
  order_by?: string
  sign_in_person?: string
  printing_method?: string
  unit_l?: string
  unit_w?: string
  straight?: string
  increase?: string
  flange?: string
  cylinder_model?: string
  cylinder_making?: string
  material_model?: string
  new_material?: string
  placing_member?: string
  color_numbers?: string
  print_color?: string
  real_dia?: string
  customer_material_qty?: string
  production_qty?: string
  details: {
    steps: Array<Record<string, string | number | boolean | null>>
    process_records: Array<Record<string, string | number | boolean | null>>
    inspections: Array<Record<string, string | number | boolean | null>>
    reworks: Array<Record<string, string | number | boolean | null>>
    requirements: Record<string, string | number | boolean | null>
  }
}

export interface UserOption {
  id: string
  username: string
  real_name: string
  department: string
  phone?: string
  email?: string
  status: string
  device_mac_address?: string
  device_bound_at?: string
  last_login_at?: string
  roles: string[]
  role_permissions?: string[]
  extra_permissions?: string[]
  disabled_permissions?: string[]
  permissions?: string[]
}

export interface RoleOption {
  id: string
  code: string
  name: string
  status: string
  permissions?: string[]
}

export interface PermissionOption {
  id: string
  code: string
  name: string
  type: string
  sort_no: number
}

export interface PendingInspectionTask {
  step_id: string
  work_order_id: string
  work_order_no: string
  product_name: string
  step_no: number
  step_name: string
  quantity: number
  status: string
}

export interface InspectionRecord {
  id: string
  inspection_no: string
  sales_order_id: string
  work_order_id: string
  work_order_step_id: string
  inspector_id: string
  inspection_type: string
  result: string
  inspected_qty: number
  passed_qty?: number
  failed_qty?: number
  reason?: string
  rework_to_step_id?: string
  inspected_at: string
}

export interface DeliverableOrder {
  sales_order_id: string
  order_no: string
  customer_id: string
  customer_name: string
  address?: string
  product_summary: string
  total_amount: number
  status: string
}

export interface DeliveryOrder {
  id: string
  delivery_no: string
  legacy_order_mst_id?: string
  legacy_order_mst_rid?: string
  legacy_bill_type?: string
  sales_order_id: string
  customer_id: string
  address: string
  delivery_time: string
  driver_name?: string
  logistics_no?: string
  status: string
  signed_by?: string
  signed_at?: string
  remark?: string
  items: Array<{
    id: string
    sales_order_item_id?: string
    product_name: string
    specification?: string
    quantity: number
    unit: string
  }>
}

export interface Receivable {
  id: string
  receivable_no: string
  cylinder_no?: string
  sales_order_id?: string
  delivery_order_id?: string
  customer_id: string
  amount: number
  received_amount: number
  balance_amount: number
  due_date: string
  source_type?: string
  invoice_status: string
  finance_status: string
  status: string
}

export interface Payment {
  id: string
  payment_no: string
  receivable_id: string
  customer_id: string
  amount: number
  payment_date: string
  payment_method?: string
  reference_no?: string
  remark?: string
}

export interface ReceiptAllocation {
  id: string
  daily_entry_id: string
  customer_id: string
  sales_order_id?: string
  cylinder_no: string
  accounting_month: string
  amount: number
  remark?: string
}

export interface ReceiptDailyEntry {
  id: string
  receipt_no: string
  customer_id: string
  received_date: string
  payment_method: string
  cash_amount: number
  bank_amount: number
  other_amount: number
  total_amount: number
  salesman_name?: string
  payee_name?: string
  abstract?: string
  status: string
  checked_at?: string
  checked_by?: string
  remark?: string
  allocations: ReceiptAllocation[]
}

export interface MonthlyPaymentSummary {
  id: string
  customer_id: string
  cylinder_no: string
  accounting_month: string
  receivable_amount: number
  received_amount: number
  due_amount: number
  status: string
  calculated_at?: string
  remark?: string
}

export interface CustomerStatementRun {
  id: string
  statement_no: string
  customer_id: string
  statement_month: string
  selected_cylinder_nos: string[]
  previous_balance: number
  current_receivable: number
  received_amount: number
  due_amount: number
  status: string
  price_approval_status: string
  price_approved_at?: string
  price_approved_by?: string
  price_approval_remark?: string
  printed_at?: string
  remark?: string
}

export interface EngravingColorRow {
  date?: string
  color_order?: number
  color_no?: string
  color_cylinder_no?: string
  curve?: string
  grid_line?: string
  screen_angle?: string
  stitch?: string
  file_saved?: boolean
  shade_front?: string
  shade_middle?: string
  shade_back?: string
  thorough_front?: string
  thorough_middle?: string
  thorough_back?: string
  highlight_front?: string
  highlight_middle?: string
  highlight_back?: string
  makeup_man?: string
  remarks?: string
  [key: string]: string | number | boolean | undefined
}

export interface EngravingRecord {
  cylinder_no?: string
  product_name?: string
  salesman?: string
  phone?: string
  printed_material?: string
  printing_method?: string
  cylinder_circumference?: number
  cylinder_length?: number
  carving_width?: number
  edge?: number
  h_size?: number
  testing_block?: string
  testing_position?: string
  keyway_position?: string
  note?: string
  rows: EngravingColorRow[]
  updated_at?: string
}

export interface InventoryLot {
  id: string
  lot_no: string
  owner_type: string
  customer_id?: string
  warehouse_name: string
  supplier_name?: string
  product_name: string
  specification?: string
  unit: string
  unit_price: number
  quantity_on_hand: number
  status: string
  remark?: string
}

export interface InventoryTransaction {
  id: string
  movement_no: string
  movement_type: string
  lot_id?: string
  customer_id?: string
  sales_order_id?: string
  work_order_id?: string
  cylinder_no?: string
  warehouse_name: string
  supplier_name?: string
  product_name: string
  specification?: string
  unit: string
  quantity: number
  unit_price: number
  total_amount: number
  movement_date: string
  status: string
  handler_name?: string
  department?: string
  receiver_name?: string
  remark?: string
}

export interface CylinderStock {
  id: string
  stock_no: string
  cylinder_no: string
  customer_id?: string
  sales_order_id?: string
  warehouse_name: string
  diameter?: number
  cylinder_length?: number
  hole?: string
  area_cm2?: number
  unit_price: number
  quantity: number
  total_amount: number
  stock_status: string
  stock_in_date: string
  remark?: string
}

export interface CylinderLedger {
  cylinder_no: string
  orders: SalesOrder[]
  monthly_receipts: MonthlyPaymentSummary[]
  stocks: CylinderStock[]
}

export interface PrintJob {
  id: string
  print_no: string
  document_type: string
  target_type: string
  target_id?: string
  template_version: string
  printed_by?: string
  printed_at: string
  snapshot?: Record<string, unknown>
  remark?: string
}

export interface CostRecord {
  id: string
  sales_order_id: string
  work_order_id?: string
  work_order_step_id?: string
  cost_type: string
  amount: number
  cost_date: string
  remark?: string
}

export interface ProfitReportRow {
  sales_order_id: string
  order_no: string
  customer_name: string
  product_summary: string
  order_date: string
  due_date: string
  revenue: number
  total_cost: number
  gross_profit: number
  gross_margin: number
}

export interface ProfitReport {
  rows: ProfitReportRow[]
  summary: {
    revenue: number
    total_cost: number
    gross_profit: number
    gross_margin: number
  }
}

export interface SalesMonthlySummary {
  new_pcs: number
  old_pcs: number
  total_amount: number
}

export interface SalespersonMonthlyRow {
  salesperson: string
  customer_id: string
  customer_name: string
  settlement_type: string
  new_pcs: number
  old_pcs: number
  total_amount: number
}

export interface CustomerMonthlySalesRow {
  salesperson: string
  customer_id: string
  customer_name: string
  settlement_type: string
  pcs: number
  new_pcs: number
  old_pcs: number
  total_amount: number
  price: number
}

export interface SalespersonMonthlyReport {
  rows: SalespersonMonthlyRow[]
  summary: SalesMonthlySummary
}

export interface CustomerMonthlySalesReport {
  rows: CustomerMonthlySalesRow[]
  summary: SalesMonthlySummary
}

export interface OperationLog {
  id: string
  user_id: string
  module: string
  action: string
  target_type: string
  target_id?: string
  before_data?: Record<string, unknown>
  after_data?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

export interface FileAsset {
  id: string
  owner_type: string
  owner_id: string
  file_type: string
  file_name: string
  mime_type?: string
  size_bytes?: number
  version: number
  uploaded_by: string
  created_at: string
}

export interface TimelineItem {
  occurred_at?: string
  category: string
  title: string
  description?: string
  status?: string
  entity_type: string
  entity_id?: string
  meta: Record<string, unknown>
}

export interface MasterDataCleanup {
  summary: {
    inactive_templates: number
    unused_templates: number
    inactive_routes: number
    unused_routes: number
    inactive_products: number
    unused_products: number
  }
  templates: Array<{
    id: string
    code: string
    name: string
    category?: string
    enabled: boolean
    route_step_count: number
    work_order_step_count: number
    can_delete: boolean
    reason: string
    created_at?: string
    updated_at?: string
  }>
  routes: Array<{
    id: string
    route_code: string
    name: string
    version: number
    status: string
    product_count: number
    sales_order_count: number
    work_order_count: number
    can_restore: boolean
    reason: string
    created_at?: string
    updated_at?: string
  }>
  products: Array<{
    id: string
    product_code: string
    name: string
    specification?: string
    unit: string
    status: string
    deleted_at?: string
    sales_order_item_count: number
    work_order_count: number
    can_restore: boolean
    reason: string
    created_at?: string
    updated_at?: string
  }>
}

export interface WorkflowTemplateNode {
  id: string
  node_code: string
  node_name: string
  department?: string
  node_type: string
  sort_order: number
  branch_code?: string
  is_parallel_node: boolean
  is_join_node: boolean
  is_required: boolean
  allow_skip: boolean
  required_permission?: string
}

export interface WorkflowTemplateEdge {
  id: string
  from_node_id: string
  to_node_id: string
  condition_type: string
  condition_expression?: string
}

export interface WorkflowTemplate {
  id: string
  template_code: string
  template_name: string
  template_type: string
  version: number
  is_default: boolean
  is_active: boolean
  nodes: WorkflowTemplateNode[]
  edges: WorkflowTemplateEdge[]
}

export interface WorkflowNode {
  id: string
  order_workflow_id: string
  sales_order_id: string
  node_id: string
  node_code: string
  node_name: string
  department?: string
  node_type: string
  branch_code?: string
  sort_order: number
  status: string
  assigned_user_id?: string
  started_at?: string
  completed_at?: string
  waiting_reason?: string
  is_current: boolean
  remarks?: string
}

export interface WorkflowGraphEdge {
  from_node_code: string
  to_node_code: string
  condition_type: string
  condition_expression?: string
}

export interface WorkflowGraph {
  workflow_id: string
  sales_order_id: string
  template_id: string
  status: string
  started_at: string
  completed_at?: string
  nodes: WorkflowNode[]
  edges: WorkflowGraphEdge[]
}

export interface WorkflowJoinCheck {
  ready: boolean
  join_node_code: string
  waiting_for: string[]
  epin_completed: boolean
  copper_grind_completed: boolean
}

export interface PreOrder {
  id: string
  pre_order_no: string
  sample_no: string
  customer_id?: string
  customer_name: string
  product_name: string
  type?: string
  order_time: string
  salesperson_id?: string
  num: number
  receiver_id?: string
  print_color?: string
  remarks?: string
  status: string
  customer_confirmed_at?: string
  converted_order_id?: string
  created_at: string
  updated_at: string
}

export interface PreOrderCreatePayload {
  sample_no: string
  customer_id?: string
  customer_name: string
  product_name: string
  type?: string
  num: number
  receiver_id?: string
  print_color?: string
  remarks?: string
}

export interface ConvertPreOrderPayload {
  customer_id?: string
  due_date: string
  priority: string
  unit_price: number
  route_id?: string
}

export interface AbnormalFlow {
  id: string
  sales_order_id: string
  abnormal_type: string
  reason: string
  selected_start_node: string
  selected_process_nodes: string[]
  need_inspection: boolean
  need_finance_bill: boolean
  need_delivery: boolean
  initiated_by: string
  approved_by?: string
  status: string
  created_at: string
  updated_at: string
}

export interface AbnormalFlowCreatePayload {
  abnormal_type: string
  reason: string
  selected_start_node: string
  selected_process_nodes: string[]
  need_inspection: boolean
  need_finance_bill: boolean
  need_delivery: boolean
}

export interface MakingAssignment {
  id: string
  sales_order_id: string
  making_task_id?: string
  supervisor_id: string
  employee_id: string
  assigned_sets: number
  completed_sets: number
  status: string
  submitted_to_epin_at?: string
  remarks?: string
  created_at: string
  updated_at: string
}

export interface EpinBatch {
  id: string
  sales_order_id: string
  making_assignment_id: string
  employee_id: string
  sets_count: number
  status: string
  received_by?: string
  received_at?: string
  completed_at?: string
  remarks?: string
  created_at: string
  updated_at: string
}

export interface WorkflowFinanceBillSummary {
  id: string
  bill_no: string
  amount?: number | null
  bill_status: string
  printed_at?: string | null
  released_at?: string | null
  remarks?: string | null
}

export interface WorkflowDeliverySummary {
  id: string
  delivery_no: string
  status: string
  address: string
  delivery_time: string
  driver_name?: string | null
  logistics_no?: string | null
  signed_by?: string | null
  signed_at?: string | null
  remark?: string | null
}

export interface WorkflowSignSummary {
  id: string
  signed_by: string
  signed_at: string
  remarks?: string | null
}

export interface WorkflowFulfillmentSummary {
  sales_order_id: string
  bill?: WorkflowFinanceBillSummary
  delivery?: WorkflowDeliverySummary
  sign?: WorkflowSignSummary
  current_stage: string
  can_view_amount: boolean
}
