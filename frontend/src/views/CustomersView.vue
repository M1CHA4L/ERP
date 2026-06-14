<template>
  <section class="page-stack">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索客户名称或编号" clearable :prefix-icon="Search" />
      <div class="toolbar-left">
        <el-button type="success" :icon="Download" v-permission="'report:export'" @click="exportCustomers">
          导出 Excel
        </el-button>
        <el-button type="primary" :icon="Plus" v-permission="'customer:create'" @click="openCreateDrawer">
          新增客户
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <div class="table-summary">
        <strong>共 {{ totalCustomers }} 个客户</strong>
        <span>当前第 {{ page }} 页，每页 {{ pageSize }} 个</span>
      </div>
      <el-table :data="customers" v-loading="loadingCustomers" stripe @row-dblclick="openCustomerDetail">
        <el-table-column prop="customer_code" label="客户编号" min-width="150" />
        <el-table-column prop="name" label="客户名称" min-width="190" />
        <el-table-column prop="customer_type" label="客户等级" width="110" />
        <el-table-column prop="contact_name" label="联系人" width="120" />
        <el-table-column prop="phone" label="电话" min-width="140" />
        <el-table-column prop="payment_method" label="结款方式" width="120" />
        <el-table-column prop="payment_terms_days" label="账期" width="100">
          <template #default="{ row }">{{ row.payment_terms_days }} 天</template>
        </el-table-column>
        <el-table-column prop="minimum_price" label="最低价" width="110">
          <template #default="{ row }">{{ row.minimum_price ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="税务" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.vat_enabled" size="small">VAT</el-tag>
            <el-tag v-if="row.ait_enabled" size="small" type="warning">AIT</el-tag>
            <span v-if="!row.vat_enabled && !row.ait_enabled">-</span>
          </template>
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
      <div class="pagination-row">
        <span>共 {{ totalCustomers }} 个客户</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="totalCustomers"
          :page-sizes="[20, 50, 100]"
          background
          layout="sizes, prev, pager, next, jumper"
          @current-change="loadCustomers"
          @size-change="handlePageSizeChange"
        />
      </div>
    </el-card>

    <el-drawer v-model="drawerVisible" :title="editingCustomerId ? 'Edit Customer' : 'New Customer'" size="94%">
      <el-form :model="form" label-position="top" class="customer-form compact-customer-form">
        <section class="form-section">
          <div class="section-title">客户档案</div>
          <div class="field-grid">
            <el-form-item label="Customer name">
              <el-input v-model="form.name" />
            </el-form-item>
            <el-form-item label="客户编号">
              <el-input v-model="form.customer_code" placeholder="留空自动生成" />
            </el-form-item>
            <el-form-item label="旧ERP客户RID">
              <el-input v-model="form.legacy_company_id" />
            </el-form-item>
            <el-form-item label="Customer level">
              <el-input v-model="form.customer_type" />
            </el-form-item>
            <el-form-item label="Contact person">
              <el-input v-model="form.contact_name" />
            </el-form-item>
            <el-form-item label="Tel.">
              <el-input v-model="form.phone" />
            </el-form-item>
            <el-form-item label="公司电话">
              <el-input v-model="form.company_phone" />
            </el-form-item>
            <el-form-item label="传真">
              <el-input v-model="form.fax" />
            </el-form-item>
            <el-form-item label="Address" class="wide-field">
              <el-input v-model="form.address" type="textarea" :rows="1" />
            </el-form-item>
          </div>
        </section>

        <section class="form-section">
          <div class="section-title">账期与税务</div>
          <div class="field-grid">
            <el-form-item label="Payment method">
              <el-select v-model="form.payment_method" clearable filterable allow-create placeholder="选择或输入">
                <el-option label="Cash" value="Cash" />
                <el-option label="Month" value="Month" />
                <el-option label="Monthly" value="Monthly" />
                <el-option label="15days" value="15days" />
                <el-option label="45days" value="45days" />
              </el-select>
            </el-form-item>
            <el-form-item label="Account period">
              <el-input-number v-model="form.payment_terms_days" :min="0" controls-position="right" />
            </el-form-item>
            <el-form-item label="Advance %">
              <el-input-number v-model="form.advance_percent" :min="0" :max="100" :precision="2" controls-position="right" />
            </el-form-item>
            <el-form-item label="Minimum price">
              <el-input-number v-model="form.minimum_price" :min="0" :precision="2" controls-position="right" />
            </el-form-item>
            <el-form-item label="VAT 15%">
              <el-switch v-model="form.vat_enabled" active-text="Y" inactive-text="N" />
            </el-form-item>
            <el-form-item label="AIT 5%">
              <el-switch v-model="form.ait_enabled" active-text="Y" inactive-text="N" />
            </el-form-item>
            <el-form-item label="Salesman">
              <el-select v-model="form.salesperson_id" clearable filterable placeholder="选择业务员">
                <el-option v-for="user in users" :key="user.id" :label="user.real_name" :value="user.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="Lister">
              <el-input v-model="form.lister" />
            </el-form-item>
          </div>
        </section>

        <section class="form-section">
          <div class="section-title">银行与生产参数</div>
          <div class="field-grid">
            <el-form-item label="税号">
              <el-input v-model="form.tax_no" />
            </el-form-item>
            <el-form-item label="开户银行">
              <el-input v-model="form.bank_name" />
            </el-form-item>
            <el-form-item label="开户账号">
              <el-input v-model="form.bank_account" />
            </el-form-item>
            <el-form-item label="交货方式">
              <el-input v-model="form.delivery_method" />
            </el-form-item>
            <el-form-item label="铜厚">
              <el-input-number v-model="form.copper_thickness" :min="0" :precision="2" controls-position="right" />
            </el-form-item>
            <el-form-item label="镀铬时间">
              <el-input-number v-model="form.chrome_time" :min="0" :precision="2" controls-position="right" />
            </el-form-item>
            <el-form-item label="退镀成本">
              <el-input-number v-model="form.stripping_cost" :min="0" :precision="2" controls-position="right" />
            </el-form-item>
            <el-form-item label="对账周期">
              <el-input v-model="form.reconciliation_cycle" />
            </el-form-item>
            <el-form-item label="对账日">
              <el-input-number v-model="form.reconciliation_day" :min="0" :max="31" controls-position="right" />
            </el-form-item>
            <el-form-item label="期初备注" class="wide-field">
              <el-input v-model="form.opening_remark" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item label="备注" class="wide-field">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </div>
        </section>

        <section class="form-section">
          <div class="section-title">价格矩阵</div>
          <el-table :data="form.price_rules" row-key="uid" class="price-table compact-price-table">
            <el-table-column label="≤ CM²" min-width="96">
              <template #default="{ row }">
                <el-input-number v-model="row.max_cm2" :min="0" :precision="2" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="> CM²" min-width="96">
              <template #default="{ row }">
                <el-input-number v-model="row.min_cm2" :min="0" :precision="2" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="> Minim L" min-width="102">
              <template #default="{ row }">
                <el-input-number v-model="row.min_l" :min="0" :precision="2" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="≤ Maxim L" min-width="120">
              <template #header>≤ Maxim L</template>
              <template #default="{ row }">
                <el-input-number v-model="row.max_l" :min="0" :precision="2" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="> Minim C" min-width="102">
              <template #default="{ row }">
                <el-input-number v-model="row.min_c" :min="0" :precision="2" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="≤ Maxim C" min-width="120">
              <template #header>≤ Maxim C</template>
              <template #default="{ row }">
                <el-input-number v-model="row.max_c" :min="0" :precision="2" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="Old /Pcs" min-width="102">
              <template #default="{ row }">
                <el-input-number v-model="row.old_pcs" :min="0" :precision="2" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="Repair chromium/pcs" min-width="136">
              <template #default="{ row }">
                <el-input-number v-model="row.repair_chromium_pcs" :min="0" :precision="2" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="Special Cyl. Price" min-width="128">
              <template #default="{ row }">
                <el-input-number v-model="row.special_cyl_price" :min="0" :precision="2" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ $index }">
                <el-button text type="danger" :disabled="form.price_rules.length === 1" @click="removePriceRule($index)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="matrix-actions">
            <el-button :icon="Plus" @click="addPriceRule">新增价格行</el-button>
          </div>
        </section>

        <div class="drawer-actions">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="createCustomer">保存</el-button>
        </div>
      </el-form>
    </el-drawer>

    <el-drawer
      v-model="detailDrawerVisible"
      :title="selectedCustomer ? `客户详情：${selectedCustomer.name}` : '客户详情'"
      size="860px"
    >
      <template v-if="selectedCustomer">
        <div class="detail-actions">
          <el-button type="primary" v-permission="'customer:update'" @click="openCustomerEdit(selectedCustomer)">
            Edit Customer
          </el-button>
        </div>
        <div class="detail-grid customer-detail-grid">
          <div><span>客户编号</span><strong>{{ selectedCustomer.customer_code }}</strong></div>
          <div><span>客户等级</span><strong>{{ selectedCustomer.customer_type || '-' }}</strong></div>
          <div><span>联系人</span><strong>{{ selectedCustomer.contact_name || '-' }}</strong></div>
          <div><span>电话</span><strong>{{ selectedCustomer.phone || '-' }}</strong></div>
          <div><span>结款方式</span><strong>{{ selectedCustomer.payment_method || '-' }}</strong></div>
          <div><span>账期</span><strong>{{ selectedCustomer.payment_terms_days }} 天</strong></div>
          <div><span>最低价</span><strong>{{ selectedCustomer.minimum_price ?? '-' }}</strong></div>
          <div><span>预付款</span><strong>{{ selectedCustomer.advance_percent ?? '-' }}%</strong></div>
          <div><span>VAT 15%</span><strong>{{ selectedCustomer.vat_enabled ? 'Y' : 'N' }}</strong></div>
          <div><span>AIT 5%</span><strong>{{ selectedCustomer.ait_enabled ? 'Y' : 'N' }}</strong></div>
          <div><span>业务员</span><strong>{{ selectedCustomer.salesperson_name || '-' }}</strong></div>
          <div><span>Lister</span><strong>{{ selectedCustomer.lister || '-' }}</strong></div>
        </div>

        <div class="customer-address">
          <span>地址</span>
          <strong>{{ selectedCustomer.address || '-' }}</strong>
        </div>

        <el-table v-if="selectedCustomer.price_rules?.length" :data="selectedCustomer.price_rules" class="price-table" size="small">
          <el-table-column prop="max_cm2" label="≤ CM²" />
          <el-table-column prop="min_cm2" label="> CM²" />
          <el-table-column prop="min_l" label="> Minim L" />
          <el-table-column prop="max_l" label="≤ Maxim L" />
          <el-table-column prop="min_c" label="> Minim C" />
          <el-table-column prop="max_c" label="≤ Maxim C" />
          <el-table-column prop="old_pcs" label="Old /Pcs" />
          <el-table-column prop="repair_chromium_pcs" label="Repair chromium/pcs" />
          <el-table-column prop="special_cyl_price" label="Special Cyl. Price" />
        </el-table>

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
import type { Customer, PageResponse, SalesOrder, UserOption } from '../api/types'
import { formatCurrency } from '../utils/format'

