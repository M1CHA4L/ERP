<template>
  <section class="page-stack">
    <div class="toolbar finance-toolbar">
      <div class="toolbar-left">
        <strong>财务应收</strong>
        <el-select v-model="customerFilter" filterable clearable placeholder="客户筛选" class="filter-control">
          <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
        </el-select>
        <el-input v-model="cylinderFilter" placeholder="客户 / 订单 / 版号 / 应收号" clearable class="filter-control" :prefix-icon="Search" />
        <el-select v-model="statusFilter" placeholder="收款状态" clearable class="filter-control">
          <el-option label="待开票" value="pending_invoice" />
          <el-option label="部分收款" value="partial_paid" />
          <el-option label="已结清" value="closed" />
          <el-option label="历史归档" value="archived" />
        </el-select>
        <el-switch v-model="overdueOnly" active-text="只看逾期" />
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
      <div class="toolbar-left">
        <el-button
          type="primary"
          :icon="Plus"
          :loading="generating"
          :disabled="!pendingReceivableDeliveries.length"
          v-permission="'finance:receivable:create'"
          @click="batchCreateReceivables"
        >
          一键生成应收
        </el-button>
        <el-button type="success" :icon="Download" v-permission="'report:export'" @click="exportReceivables">
          导出 Excel
        </el-button>
      </div>
    </div>

    <div class="finance-summary">
      <div>
        <span>待生成应收</span>
        <strong>{{ pendingReceivableDeliveries.length }}</strong>
      </div>
      <div>
        <span>本页应收</span>
        <strong>{{ formatCurrency(receivableTotal) }}</strong>
      </div>
      <div>
        <span>本页已收</span>
        <strong>{{ formatCurrency(receivedTotal) }}</strong>
      </div>
      <div>
        <span>本页未收</span>
        <strong>{{ formatCurrency(balanceTotal) }}</strong>
      </div>
      <div>
        <span>逾期笔数</span>
        <strong>{{ overdueCount }}</strong>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>已签收待生成应收</span>
          <el-tag>{{ pendingReceivableDeliveries.length }} 单</el-tag>
        </div>
      </template>
      <el-table :data="pendingReceivableDeliveries" stripe empty-text="暂无待生成应收的签收单">
        <el-table-column prop="delivery_no" label="送货单号" min-width="170" />
        <el-table-column label="客户" min-width="180">
          <template #default="{ row }">{{ customerName(row.customer_id) }}</template>
        </el-table-column>
        <el-table-column prop="address" label="地址" min-width="220" show-overflow-tooltip />
        <el-table-column prop="signed_by" label="签收人" width="120" />
        <el-table-column prop="signed_at" label="签收时间" min-width="180" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button type="primary" size="small" v-permission="'finance:receivable:create'" @click="createReceivable(row)">
              生成应收
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>应收账款</span>
          <el-tag>{{ receivables.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="receivables" stripe empty-text="暂无应收记录">
        <el-table-column prop="receivable_no" label="应收编号" min-width="180" />
        <el-table-column prop="cylinder_no" label="版号" min-width="160" show-overflow-tooltip />
        <el-table-column label="客户" min-width="180">
          <template #default="{ row }">{{ customerName(row.customer_id) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="应收金额(Tk)" width="130">
          <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="received_amount" label="已收(Tk)" width="120">
          <template #default="{ row }">{{ formatCurrency(row.received_amount) }}</template>
        </el-table-column>
        <el-table-column prop="balance_amount" label="未收(Tk)" width="120">
          <template #default="{ row }">
            <strong :class="{ danger: Number(row.balance_amount) > 0 && isOverdue(row) }">{{ formatCurrency(row.balance_amount) }}</strong>
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="到期日" width="150">
          <template #default="{ row }">
            <span>{{ row.due_date }}</span>
            <el-tag v-if="isOverdue(row)" size="small" type="danger" effect="plain">逾期</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="finance_status" label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="financeTagType(row)">
              {{ receivableStatusLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button
              type="success"
              size="small"
              :disabled="Number(row.balance_amount) <= 0"
              v-permission="'finance:payment:create'"
              @click="openPayment(row)"
            >
              收款
            </el-button>
            <el-button
              v-if="row.status !== 'archived'"
              text
              type="primary"
              :disabled="Number(row.balance_amount) > 0"
              v-permission="'finance:adjust'"
              @click="archiveReceivable(row)"
            >
              归档
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="paymentVisible" title="收款登记" width="480px">
      <el-form :model="paymentForm" label-position="top">
        <el-form-item label="收款金额">
          <div class="payment-amount-row">
            <el-input-number v-model="paymentForm.amount" :min="0" :max="paymentLimit" :precision="2" />
            <el-button-group>
              <el-button @click="setPaymentRatio(1)">全额</el-button>
              <el-button @click="setPaymentRatio(0.5)">50%</el-button>
            </el-button-group>
          </div>
          <span class="form-tip">本次最多 {{ formatCurrency(paymentLimit) }}</span>
        </el-form-item>
        <el-form-item label="收款日期">
          <el-date-picker v-model="paymentForm.payment_date" value-format="YYYY-MM-DD" type="date" />
        </el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="paymentForm.payment_method" placeholder="选择方式">
            <el-option label="现金" value="cash" />
            <el-option label="银行" value="bank" />
            <el-option label="支票" value="check" />
            <el-option label="银行支票" value="bank_check" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="流水号">
          <el-input v-model="paymentForm.reference_no" placeholder="银行/支票流水号，重复会被拦截" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="paymentForm.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="paymentVisible = false">取消</el-button>
        <el-button type="primary" :loading="paying" @click="submitPayment">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { Customer, DeliveryOrder, PageResponse, Receivable } from '../api/types'
import { formatCurrency } from '../utils/format'

const customers = ref<Customer[]>([])
const signedDeliveries = ref<DeliveryOrder[]>([])
const receivables = ref<Receivable[]>([])
const receivableIndex = ref<Receivable[]>([])
const customerFilter = ref('')
const cylinderFilter = ref('')
const statusFilter = ref('')
const overdueOnly = ref(false)
const paymentVisible = ref(false)
const paying = ref(false)
const generating = ref(false)
const currentReceivable = ref<Receivable | null>(null)

const pendingReceivableDeliveries = computed(() => {
  const createdDeliveryIds = new Set(receivableIndex.value.map((item) => item.delivery_order_id).filter(Boolean))
  return signedDeliveries.value.filter((delivery) => !createdDeliveryIds.has(delivery.id))
})

const receivableTotal = computed(() => receivables.value.reduce((sum, item) => sum + Number(item.amount || 0), 0))
const receivedTotal = computed(() => receivables.value.reduce((sum, item) => sum + Number(item.received_amount || 0), 0))
const balanceTotal = computed(() => receivables.value.reduce((sum, item) => sum + Number(item.balance_amount || 0), 0))
const overdueCount = computed(() => receivables.value.filter((item) => isOverdue(item)).length)
const paymentLimit = computed(() => Number(currentReceivable.value?.balance_amount || 0))

const paymentForm = reactive({
  amount: 0,
  payment_date: new Date().toISOString().slice(0, 10),
  payment_method: 'cash',
  reference_no: '',
  remark: ''
})

async function fetchAllPages<T>(path: string, params: Record<string, string | number | boolean | undefined> = {}) {
  const items: T[] = []
  let page = 1
  const pageSize = 100
  while (true) {
    const { data } = await apiClient.get<PageResponse<T>>(path, {
      params: { ...params, page, page_size: pageSize }
    })
    items.push(...data.items)
    if (items.length >= data.total || data.items.length < pageSize) break
    page += 1
  }
  return items
}

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function customerName(customerId: string) {
  return customers.value.find((customer) => customer.id === customerId)?.name || customerId
}

function financeStatusLabel(status: string) {
  const map: Record<string, string> = {
    pending_invoice: '待开票',
    invoiced: '已开票',
    partial_paid: '部分收款',
    paid: '已收款',
    closed: '已结清',
    overdue: '逾期',
    archived: '已归档'
  }
  return map[status] || status
}

function receivableStatusLabel(receivable: Receivable) {
  return receivable.status === 'archived' ? '已归档' : financeStatusLabel(receivable.finance_status)
}

function financeTagType(receivable: Receivable) {
  if (receivable.status === 'archived') return 'info'
  if (receivable.finance_status === 'closed') return 'success'
  if (receivable.finance_status === 'partial_paid') return 'warning'
  return 'info'
}

function isOverdue(receivable: Receivable) {
  return Number(receivable.balance_amount || 0) > 0 && receivable.due_date < new Date().toISOString().slice(0, 10)
}

async function loadCustomers() {
  customers.value = await fetchAllPages<Customer>('/customers')
}

async function loadSignedDeliveries() {
  signedDeliveries.value = await fetchAllPages<DeliveryOrder>('/delivery-orders', { status_filter: 'signed' })
}

async function loadReceivableIndex() {
  receivableIndex.value = await fetchAllPages<Receivable>('/finance/receivables', { include_archived: true })
}

async function loadReceivables() {
  const { data } = await apiClient.get<PageResponse<Receivable>>('/finance/receivables', {
    params: {
      status_filter: statusFilter.value || undefined,
      customer_id: customerFilter.value || undefined,
      keyword: cylinderFilter.value.trim() || undefined,
      overdue_only: overdueOnly.value || undefined,
      page_size: 100
    }
  })
  receivables.value = data.items
}

async function loadAll() {
  await Promise.all([loadCustomers(), loadSignedDeliveries(), loadReceivableIndex(), loadReceivables()])
}

async function createReceivable(delivery: DeliveryOrder) {
  try {
    await apiClient.post(`/finance/delivery-orders/${delivery.id}/receivable`, {})
    ElMessage.success('应收已生成')
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function batchCreateReceivables() {
  if (!pendingReceivableDeliveries.value.length) return
  generating.value = true
  const targets = [...pendingReceivableDeliveries.value]
  const results = await Promise.allSettled(targets.map((delivery) => apiClient.post(`/finance/delivery-orders/${delivery.id}/receivable`, {})))
  const successCount = results.filter((result) => result.status === 'fulfilled').length
  const failedCount = results.length - successCount
  if (successCount) ElMessage.success(`已生成 ${successCount} 笔应收`)
  if (failedCount) ElMessage.warning(`${failedCount} 笔未生成，请检查是否已存在或送货状态变化`)
  generating.value = false
  await loadAll()
}

function openPayment(receivable: Receivable) {
  currentReceivable.value = receivable
  Object.assign(paymentForm, {
    amount: Number(receivable.balance_amount),
    payment_date: new Date().toISOString().slice(0, 10),
    payment_method: 'cash',
    reference_no: '',
    remark: ''
  })
  paymentVisible.value = true
}

function setPaymentRatio(ratio: number) {
  paymentForm.amount = Number((paymentLimit.value * ratio).toFixed(2))
}

async function submitPayment() {
  if (!currentReceivable.value) return
  if (Number(paymentForm.amount) <= 0 || Number(paymentForm.amount) > paymentLimit.value) {
    ElMessage.warning('请填写有效的收款金额')
    return
  }
  paying.value = true
  try {
    await apiClient.post(`/finance/receivables/${currentReceivable.value.id}/payments`, {
      ...paymentForm,
      reference_no: paymentForm.reference_no.trim() || null
    })
    ElMessage.success('收款已登记')
    paymentVisible.value = false
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    paying.value = false
  }
}

async function archiveReceivable(receivable: Receivable) {
  if (Number(receivable.balance_amount || 0) > 0) {
    ElMessage.warning('未收金额为 0 后才能归档')
    return
  }
  try {
    await ElMessageBox.confirm('归档后这笔应收会从默认财务列表隐藏，对应订单也会进入历史归档。', '确认归档', {
      type: 'warning',
      confirmButtonText: '归档',
      cancelButtonText: '取消'
    })
    await apiClient.post(`/finance/receivables/${receivable.id}/archive`)
    ElMessage.success('应收已归档')
    await loadAll()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(errorMessage(error))
  }
}

async function exportReceivables() {
  try {
    const response = await apiClient.get('/finance/receivables/export', {
      params: {
        status_filter: statusFilter.value || undefined,
        customer_id: customerFilter.value || undefined,
        keyword: cylinderFilter.value.trim() || undefined,
        overdue_only: overdueOnly.value || undefined
      },
      responseType: 'blob'
    })
    const url = URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `receivables-${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

watch([statusFilter, customerFilter, cylinderFilter, overdueOnly], loadReceivables)
onMounted(loadAll)
</script>

<style scoped>
.finance-toolbar {
  align-items: flex-start;
  gap: 12px;
}

.filter-control {
  width: 190px;
}

.finance-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.finance-summary div {
  min-height: 72px;
  padding: 12px 14px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #f8fafc;
}

.finance-summary span,
.form-tip {
  color: #667085;
  font-size: 13px;
}

.finance-summary strong {
  display: block;
  margin-top: 8px;
  font-size: 20px;
}

.danger {
  color: #c45656;
}

.payment-amount-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

@media (max-width: 1100px) {
  .finance-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
