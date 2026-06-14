<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="customerFilter" filterable clearable placeholder="客户筛选">
          <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
        </el-select>
        <el-input v-model="productFilter" placeholder="客户 / 品名 / 单号 / 版号" clearable :prefix-icon="Search" />
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
      <div class="toolbar-left">
        <el-button type="primary" :icon="Plus" v-permission="'inventory:receive'" @click="receiptVisible = true">入库单</el-button>
        <el-button type="warning" :icon="Minus" v-permission="'inventory:issue'" @click="issueVisible = true">领料单</el-button>
        <el-button type="success" :icon="Tickets" v-permission="'cylinder:stock_in'" @click="cylinderVisible = true">版辊入库</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="库存批次" name="lots">
        <el-card shadow="never" class="table-card">
          <el-table :data="lots" stripe>
            <el-table-column prop="lot_no" label="批次号" min-width="150" />
            <el-table-column label="归属" width="120">
              <template #default="{ row }">
                <el-tag :type="row.owner_type === 'customer' ? 'warning' : 'success'">
                  {{ row.owner_type === 'customer' ? '客户来料' : '公司材料' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="客户" min-width="180">
              <template #default="{ row }">{{ row.customer_id ? customerName(row.customer_id) : '-' }}</template>
            </el-table-column>
            <el-table-column prop="warehouse_name" label="仓库" min-width="140" />
            <el-table-column prop="product_name" label="品名" min-width="160" />
            <el-table-column prop="specification" label="规格" min-width="150" />
            <el-table-column prop="quantity_on_hand" label="库存" width="110" />
            <el-table-column prop="unit" label="单位" width="90" />
            <el-table-column prop="unit_price" label="单价" width="110">
              <template #default="{ row }">{{ formatCurrency(row.unit_price) }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="库存流水" name="transactions">
        <el-card shadow="never" class="table-card">
          <el-table :data="transactions" stripe>
            <el-table-column prop="movement_no" label="流水号" min-width="150" />
            <el-table-column prop="movement_type" label="类型" width="120" />
            <el-table-column prop="movement_date" label="日期" width="120" />
            <el-table-column prop="product_name" label="品名" min-width="160" />
            <el-table-column prop="specification" label="规格" min-width="150" />
            <el-table-column prop="quantity" label="数量" width="110" />
            <el-table-column prop="total_amount" label="金额" width="120">
              <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
            </el-table-column>
            <el-table-column label="客户" min-width="180">
              <template #default="{ row }">{{ row.customer_id ? customerName(row.customer_id) : '-' }}</template>
            </el-table-column>
            <el-table-column prop="cylinder_no" label="版号" min-width="140" />
            <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="版辊入库" name="cylinders">
        <el-card shadow="never" class="table-card">
          <el-table :data="cylinders" stripe>
            <el-table-column prop="stock_no" label="入库单号" min-width="150" />
            <el-table-column prop="cylinder_no" label="版号" min-width="150" />
            <el-table-column label="客户" min-width="180">
              <template #default="{ row }">{{ row.customer_id ? customerName(row.customer_id) : '-' }}</template>
            </el-table-column>
            <el-table-column prop="warehouse_name" label="仓库" min-width="150" />
            <el-table-column prop="diameter" label="直径" width="100" />
            <el-table-column prop="cylinder_length" label="版长" width="100" />
            <el-table-column prop="quantity" label="支数" width="90" />
            <el-table-column prop="total_amount" label="金额" width="120">
              <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
            </el-table-column>
            <el-table-column prop="stock_in_date" label="入库日期" width="130" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="receiptVisible" title="入库单 Bill of entry" width="860px">
      <el-form :model="receiptForm" label-position="top">
        <div class="form-grid">
          <el-form-item label="仓库">
            <el-input v-model="receiptForm.warehouse_name" />
          </el-form-item>
          <el-form-item label="供应商">
            <el-input v-model="receiptForm.supplier_name" />
          </el-form-item>
          <el-form-item label="入库日期">
            <el-date-picker v-model="receiptForm.movement_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="经手人">
            <el-input v-model="receiptForm.handler_name" />
          </el-form-item>
        </div>
        <div class="table-tools">
          <span>客户来料需要选择客户，后续下单时会优先提示</span>
          <el-button :icon="Plus" @click="addReceiptItem">新增明细</el-button>
        </div>
        <el-table :data="receiptForm.items">
          <el-table-column label="归属" width="130">
            <template #default="{ row }">
              <el-select v-model="row.owner_type">
                <el-option label="公司材料" value="company" />
                <el-option label="客户来料" value="customer" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="客户" min-width="160">
            <template #default="{ row }">
              <el-select v-model="row.customer_id" filterable clearable :disabled="row.owner_type !== 'customer'">
                <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="品名" min-width="150">
            <template #default="{ row }"><el-input v-model="row.product_name" /></template>
          </el-table-column>
          <el-table-column label="规格" min-width="130">
            <template #default="{ row }"><el-input v-model="row.specification" /></template>
          </el-table-column>
          <el-table-column label="单位" width="100">
            <template #default="{ row }"><el-input v-model="row.unit" /></template>
          </el-table-column>
          <el-table-column label="数量" width="150">
            <template #default="{ row }"><el-input-number v-model="row.quantity" :min="0" :precision="3" /></template>
          </el-table-column>
          <el-table-column label="单价" width="150">
            <template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" /></template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ $index }"><el-button text type="danger" @click="removeReceiptItem($index)">删除</el-button></template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="receiptVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingReceipt" @click="saveReceipt">审核入库</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="issueVisible" title="领料单 Material requisition" width="760px">
      <el-form :model="issueForm" label-position="top">
        <div class="form-grid">
          <el-form-item label="出库日期">
            <el-date-picker v-model="issueForm.movement_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="领料部门">
            <el-input v-model="issueForm.department" />
          </el-form-item>
          <el-form-item label="领料人">
            <el-input v-model="issueForm.receiver_name" />
          </el-form-item>
          <el-form-item label="关联版号">
            <el-input v-model="issueForm.cylinder_no" />
          </el-form-item>
        </div>
        <el-form-item label="库存批次">
          <el-select v-model="issueForm.lot_id" filterable placeholder="选择要领用的库存">
            <el-option
              v-for="lot in availableLots"
              :key="lot.id"
              :label="`${lot.lot_no} · ${lot.product_name} · ${lot.quantity_on_hand}${lot.unit}`"
              :value="lot.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="issueForm.quantity" :min="0" :precision="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="issueVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingIssue" @click="saveIssue">审核出库</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="cylinderVisible" title="版辊入库单" width="720px">
      <el-form :model="cylinderForm" label-position="top">
        <div class="form-grid">
          <el-form-item label="版号">
            <el-input v-model="cylinderForm.cylinder_no" />
          </el-form-item>
          <el-form-item label="客户">
            <el-select v-model="cylinderForm.customer_id" filterable clearable>
              <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="仓库">
            <el-input v-model="cylinderForm.warehouse_name" />
          </el-form-item>
          <el-form-item label="入库日期">
            <el-date-picker v-model="cylinderForm.stock_in_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="直径">
            <el-input-number v-model="cylinderForm.diameter" :min="0" :precision="3" />
          </el-form-item>
          <el-form-item label="版长">
            <el-input-number v-model="cylinderForm.cylinder_length" :min="0" :precision="3" />
          </el-form-item>
          <el-form-item label="支数">
            <el-input-number v-model="cylinderForm.quantity" :min="1" :precision="3" />
          </el-form-item>
          <el-form-item label="单价">
            <el-input-number v-model="cylinderForm.unit_price" :min="0" :precision="2" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="cylinderVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingCylinder" @click="saveCylinder">入库</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Minus, Plus, Refresh, Search, Tickets } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { Customer, CylinderStock, InventoryLot, InventoryTransaction, PageResponse } from '../api/types'
import { formatCurrency } from '../utils/format'

const activeTab = ref('lots')
const customers = ref<Customer[]>([])
const lots = ref<InventoryLot[]>([])
const transactions = ref<InventoryTransaction[]>([])
const cylinders = ref<CylinderStock[]>([])
const customerFilter = ref('')
const productFilter = ref('')
const receiptVisible = ref(false)
const issueVisible = ref(false)
const cylinderVisible = ref(false)
const savingReceipt = ref(false)
const savingIssue = ref(false)
const savingCylinder = ref(false)

const receiptForm = reactive({
  warehouse_name: 'Main',
  supplier_name: '',
  movement_date: new Date().toISOString().slice(0, 10),
  handler_name: '',
  items: [{ owner_type: 'company', customer_id: '', product_name: '', specification: '', unit: 'pcs', quantity: 1, unit_price: 0 }]
})

const issueForm = reactive({
  movement_date: new Date().toISOString().slice(0, 10),
  department: '',
  receiver_name: '',
  cylinder_no: '',
  lot_id: '',
  quantity: 1
})

const cylinderForm = reactive({
  cylinder_no: '',
  customer_id: '',
  warehouse_name: 'Cylinder Warehouse',
  stock_in_date: new Date().toISOString().slice(0, 10),
  diameter: 0,
  cylinder_length: 0,
  quantity: 1,
  unit_price: 0
})

const availableLots = computed(() => lots.value.filter((lot) => Number(lot.quantity_on_hand) > 0))

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function customerName(customerId: string) {
  return customers.value.find((customer) => customer.id === customerId)?.name || customerId
}

async function loadCustomers() {
  const items: Customer[] = []
  let page = 1
  let total = 0
  do {
    const { data } = await apiClient.get<PageResponse<Customer>>('/customers', { params: { page, page_size: 100 } })
    items.push(...data.items)
    total = data.total
    page += 1
  } while (items.length < total)
  customers.value = items
}

async function loadLots() {
  const { data } = await apiClient.get<PageResponse<InventoryLot>>('/inventory/lots', {
    params: {
      customer_id: customerFilter.value || undefined,
      keyword: productFilter.value || undefined,
      page_size: 80
    }
  })
  lots.value = data.items
}

async function loadTransactions() {
  const { data } = await apiClient.get<PageResponse<InventoryTransaction>>('/inventory/transactions', {
    params: {
      customer_id: customerFilter.value || undefined,
      keyword: productFilter.value || undefined,
      page_size: 80
    }
  })
  transactions.value = data.items
}

async function loadCylinders() {
  const { data } = await apiClient.get<PageResponse<CylinderStock>>('/inventory/cylinder-stocks', {
    params: {
      customer_id: customerFilter.value || undefined,
      keyword: productFilter.value || undefined,
      page_size: 80
    }
  })
  cylinders.value = data.items
}

async function loadAll() {
  await Promise.all([loadLots(), loadTransactions(), loadCylinders()])
}

function addReceiptItem() {
  receiptForm.items.push({ owner_type: 'company', customer_id: '', product_name: '', specification: '', unit: 'pcs', quantity: 1, unit_price: 0 })
}

function removeReceiptItem(index: number) {
  receiptForm.items.splice(index, 1)
}

async function saveReceipt() {
  const items = receiptForm.items.filter((item) => item.product_name && item.quantity > 0)
  if (!items.length) {
    ElMessage.warning('请填写入库明细')
    return
  }
  savingReceipt.value = true
  try {
    await apiClient.post('/inventory/receipts', {
      ...receiptForm,
      supplier_name: receiptForm.supplier_name || null,
      items: items.map((item) => ({
        ...item,
        customer_id: item.owner_type === 'customer' ? item.customer_id || null : null
      }))
    })
    ElMessage.success('入库已审核')
    receiptVisible.value = false
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingReceipt.value = false
  }
}

async function saveIssue() {
  if (!issueForm.lot_id || issueForm.quantity <= 0) {
    ElMessage.warning('请选择库存并填写数量')
    return
  }
  savingIssue.value = true
  try {
    await apiClient.post('/inventory/issues', {
      movement_date: issueForm.movement_date,
      department: issueForm.department || null,
      receiver_name: issueForm.receiver_name || null,
      cylinder_no: issueForm.cylinder_no || null,
      items: [{ lot_id: issueForm.lot_id, quantity: issueForm.quantity }]
    })
    ElMessage.success('领料已出库')
    issueVisible.value = false
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingIssue.value = false
  }
}

async function saveCylinder() {
  if (!cylinderForm.cylinder_no) {
    ElMessage.warning('请填写版号')
    return
  }
  savingCylinder.value = true
  try {
    await apiClient.post('/inventory/cylinder-stock-ins', {
      ...cylinderForm,
      customer_id: cylinderForm.customer_id || null
    })
    ElMessage.success('版辊已入库')
    cylinderVisible.value = false
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingCylinder.value = false
  }
}

watch([customerFilter, productFilter], loadAll)
onMounted(async () => {
  await loadCustomers()
  await loadAll()
})
</script>

<style scoped>
.table-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
</style>
