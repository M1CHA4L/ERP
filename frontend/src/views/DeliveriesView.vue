<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>送货管理</strong>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>可送货订单</span>
          <el-tag>{{ deliverableOrders.length }} 单</el-tag>
        </div>
      </template>
      <el-table :data="deliverableOrders" stripe>
        <el-table-column prop="order_no" label="订单编号" min-width="190" />
        <el-table-column prop="customer_name" label="客户" min-width="150" />
        <el-table-column prop="product_summary" label="产品" min-width="180" />
        <el-table-column prop="total_amount" label="金额" width="120">
          <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" v-permission="'delivery:create'" @click="openCreate(row)">
              生成送货单
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>送货单</span>
          <el-select v-model="statusFilter" placeholder="状态" clearable>
            <el-option label="草稿" value="draft" />
            <el-option label="已发货" value="shipped" />
            <el-option label="已签收" value="signed" />
          </el-select>
        </div>
      </template>
      <el-table :data="deliveryOrders" stripe>
        <el-table-column prop="delivery_no" label="送货单号" min-width="190" />
        <el-table-column prop="address" label="地址" min-width="220" />
        <el-table-column prop="driver_name" label="司机/物流" min-width="130" />
        <el-table-column prop="delivery_time" label="送货时间" min-width="180" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'signed' ? 'success' : row.status === 'shipped' ? 'warning' : 'info'">
              {{ deliveryStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :disabled="row.status !== 'draft'" v-permission="'delivery:create'" @click="ship(row)">
              发货
            </el-button>
            <el-button
              size="small"
              type="success"
              :disabled="row.status === 'signed'"
              v-permission="'delivery:create'"
              @click="openSign(row)"
            >
              签收
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="生成送货单" width="520px">
      <el-form :model="createForm" label-position="top">
        <el-form-item label="送货地址">
          <el-input v-model="createForm.address" type="textarea" />
        </el-form-item>
        <el-form-item label="司机/物流">
          <el-input v-model="createForm.driver_name" />
        </el-form-item>
        <el-form-item label="物流单号">
          <el-input v-model="createForm.logistics_no" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createDelivery">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="signVisible" title="签收确认" width="420px">
      <el-form :model="signForm" label-position="top">
        <el-form-item label="签收人">
          <el-input v-model="signForm.signed_by" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="signVisible = false">取消</el-button>
        <el-button type="primary" :loading="signing" @click="sign">确认签收</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { DeliverableOrder, DeliveryOrder, PageResponse } from '../api/types'
import { formatCurrency } from '../utils/format'

const deliverableOrders = ref<DeliverableOrder[]>([])
const deliveryOrders = ref<DeliveryOrder[]>([])
const statusFilter = ref('')
const createVisible = ref(false)
const signVisible = ref(false)
const creating = ref(false)
const signing = ref(false)
const currentDeliverable = ref<DeliverableOrder | null>(null)
const currentDelivery = ref<DeliveryOrder | null>(null)

const createForm = reactive({
  address: '',
  driver_name: '',
  logistics_no: '',
  remark: ''
})

const signForm = reactive({
  signed_by: ''
})

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function deliveryStatusLabel(status: string) {
  const map: Record<string, string> = { draft: '草稿', shipped: '已发货', signed: '已签收', cancelled: '已取消' }
  return map[status] || status
}

async function loadDeliverable() {
  const { data } = await apiClient.get<DeliverableOrder[]>('/delivery-orders/deliverable')
  deliverableOrders.value = data
}

async function loadDeliveryOrders() {
  const { data } = await apiClient.get<PageResponse<DeliveryOrder>>('/delivery-orders', {
    params: { status_filter: statusFilter.value || undefined }
  })
  deliveryOrders.value = data.items
}

async function loadAll() {
  await Promise.all([loadDeliverable(), loadDeliveryOrders()])
}

function openCreate(order: DeliverableOrder) {
  currentDeliverable.value = order
  Object.assign(createForm, {
    address: order.address || '',
    driver_name: '',
    logistics_no: '',
    remark: ''
  })
  createVisible.value = true
}

async function createDelivery() {
  if (!currentDeliverable.value) return
  creating.value = true
  try {
    await apiClient.post('/delivery-orders', {
      sales_order_id: currentDeliverable.value.sales_order_id,
      address: createForm.address,
      driver_name: createForm.driver_name,
      logistics_no: createForm.logistics_no,
      remark: createForm.remark
    })
    ElMessage.success('送货单已创建')
    createVisible.value = false
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    creating.value = false
  }
}

async function ship(delivery: DeliveryOrder) {
  try {
    await apiClient.post(`/delivery-orders/${delivery.id}/ship`, {
      logistics_no: delivery.logistics_no,
      driver_name: delivery.driver_name
    })
    ElMessage.success('送货单已发货')
    await loadDeliveryOrders()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function openSign(delivery: DeliveryOrder) {
  currentDelivery.value = delivery
  signForm.signed_by = ''
  signVisible.value = true
}

async function sign() {
  if (!currentDelivery.value) return
  if (!signForm.signed_by) {
    ElMessage.warning('请填写签收人')
    return
  }
  signing.value = true
  try {
    await apiClient.post(`/delivery-orders/${currentDelivery.value.id}/sign`, signForm)
    ElMessage.success('签收完成，可进入财务应收')
    signVisible.value = false
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    signing.value = false
  }
}

watch(statusFilter, loadDeliveryOrders)
onMounted(loadAll)
</script>
