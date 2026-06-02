<template>
  <section class="page-stack entrust-page">
    <div class="toolbar no-print">
      <div class="toolbar-left">
        <el-button :icon="ArrowLeft" @click="router.push(`/orders/${route.params.id}`)">返回订单</el-button>
        <strong>制版委托书</strong>
      </div>
      <div class="toolbar-left">
        <el-button :icon="Refresh" :loading="loading" @click="loadEntrust">刷新</el-button>
        <el-button v-if="sheet && canUpdateLayout" :icon="Check" :loading="savingLayout" @click="saveLayout">保存版式</el-button>
        <el-button type="primary" :icon="Printer" :disabled="!sheet" @click="printSheet">打印</el-button>
      </div>
    </div>

    <el-card v-if="sheet" shadow="never" class="layout-controls no-print">
      <template #header>
        <div class="panel-title">
          <span>委托书打印版式</span>
          <el-tag>{{ layoutStyleLabel }}</el-tag>
        </div>
      </template>
      <el-form :model="layoutForm" label-position="top" class="layout-control-form">
        <el-form-item label="标题类型">
          <el-select v-model="layoutForm.title_mode">
            <el-option label="新版 New cylinder" value="new_cylinder" />
            <el-option label="旧版/加做" value="old_cylinder" />
            <el-option label="退镀" value="dechrome" />
            <el-option label="返工" value="rework" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="Layout 样式">
          <el-select v-model="layoutForm.diagram_style">
            <el-option label="三段式版面" value="three_section" />
            <el-option label="整版窗口" value="single_window" />
            <el-option label="只显示文字要求" value="text_only" />
          </el-select>
        </el-form-item>
        <el-form-item label="颜色列数">
          <el-input-number v-model="layoutForm.color_columns" :min="4" :max="14" />
        </el-form-item>
        <el-form-item label="左侧标注">
          <el-input v-model="layoutForm.left_label" />
        </el-form-item>
        <el-form-item label="中间标注">
          <el-input v-model="layoutForm.center_label" />
        </el-form-item>
        <el-form-item label="右侧标注">
          <el-input v-model="layoutForm.right_label" />
        </el-form-item>
        <el-form-item label="上方说明" class="wide-field">
          <el-input v-model="layoutForm.top_note" />
        </el-form-item>
        <el-form-item label="下方说明" class="wide-field">
          <el-input v-model="layoutForm.bottom_note" />
        </el-form-item>
        <el-form-item label="宽度/雕刻说明" class="wide-field">
          <el-input v-model="layoutForm.width_label" />
        </el-form-item>
        <el-form-item label="自定义 Layout 要求" class="wide-field">
          <el-input v-model="layoutForm.custom_note" type="textarea" :rows="2" />
        </el-form-item>
        <div class="switch-row wide-field">
          <el-switch v-model="layoutForm.show_info_table" active-text="显示主信息" />
          <el-switch v-model="layoutForm.show_color_table" active-text="显示颜色表" />
          <el-switch v-model="layoutForm.show_layout_diagram" active-text="显示 Layout" />
          <el-switch v-model="layoutForm.show_requirements" active-text="显示要求" />
        </div>
      </el-form>
    </el-card>

    <div v-if="sheet" class="print-sheet">
      <header class="sheet-header">
        <h1>BANGLA SHANGHAI PLATE MAKING LTD.</h1>
        <h2>{{ entrustTitle }}</h2>
      </header>

      <table v-if="layoutForm.show_info_table" class="info-table">
        <tbody>
          <tr>
            <th>Customer</th>
            <td class="value strong">{{ value(sheet.customer_name || details.customer_text) }}</td>
            <th>Sign</th>
            <td class="value">{{ value(details.sign_in_person) }}</td>
            <th>SampleNo</th>
            <td class="value strong">{{ sheet.entrust_no }}</td>
          </tr>
          <tr>
            <th>NO</th>
            <td class="value red">{{ order.order_no }}</td>
            <th>ProductName</th>
            <td class="value red" colspan="3">{{ value(details.product_name || order.product_summary) }}</td>
          </tr>
          <tr>
            <th>Printing Method</th>
            <td class="value red">{{ value(details.printing_method) }}</td>
            <th>Material Model</th>
            <td class="value">{{ value(details.material_model) }}</td>
            <th>New</th>
            <td class="value red">{{ value(details.material_new || details.new_material) }}</td>
          </tr>
          <tr>
            <th>Returns</th>
            <td class="value red" colspan="2">{{ value(details.returns) }}</td>
            <th>Archives</th>
            <td class="value red" colspan="2">{{ value(details.archives) }}</td>
          </tr>
          <tr>
            <th>C</th>
            <td class="value red">{{ value(details.c_value) }}</td>
            <th>L</th>
            <td class="value red">{{ value(details.l_value) }}</td>
            <th>D</th>
            <td class="value red">{{ value(firstColor.real_dia || firstColor.dia) }}</td>
          </tr>
          <tr>
            <th>Increase</th>
            <td class="value red">{{ value(details.increase) }}</td>
            <th>Flange</th>
            <td class="value red">{{ value(details.flange) }}</td>
            <th>Hole</th>
            <td class="value red">{{ value(details.hole) }}</td>
          </tr>
          <tr>
            <th>Keyway</th>
            <td class="value red">{{ value(details.key_way) }}</td>
            <th>Set Type</th>
            <td class="value red">{{ value(details.set_type) }}</td>
            <th>Unit</th>
            <td class="value red">{{ unitText }}</td>
          </tr>
        </tbody>
      </table>

      <table v-if="layoutForm.show_color_table" class="color-table">
        <thead>
          <tr>
            <th>Color NO</th>
            <th v-for="index in colorIndexes" :key="index">{{ index - 2 }}</th>
            <th>QTY</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th>PrintColor</th>
            <td v-for="index in colorIndexes" :key="index" class="value red">{{ value(colorRows[index - 1]?.print_color) }}</td>
            <td class="value red">{{ totalColorQty }}</td>
          </tr>
          <tr>
            <th>QTY</th>
            <td v-for="index in colorIndexes" :key="index" class="value red">{{ value(colorRows[index - 1]?.qty) }}</td>
            <td></td>
          </tr>
          <tr>
            <th>Real Dia</th>
            <td v-for="index in colorIndexes" :key="index" class="value red">{{ value(colorRows[index - 1]?.real_dia) }}</td>
            <td></td>
          </tr>
          <tr>
            <th>Print Method</th>
            <td v-for="index in colorIndexes" :key="index" class="value red">{{ value(colorRows[index - 1]?.printing_method) }}</td>
            <td></td>
          </tr>
        </tbody>
      </table>

      <template v-if="layoutForm.show_layout_diagram">
        <h3 class="layout-title">Layout</h3>
        <table v-if="layoutForm.diagram_style === 'text_only'" class="layout-note-table">
          <tbody>
            <tr>
              <th>Layout Requirement</th>
              <td class="red">{{ value(layoutForm.custom_note || layoutForm.bottom_note || details.computer_requirement) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="layout-box" :class="`layout-${layoutForm.diagram_style}`">
          <div class="side-label left-label">{{ value(layoutForm.left_label || details.flange, 'Flange') }}</div>
          <div class="layout-core">
            <div class="layout-top">
              <span>{{ value(layoutForm.top_note || details.mark_line, 'mark line') }}</span>
              <span>{{ value(details.test_line, 'test line') }}</span>
              <span>{{ value(details.test_spot, 'test spot') }}</span>
            </div>
            <div class="layout-window">
              <template v-if="layoutForm.diagram_style === 'single_window'">
                <div class="layout-section layout-section-full red">
                  {{ value(layoutForm.center_label || layoutForm.custom_note || details.c_value, 'Layout') }}
                </div>
              </template>
              <template v-else>
                <div class="layout-section red">{{ value(details.unit_l || details.l_value, 'L') }}</div>
                <div class="layout-section red">{{ value(layoutForm.center_label || details.c_value, 'C') }}</div>
                <div class="layout-section red">{{ value(details.unit_w, 'W') }}</div>
              </template>
            </div>
            <div class="layout-bottom">
              <span>{{ value(layoutForm.width_label, 'Width of Engraving') }}</span>
              <strong class="red">{{ value(layoutForm.bottom_note || details.engraving_requirement || details.unit_l) }}</strong>
              <span>mm</span>
            </div>
          </div>
          <div class="side-label right-label">{{ value(layoutForm.right_label || details.hole, 'Hole') }}</div>
        </div>
      </template>

      <table v-if="layoutForm.show_requirements" class="requirement-table">
        <tbody>
          <tr>
            <th>Computer Requirement</th>
            <td class="red">{{ value(details.computer_requirement || details.common_remarks) }}</td>
          </tr>
          <tr>
            <th>Color Separation</th>
            <td class="red">{{ value(details.color_separation) }}</td>
          </tr>
          <tr>
            <th>Engraving Requirement</th>
            <td class="red">{{ value(details.engraving_note || details.engraving_requirement) }}</td>
          </tr>
          <tr>
            <th>Inspection Requirement</th>
            <td class="red">{{ value(details.inspection_requirement) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Check, Printer, Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { ColorRow, EntrustLayoutSettings, EntrustSheet, PlateDetails, PlateValue, SalesOrder } from '../api/types'
import { hasPermission } from '../stores/session'

const route = useRoute()
const router = useRouter()
const sheet = ref<EntrustSheet | null>(null)
const loading = ref(false)
const savingLayout = ref(false)

interface EntrustLayoutForm {
  title_mode: string
  diagram_style: string
  color_columns: number
  show_info_table: boolean
  show_color_table: boolean
  show_layout_diagram: boolean
  show_requirements: boolean
  left_label: string
  center_label: string
  right_label: string
  top_note: string
  bottom_note: string
  width_label: string
  custom_note: string
}

const layoutForm = reactive<EntrustLayoutForm>({
  title_mode: 'new_cylinder',
  diagram_style: 'three_section',
  color_columns: 12,
  show_info_table: true,
  show_color_table: true,
  show_layout_diagram: true,
  show_requirements: true,
  left_label: '',
  center_label: '',
  right_label: '',
  top_note: '',
  bottom_note: '',
  width_label: '',
  custom_note: ''
})

const order = computed(() => sheet.value!.order)
const details = computed<PlateDetails>(() => sheet.value?.order.plate_details || {})
const colorRows = computed<ColorRow[]>(() => sheet.value?.order.color_rows || [])
const firstColor = computed<ColorRow>(() => colorRows.value[0] || {})
const canUpdateLayout = computed(() => hasPermission('order:update'))
const colorIndexes = computed(() => Array.from({ length: Number(layoutForm.color_columns || 12) }, (_, index) => index + 1))
const layoutStyleLabel = computed(() => {
  const map: Record<string, string> = {
    three_section: '三段式版面',
    single_window: '整版窗口',
    text_only: '文字要求'
  }
  return map[layoutForm.diagram_style] || '三段式版面'
})
const entrustTitle = computed(() => {
  const orderType = String(layoutForm.title_mode || details.value.order_type || 'new_cylinder')
  const map: Record<string, string> = {
    new_cylinder: '(新版 New cylinder) 制版委托书',
    old_cylinder: '(旧版 / 加做) 制版委托书',
    dechrome: '(退镀) 制版委托书',
    rework: '(返工) 制版委托书',
    custom: String(layoutForm.custom_note || '制版委托书')
  }
  return map[orderType] || '制版委托书'
})
const unitText = computed(() => {
  const l = details.value.unit_l ? String(details.value.unit_l) : ''
  const w = details.value.unit_w ? String(details.value.unit_w) : ''
  return [l, w].filter(Boolean).join('*') || '-'
})
const totalColorQty = computed(() =>
  colorRows.value.reduce((sum, row) => {
    const qty = Number(row.qty || 0)
    return Number.isFinite(qty) ? sum + qty : sum
  }, 0) || value(details.value.total_qty)
)

function value(input: PlateValue, fallback = '-') {
  const text = input === null || input === undefined ? '' : String(input)
  return text.trim() || fallback
}

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function applyLayoutSettings(settings?: EntrustLayoutSettings) {
  const next = settings || {}
  layoutForm.title_mode = String(next.title_mode || details.value.order_type || 'new_cylinder')
  layoutForm.diagram_style = String(next.diagram_style || 'three_section')
  layoutForm.color_columns = Number(next.color_columns || 12)
  layoutForm.show_info_table = next.show_info_table ?? true
  layoutForm.show_color_table = next.show_color_table ?? true
  layoutForm.show_layout_diagram = next.show_layout_diagram ?? true
  layoutForm.show_requirements = next.show_requirements ?? true
  layoutForm.left_label = String(next.left_label || '')
  layoutForm.center_label = String(next.center_label || '')
  layoutForm.right_label = String(next.right_label || '')
  layoutForm.top_note = String(next.top_note || '')
  layoutForm.bottom_note = String(next.bottom_note || '')
  layoutForm.width_label = String(next.width_label || '')
  layoutForm.custom_note = String(next.custom_note || '')
}

async function loadEntrust() {
  loading.value = true
  try {
    const { data } = await apiClient.get<EntrustSheet>(`/sales-orders/${route.params.id}/entrust`)
    sheet.value = data
    applyLayoutSettings(data.order.plate_details?.entrust_layout)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function saveLayout() {
  if (!sheet.value) return
  savingLayout.value = true
  try {
    const { data } = await apiClient.put<SalesOrder>(`/sales-orders/${sheet.value.order.id}/entrust-layout`, { ...layoutForm })
    sheet.value = { ...sheet.value, order: data }
    ElMessage.success('委托书版式已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingLayout.value = false
  }
}

function printSheet() {
  window.print()
}

onMounted(loadEntrust)
</script>

<style scoped>
.entrust-page {
  align-items: center;
}

.print-sheet {
  width: min(100%, 960px);
  padding: 24px 28px;
  color: #111827;
  background: #ffffff;
  border: 1px solid #d9dee8;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}

.layout-controls {
  width: min(100%, 960px);
}

.layout-control-form {
  display: grid;
  grid-template-columns: repeat(3, minmax(180px, 1fr));
  gap: 12px 14px;
}

.layout-control-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.wide-field {
  grid-column: span 2;
}

.switch-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
}

.sheet-header {
  text-align: center;
  margin-bottom: 10px;
}

.sheet-header h1 {
  margin: 0;
  font-size: 18px;
  letter-spacing: 0;
}

.sheet-header h2 {
  margin: 4px 0 0;
  font-size: 18px;
  letter-spacing: 0;
}

table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

th,
td {
  min-height: 28px;
  padding: 5px 6px;
  border: 1px solid #111827;
  font-size: 12px;
  line-height: 1.35;
  text-align: center;
  vertical-align: middle;
  overflow-wrap: anywhere;
}

th {
  font-weight: 600;
  color: #0f172a;
  background: #f8fafc;
}

.value {
  font-family: "Courier New", monospace;
}

.strong {
  font-weight: 700;
}

.red {
  color: #e00000;
  font-weight: 700;
}

.color-table,
.requirement-table {
  margin-top: 10px;
}

.layout-title {
  margin: 12px 0 4px;
  font-size: 24px;
  line-height: 1;
  text-align: center;
}

.layout-box {
  position: relative;
  display: grid;
  grid-template-columns: 72px 1fr 72px;
  min-height: 270px;
  margin: 0 42px 18px;
  border-bottom: 2px solid #111827;
}

.layout-core {
  display: grid;
  grid-template-rows: 32px 1fr 44px;
  border: 2px solid #111827;
  border-bottom: 0;
}

.layout-top,
.layout-bottom {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  font-size: 12px;
}

.layout-window {
  display: grid;
  grid-template-columns: 1fr 1.4fr 1fr;
  border-top: 2px solid #111827;
  border-bottom: 2px solid #111827;
}

.layout-single_window .layout-window {
  grid-template-columns: 1fr;
}

.layout-section {
  display: grid;
  place-items: center;
  border-right: 2px solid #111827;
  font-family: "Courier New", monospace;
}

.layout-section-full {
  min-height: 130px;
  border-right: 0;
  font-size: 18px;
  line-height: 1.45;
  padding: 12px;
  white-space: pre-wrap;
}

.layout-section:last-child {
  border-right: 0;
}

.side-label {
  display: grid;
  place-items: center;
  color: #e00000;
  font-family: "Courier New", monospace;
  font-weight: 700;
}

.left-label {
  border-right: 2px solid #111827;
}

.right-label {
  border-left: 2px solid #111827;
}

.requirement-table th {
  width: 130px;
}

.layout-note-table {
  margin: 0 0 14px;
}

.layout-note-table th {
  width: 170px;
}

.layout-note-table td {
  height: 90px;
  padding: 10px 12px;
  text-align: left;
  white-space: pre-wrap;
}

.requirement-table td {
  height: 54px;
  text-align: left;
  padding-left: 12px;
}

@media (max-width: 800px) {
  .print-sheet {
    padding: 18px;
    overflow-x: auto;
  }

  .layout-box {
    margin-inline: 0;
  }

  .layout-control-form {
    grid-template-columns: 1fr;
  }

  .wide-field {
    grid-column: auto;
  }
}

@media print {
  :global(body) {
    background: #ffffff !important;
  }

  .no-print {
    display: none !important;
  }

  .entrust-page {
    display: block;
    padding: 0;
  }

  .print-sheet {
    width: 100%;
    padding: 0;
    border: 0;
    box-shadow: none;
  }
}
</style>
