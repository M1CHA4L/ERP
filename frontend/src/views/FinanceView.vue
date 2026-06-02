<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>财务应收</strong>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
        <el-button type="success" :icon="Download" v-permission="'report:export'" @click="exportReceivables">
          导出 Excel
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>已签收待生成应收</span>
          <el-tag>{{ pendingReceivableDeliveries.length }} 单</el-tag>
        </div>
      </template>
      <el-table :data="pendingReceivableDeliveries" stripe>
        <el-table-column prop="delivery_no" label="送货单号" min-width="190" />
        <el-table-column prop="address" label="地址" min-width="220" />
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
          <el-select v-model="statusFilter" placeholder="收款状态" clearable>
            <el-option label="待开票" value="pending_invoice" />
            <el-option label="部分收款" value="partial_paid" />
            <el-option label="已结清" value="closed" />
          </el-select>
        </div>
      </template>
      <el-table :data="receivables" stripe>
        <el-table-column prop="receivable_no" label="应收编号" min-width="190" />
        <el-table-column prop="amount" label="应收金额(Tk)" width="130">
          <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="received_amount" label="已收(Tk)" width="120">
          <template #default="{ row }">{{ formatCurrency(row.received_amount) }}</template>
        </el-table-column>
        <el-table-column prop="balance_amount" label="未收(Tk)" width="120">
          <template #default="{ row }">{{ formatCurrency(row.balance_amount) }}</template>
        </el-table-column>
        <el-table-column prop="due_date" label="到期日" width="130" />
        <el-table-column prop="finance_status" label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="row.finance_status === 'closed' ? 'success' : row.finance_status === 'partial_paid' ? 'warning' : 'info'">
              {{ financeStatusLabel(row.finance_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
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
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="paymentVisible" title="收款登记" width="460px">
      <el-form :model="paymentForm" label-position="top">
        <el-form-item label="收款金额">
          <el-input-number v-model="paymentForm.amount" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="收款日期">
          <el-date-picker v-model="paymentForm.payment_date" value-format="YYYY-MM-DD" type="date" />
        </el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="paymentForm.payment_method" placeholder="选择方式">
            <el-option label="现金" value="cash" />
            <el-option label="支票" value="check" />
          </el-select>
        </el-form-item>
        <el-form-item label="流水号">
          <el-input v-model="paymentForm.reference_no" />
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
import { ElMessage } from 'element-plus'
import { Download, Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { DeliveryOrder, PageResponse, Receivable } from '../api/types'
import { formatCurrency } from '../utils/format'

const signedDeliveries = ref<DeliveryOrder[]>([])
const receivables = ref<Receivable[]>([])
const statusFilter = ref('')
const paymentVisible = ref(false)
const paying = ref(false)
const currentReceivable = ref<Receivable | null>(null)

const pendingReceivableDeliveries = computed(() => {
  const createdDeliveryIds = new Set(receivables.value.map((item) => item.delivery_order_id).filter(Boolean))
  return signedDeliveries.value.filter((delivery) => !createdDeliveryIds.has(delivery.id))
})

const paymentForm = reactive({
  amount: 0,
  payment_date: new Date().toISOString().slice(0, 10),
  payment_method: 'cash',
  reference_no: '',
  remark: ''
})

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function financeStatusLabel(status: string) {
  const map: Record<string, string> = {
    pending_invoice: '待开票',
    invoiced: '已开票',
    partial_paid: '部分收款',
    paid: '已收款',
    closed: '已结清',
    overdue: '逾期'
  }
  return map[status] || status
}

async function loadSignedDeliveries() {
  const { data } = await apiClient.get<PageResponse<DeliveryOrder>>('/delivery-orders', {
    params: { status_filter: 'signed' }
  })
  signedDeliveries.value = data.items
}

async function loadReceivables() {
  const { data } = await apiClient.get<PageResponse<Receivable>>('/finance/receivables', {
    params: { status_filter: statusFilter.value || undefined }
  })
  receivables.value = data.items
}

async function loadAll() {
  await Promise.all([loadSignedDeliveries(), loadReceivables()])
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

async function submitPayment() {
  if (!currentReceivable.value) return
  paying.value = true
  try {
    await apiClient.post(`/finance/receivables/${currentReceivable.value.id}/payments`, paymentForm)
    ElMessage.success('收款已登记')
    paymentVisible.value = false
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    paying.value = false
  }
}

async function exportReceivables() {
  try {
    const response = await apiClient.get('/finance/receivables/export', {
      params: { status_filter: statusFilter.value || undefined },
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

watch(statusFilter, loadReceivables)
onMounted(loadAll)
</script>
