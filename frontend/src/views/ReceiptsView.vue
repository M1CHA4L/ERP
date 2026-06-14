<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="customerFilter" filterable clearable placeholder="客户筛选">
          <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
        </el-select>
        <el-input v-model="cylinderFilter" placeholder="版号筛选" clearable />
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
      <div class="toolbar-left">
        <el-button type="primary" :icon="Plus" v-permission="'finance:payment:create'" @click="openReceiptDialog">登记日收入</el-button>
        <el-button type="success" :icon="Calendar" v-permission="'finance:month_close'" @click="closeMonth">月末汇总</el-button>
        <el-button :icon="Download" v-permission="'report:export'" @click="exportDailyReceipts">导出日收入</el-button>
        <el-button :icon="Download" v-permission="'report:export'" @click="exportMonthlyReceipts">导出版号月结</el-button>
        <el-button :icon="Download" v-permission="'report:export'" @click="exportCustomerStatements">导出客户账单</el-button>
      </div>
    </div>

    <div class="form-grid">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="panel-title">
            <span>月结操作</span>
          </div>
        </template>
        <el-form label-position="top">
          <el-form-item label="汇总月份">
            <el-date-picker v-model="monthCloseDate" value-format="YYYY-MM-DD" type="month" />
          </el-form-item>
          <el-form-item label="客户账单">
            <el-select v-model="statementForm.customer_id" filterable clearable placeholder="选择客户">
              <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="勾选版号（逗号分隔）">
            <el-input v-model="statementForm.cylinder_nos" placeholder="S26052340, S26052353" />
          </el-form-item>
          <el-button type="primary" :loading="creatingStatement" v-permission="'finance:month_close'" @click="createStatement">生成客户账单</el-button>
          <el-button v-if="lastStatement && lastStatement.price_approval_status !== 'approved'" text type="success" v-permission="'finance:bill_price:approve'" @click="approveStatementPrice(lastStatement)">审核价格</el-button>
          <el-button v-if="lastStatement" text type="primary" :disabled="lastStatement.price_approval_status !== 'approved'" v-permission="'finance:receipt:print'" @click="printStatement(lastStatement.id, true)">
            带抬头打印 {{ lastStatement.statement_no }}
          </el-button>
          <el-button v-if="lastStatement" text :disabled="lastStatement.price_approval_status !== 'approved'" v-permission="'finance:receipt:print'" @click="printStatement(lastStatement.id, false)">
            无抬头打印
          </el-button>
        </el-form>
      </el-card>

      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="panel-title">
            <span>本页汇总</span>
          </div>
        </template>
        <div class="receipt-summary">
          <div><span>日收入合计</span><strong>{{ formatCurrency(receiptTotal) }}</strong></div>
          <div><span>现金</span><strong>{{ formatCurrency(cashTotal) }}</strong></div>
          <div><span>银行</span><strong>{{ formatCurrency(bankTotal) }}</strong></div>
          <div><span>其他</span><strong>{{ formatCurrency(otherTotal) }}</strong></div>
        </div>
      </el-card>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>日收入表</span>
          <el-tag>{{ receipts.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="receipts" stripe>
        <el-table-column prop="receipt_no" label="Receipt No." min-width="150" />
        <el-table-column label="Customer" min-width="180">
          <template #default="{ row }">{{ customerName(row.customer_id) }}</template>
        </el-table-column>
        <el-table-column prop="received_date" label="Received Date" width="130" />
        <el-table-column prop="payment_method" label="Payment Method" width="150" />
        <el-table-column prop="cash_amount" label="Cash Amount" width="130">
          <template #default="{ row }">{{ formatCurrency(row.cash_amount) }}</template>
        </el-table-column>
        <el-table-column prop="bank_amount" label="Bank Amount" width="130">
          <template #default="{ row }">{{ formatCurrency(row.bank_amount) }}</template>
        </el-table-column>
        <el-table-column prop="other_amount" label="Other Amount" width="130">
          <template #default="{ row }">{{ formatCurrency(row.other_amount) }}</template>
        </el-table-column>
        <el-table-column prop="salesman_name" label="Salesman" width="120" />
        <el-table-column label="VAT" width="90"> <template #default>0</template> </el-table-column>
        <el-table-column label="AIT" width="90"> <template #default>0</template> </el-table-column>
        <el-table-column label="Total Tax" width="110"> <template #default>0</template> </el-table-column>
        <el-table-column prop="total_amount" label="Total Amount" width="130">
          <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="Remark" min-width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status !== 'checked'" text type="primary" @click="checkReceipt(row)">审核</el-button>
            <el-button text type="primary" :disabled="row.status !== 'checked'" @click="printReceipt(row.id)">收据</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>版号月结</span>
          <el-tag>{{ monthly.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="monthly" stripe>
        <el-table-column prop="accounting_month" label="月份" width="130" />
        <el-table-column label="客户" min-width="180">
          <template #default="{ row }">{{ customerName(row.customer_id) }}</template>
        </el-table-column>
        <el-table-column prop="cylinder_no" label="版号" min-width="150" />
        <el-table-column prop="receivable_amount" label="应收" width="120">
          <template #default="{ row }">{{ formatCurrency(row.receivable_amount) }}</template>
        </el-table-column>
        <el-table-column prop="received_amount" label="已收" width="120">
          <template #default="{ row }">{{ formatCurrency(row.received_amount) }}</template>
        </el-table-column>
        <el-table-column prop="due_amount" label="待结" width="120">
          <template #default="{ row }">{{ formatCurrency(row.due_amount) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" />
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>客户账单</span>
          <el-tag>{{ statements.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="statements" stripe>
        <el-table-column prop="statement_no" label="Bill No." min-width="150" />
        <el-table-column prop="statement_month" label="月份" width="120" />
        <el-table-column label="客户" min-width="180">
          <template #default="{ row }">{{ customerName(row.customer_id) }}</template>
        </el-table-column>
        <el-table-column prop="current_receivable" label="金额" width="130">
          <template #default="{ row }">{{ formatWholeCurrency(row.current_receivable) }}</template>
        </el-table-column>
        <el-table-column label="VAT 15%" width="130">
          <template #default="{ row }">{{ formatCurrency(statementVat(row)) }}</template>
        </el-table-column>
        <el-table-column label="含税应收" width="140">
          <template #default="{ row }">{{ formatCurrency(statementTotalWithVat(row)) }}</template>
        </el-table-column>
        <el-table-column label="价格审核" width="130">
          <template #default="{ row }">
            <el-tag :type="row.price_approval_status === 'approved' ? 'success' : 'warning'">
              {{ statementApprovalLabel(row.price_approval_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="printed_at" label="打印时间" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.price_approval_status !== 'approved'" text type="success" v-permission="'finance:bill_price:approve'" @click="approveStatementPrice(row)">审核价格</el-button>
            <el-button text type="primary" :disabled="row.price_approval_status !== 'approved'" v-permission="'finance:receipt:print'" @click="printStatement(row.id, true)">带抬头</el-button>
            <el-button text :disabled="row.price_approval_status !== 'approved'" v-permission="'finance:receipt:print'" @click="printStatement(row.id, false)">无抬头</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="receiptVisible" title="登记日收入" width="860px">
      <el-form :model="receiptForm" label-position="top">
        <div class="form-grid">
          <el-form-item label="客户">
            <el-select v-model="receiptForm.customer_id" filterable placeholder="选择客户">
              <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="收款日期">
            <el-date-picker v-model="receiptForm.received_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="方式">
            <el-select v-model="receiptForm.payment_method">
              <el-option label="现金" value="cash" />
              <el-option label="银行" value="bank" />
              <el-option label="支票" value="check" />
              <el-option label="银行支票" value="bank_check" />
              <el-option label="其他" value="other" />
            </el-select>
          </el-form-item>
          <el-form-item label="收款人">
            <el-input v-model="receiptForm.payee_name" />
          </el-form-item>
          <el-form-item label="现金">
            <el-input-number v-model="receiptForm.cash_amount" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="银行">
            <el-input-number v-model="receiptForm.bank_amount" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="其他">
            <el-input-number v-model="receiptForm.other_amount" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="业务员">
            <el-input v-model="receiptForm.salesman_name" />
          </el-form-item>
        </div>
        <el-form-item label="摘要">
          <el-input v-model="receiptForm.abstract" placeholder="例如 May 2026 / April 2026" />
        </el-form-item>
        <div class="table-tools">
          <span>
            收款总额 {{ formatCurrency(receiptFormTotal) }} / 分摊合计 {{ formatCurrency(allocationTotal) }}
            <el-tag v-if="allocationDiff !== 0" size="small" type="warning" effect="plain">差额 {{ formatCurrency(allocationDiff) }}</el-tag>
          </span>
          <div class="table-actions">
            <el-button :disabled="allocationDiff === 0" @click="fillAllocationBalance">补齐差额</el-button>
            <el-button :icon="Plus" @click="addAllocation">添加版号</el-button>
          </div>
        </div>
        <el-table :data="receiptForm.allocations">
          <el-table-column label="版号" min-width="180">
            <template #default="{ row }"><el-input v-model="row.cylinder_no" /></template>
          </el-table-column>
          <el-table-column label="月份" width="170">
            <template #default="{ row }"><el-date-picker v-model="row.accounting_month" value-format="YYYY-MM-DD" type="month" /></template>
          </el-table-column>
          <el-table-column label="金额" width="160">
            <template #default="{ row }"><el-input-number v-model="row.amount" :min="0" :precision="2" /></template>
          </el-table-column>
          <el-table-column label="备注" min-width="160">
            <template #default="{ row }"><el-input v-model="row.remark" /></template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ $index }"><el-button text type="danger" @click="removeAllocation($index)">删除</el-button></template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="receiptVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingReceipt" @click="saveReceipt">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Calendar, Download, Plus, Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { Customer, CustomerStatementRun, MonthlyPaymentSummary, PageResponse, ReceiptDailyEntry } from '../api/types'
import { formatCurrency } from '../utils/format'

const customers = ref<Customer[]>([])
const receipts = ref<ReceiptDailyEntry[]>([])
const monthly = ref<MonthlyPaymentSummary[]>([])
const statements = ref<CustomerStatementRun[]>([])
const customerFilter = ref('')
const cylinderFilter = ref('')
const receiptVisible = ref(false)
const savingReceipt = ref(false)
const creatingStatement = ref(false)
const lastStatement = ref<CustomerStatementRun | null>(null)
const monthCloseDate = ref(`${new Date().toISOString().slice(0, 7)}-01`)

const receiptForm = reactive({
  customer_id: '',
  received_date: new Date().toISOString().slice(0, 10),
  payment_method: 'cash',
  cash_amount: 0,
  bank_amount: 0,
  other_amount: 0,
  salesman_name: '',
  payee_name: '',
  abstract: '',
  allocations: [{ cylinder_no: '', accounting_month: `${new Date().toISOString().slice(0, 7)}-01`, amount: 0, remark: '' }]
})

const statementForm = reactive({
  customer_id: '',
  cylinder_nos: ''
})

const receiptTotal = computed(() => receipts.value.reduce((sum, item) => sum + Number(item.total_amount || 0), 0))
const cashTotal = computed(() => receipts.value.reduce((sum, item) => sum + Number(item.cash_amount || 0), 0))
const bankTotal = computed(() => receipts.value.reduce((sum, item) => sum + Number(item.bank_amount || 0), 0))
const otherTotal = computed(() => receipts.value.reduce((sum, item) => sum + Number(item.other_amount || 0), 0))
const receiptFormTotal = computed(() => Number(receiptForm.cash_amount || 0) + Number(receiptForm.bank_amount || 0) + Number(receiptForm.other_amount || 0))
const allocationTotal = computed(() => receiptForm.allocations.reduce((sum, item) => sum + Number(item.amount || 0), 0))
const allocationDiff = computed(() => Number((receiptFormTotal.value - allocationTotal.value).toFixed(2)))

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function customerName(customerId: string) {
  return customers.value.find((customer) => customer.id === customerId)?.name || customerId
}

function formatWholeCurrency(value: number | string | null | undefined) {
  return `Tk ${Math.round(Number(value || 0)).toLocaleString()}`
}

function statementVat(statement: CustomerStatementRun) {
  return Number((Number(statement.current_receivable || 0) * 0.15).toFixed(2))
}

function statementTotalWithVat(statement: CustomerStatementRun) {
  return Number((Number(statement.current_receivable || 0) + statementVat(statement)).toFixed(2))
}

function statementApprovalLabel(status: string) {
  if (status === 'approved') return '已审核'
  if (status === 'rejected') return '已驳回'
  return '待老板审核'
}

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

async function loadCustomers() {
  customers.value = await fetchAllPages<Customer>('/customers')
}

async function loadReceipts() {
  const { data } = await apiClient.get<PageResponse<ReceiptDailyEntry>>('/finance/receipts/daily', {
    params: {
      customer_id: customerFilter.value || undefined,
      cylinder_no: cylinderFilter.value || undefined,
      page_size: 50
    }
  })
  receipts.value = data.items
}

async function loadMonthly() {
  const { data } = await apiClient.get<PageResponse<MonthlyPaymentSummary>>('/finance/monthly-receipts', {
    params: {
      customer_id: customerFilter.value || undefined,
      cylinder_no: cylinderFilter.value || undefined,
      page_size: 50
    }
  })
  monthly.value = data.items
}

async function loadStatements() {
  const { data } = await apiClient.get<PageResponse<CustomerStatementRun>>('/finance/customer-statements', {
    params: {
      customer_id: statementForm.customer_id || customerFilter.value || undefined,
      statement_month: monthCloseDate.value,
      page_size: 50
    }
  })
  statements.value = data.items
}

async function loadAll() {
  await Promise.all([loadReceipts(), loadMonthly(), loadStatements()])
}

function addAllocation() {
  receiptForm.allocations.push({ cylinder_no: '', accounting_month: monthCloseDate.value, amount: 0, remark: '' })
}

function removeAllocation(index: number) {
  receiptForm.allocations.splice(index, 1)
}

function openReceiptDialog() {
  resetReceiptForm()
  receiptVisible.value = true
}

function resetReceiptForm() {
  Object.assign(receiptForm, {
    customer_id: '',
    received_date: new Date().toISOString().slice(0, 10),
    payment_method: 'cash',
    cash_amount: 0,
    bank_amount: 0,
    other_amount: 0,
    salesman_name: '',
    payee_name: '',
    abstract: '',
    allocations: [{ cylinder_no: '', accounting_month: monthCloseDate.value, amount: 0, remark: '' }]
  })
}

function fillAllocationBalance() {
  if (!receiptForm.allocations.length) addAllocation()
  const target = [...receiptForm.allocations].reverse().find((item) => item.cylinder_no) || receiptForm.allocations[receiptForm.allocations.length - 1]
  target.amount = Number((Number(target.amount || 0) + allocationDiff.value).toFixed(2))
}

async function saveReceipt() {
  if (!receiptForm.customer_id || receiptFormTotal.value <= 0) {
    ElMessage.warning('请选择客户并填写收款金额')
    return
  }
  const allocations = receiptForm.allocations.filter((item) => item.cylinder_no && item.amount > 0)
  if (!allocations.length) {
    ElMessage.warning('请至少分摊到一个版号')
    return
  }
  if (allocationDiff.value !== 0) {
    ElMessage.warning('分摊合计必须等于收款总额')
    return
  }
  savingReceipt.value = true
  try {
    await apiClient.post('/finance/receipts/daily', { ...receiptForm, allocations })
    ElMessage.success('日收入已登记')
    receiptVisible.value = false
    resetReceiptForm()
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingReceipt.value = false
  }
}

async function checkReceipt(row: ReceiptDailyEntry) {
  try {
    await apiClient.post(`/finance/receipts/daily/${row.id}/check`)
    ElMessage.success('收据已审核')
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function closeMonth() {
  try {
    const { data } = await apiClient.post<MonthlyPaymentSummary[]>('/finance/monthly-receipts/close', {
      accounting_month: monthCloseDate.value,
      customer_id: customerFilter.value || null
    })
    ElMessage.success(`已汇总 ${data.length} 条版号月结`)
    await loadMonthly()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function createStatement() {
  if (!statementForm.customer_id || !statementForm.cylinder_nos.trim()) {
    ElMessage.warning('请选择客户并填写版号')
    return
  }
  creatingStatement.value = true
  try {
    const { data } = await apiClient.post<CustomerStatementRun>('/finance/customer-statements', {
      customer_id: statementForm.customer_id,
      statement_month: monthCloseDate.value,
      selected_cylinder_nos: statementForm.cylinder_nos.split(',').map((item) => item.trim()).filter(Boolean),
      include_previous_balance: true
    })
    lastStatement.value = data
    ElMessage.success('客户账单已生成')
    await loadStatements()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    creatingStatement.value = false
  }
}

async function approveStatementPrice(statement: CustomerStatementRun) {
  try {
    const { data } = await apiClient.post<CustomerStatementRun>(`/finance/customer-statements/${statement.id}/approve-price`)
    if (lastStatement.value?.id === statement.id) lastStatement.value = data
    ElMessage.success('Bill 价格已审核')
    await loadStatements()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function openPrintable(path: string) {
  try {
    const response = await apiClient.get(path, { responseType: 'text' })
    const url = URL.createObjectURL(new Blob([response.data], { type: 'text/html' }))
    window.open(url, '_blank')
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function downloadReport(path: string, filename: string, params: Record<string, string | undefined> = {}) {
  try {
    const response = await apiClient.get(path, { params, responseType: 'blob' })
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

function exportDailyReceipts() {
  downloadReport('/finance/receipts/daily/export', 'daily_receipts.xlsx', {
    customer_id: customerFilter.value || undefined,
    cylinder_no: cylinderFilter.value || undefined
  })
}

function exportMonthlyReceipts() {
  downloadReport('/finance/monthly-receipts/export', 'monthly_receipts.xlsx', {
    customer_id: customerFilter.value || undefined,
    cylinder_no: cylinderFilter.value || undefined,
    accounting_month: monthCloseDate.value
  })
}

function exportCustomerStatements() {
  downloadReport('/finance/customer-statements/export', 'customer_statements.xlsx', {
    customer_id: statementForm.customer_id || customerFilter.value || undefined,
    statement_month: monthCloseDate.value
  })
}

function printReceipt(id: string) {
  openPrintable(`/finance/receipts/daily/${id}/print`)
}

function printStatement(id: string, withHeader = true) {
  openPrintable(`/finance/customer-statements/${id}/print?with_header=${withHeader ? 'true' : 'false'}`)
}

watch([customerFilter, cylinderFilter, monthCloseDate, () => statementForm.customer_id], loadAll)
onMounted(async () => {
  await loadCustomers()
  await loadAll()
})
</script>

<style scoped>
.receipt-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.receipt-summary div {
  display: grid;
  gap: 6px;
  min-height: 72px;
  padding: 12px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #f8fafc;
}

.receipt-summary span {
  color: #667085;
  font-size: 13px;
}

.receipt-summary strong {
  font-size: 20px;
}

.table-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.table-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
