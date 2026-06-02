<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-date-picker v-model="filters.date_from" value-format="YYYY-MM-DD" type="date" placeholder="开始日期" />
        <el-date-picker v-model="filters.date_to" value-format="YYYY-MM-DD" type="date" placeholder="结束日期" />
        <el-select v-model="filters.customer_id" filterable clearable class="customer-select" placeholder="选择客户">
          <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
        </el-select>
        <el-select v-model="filters.salesperson" filterable clearable class="salesperson-select" placeholder="选择业务员">
          <el-option v-for="name in salespersonOptions" :key="name" :label="name" :value="name" />
        </el-select>
        <el-select v-model="filters.rework_mode" class="mode-select">
          <el-option label="统计全部" value="all" />
          <el-option label="只统计返工" value="only_rework" />
          <el-option label="不统计返工" value="exclude_rework" />
        </el-select>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
      <div class="toolbar-left">
        <el-button type="success" :icon="Download" v-permission="'report:export'" @click="exportSalesperson">
          导出销售月绩
        </el-button>
        <el-button :icon="Download" v-permission="'report:export'" @click="exportCustomers">
          导出客户月销售额
        </el-button>
      </div>
    </div>

    <div class="metric-grid">
      <el-card shadow="never" class="metric-card">
        <span>新支数</span>
        <strong>{{ summary.new_pcs }}</strong>
        <small>按当前日期和返工口径汇总</small>
      </el-card>
      <el-card shadow="never" class="metric-card">
        <span>旧支数</span>
        <strong>{{ summary.old_pcs }}</strong>
        <small>退镀、返工、旧版归为旧支数</small>
      </el-card>
      <el-card shadow="never" class="metric-card">
        <span>销售额</span>
        <strong>{{ formatCurrency(summary.total_amount) }}</strong>
        <small>来自订单总金额</small>
      </el-card>
    </div>

    <el-card shadow="never" class="table-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="销售月成绩" name="salesperson">
          <el-table :data="salespersonReport.rows" stripe show-summary :summary-method="salespersonSummary">
            <el-table-column prop="salesperson" label="业务员" min-width="180" />
            <el-table-column prop="new_pcs" label="新支数" width="150" />
            <el-table-column prop="old_pcs" label="旧支数" width="150" />
            <el-table-column prop="total_amount" label="销售额" min-width="180">
              <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="客户月销售额" name="customer">
          <el-table :data="customerReport.rows" stripe show-summary :summary-method="customerSummary">
            <el-table-column prop="salesperson" label="业务员" width="150" />
            <el-table-column prop="customer_name" label="客户名称" min-width="220" />
            <el-table-column prop="new_pcs" label="新支数" width="120" />
            <el-table-column prop="old_pcs" label="旧支数" width="120" />
            <el-table-column prop="total_amount" label="销售额" min-width="160">
              <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
            </el-table-column>
            <el-table-column prop="price" label="平均单价" width="110">
              <template #default="{ row }">{{ Number(row.price || 0).toFixed(2) }}</template>
            </el-table-column>
            <el-table-column prop="settlement_type" label="结算方式" min-width="150" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type {
  Customer,
  CustomerMonthlySalesReport,
  CustomerMonthlySalesRow,
  PageResponse,
  SalesMonthlySummary,
  SalespersonMonthlyReport
} from '../api/types'
import { formatCurrency } from '../utils/format'

function localDate(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const today = new Date()
const monthStart = localDate(new Date(today.getFullYear(), today.getMonth(), 1))
const monthEnd = localDate(new Date(today.getFullYear(), today.getMonth() + 1, 0))

const filters = reactive({
  date_from: monthStart,
  date_to: monthEnd,
  customer_id: '',
  salesperson: '',
  rework_mode: 'all'
})
const activeTab = ref('salesperson')
const customers = ref<Customer[]>([])
const salespersonReport = ref<SalespersonMonthlyReport>({
  rows: [],
  summary: { new_pcs: 0, old_pcs: 0, total_amount: 0 }
})
const customerReport = ref<CustomerMonthlySalesReport>({
  rows: [],
  summary: { new_pcs: 0, old_pcs: 0, total_amount: 0 }
})

const summary = computed<SalesMonthlySummary>(() => salespersonReport.value.summary)
const salespersonOptions = computed(() => {
  const names = new Set<string>()
  customers.value.forEach((customer) => {
    if (customer.salesperson_name) names.add(customer.salesperson_name)
  })
  salespersonReport.value.rows.forEach((row) => {
    if (row.salesperson) names.add(row.salesperson)
  })
  customerReport.value.rows.forEach((row) => {
    if (row.salesperson) names.add(row.salesperson)
  })
  return Array.from(names).sort((a, b) => a.localeCompare(b))
})

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function params() {
  return {
    date_from: filters.date_from || undefined,
    date_to: filters.date_to || undefined,
    customer_id: filters.customer_id || undefined,
    salesperson: filters.salesperson || undefined,
    rework_mode: filters.rework_mode
  }
}

async function loadCustomers() {
  const { data } = await apiClient.get<PageResponse<Customer>>('/customers', { params: { page_size: 100 } })
  customers.value = data.items
}

async function loadSalespersonReport() {
  const { data } = await apiClient.get<SalespersonMonthlyReport>('/reports/salesperson-monthly', { params: params() })
  salespersonReport.value = data
}

async function loadCustomerReport() {
  const { data } = await apiClient.get<CustomerMonthlySalesReport>('/reports/customer-monthly-sales', { params: params() })
  customerReport.value = data
}

async function loadAll() {
  try {
    await Promise.all([loadSalespersonReport(), loadCustomerReport()])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function downloadReport(path: string, filename: string) {
  try {
    const response = await apiClient.get(path, { params: params(), responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function exportSalesperson() {
  downloadReport('/reports/salesperson-monthly/export', `salesperson-monthly-${filters.date_from}-${filters.date_to}.xlsx`)
}

function exportCustomers() {
  downloadReport('/reports/customer-monthly-sales/export', `customer-monthly-sales-${filters.date_from}-${filters.date_to}.xlsx`)
}

function salespersonSummary() {
  return ['合计', summary.value.new_pcs, summary.value.old_pcs, formatCurrency(summary.value.total_amount)]
}

function customerSummary({ columns, data }: { columns: unknown[]; data: CustomerMonthlySalesRow[] }) {
  const total = data.reduce(
    (acc, row) => {
      acc.new_pcs += Number(row.new_pcs || 0)
      acc.old_pcs += Number(row.old_pcs || 0)
      acc.total_amount += Number(row.total_amount || 0)
      return acc
    },
    { new_pcs: 0, old_pcs: 0, total_amount: 0 }
  )
  return columns.map((_, index) => {
    if (index === 0) return '合计'
    if (index === 2) return total.new_pcs
    if (index === 3) return total.old_pcs
    if (index === 4) return formatCurrency(total.total_amount)
    return ''
  })
}

watch(filters, loadAll)
onMounted(async () => {
  await loadCustomers()
  await loadAll()
})
</script>

<style scoped>
.mode-select {
  width: 150px;
}

.customer-select {
  width: 220px;
}

.salesperson-select {
  width: 160px;
}
</style>