interface PriceRuleForm {
  uid: string
  max_cm2: number | null
  min_cm2: number | null
  min_l: number | null
  max_l: number | null
  min_c: number | null
  max_c: number | null
  old_pcs: number | null
  repair_chromium_pcs: number | null
  special_cyl_price: number | null
}

const router = useRouter()
const keyword = ref('')
const customers = ref<Customer[]>([])
const totalCustomers = ref(0)
const page = ref(1)
const pageSize = ref(100)
const loadingCustomers = ref(false)
const users = ref<UserOption[]>([])
const drawerVisible = ref(false)
const saving = ref(false)
const detailDrawerVisible = ref(false)
const selectedCustomer = ref<Customer | null>(null)
const customerOrders = ref<SalesOrder[]>([])
const loadingOrders = ref(false)
const editingCustomerId = ref('')

const form = reactive({
  customer_code: '',
  legacy_company_id: '',
  name: '',
  customer_type: '',
  contact_name: '',
  phone: '',
  company_phone: '',
  fax: '',
  address: '',
  salesperson_id: '',
  payment_terms_days: 30,
  payment_method: '',
  minimum_price: null as number | null,
  vat_enabled: false,
  ait_enabled: false,
  advance_percent: null as number | null,
  lister: '',
  tax_no: '',
  bank_name: '',
  bank_account: '',
  delivery_method: '',
  copper_thickness: null as number | null,
  chrome_time: null as number | null,
  stripping_cost: null as number | null,
  reconciliation_cycle: '',
  reconciliation_day: null as number | null,
  opening_remark: '',
  remark: '',
  price_rules: [] as PriceRuleForm[]
})

