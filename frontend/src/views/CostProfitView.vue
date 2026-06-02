<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>成本利润</strong>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
      <div class="toolbar-left">
        <el-button type="primary" :icon="Plus" v-permission="'cost:create'" @click="openCostDrawer">录入成本</el-button>
        <el-button type="success" :icon="Download" v-permission="'report:export'" @click="exportProfitExcel">
          导出 Excel
        </el-button>
      </div>
    </div>

    <div class="metric-grid">
      <el-card shadow="never" class="metric-card">
        <span>订单金额</span>
        <strong>{{ formatCurrency(report.summary.revenue) }}</strong>
        <small>当前报表总收入</small>
      </el-card>
      <el-card shadow="never" class="metric-card">
        <span>总成本</span>
        <strong>{{ formatCurrency(report.summary.total_cost) }}</strong>
        <small>人工/材料/外协/加工等</small>
      </el-card>
      <el-card shadow="never" class="metric-card">
        <span>毛利</span>
        <strong>{{ formatCurrency(report.summary.gross_profit) }}</strong>
        <small>订单金额 - 总成本</small>
      </el-card>
      <el-card shadow="never" class="metric-card">
        <span>毛利率</span>
        <strong>{{ report.summary.gross_margin.toFixed(2) }}%</strong>
        <small>毛利 / 订单金额</small>
      </el-card>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>利润报表</span>
          <el-tag>{{ report.rows.length }} 单</el-tag>
        </div>
      </template>
      <el-table :data="report.rows" stripe>
        <el-table-column prop="order_no" label="订单编号" min-width="190" />
        <el-table-column prop="customer_name" label="客户" min-width="150" />
        <el-table-column prop="product_summary" label="产品" min-width="180" />
        <el-table-column prop="revenue" label="订单金额" width="130">
          <template #default="{ row }">{{ formatCurrency(row.revenue) }}</template>
        </el-table-column>
        <el-table-column prop="total_cost" label="总成本" width="130">
          <template #default="{ row }">{{ formatCurrency(row.total_cost) }}</template>
        </el-table-column>
        <el-table-column prop="gross_profit" label="毛利" width="130">
          <template #default="{ row }">{{ formatCurrency(row.gross_profit) }}</template>
        </el-table-column>
        <el-table-column prop="gross_margin" label="毛利率" width="110">
          <template #default="{ row }">{{ Number(row.gross_margin).toFixed(2) }}%</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>成本记录</span>
          <el-tag>{{ costs.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="costs" stripe>
        <el-table-column prop="cost_date" label="日期" width="130" />
        <el-table-column prop="cost_type" label="类型" width="130">
          <template #default="{ row }">{{ costTypeLabel(row.cost_type) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="130">
          <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="sales_order_id" label="订单 ID" min-width="260" />
        <el-table-column prop="remark" label="备注" min-width="180" />
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" title="录入成本" size="480px">
      <el-form :model="form" label-position="top">
        <el-form-item label="销售订单">
          <el-select v-model="form.sales_order_id" filterable placeholder="选择订单">
            <el-option
              v-for="order in orders"
              :key="order.id"
              :label="`${order.order_no} - ${order.product_summary}`"
              :value="order.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="成本类型">
          <el-select v-model="form.cost_type">
            <el-option label="人工成本" value="labor" />
            <el-option label="材料成本" value="material" />
            <el-option label="外协成本" value="outsourcing" />
            <el-option label="加工费用" value="processing" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="form.amount" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="成本日期">
          <el-date-picker v-model="form.cost_date" value-format="YYYY-MM-DD" type="date" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" />
        </el-form-item>
        <el-button type="primary" :loading="saving" @click="createCost">保存成本</el-button>
      </el-form>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Plus, Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { CostRecord, PageResponse, ProfitReport, SalesOrder } from '../api/types'
import { formatCurrency } from '../utils/format'

const orders = ref<SalesOrder[]>([])
const costs = ref<CostRecord[]>([])
const report = ref<ProfitReport>({
  rows: [],
  summary: {
    revenue: 0,
    total_cost: 0,
    gross_profit: 0,
    gross_margin: 0
  }
})
const drawerVisible = ref(false)
const saving = ref(false)

const form = reactive({
  sales_order_id: '',
  cost_type: 'labor',
  amount: 0,
  cost_date: new Date().toISOString().slice(0, 10),
  remark: ''
})

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function costTypeLabel(type: string) {
  const map: Record<string, string> = {
    labor: '人工成本',
    material: '材料成本',
    outsourcing: '外协成本',
    processing: '加工费用',
    other: '其他'
  }
  return map[type] || type
}

async function loadOrders() {
  const { data } = await apiClient.get<PageResponse<SalesOrder>>('/sales-orders')
  orders.value = data.items
}

async function loadCosts() {
  const { data } = await apiClient.get<PageResponse<CostRecord>>('/cost-records')
  costs.value = data.items
}

async function loadReport() {
  const { data } = await apiClient.get<ProfitReport>('/reports/profit')
  report.value = data
}

async function loadAll() {
  await Promise.all([loadOrders(), loadCosts(), loadReport()])
}

function openCostDrawer() {
  drawerVisible.value = true
  if (!orders.value.length) {
    loadOrders()
  }
}

async function createCost() {
  if (!form.sales_order_id || !form.amount) {
    ElMessage.warning('请选择订单并填写成本金额')
    return
  }
  saving.value = true
  try {
    await apiClient.post('/cost-records', form)
    ElMessage.success('成本已保存')
    drawerVisible.value = false
    form.amount = 0
    form.remark = ''
    await Promise.all([loadCosts(), loadReport()])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function exportProfitExcel() {
  try {
    const response = await apiClient.get('/reports/profit/export', { responseType: 'blob' })
    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `profit-report-${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

onMounted(loadAll)
</script>
