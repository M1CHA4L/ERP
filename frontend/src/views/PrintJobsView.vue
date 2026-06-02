<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>打印中心</strong>
        <el-tag type="success">生产通知单入口</el-tag>
      </div>
      <div class="toolbar-left">
        <el-button :icon="Refresh" @click="reloadActive">刷新</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="print-tabs">
      <el-tab-pane label="生产通知单" name="production">
        <el-card shadow="never" class="table-card">
          <template #header>
            <div class="panel-title">
              <span>待打印生产通知单</span>
              <el-tag>{{ productionOrders.length }} 单</el-tag>
            </div>
          </template>

          <div class="table-tools print-filter-bar">
            <el-input
              v-model="productionKeyword"
              clearable
              placeholder="订单号 / 产品 / 客户 / 版号"
              :prefix-icon="Search"
              @keyup.enter="loadProductionOrders"
            />
            <el-select v-model="productionCustomerId" filterable clearable placeholder="选择客户">
              <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
            </el-select>
            <el-input v-model="productionCylinderNo" clearable placeholder="版号" @keyup.enter="loadProductionOrders" />
            <el-select v-model="productionStatus" clearable placeholder="订单状态">
              <el-option label="草稿" value="draft" />
              <el-option label="已确认" value="confirmed" />
              <el-option label="生产中" value="in_production" />
              <el-option label="待检验" value="pending_inspection" />
              <el-option label="待送货" value="pending_delivery" />
            </el-select>
            <el-date-picker v-model="productionDateFrom" value-format="YYYY-MM-DD" type="date" placeholder="下单开始" />
            <el-date-picker v-model="productionDateTo" value-format="YYYY-MM-DD" type="date" placeholder="下单结束" />
            <el-button type="primary" :icon="Search" @click="loadProductionOrders">查询</el-button>
          </div>

          <el-table :data="productionOrders" stripe @row-dblclick="printProductionOrder">
            <el-table-column prop="order_no" label="订单号" min-width="150" />
            <el-table-column label="客户" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ customerName(row.customer_id) }}</template>
            </el-table-column>
            <el-table-column label="版号" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ cylinderLabel(row) }}</template>
            </el-table-column>
            <el-table-column prop="product_summary" label="产品" min-width="190" show-overflow-tooltip />
            <el-table-column prop="order_date" label="下单日期" width="120" />
            <el-table-column prop="due_date" label="交期" width="120" />
            <el-table-column prop="total_amount" label="金额" width="130">
              <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag>{{ statusLabel(orderStatusMap, row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="打印" width="230" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" :icon="Printer" @click.stop="printProductionOrder(row)">生产通知单</el-button>
                <el-button text @click.stop="goOrder(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="打印记录" name="history">
        <el-card shadow="never" class="table-card">
          <template #header>
            <div class="panel-title">
              <span>打印留痕</span>
              <el-tag>{{ printJobs.length }} 条</el-tag>
            </div>
          </template>

          <div class="table-tools print-filter-bar">
            <el-select v-model="documentType" placeholder="单据类型" clearable>
              <el-option label="收据" value="money_receipt" />
              <el-option label="客户账单" value="customer_statement" />
              <el-option label="生产通知单" value="production_order" />
              <el-option label="车间任务单" value="workshop_daily" />
            </el-select>
            <el-date-picker v-model="dateFrom" value-format="YYYY-MM-DD" type="date" placeholder="开始日期" />
            <el-date-picker v-model="dateTo" value-format="YYYY-MM-DD" type="date" placeholder="结束日期" />
            <el-button type="primary" :icon="Search" @click="loadPrintJobs">查询</el-button>
          </div>

          <el-table :data="printJobs" stripe>
            <el-table-column prop="print_no" label="打印号" min-width="190" />
            <el-table-column label="单据类型" width="140">
              <template #default="{ row }">{{ documentLabel(row.document_type) }}</template>
            </el-table-column>
            <el-table-column prop="target_type" label="目标类型" width="150" />
            <el-table-column prop="target_id" label="目标 ID" min-width="260" />
            <el-table-column prop="printed_at" label="打印时间" min-width="190" />
            <el-table-column label="快照" min-width="320">
              <template #default="{ row }">
                <code>{{ compactSnapshot(row.snapshot) }}</code>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Printer, Refresh, Search } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { Customer, PageResponse, PrintJob, SalesOrder } from '../api/types'
import { formatCurrency } from '../utils/format'
import { orderStatusMap, statusLabel } from '../utils/status'

const router = useRouter()
const activeTab = ref('production')
const printJobs = ref<PrintJob[]>([])
const productionOrders = ref<SalesOrder[]>([])
const customers = ref<Customer[]>([])
const customerMap = computed(() => new Map(customers.value.map((customer) => [customer.id, customer.name])))

const documentType = ref('')
const dateFrom = ref('')
const dateTo = ref('')

const productionKeyword = ref('')
const productionCustomerId = ref('')
const productionCylinderNo = ref('')
const productionStatus = ref('')
const productionDateFrom = ref('')
const productionDateTo = ref('')

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function documentLabel(value: string) {
  const labels: Record<string, string> = {
    money_receipt: '收据',
    customer_statement: '客户账单',
    production_order: '生产通知单',
    workshop_daily: '车间任务单'
  }
  return labels[value] || value
}

function compactSnapshot(snapshot?: Record<string, unknown>) {
  if (!snapshot) return ''
  const keys = ['receipt_no', 'statement_no', 'order_no', 'customer_name', 'date_from', 'date_to', 'total_amount', 'due_amount']
  const picked = Object.fromEntries(keys.filter((key) => snapshot[key] !== undefined).map((key) => [key, snapshot[key]]))
  return JSON.stringify(Object.keys(picked).length ? picked : snapshot)
}

function customerName(customerId: string) {
  return customerMap.value.get(customerId) || customerId
}

function cylinderLabel(order: SalesOrder) {
  const details = order.plate_details || {}
  const row = order.color_rows?.[0] || {}
  return String(details.cylinder_id || details.no || details.sample_no || row.public_no || order.order_no)
}

async function openPrintable(path: string) {
  const popup = window.open('', '_blank')
  try {
    const { data } = await apiClient.get<string>(path, { responseType: 'text' })
    const url = URL.createObjectURL(new Blob([data], { type: 'text/html;charset=utf-8' }))
    if (popup) {
      popup.location.href = url
    } else {
      window.open(url, '_blank')
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    popup?.close()
    ElMessage.error(errorMessage(error))
  }
}

function printProductionOrder(order: SalesOrder) {
  openPrintable(`/plate-orders/${order.id}/production-order`)
}

function goOrder(order: SalesOrder) {
  router.push(`/orders/${order.id}`)
}

async function loadCustomers() {
  const { data } = await apiClient.get<PageResponse<Customer>>('/customers', { params: { page_size: 100 } })
  customers.value = data.items
}

async function loadProductionOrders() {
  try {
    const { data } = await apiClient.get<PageResponse<SalesOrder>>('/plate-orders', {
      params: {
        keyword: productionKeyword.value || undefined,
        customer_id: productionCustomerId.value || undefined,
        cylinder_no: productionCylinderNo.value || undefined,
        status_filter: productionStatus.value || undefined,
        date_from: productionDateFrom.value || undefined,
        date_to: productionDateTo.value || undefined,
        page_size: 80
      }
    })
    productionOrders.value = data.items
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function loadPrintJobs() {
  try {
    const { data } = await apiClient.get<PageResponse<PrintJob>>('/print-jobs', {
      params: {
        document_type: documentType.value || undefined,
        date_from: dateFrom.value || undefined,
        date_to: dateTo.value || undefined,
        page_size: 80
      }
    })
    printJobs.value = data.items
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function reloadActive() {
  if (activeTab.value === 'production') {
    loadProductionOrders()
  } else {
    loadPrintJobs()
  }
}

watch([documentType, dateFrom, dateTo], loadPrintJobs)
watch([productionCustomerId, productionStatus, productionDateFrom, productionDateTo], loadProductionOrders)
onMounted(async () => {
  try {
    await loadCustomers()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
  await Promise.all([loadProductionOrders(), loadPrintJobs()])
})
</script>

<style scoped>
.print-tabs {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.print-filter-bar {
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) minmax(180px, 1fr) minmax(130px, 0.8fr) minmax(130px, 0.8fr) minmax(140px, 0.8fr) minmax(140px, 0.8fr) auto;
  align-items: center;
  margin-bottom: 12px;
}

@media (max-width: 1200px) {
  .print-filter-bar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .print-filter-bar {
    grid-template-columns: 1fr;
  }
}
</style>
