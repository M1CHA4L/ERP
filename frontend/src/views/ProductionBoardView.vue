<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>工序看板</strong>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadBoard">刷新</el-button>
      </div>
    </div>

    <div class="metric-grid">
      <el-card v-for="metric in metrics" :key="metric.label" shadow="never" class="metric-card">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <small>{{ metric.note }}</small>
      </el-card>
    </div>

    <el-card shadow="never" class="table-card production-flow-card">
      <template #header>
        <div class="panel-title flow-panel-title">
          <div class="flow-title-left">
            <span>工序流程</span>
            <el-tag type="info">{{ flowTotal }} 条</el-tag>
          </div>
          <el-popover placement="bottom-end" trigger="click" width="360">
            <template #reference>
              <el-button :icon="Setting">表头</el-button>
            </template>
            <div class="column-picker">
              <div class="column-picker-header">
                <strong>显示表头</strong>
                <el-button text type="primary" @click="resetFlowColumns">默认</el-button>
              </div>
              <el-checkbox-group v-model="visibleFlowColumnKeys" class="column-picker-grid">
                <el-checkbox v-for="column in flowColumns" :key="column.key" :label="column.key">
                  {{ column.label }}
                </el-checkbox>
              </el-checkbox-group>
              <div class="column-picker-actions">
                <el-button size="small" @click="selectAllFlowColumns">全选</el-button>
              </div>
            </div>
          </el-popover>
        </div>
      </template>
      <div class="flow-filters">
        <el-date-picker v-model="flowFilters.date_from" value-format="YYYY-MM-DD" type="date" placeholder="下单开始" />
        <el-date-picker v-model="flowFilters.date_to" value-format="YYYY-MM-DD" type="date" placeholder="下单结束" />
        <el-input v-model="flowFilters.search" clearable placeholder="版号 / 客户 / 产品 / 工单" />
        <el-input v-model="flowFilters.production_position" clearable placeholder="生产位置" />
        <el-input v-model="flowFilters.cylinder_making" clearable placeholder="Cylinder Making" />
        <el-input v-model="flowFilters.salesman" clearable placeholder="SalesMan" />
        <el-checkbox v-model="flowFilters.unfinished_only">查询未完成</el-checkbox>
        <el-button type="primary" :icon="Refresh" :loading="flowLoading" @click="loadProductionFlow">查询</el-button>
      </div>
      <el-table
        :key="visibleFlowColumnSignature"
        :data="flowRows"
        row-key="work_order_id"
        stripe
        border
        class="production-flow-table"
        @row-dblclick="goFlowRow"
      >
        <el-table-column type="expand" width="42">
          <template #default="{ row }">
            <div class="flow-expand">
              <el-tabs>
                <el-tab-pane label="工序完成记录表">
                  <el-table :data="row.details.steps" size="small" border>
                    <el-table-column prop="step_no" label="#" width="54" />
                    <el-table-column prop="step_name" label="工序" min-width="120" />
                    <el-table-column label="状态" width="110">
                      <template #default="{ row: step }">{{ statusLabel(stepStatusMap, String(step.status || '')) }}</template>
                    </el-table-column>
                    <el-table-column prop="assigned_user_name" label="负责人" width="110" />
                    <el-table-column prop="actual_start_at" label="开始" min-width="150" />
                    <el-table-column prop="actual_end_at" label="完成" min-width="150" />
                    <el-table-column prop="qualified_qty" label="合格" width="80" />
                    <el-table-column prop="defective_qty" label="不良" width="80" />
                    <el-table-column prop="remark" label="备注" min-width="160" />
                  </el-table>
                </el-tab-pane>
                <el-tab-pane label="操作日志">
                  <el-table :data="row.details.process_records" size="small" border>
                    <el-table-column prop="reported_at" label="时间" min-width="150" />
                    <el-table-column prop="step_name" label="工序" min-width="120" />
                    <el-table-column prop="operator_name" label="操作人" width="110" />
                    <el-table-column prop="action" label="动作" width="90" />
                    <el-table-column prop="processed_qty" label="加工数" width="90" />
                    <el-table-column prop="qualified_qty" label="合格数" width="90" />
                    <el-table-column prop="work_hours" label="工时" width="80" />
                    <el-table-column prop="remark" label="备注" min-width="180" />
                  </el-table>
                </el-tab-pane>
                <el-tab-pane label="返工信息">
                  <div class="expand-two-col">
                    <el-table :data="row.details.inspections" size="small" border>
                      <el-table-column prop="inspection_no" label="质检号" min-width="130" />
                      <el-table-column prop="step_name" label="工序" min-width="100" />
                      <el-table-column prop="result" label="结果" width="90" />
                      <el-table-column prop="inspector_name" label="检验员" width="100" />
                      <el-table-column prop="failed_qty" label="不良数" width="80" />
                      <el-table-column prop="reason" label="原因" min-width="160" />
                    </el-table>
                    <el-table :data="row.details.reworks" size="small" border>
                      <el-table-column prop="rework_no" label="返工号" min-width="130" />
                      <el-table-column prop="from_step_name" label="来源" width="100" />
                      <el-table-column prop="to_step_name" label="返回工序" width="110" />
                      <el-table-column prop="quantity" label="数量" width="80" />
                      <el-table-column prop="status" label="状态" width="90" />
                      <el-table-column prop="reason" label="原因" min-width="160" />
                    </el-table>
                  </div>
                </el-tab-pane>
                <el-tab-pane label="版辊生产要求">
                  <div class="requirements-grid">
                    <div><span>Engraving Requirement</span><strong>{{ detailValue(row.details.requirements.engraving_requirement) }}</strong></div>
                    <div><span>Proofing Requirement</span><strong>{{ detailValue(row.details.requirements.proofing_requirement) }}</strong></div>
                    <div><span>Inspection Requirement</span><strong>{{ detailValue(row.details.requirements.inspection_requirement) }}</strong></div>
                    <div><span>Color Separation</span><strong>{{ detailValue(row.details.requirements.color_separation) }}</strong></div>
                    <div><span>Design Requirement</span><strong>{{ detailValue(row.details.requirements.design_requirement) }}</strong></div>
                    <div><span>Production Remark</span><strong>{{ detailValue(row.details.requirements.production_remark) }}</strong></div>
                  </div>
                </el-tab-pane>
              </el-tabs>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="选择" width="62">
          <template #default="{ $index }">{{ (flowPage - 1) * flowPageSize + $index + 1 }}</template>
        </el-table-column>
        <el-table-column
          v-for="column in visibleFlowColumns"
          :key="column.key"
          :prop="column.prop"
          :label="column.label"
          :width="column.width"
          :min-width="column.minWidth"
          :fixed="column.fixed"
          show-overflow-tooltip
        />
      </el-table>
      <div class="pagination-row">
        <el-pagination
          v-model:current-page="flowPage"
          v-model:page-size="flowPageSize"
          :total="flowTotal"
          :page-sizes="[20, 30, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadProductionFlow"
          @size-change="loadProductionFlow"
        />
      </div>
    </el-card>

    <div class="content-grid">
      <el-card shadow="never" class="table-card">
        <template #header>
          <div class="panel-title">
            <span>工序队列</span>
            <el-tag type="info">{{ board?.queues.length || 0 }} 个工序</el-tag>
          </div>
        </template>
        <el-table :data="board?.queues || []" stripe>
          <el-table-column prop="step_name" label="工序" min-width="130" />
          <el-table-column prop="pending_count" label="待加工" width="90" />
          <el-table-column prop="processing_count" label="加工中" width="90" />
          <el-table-column prop="pending_inspection_count" label="待检" width="80" />
          <el-table-column prop="reworking_count" label="返工" width="80" />
          <el-table-column prop="overdue_count" label="逾期" width="80">
            <template #default="{ row }">
              <el-tag :type="row.overdue_count > 0 ? 'danger' : 'info'" size="small">{{ row.overdue_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="total_count" label="合计" width="80" />
        </el-table>
      </el-card>

      <el-card shadow="never" class="table-card">
        <template #header>
          <div class="panel-title">
            <span>当前卡点</span>
            <el-tag type="warning">{{ board?.active_tasks.length || 0 }} 条</el-tag>
          </div>
        </template>
        <el-table :data="board?.active_tasks || []" stripe @row-dblclick="goWorkOrder">
          <el-table-column prop="work_order_no" label="工单" min-width="150" />
          <el-table-column prop="product_name" label="产品" min-width="130" />
          <el-table-column prop="step_name" label="当前工序" width="110" />
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_overdue ? 'danger' : 'info'">{{ statusLabel(stepStatusMap, row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="assigned_user_name" label="负责人" width="110">
            <template #default="{ row }">{{ row.assigned_user_name || '未派工' }}</template>
          </el-table-column>
          <el-table-column prop="due_date" label="交期" width="120" />
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" :icon="View" @click="goWorkOrder(row)" />
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Setting, View } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { PageResponse, ProductionBoard, ProductionFlowRow, WorkOrderStepTask } from '../api/types'
import { statusLabel, stepStatusMap } from '../utils/status'

const router = useRouter()
const loading = ref(false)
const flowLoading = ref(false)
const board = ref<ProductionBoard | null>(null)
const flowRows = ref<ProductionFlowRow[]>([])
const flowTotal = ref(0)
const flowPage = ref(1)
const flowPageSize = ref(30)
const flowFilters = reactive({
  date_from: '',
  date_to: '',
  search: '',
  production_position: '',
  cylinder_making: '',
  salesman: '',
  unfinished_only: true
})

type FlowColumnKey =
  | 'cylinder_no'
  | 'salesman'
  | 'order_date'
  | 'completed_date'
  | 'period'
  | 'customer_name'
  | 'product_name'
  | 'c_value'
  | 'l_value'
  | 'total_qty'
  | 'new_base'
  | 'old_base'
  | 'production_position'
  | 'computer_position'
  | 'square'
  | 'dia'
  | 'hole'
  | 'slope'
  | 'keyway'
  | 'single_double'
  | 'order_by'
  | 'sign_in_person'
  | 'printing_method'
  | 'unit_l'
  | 'unit_w'
  | 'straight'
  | 'increase'
  | 'flange'
  | 'cylinder_model'
  | 'cylinder_making'
  | 'material_model'
  | 'new_material'
  | 'placing_member'
  | 'color_numbers'
  | 'print_color'
  | 'real_dia'
  | 'customer_material_qty'
  | 'production_qty'

interface FlowColumn {
  key: FlowColumnKey
  prop: FlowColumnKey
  label: string
  width?: number
  minWidth?: number
  fixed?: 'left' | 'right'
  defaultVisible?: boolean
}

const FLOW_COLUMN_STORAGE_KEY = 'bspm.productionBoard.flowColumns'
const flowColumns: FlowColumn[] = [
  { key: 'cylinder_no', prop: 'cylinder_no', label: '版号', minWidth: 140, fixed: 'left' },
  { key: 'salesman', prop: 'salesman', label: '业务员', minWidth: 110 },
  { key: 'order_date', prop: 'order_date', label: '下单日期', width: 120 },
  { key: 'completed_date', prop: 'completed_date', label: '完成日期', width: 120 },
  { key: 'period', prop: 'period', label: '工期', width: 88 },
  { key: 'customer_name', prop: 'customer_name', label: '客户名称', minWidth: 180 },
  { key: 'product_name', prop: 'product_name', label: '产品名称', minWidth: 200 },
  { key: 'c_value', prop: 'c_value', label: '版周 C', width: 88 },
  { key: 'l_value', prop: 'l_value', label: '版长 L', width: 88 },
  { key: 'total_qty', prop: 'total_qty', label: '总支数', width: 96 },
  { key: 'new_base', prop: 'new_base', label: '新基', width: 80 },
  { key: 'old_base', prop: 'old_base', label: '旧基', width: 80 },
  { key: 'production_position', prop: 'production_position', label: '生产位置', minWidth: 130 },
  { key: 'computer_position', prop: 'computer_position', label: '文件位置', minWidth: 140 },
  { key: 'square', prop: 'square', label: '平方', width: 90 },
  { key: 'dia', prop: 'dia', label: '直径', width: 90 },
  { key: 'hole', prop: 'hole', label: '内孔', width: 90 },
  { key: 'slope', prop: 'slope', label: '斜度', width: 90 },
  { key: 'keyway', prop: 'keyway', label: '键槽', minWidth: 110 },
  { key: 'single_double', prop: 'single_double', label: '单, 双', width: 90 },
  { key: 'order_by', prop: 'order_by', label: 'Order By', minWidth: 110, defaultVisible: false },
  { key: 'sign_in_person', prop: 'sign_in_person', label: 'Sign', minWidth: 110, defaultVisible: false },
  { key: 'printing_method', prop: 'printing_method', label: 'Printing Method', minWidth: 140, defaultVisible: false },
  { key: 'unit_l', prop: 'unit_l', label: 'Unit L', width: 90, defaultVisible: false },
  { key: 'unit_w', prop: 'unit_w', label: 'Unit W', width: 90, defaultVisible: false },
  { key: 'straight', prop: 'straight', label: 'Straight', width: 90, defaultVisible: false },
  { key: 'increase', prop: 'increase', label: 'Increase', width: 90, defaultVisible: false },
  { key: 'flange', prop: 'flange', label: 'Flange', width: 90, defaultVisible: false },
  { key: 'cylinder_model', prop: 'cylinder_model', label: 'Cylinder Model', minWidth: 130, defaultVisible: false },
  { key: 'cylinder_making', prop: 'cylinder_making', label: 'Cylinder Making', minWidth: 150, defaultVisible: false },
  { key: 'material_model', prop: 'material_model', label: 'Material Model', minWidth: 130, defaultVisible: false },
  { key: 'new_material', prop: 'new_material', label: 'New Material', minWidth: 120, defaultVisible: false },
  { key: 'placing_member', prop: 'placing_member', label: 'Placing Member', minWidth: 130, defaultVisible: false },
  { key: 'color_numbers', prop: 'color_numbers', label: 'Color NO', minWidth: 110, defaultVisible: false },
  { key: 'print_color', prop: 'print_color', label: 'PrintColor', minWidth: 120, defaultVisible: false },
  { key: 'real_dia', prop: 'real_dia', label: 'Real Dia', width: 95, defaultVisible: false },
  { key: 'customer_material_qty', prop: 'customer_material_qty', label: 'Customer Material QTY', minWidth: 170, defaultVisible: false },
  { key: 'production_qty', prop: 'production_qty', label: 'Production QTY', minWidth: 130, defaultVisible: false }
]
const allFlowColumnKeys = flowColumns.map((column) => column.key)
const defaultFlowColumnKeys = flowColumns.filter((column) => column.defaultVisible !== false).map((column) => column.key)
const flowColumnKeySet = new Set(allFlowColumnKeys)
const visibleFlowColumnKeys = ref<FlowColumnKey[]>(loadFlowColumnKeys())
const visibleFlowColumns = computed(() => {
  const visibleKeySet = new Set(visibleFlowColumnKeys.value)
  return flowColumns.filter((column) => visibleKeySet.has(column.key))
})
const visibleFlowColumnSignature = computed(() => visibleFlowColumnKeys.value.join('|'))

const metrics = computed(() => [
  { label: '待加工', value: board.value?.pending_steps || 0, note: '可开工任务' },
  { label: '加工中', value: board.value?.processing_steps || 0, note: '现场进行中' },
  { label: '待检验', value: board.value?.pending_inspection_steps || 0, note: '等待质检' },
  { label: '返工异常', value: board.value?.reworking_steps || 0, note: '需处理' },
  { label: '未派工', value: board.value?.unassigned_steps || 0, note: '需主管分配' },
  { label: '逾期风险', value: board.value?.overdue_steps || 0, note: `订单 ${board.value?.due_today_orders || 0}` }
])

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function normalizeFlowColumnKeys(keys: string[]) {
  const normalized = keys.filter((key): key is FlowColumnKey => flowColumnKeySet.has(key as FlowColumnKey))
  return normalized.length ? normalized : [...defaultFlowColumnKeys]
}

function loadFlowColumnKeys() {
  try {
    const saved = window.localStorage.getItem(FLOW_COLUMN_STORAGE_KEY)
    if (!saved) return [...defaultFlowColumnKeys]
    const parsed = JSON.parse(saved)
    return Array.isArray(parsed) ? normalizeFlowColumnKeys(parsed) : [...defaultFlowColumnKeys]
  } catch {
    return [...defaultFlowColumnKeys]
  }
}

function saveFlowColumnKeys(keys: FlowColumnKey[]) {
  window.localStorage.setItem(FLOW_COLUMN_STORAGE_KEY, JSON.stringify(keys))
}

function selectAllFlowColumns() {
  visibleFlowColumnKeys.value = [...allFlowColumnKeys]
}

function resetFlowColumns() {
  visibleFlowColumnKeys.value = [...defaultFlowColumnKeys]
}

async function loadBoard() {
  loading.value = true
  try {
    const { data } = await apiClient.get<ProductionBoard>('/work-orders/board')
    board.value = data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function loadProductionFlow() {
  flowLoading.value = true
  try {
    const { data } = await apiClient.get<PageResponse<ProductionFlowRow>>('/work-orders/production-flow', {
      params: {
        page: flowPage.value,
        page_size: flowPageSize.value,
        date_from: flowFilters.date_from || undefined,
        date_to: flowFilters.date_to || undefined,
        search: flowFilters.search || undefined,
        production_position: flowFilters.production_position || undefined,
        cylinder_making: flowFilters.cylinder_making || undefined,
        salesman: flowFilters.salesman || undefined,
        unfinished_only: flowFilters.unfinished_only
      }
    })
    flowRows.value = data.items
    flowTotal.value = data.total
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    flowLoading.value = false
  }
}

function detailValue(value: unknown) {
  const text = String(value ?? '').trim()
  return text || '-'
}

function goWorkOrder(row: WorkOrderStepTask) {
  router.push(`/work-orders/${row.work_order_id}`)
}

function goFlowRow(row: ProductionFlowRow) {
  router.push(`/work-orders/${row.work_order_id}`)
}

watch(visibleFlowColumnKeys, (keys) => {
  const normalized = normalizeFlowColumnKeys(keys)
  if (normalized.length !== keys.length || normalized.some((key, index) => key !== keys[index])) {
    visibleFlowColumnKeys.value = normalized
    return
  }
  saveFlowColumnKeys(normalized)
}, { deep: true })

onMounted(() => {
  loadBoard()
  loadProductionFlow()
})
</script>

<style scoped>
.toolbar {
  order: -2;
}

.production-flow-card {
  overflow: hidden;
  order: -1;
}

.flow-panel-title {
  justify-content: space-between;
  width: 100%;
}

.flow-title-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.column-picker {
  display: grid;
  gap: 10px;
}

.column-picker-header,
.column-picker-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.column-picker-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 10px;
  max-height: 260px;
  overflow: auto;
}

.column-picker-grid :deep(.el-checkbox) {
  height: 24px;
  margin-right: 0;
}

.column-picker-grid :deep(.el-checkbox__label) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flow-filters {
  display: grid;
  grid-template-columns: repeat(2, minmax(132px, 0.8fr)) minmax(220px, 1.4fr) repeat(3, minmax(150px, 1fr)) auto auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}

.production-flow-table {
  width: 100%;
}

.production-flow-table :deep(.el-table__cell) {
  padding: 5px 0;
}

.production-flow-table :deep(.cell) {
  line-height: 1.25;
}

.flow-expand {
  padding: 8px 12px 12px;
  background: #f8fafc;
}

.expand-two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.requirements-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.requirements-grid > div {
  min-height: 64px;
  padding: 8px;
  border: 1px solid #dbe5ef;
  border-radius: 6px;
  background: #fff;
}

.requirements-grid span {
  display: block;
  margin-bottom: 4px;
  color: #667085;
  font-size: 12px;
}

.requirements-grid strong {
  display: block;
  color: #111827;
  font-size: 13px;
  font-weight: 600;
  white-space: pre-wrap;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

@media (max-width: 1280px) {
  .flow-filters {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .expand-two-col,
  .requirements-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .flow-filters {
    grid-template-columns: 1fr;
  }
}
</style>