function newUid() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function blankPriceRule(): PriceRuleForm {
  return {
    uid: newUid(),
    max_cm2: null,
    min_cm2: null,
    min_l: null,
    max_l: null,
    min_c: null,
    max_c: null,
    old_pcs: null,
    repair_chromium_pcs: null,
    special_cyl_price: null
  }
}

function resetForm() {
  Object.assign(form, {
    customer_code: '',
    legacy_company_id: '',
    name: '',
    customer_type: '',
    contact_name: '',
    phone: '',
    company_phone: '',
    fax: '',
    address: '',
    salesperson_id: '',
    payment_terms_days: 30,
    payment_method: '',
    minimum_price: null,
    vat_enabled: false,
    ait_enabled: false,
    advance_percent: null,
    lister: '',
    tax_no: '',
    bank_name: '',
    bank_account: '',
    delivery_method: '',
    copper_thickness: null,
    chrome_time: null,
    stripping_cost: null,
    reconciliation_cycle: '',
    reconciliation_day: null,
    opening_remark: '',
    remark: '',
    price_rules: [blankPriceRule(), blankPriceRule(), blankPriceRule()]
  })
}

function nullableNumber(value: unknown) {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function priceRuleToForm(rule: NonNullable<Customer['price_rules']>[number]): PriceRuleForm {
  return {
    uid: newUid(),
    max_cm2: nullableNumber(rule.max_cm2),
    min_cm2: nullableNumber(rule.min_cm2),
    min_l: nullableNumber(rule.min_l),
    max_l: nullableNumber(rule.max_l),
    min_c: nullableNumber(rule.min_c),
    max_c: nullableNumber(rule.max_c),
    old_pcs: nullableNumber(rule.old_pcs),
    repair_chromium_pcs: nullableNumber(rule.repair_chromium_pcs),
    special_cyl_price: nullableNumber(rule.special_cyl_price)
  }
}

function populateCustomerForm(customer: Customer) {
  const rules = customer.price_rules?.map(priceRuleToForm) || []
  Object.assign(form, {
    customer_code: customer.customer_code || '',
    legacy_company_id: customer.legacy_company_id || '',
    name: customer.name || '',
    customer_type: customer.customer_type || '',
    contact_name: customer.contact_name || '',
    phone: customer.phone || '',
    company_phone: customer.company_phone || '',
    fax: customer.fax || '',
    address: customer.address || '',
    salesperson_id: customer.salesperson_id || '',
    payment_terms_days: nullableNumber(customer.payment_terms_days) ?? 30,
    payment_method: customer.payment_method || '',
    minimum_price: nullableNumber(customer.minimum_price),
    vat_enabled: Boolean(customer.vat_enabled),
    ait_enabled: Boolean(customer.ait_enabled),
    advance_percent: nullableNumber(customer.advance_percent),
    lister: customer.lister || '',
    tax_no: customer.tax_no || '',
    bank_name: customer.bank_name || '',
    bank_account: customer.bank_account || '',
    delivery_method: customer.delivery_method || '',
    copper_thickness: nullableNumber(customer.copper_thickness),
    chrome_time: nullableNumber(customer.chrome_time),
    stripping_cost: nullableNumber(customer.stripping_cost),
    reconciliation_cycle: customer.reconciliation_cycle || '',
    reconciliation_day: nullableNumber(customer.reconciliation_day),
    opening_remark: customer.opening_remark || '',
    remark: customer.remark || '',
    price_rules: rules.length ? rules : [blankPriceRule(), blankPriceRule(), blankPriceRule()]
  })
}

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

function cleanPriceRules() {
  return form.price_rules
    .map(({ uid: _uid, ...rule }) => rule)
    .filter((rule) => Object.values(rule).some((value) => value !== null && value !== undefined && value !== 0))
}

async function loadCustomers() {
  loadingCustomers.value = true
  try {
    const { data } = await apiClient.get<PageResponse<Customer>>('/customers', {
      params: {
        keyword: keyword.value || undefined,
        page: page.value,
        page_size: pageSize.value
      }
    })
    customers.value = data.items
    totalCustomers.value = data.total
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loadingCustomers.value = false
  }
}

async function loadUsers() {
  try {
    const { data } = await apiClient.get<UserOption[]>('/users/options', { params: { role_code: 'sales' } })
    users.value = data
  } catch {
    users.value = []
  }
}

async function loadCustomerOrders(customer: Customer) {
  loadingOrders.value = true
  try {
    const items: SalesOrder[] = []
    let pageNo = 1
    let total = 0
    do {
      const { data } = await apiClient.get<PageResponse<SalesOrder>>('/sales-orders', {
        params: { customer_id: customer.id, include_history: true, page: pageNo, page_size: 100 }
      })
      items.push(...data.items)
      total = data.total
      pageNo += 1
    } while (items.length < total)
    customerOrders.value = items
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loadingOrders.value = false
  }
}

function openCreateDrawer() {
  resetForm()
  editingCustomerId.value = ''
  drawerVisible.value = true
  loadUsers()
}

async function openCustomerDetail(customer: Customer) {
  customerOrders.value = []
  detailDrawerVisible.value = true
  try {
    const { data } = await apiClient.get<Customer>(`/customers/${customer.id}`)
    selectedCustomer.value = data
    await loadCustomerOrders(data)
  } catch (error) {
    selectedCustomer.value = customer
    await loadCustomerOrders(customer)
  }
}

function openCustomerEdit(customer: Customer) {
  selectedCustomer.value = customer
  editingCustomerId.value = customer.id
  populateCustomerForm(customer)
  drawerVisible.value = true
  loadUsers()
}

async function createCustomer() {
  if (!form.name) {
    ElMessage.warning('请填写客户名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      ...form,
      customer_code: form.customer_code || null,
      legacy_company_id: form.legacy_company_id || null,
      salesperson_id: form.salesperson_id || null,
      customer_type: form.customer_type || null,
      contact_name: form.contact_name || null,
      phone: form.phone || null,
      company_phone: form.company_phone || null,
      fax: form.fax || null,
      address: form.address || null,
      payment_method: form.payment_method || null,
      lister: form.lister || null,
      tax_no: form.tax_no || null,
      bank_name: form.bank_name || null,
      bank_account: form.bank_account || null,
      delivery_method: form.delivery_method || null,
      reconciliation_cycle: form.reconciliation_cycle || null,
      opening_remark: form.opening_remark || null,
      remark: form.remark || null,
      price_rules: cleanPriceRules()
    }
    const wasEditing = Boolean(editingCustomerId.value)
    if (editingCustomerId.value) {
      const { data } = await apiClient.put<Customer>(`/customers/${editingCustomerId.value}`, payload)
      selectedCustomer.value = data
      const index = customers.value.findIndex((item) => item.id === data.id)
      if (index >= 0) customers.value.splice(index, 1, data)
      await loadCustomerOrders(data)
      ElMessage.success('Customer updated')
    } else {
      await apiClient.post('/customers', payload)
      ElMessage.success('Customer created')
    }
    drawerVisible.value = false
    resetForm()
    editingCustomerId.value = ''
    if (!wasEditing) keyword.value = ''
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

function addPriceRule() {
  form.price_rules.push(blankPriceRule())
}

function removePriceRule(index: number) {
  form.price_rules.splice(index, 1)
}

function handlePageSizeChange() {
  page.value = 1
  loadCustomers()
}

function goOrder(orderId: string) {
  detailDrawerVisible.value = false
  router.push(`/orders/${orderId}`)
}

watch(keyword, () => {
  page.value = 1
  loadCustomers()
})
onMounted(() => {
  resetForm()
  loadCustomers()
})
</script>

<style scoped>
.customer-form {
  display: grid;
  gap: 10px;
}

.form-section {
  display: grid;
  gap: 8px;
}

.section-title {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(140px, 1fr));
  gap: 8px 10px;
  align-items: start;
}

.wide-field {
  grid-column: span 2;
}

.compact-customer-form {
  max-width: 1040px;
}

.compact-customer-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.compact-customer-form :deep(.el-form-item__label) {
  margin-bottom: 4px;
  padding-bottom: 0;
  font-size: 12px;
  line-height: 1.15;
}

.compact-customer-form :deep(.el-input__wrapper),
.compact-customer-form :deep(.el-select__wrapper),
.compact-customer-form :deep(.el-input-number .el-input__wrapper) {
  min-height: 30px;
}

.compact-customer-form :deep(.el-input-number) {
  width: 100%;
}

.compact-customer-form .form-section:first-of-type .field-grid > :nth-child(8),
.compact-customer-form .form-section:nth-of-type(3) {
  display: none;
}

.price-table :deep(.el-input-number) {
  width: 100%;
}

.compact-price-table :deep(.el-table__cell) {
  padding: 3px 0;
}

.compact-price-table :deep(.cell) {
  padding: 0 4px;
  line-height: 1.2;
}

.compact-price-table :deep(.el-input__inner) {
  font-size: 12px;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.table-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
  color: #667085;
}

.table-summary strong {
  color: #18212f;
  font-size: 15px;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 16px;
  color: #667085;
  font-size: 13px;
}

.matrix-actions,
.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}

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
  margin: 16px 0 12px;
}

@media (max-width: 1180px) {
  .field-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .field-grid {
    grid-template-columns: 1fr;
  }

  .wide-field {
    grid-column: auto;
  }
}
</style>
