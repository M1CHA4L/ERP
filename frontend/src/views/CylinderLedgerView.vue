<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input v-model="cylinderNo" placeholder="输入版号 / Cylinder No." clearable :prefix-icon="Search" @keyup.enter="loadLedger" />
        <el-button type="primary" :icon="Search" @click="loadLedger">查询版号</el-button>
        <el-button :icon="Refresh" @click="loadOrders">刷新订单</el-button>
      </div>
    </div>

    <div class="metric-grid ledger-metrics">
      <el-card shadow="never" class="metric-card">
        <span>版号</span>
        <strong>{{ ledger?.cylinder_no || '-' }}</strong>
        <small>统一追踪生产、库存和收款</small>
      </el-card>
      <el-card shadow="never" class="metric-card">
        <span>相关订单</span>
        <strong>{{ ledger?.orders.length || orders.length }}</strong>
        <small>来自制版订单和历史复制</small>
      </el-card>
      <el-card shadow="never" class="metric-card">
        <span>已收</span>
        <strong>{{ formatCurrency(receivedTotal) }}</strong>
        <small>按月度汇总</small>
      </el-card>
      <el-card shadow="never" class="metric-card">
        <span>待结</span>
        <strong>{{ formatCurrency(dueTotal) }}</strong>
        <small>上期 + 本期 - 已收</small>
      </el-card>
      <el-card shadow="never" class="metric-card">
        <span>库存支数</span>
        <strong>{{ stockQty }}</strong>
        <small>版辊入库记录</small>
      </el-card>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>制版订单</span>
          <el-tag>{{ orders.length }} 单</el-tag>
        </div>
      </template>
      <el-table :data="orders" stripe @row-dblclick="goOrder">
        <el-table-column prop="order_no" label="订单号" min-width="160" />
        <el-table-column label="版号" min-width="150">
          <template #default="{ row }">{{ cylinderLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="product_summary" label="产品" min-width="180" show-overflow-tooltip />
        <el-table-column prop="order_date" label="下单日期" width="120" />
        <el-table-column prop="due_date" label="交期" width="120" />
        <el-table-column prop="total_amount" label="金额" width="120">
          <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click.stop="goOrder(row)">详情</el-button>
            <el-button text type="primary" @click.stop="printProductionOrder(row)">生产单</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>月度收款</span>
          <el-tag>{{ ledger?.monthly_receipts.length || 0 }} 月</el-tag>
        </div>
      </template>
      <el-table :data="ledger?.monthly_receipts || []" stripe empty-text="查询版号后显示月结记录">
        <el-table-column prop="accounting_month" label="月份" width="130" />
        <el-table-column prop="receivable_amount" label="本月应收" width="130">
          <template #default="{ row }">{{ formatCurrency(row.receivable_amount) }}</template>
        </el-table-column>
        <el-table-column prop="received_amount" label="本月已收" width="130">
          <template #default="{ row }">{{ formatCurrency(row.received_amount) }}</template>
        </el-table-column>
        <el-table-column prop="due_amount" label="待结" width="130">
          <template #default="{ row }">{{ formatCurrency(row.due_amount) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="calculated_at" label="汇总时间" min-width="180" />
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>版辊库存</span>
          <el-tag>{{ ledger?.stocks.length || 0 }} 条</el-tag>
        </div>
      </template>
      <el-table :data="ledger?.stocks || []" stripe empty-text="暂无版辊入库记录">
        <el-table-column prop="stock_no" label="入库单号" min-width="150" />
        <el-table-column prop="warehouse_name" label="仓库" min-width="150" />
        <el-table-column prop="diameter" label="直径" width="100" />
        <el-table-column prop="cylinder_length" label="版长" width="100" />
        <el-table-column prop="quantity" label="支数" width="90" />
        <el-table-column prop="total_amount" label="金额" width="120">
          <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column prop="stock_in_date" label="入库日期" width="130" />
        <el-table-column prop="stock_status" label="状态" width="110" />
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { CylinderLedger, PageResponse, SalesOrder } from '../api/types'
import { formatCurrency } from '../utils/format'

const router = useRouter()
const cylinderNo = ref('')
const ledger = ref<CylinderLedger | null>(null)
const fallbackOrders = ref<SalesOrder[]>([])

const orders = computed(() => ledger.value?.orders || fallbackOrders.value)
const receivedTotal = computed(() => (ledger.value?.monthly_receipts || []).reduce((sum, row) => sum + Number(row.received_amount || 0), 0))
const dueTotal = computed(() => (ledger.value?.monthly_receipts || []).reduce((sum, row) => sum + Number(row.due_amount || 0), 0))
const stockQty = computed(() => (ledger.value?.stocks || []).reduce((sum, row) => sum + Number(row.quantity || 0), 0))

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function cylinderLabel(order: SalesOrder) {
  const details = order.plate_details || {}
  const row = order.color_rows?.[0] || {}
  return String(details.cylinder_id || details.no || details.sample_no || row.public_no || order.order_no)
}

async function loadOrders() {
  const { data } = await apiClient.get<PageResponse<SalesOrder>>('/plate-orders', {
    params: { cylinder_no: cylinderNo.value || undefined, page_size: 50 }
  })
  fallbackOrders.value = data.items
}

async function loadLedger() {
  if (!cylinderNo.value.trim()) {
    ledger.value = null
    await loadOrders()
    return
  }
  try {
    const { data } = await apiClient.get<CylinderLedger>(`/plate-orders/cylinders/${encodeURIComponent(cylinderNo.value.trim())}`)
    ledger.value = data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function goOrder(order: SalesOrder) {
  router.push(`/orders/${order.id}`)
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

onMounted(loadOrders)
</script>

<style scoped>
.ledger-metrics {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

@media (max-width: 1100px) {
  .ledger-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
