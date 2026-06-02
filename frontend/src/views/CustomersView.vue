<template>
  <section class="page-stack">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索客户名称或编号" clearable :prefix-icon="Search" />
      <div class="toolbar-left">
        <el-button type="success" :icon="Download" v-permission="'report:export'" @click="exportCustomers">
          导出 Excel
        </el-button>
        <el-button type="primary" :icon="Plus" v-permission="'customer:create'" @click="drawerVisible = true">
          新增客户
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="customers" stripe @row-dblclick="openCustomerDetail">
        <el-table-column prop="customer_code" label="客户编号" min-width="150" />
        <el-table-column prop="name" label="客户名称" min-width="180" />
        <el-table-column prop="contact_name" label="联系人" width="120" />
        <el-table-column prop="phone" label="电话" min-width="140" />
        <el-table-column prop="payment_terms_days" label="账期" width="100">
          <template #default="{ row }">{{ row.payment_terms_days }} 天</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openCustomerDetail(row)">详情</el-button>
            <el-button text type="danger" v-permission="'customer:delete'" @click="deleteCustomer(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" title="新增客户" size="420px">
      <el-form :model="form" label-position="top">
        <el-form-item label="客户名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact_name" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" type="textarea" />
        </el-form-item>
        <el-form-item label="账期天数">
          <el-input-number v-model="form.payment_terms_days" :min="0" />
        </el-form-item>
        <el-button type="primary" :loading="saving" @click="createCustomer">保存</el-button>
      </el-form>
    </el-drawer>

    <el-drawer
      v-model="detailDrawerVisible"
      :title="selectedCustomer ? `客户详情：${selectedCustomer.name}` : '客户详情'"
      size="760px"
    >
      <template v-if="selectedCustomer">
        <div class="detail-grid customer-detail-grid">
          <div>
            <span>客户编号</span>
            <strong>{{ selectedCustomer.customer_code }}</strong>
          </div>
          <div>
            <span>联系人</span>
            <strong>{{ selectedCustomer.contact_name || '-' }}</strong>
          </div>
          <div>
            <span>电话</span>
            <strong>{{ selectedCustomer.phone || '-' }}</strong>
          </div>
          <div>
            <span>账期</span>
            <strong>{{ selectedCustomer.payment_terms_days }} 天</strong>
          </div>
        </div>

        <div class="customer-address">
          <span>地址</span>
          <strong>{{ selectedCustomer.address || '-' }}</strong>
        </div>

        <div class="orders-header">
          <div class="panel-title">
            <span>现有订单</span>
            <el-tag>{{ customerOrders.length }} 单</el-tag>
          </div>
          <el-button text type="primary" @click="loadCustomerOrders(selectedCustomer)">刷新</el-button>
        </div>

        <el-table :data="customerOrders" v-loading="loadingOrders" stripe empty-text="该客户暂无订单">
          <el-table-column prop="order_no" label="订单编号" min-width="150" />
          <el-table-column prop="product_summary" label="产品" min-width="180" show-overflow-tooltip />
          <el-table-column prop="due_date" label="交期" width="120" />
          <el-table-column prop="total_amount" label="金额" width="120">
            <template #default="{ row }">{{ formatMoney(row.total_amount) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag>{{ orderStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" @click="goOrder(row.id)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Plus, Search } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { Customer, PageResponse, SalesOrder } from '../api/types'
import { formatCurrency } from '../utils/format'

const router = useRouter()
const keyword = ref('')
const customers = ref<Customer[]>([])
const drawerVisible = ref(false)
const saving = ref(false)
const detailDrawerVisible = ref(false)
const selectedCustomer = ref<Customer | null>(null)
const customerOrders = ref<SalesOrder[]>([])
const loadingOrders = ref(false)

const form = reactive({
  name: '',
  contact_name: '',
  phone: '',
  address: '',
  payment_terms_days: 30
})

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function orderStatusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: '草稿',
    confirmed: '已确认',
    in_production: '生产中',
    pending_inspection: '待检验',
    inspection_passed: '检验通过',
    pending_delivery: '待送货',
    delivered: '已送货',
    pending_payment: '待收款',
    paid: '已结清',
    archived: '已归档',
    cancelled: '已取消',
    paused: '已暂停',
    reworking: '返工中'
  }
  return labels[status] || status
}

function formatMoney(value: number) {
  return formatCurrency(value)
}

async function loadCustomers() {
  const { data } = await apiClient.get<PageResponse<Customer>>('/customers', {
    params: { keyword: keyword.value || undefined }
  })
  customers.value = data.items
}

async function loadCustomerOrders(customer: Customer) {
  loadingOrders.value = true
  try {
    const { data } = await apiClient.get<PageResponse<SalesOrder>>('/sales-orders', {
      params: { customer_id: customer.id, page_size: 50 }
    })
    customerOrders.value = data.items
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loadingOrders.value = false
  }
}

async function openCustomerDetail(customer: Customer) {
  selectedCustomer.value = customer
  customerOrders.value = []
  detailDrawerVisible.value = true
  await loadCustomerOrders(customer)
}

async function createCustomer() {
  if (!form.name) {
    ElMessage.warning('请填写客户名称')
    return
  }
  saving.value = true
  try {
    await apiClient.post('/customers', form)
    ElMessage.success('客户已创建')
    drawerVisible.value = false
    Object.assign(form, { name: '', contact_name: '', phone: '', address: '', payment_terms_days: 30 })
    keyword.value = ''
    await loadCustomers()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function deleteCustomer(customer: Customer) {
  try {
    await ElMessageBox.confirm(
      `确定删除客户「${customer.name}」吗？删除后不会再出现在客户列表中。`,
      '删除客户',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await apiClient.delete(`/customers/${customer.id}`)
    ElMessage.success('客户已删除')
    await loadCustomers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(errorMessage(error))
    }
  }
}

async function exportCustomers() {
  try {
    const response = await apiClient.get('/customers/export', {
      params: { keyword: keyword.value || undefined },
      responseType: 'blob'
    })
    const url = URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `customers-${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function goOrder(orderId: string) {
  detailDrawerVisible.value = false
  router.push(`/orders/${orderId}`)
}

watch(keyword, loadCustomers)
onMounted(loadCustomers)
</script>

<style scoped>
.customer-detail-grid {
  margin-bottom: 14px;
}

.customer-address {
  display: grid;
  gap: 8px;
  margin-bottom: 18px;
  padding: 14px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #f8fafc;
}

.customer-address span {
  color: #667085;
  font-size: 13px;
}

.customer-address strong {
  color: #18212f;
  font-size: 15px;
  overflow-wrap: anywhere;
}

.orders-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 12px 0;
}
</style>
