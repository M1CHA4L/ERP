<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="statusFilter" placeholder="订单状态" clearable>
          <el-option label="草稿" value="draft" />
          <el-option label="已确认" value="confirmed" />
          <el-option label="生产中" value="in_production" />
          <el-option v-if="canViewHistory" label="已收款" value="paid" />
          <el-option v-if="canViewHistory" label="历史归档" value="archived" />
        </el-select>
        <el-select v-model="orderTypeFilter" placeholder="订单类型" clearable>
          <el-option v-for="type in orderTypeOptions" :key="type.value" :label="type.label" :value="type.value" />
        </el-select>
        <el-button :icon="Refresh" @click="loadOrders">刷新</el-button>
      </div>
      <div class="toolbar-left">
        <el-button type="success" :icon="Download" v-permission="'report:export'" @click="exportOrders">
          导出 Excel
        </el-button>
        <el-button type="primary" :icon="Plus" v-permission="'order:create'" @click="openCreateDrawer">新建订单</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="orders" stripe @row-dblclick="goDetail">
        <el-table-column prop="order_no" label="订单编号" min-width="190" />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">{{ orderTypeLabel(row.plate_details?.order_type) }}</template>
        </el-table-column>
        <el-table-column prop="product_summary" label="产品" min-width="180" />
        <el-table-column prop="due_date" label="交期" width="130" />
        <el-table-column prop="total_amount" label="金额" width="130">
          <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="110" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag>{{ statusLabel(orderStatusMap, row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button text type="primary" @click.stop="goEntrust(row)">委托书</el-button>
            <el-button text type="primary" @click.stop="printProductionOrder(row)">生产单</el-button>
            <el-button text type="danger" v-permission="'order:cancel'" @click.stop="deleteOrder(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" title="新建订单" size="94%">
      <el-form :model="form" label-position="top" class="order-form">
        <div class="form-grid">
          <el-form-item label="客户">
            <el-select v-model="form.customer_id" filterable placeholder="选择客户" @change="applyCustomer">
              <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="订单类型">
            <el-select v-model="form.plate_details.order_type" @change="applyOrderType">
              <el-option v-for="type in orderTypeOptions" :key="type.value" :label="type.label" :value="type.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="交期">
            <el-date-picker v-model="form.due_date" value-format="YYYY-MM-DD" type="date" placeholder="选择交期" />
          </el-form-item>
          <el-form-item label="整单默认工艺路线">
            <el-select v-model="form.route_id" clearable placeholder="可选，未选时按明细行路线">
              <el-option v-for="route in activeRoutes" :key="route.id" :label="route.name" :value="route.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="form.priority">
              <el-option label="普通" value="normal" />
              <el-option label="加急" value="urgent" />
            </el-select>
          </el-form-item>
        </div>

        <el-tabs v-model="activeCreateTab" class="order-tabs">
          <el-tab-pane label="基础信息" name="basic">
            <el-alert
              v-if="customerMaterials.length"
              type="warning"
              :closable="false"
              show-icon
              class="material-alert"
            >
              <template #title>
                客户已有来料 {{ customerMaterials.length }} 批，可优先调用：
                <span v-for="material in customerMaterials.slice(0, 4)" :key="material.id" class="material-pill">
                  {{ material.product_name }} {{ material.specification || '' }} · {{ material.quantity_on_hand }}{{ material.unit }}
                </span>
              </template>
            </el-alert>
            <div class="field-grid">
              <el-form-item label="Customer">
                <el-input v-model="form.plate_details.customer_text" />
              </el-form-item>
              <el-form-item label="Product Name">
                <el-input v-model="form.plate_details.product_name" @change="syncPlateToFirstItem" />
              </el-form-item>
              <el-form-item label="Total QTY">
                <el-input v-model="form.plate_details.total_qty" @change="syncPlateToFirstItem" />
              </el-form-item>
              <el-form-item label="Unit L">
                <el-input v-model="form.plate_details.unit_l" />
              </el-form-item>
              <el-form-item label="Original No">
                <el-input v-model="form.plate_details.original_no" />
              </el-form-item>
              <el-form-item label="B/O">
                <el-input v-model="form.plate_details.no" />
              </el-form-item>
              <el-form-item label="SampleNO">
                <el-input v-model="form.plate_details.sample_no" />
              </el-form-item>
              <el-form-item label="Order Date">
                <el-date-picker v-model="form.plate_details.order_date" value-format="YYYY-MM-DD" type="date" />
              </el-form-item>
              <el-form-item label="Printing Method">
                <el-input v-model="form.plate_details.printing_method" />
              </el-form-item>
              <el-form-item label="Printings">
                <el-input v-model="form.plate_details.printings" />
              </el-form-item>
              <el-form-item label="Sign-in Person">
                <el-input v-model="form.plate_details.sign_in_person" />
              </el-form-item>
              <el-form-item label="SalesMan">
                <el-input v-model="form.plate_details.salesman" />
              </el-form-item>
              <el-form-item label="Lister">
                <el-input v-model="form.plate_details.lister" />
              </el-form-item>
              <el-form-item label="Address" class="wide-field">
                <el-input v-model="form.plate_details.address" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="版辊参数" name="plate">
            <div class="field-grid">
              <el-form-item label="Cylinder Model">
                <el-input v-model="form.plate_details.cylinder_model" />
              </el-form-item>
              <el-form-item label="Cylinder Making">
                <el-input v-model="form.plate_details.cylinder_making" />
              </el-form-item>
              <el-form-item label="New Material">
                <el-input v-model="form.plate_details.new_material" />
              </el-form-item>
              <el-form-item label="Unit W">
                <el-input v-model="form.plate_details.unit_w" />
              </el-form-item>
              <el-form-item label="Straight">
                <el-input v-model="form.plate_details.straight" />
              </el-form-item>
              <el-form-item label="Crossway">
                <el-input v-model="form.plate_details.crossway" />
              </el-form-item>
              <el-form-item label="Cylinder ID">
                <el-input v-model="form.plate_details.cylinder_id" />
              </el-form-item>
              <el-form-item label="C">
                <el-input v-model="form.plate_details.c_value" />
              </el-form-item>
              <el-form-item label="L">
                <el-input v-model="form.plate_details.l_value" />
              </el-form-item>
              <el-form-item label="Increase">
                <el-input v-model="form.plate_details.increase" />
              </el-form-item>
              <el-form-item label="Hole">
                <el-input v-model="form.plate_details.hole" />
              </el-form-item>
              <el-form-item label="Flange">
                <el-input v-model="form.plate_details.flange" />
              </el-form-item>
              <el-form-item label="Slope">
                <el-input v-model="form.plate_details.slope" />
              </el-form-item>
              <el-form-item label="Dynamic Balance">
                <el-input v-model="form.plate_details.dynamic_balance" />
              </el-form-item>
              <el-form-item label="Copper Thickness">
                <el-input v-model="form.plate_details.copper_thickness" />
              </el-form-item>
              <el-form-item label="Key Way">
                <el-input v-model="form.plate_details.key_way" />
              </el-form-item>
              <el-form-item label="Cylinder Cost">
                <el-input v-model="form.plate_details.cylinder_cost" />
              </el-form-item>
              <el-form-item label="Material Model">
                <el-input v-model="form.plate_details.material_model" />
              </el-form-item>
              <el-form-item label="Plate Thickness">
                <el-input v-model="form.plate_details.plate_thickness" />
              </el-form-item>
              <el-form-item label="Cylinder Structure">
                <el-input v-model="form.plate_details.cylinder_structure" />
              </el-form-item>
              <el-form-item label="Bag Type">
                <el-input v-model="form.plate_details.bag_type" />
              </el-form-item>
              <el-form-item label="Set Type">
                <el-input v-model="form.plate_details.set_type" />
              </el-form-item>
              <el-form-item label="Self-bring">
                <el-input v-model="form.plate_details.self_bring" />
              </el-form-item>
              <el-form-item label="Production Time">
                <el-input v-model="form.plate_details.production_time" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="要求备注" name="requirements">
            <div class="field-grid">
              <el-form-item label="Common Remarks" class="wide-field">
                <el-input v-model="form.plate_details.common_remarks" />
              </el-form-item>
              <el-form-item label="Returns">
                <el-input v-model="form.plate_details.returns" />
              </el-form-item>
              <el-form-item label="Archives">
                <el-input v-model="form.plate_details.archives" />
              </el-form-item>
              <el-form-item label="Inspection Requirement" class="wide-field">
                <el-input v-model="form.plate_details.inspection_requirement" />
              </el-form-item>
              <el-form-item label="Mark Line">
                <el-input v-model="form.plate_details.mark_line" />
              </el-form-item>
              <el-form-item label="Test Line">
                <el-input v-model="form.plate_details.test_line" />
              </el-form-item>
              <el-form-item label="Test Spot">
                <el-input v-model="form.plate_details.test_spot" />
              </el-form-item>
              <el-form-item label="Computer Position">
                <el-input v-model="form.plate_details.computer_position" />
              </el-form-item>
              <el-form-item label="Production Position">
                <el-input v-model="form.plate_details.production_position" />
              </el-form-item>
              <el-form-item label="Engraving Requirement" class="wide-field">
                <el-input v-model="form.plate_details.engraving_requirement" />
              </el-form-item>
              <el-form-item label="Proofing Requirement" class="wide-field">
                <el-input v-model="form.plate_details.proofing_requirement" />
              </el-form-item>
              <el-form-item label="Computer Requirement" class="wide-field">
                <el-input v-model="form.plate_details.computer_requirement" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item label="Color Separation" class="wide-field">
                <el-input v-model="form.plate_details.color_separation" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item label="Engraving Note" class="wide-field">
                <el-input v-model="form.plate_details.engraving_note" type="textarea" :rows="3" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane v-if="form.plate_details.order_type === 'dechrome'" label="退镀下单" name="dechrome">
            <div class="field-grid">
              <el-form-item label="Date">
                <el-date-picker v-model="form.plate_details.order_date" value-format="YYYY-MM-DD" type="date" />
              </el-form-item>
              <el-form-item label="Plan">
                <el-input v-model="form.plate_details.dechrome_plan" />
              </el-form-item>
              <el-form-item label="DeliveryTime">
                <el-date-picker v-model="form.plate_details.delivery_time" value-format="YYYY-MM-DD" type="date" />
              </el-form-item>
              <el-form-item label="Original NO">
                <el-input v-model="form.plate_details.original_no" />
              </el-form-item>
              <el-form-item label="NO">
                <el-input v-model="form.plate_details.no" />
              </el-form-item>
              <el-form-item label="C">
                <el-input v-model="form.plate_details.c_value" />
              </el-form-item>
              <el-form-item label="L">
                <el-input v-model="form.plate_details.l_value" />
              </el-form-item>
              <el-form-item label="D">
                <el-input v-model="form.plate_details.dia" />
              </el-form-item>
              <el-form-item label="Computer Position">
                <el-input v-model="form.plate_details.computer_position" />
              </el-form-item>
              <el-form-item label="Cylinder Model">
                <el-input v-model="form.plate_details.cylinder_model" />
              </el-form-item>
              <el-form-item label="Charge">
                <el-select v-model="form.plate_details.charge">
                  <el-option label="收费" value="yes" />
                  <el-option label="不收费" value="no" />
                </el-select>
              </el-form-item>
              <el-form-item label="总支数">
                <el-input v-model="form.plate_details.total_branch" />
              </el-form-item>
              <el-form-item label="财务备注" class="wide-field">
                <el-input v-model="form.plate_details.finance_note" />
              </el-form-item>
              <el-form-item label="接稿员">
                <el-input v-model="form.plate_details.receiver_name" />
              </el-form-item>
              <el-form-item label="填表员">
                <el-input v-model="form.plate_details.form_filler" />
              </el-form-item>
              <el-form-item label="镀铬要求" class="wide-field">
                <el-input v-model="form.plate_details.chrome_requirement" />
              </el-form-item>
              <el-form-item label="打样要求" class="wide-field">
                <el-input v-model="form.plate_details.polishing_requirement" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane v-if="form.plate_details.order_type === 'rework'" label="返工表" name="rework">
            <div class="field-grid">
              <el-form-item label="返工来源版号">
                <el-input v-model="form.plate_details.rework_source_cylinder_no" />
              </el-form-item>
              <el-form-item label="返工目标工序">
                <el-input v-model="form.plate_details.rework_target_step" placeholder="电雕 / 镀铬 / 打样 / 检验" />
              </el-form-item>
              <el-form-item label="返工数量">
                <el-input v-model="form.plate_details.rework_quantity" />
              </el-form-item>
              <el-form-item label="是否收费">
                <el-select v-model="form.plate_details.rework_chargeable">
                  <el-option label="收费" value="yes" />
                  <el-option label="不收费" value="no" />
                </el-select>
              </el-form-item>
              <el-form-item label="返工原因" class="wide-field">
                <el-input v-model="form.plate_details.rework_reason" type="textarea" :rows="4" />
              </el-form-item>
              <el-form-item label="检验/处理要求" class="wide-field">
                <el-input v-model="form.plate_details.inspection_requirement" type="textarea" :rows="4" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="颜色明细" name="colors">
            <div class="table-tools">
              <span>颜色 / 数量 / 直径 / 印刷方法</span>
              <el-button type="primary" :icon="Plus" @click="addColorRow">新增颜色</el-button>
            </div>
            <el-table :data="form.color_rows" row-key="uid" class="dense-table">
              <el-table-column label="Color NO" width="110">
                <template #default="{ row }"><el-input v-model="row.color_no" /></template>
              </el-table-column>
              <el-table-column label="PrintColor" min-width="140">
                <template #default="{ row }"><el-input v-model="row.print_color" /></template>
              </el-table-column>
              <el-table-column label="QTY" width="110">
                <template #default="{ row }"><el-input v-model="row.qty" /></template>
              </el-table-column>
              <el-table-column label="Dia" width="110">
                <template #default="{ row }"><el-input v-model="row.dia" /></template>
              </el-table-column>
              <el-table-column label="Real Dia" width="120">
                <template #default="{ row }"><el-input v-model="row.real_dia" /></template>
              </el-table-column>
              <el-table-column label="Public No." min-width="130">
                <template #default="{ row }"><el-input v-model="row.public_no" /></template>
              </el-table-column>
              <el-table-column label="Printing Method" min-width="150">
                <template #default="{ row }"><el-input v-model="row.printing_method" /></template>
              </el-table-column>
              <el-table-column label="Remarks" min-width="150">
                <template #default="{ row }"><el-input v-model="row.remarks" /></template>
              </el-table-column>
              <el-table-column label="操作" width="90" fixed="right">
                <template #default="{ $index }">
                  <el-button text type="danger" :disabled="form.color_rows.length === 1" @click="removeColorRow($index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="订单明细" name="items">
            <div class="table-tools">
              <div class="panel-title">
                <span>订单明细</span>
                <el-tag>合计 {{ formatCurrency(orderTotal) }}</el-tag>
              </div>
              <el-button type="primary" :icon="Plus" @click="addItem">新增明细</el-button>
            </div>
            <el-table :data="form.items" row-key="uid" class="dense-table">
              <el-table-column label="产品模板" min-width="190">
                <template #default="{ row }">
                  <el-select
                    v-model="row.product_id"
                    clearable
                    filterable
                    placeholder="可选模板"
                    @change="applyProductTemplate(row)"
                  >
                    <el-option
                      v-for="product in products"
                      :key="product.id"
                      :label="`${product.product_code} · ${product.name}`"
                      :value="product.id"
                    />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="产品名称" min-width="170">
                <template #default="{ row }">
                  <el-input v-model="row.product_name" placeholder="可手动填写" />
                </template>
              </el-table-column>
              <el-table-column label="规格" min-width="150">
                <template #default="{ row }">
                  <el-input v-model="row.specification" placeholder="可手动填写" />
                </template>
              </el-table-column>
              <el-table-column label="单位" width="100">
                <template #default="{ row }">
                  <el-input v-model="row.unit" />
                </template>
              </el-table-column>
              <el-table-column label="数量" width="130">
                <template #default="{ row }">
                  <el-input-number v-model="row.quantity" :min="0.001" :precision="3" />
                </template>
              </el-table-column>
              <el-table-column label="单价" width="130">
                <template #default="{ row }">
                  <el-input-number v-model="row.unit_price" :min="0" :precision="2" />
                </template>
              </el-table-column>
              <el-table-column label="路线" min-width="150">
                <template #default="{ row }">
                  <el-select v-model="row.route_id" clearable placeholder="可选">
                    <el-option v-for="route in activeRoutes" :key="route.id" :label="route.name" :value="route.id" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="金额" width="110">
                <template #default="{ row }">{{ formatCurrency(itemAmount(row)) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="130" fixed="right">
                <template #default="{ row, $index }">
                  <el-button text type="primary" @click="duplicateItem(row)">复制</el-button>
                  <el-button text type="danger" :disabled="form.items.length === 1" @click="removeItem($index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>

        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" />
        </el-form-item>
        <div class="drawer-actions">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="createOrder">保存草稿</el-button>
        </div>
      </el-form>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Plus, Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { Customer, InventoryLot, PageResponse, ProcessRoute, Product, SalesOrder } from '../api/types'
import { hasPermission } from '../stores/session'
import { formatCurrency } from '../utils/format'
import { orderStatusMap, statusLabel } from '../utils/status'

interface OrderItemForm {
  uid: string
  product_id: string
  product_name: string
  specification: string
  quantity: number
  unit: string
  unit_price: number
  route_id: string
  remark: string
}

interface PlateDetailsForm {
  [key: string]: string
}

interface ColorRowForm {
  uid: string
  color_no: string
  print_color: string
  qty: string
  dia: string
  real_dia: string
  public_no: string
  printing_method: string
  remarks: string
}

const router = useRouter()
const statusFilter = ref('')
const orderTypeFilter = ref('')
const orders = ref<SalesOrder[]>([])
const customers = ref<Customer[]>([])
const routes = ref<ProcessRoute[]>([])
const products = ref<Product[]>([])
const customerMaterials = ref<InventoryLot[]>([])
const drawerVisible = ref(false)
const saving = ref(false)
const activeCreateTab = ref('basic')

const form = reactive({
  customer_id: '',
  route_id: '',
  due_date: '',
  priority: 'normal',
  remark: '',
  plate_details: {} as PlateDetailsForm,
  color_rows: [] as ColorRowForm[],
  items: [] as OrderItemForm[]
})

const orderTotal = computed(() => form.items.reduce((sum, item) => sum + itemAmount(item), 0))
const activeRoutes = computed(() => routes.value.filter((route) => route.status === 'active'))
const canViewHistory = computed(() => hasPermission('order:history:view'))
const historyStatuses = new Set(['paid', 'archived', 'cancelled'])
const orderTypeOptions = [
  { label: '新版下单', value: 'new_cylinder' },
  { label: '旧版/加做', value: 'old_cylinder' },
  { label: '退镀下单', value: 'dechrome' },
  { label: '返工表', value: 'rework' }
]

const plateKeys = [
  'order_type',
  'customer_text',
  'product_name',
  'total_qty',
  'unit_l',
  'straight',
  'cylinder_id',
  'increase',
  'hole',
  'flange',
  'cylinder_model',
  'cylinder_making',
  'new_material',
  'unit_w',
  'crossway',
  'order_date',
  'dynamic_balance',
  'slope',
  'original_no',
  'printing_method',
  'self_bring',
  'production_time',
  'cylinder_cost',
  'copper_thickness',
  'key_way',
  'returns',
  'archives',
  'inspection_requirement',
  'no',
  'sample_no',
  'printings',
  'salesman',
  'sign_in_person',
  'c_value',
  'l_value',
  'material_model',
  'plate_thickness',
  'cylinder_structure',
  'address',
  'lister',
  'bag_type',
  'material_new',
  'set_type',
  'mark_line',
  'test_line',
  'test_spot',
  'computer_position',
  'production_position',
  'common_remarks',
  'engraving_requirement',
  'proofing_requirement',
  'computer_requirement',
  'color_separation',
  'engraving_note',
  'dechrome_plan',
  'delivery_time',
  'charge',
  'total_branch',
  'finance_note',
  'receiver_name',
  'form_filler',
  'chrome_requirement',
  'polishing_requirement',
  'rework_reason',
  'rework_source_cylinder_no',
  'rework_target_step',
  'rework_quantity',
  'rework_chargeable',
  'dia'
]

function newUid() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function todayString() {
  return new Date().toISOString().slice(0, 10)
}

function blankPlateDetails(): PlateDetailsForm {
  return Object.fromEntries(plateKeys.map((key) => [key, ''])) as PlateDetailsForm
}

function blankColorRow(): ColorRowForm {
  return {
    uid: newUid(),
    color_no: '',
    print_color: '',
    qty: '',
    dia: '',
    real_dia: '',
    public_no: '',
    printing_method: '',
    remarks: ''
  }
}

function blankItem(): OrderItemForm {
  return {
    uid: newUid(),
    product_id: '',
    product_name: '',
    specification: '',
    quantity: 1,
    unit: '件',
    unit_price: 0,
    route_id: '',
    remark: ''
  }
}

function resetForm() {
  Object.assign(form, {
    customer_id: '',
    route_id: '',
    due_date: '',
    priority: 'normal',
    remark: '',
    plate_details: { ...blankPlateDetails(), order_type: 'new_cylinder', order_date: todayString() },
    color_rows: [blankColorRow()],
    items: [blankItem()]
  })
  customerMaterials.value = []
  activeCreateTab.value = 'basic'
}

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function itemAmount(item: OrderItemForm) {
  return Number(item.quantity || 0) * Number(item.unit_price || 0)
}

function orderTypeLabel(value: unknown) {
  return orderTypeOptions.find((type) => type.value === String(value || 'new_cylinder'))?.label || '新版下单'
}

function applyOrderType() {
  if (form.plate_details.order_type === 'dechrome') {
    activeCreateTab.value = 'dechrome'
    form.priority = 'urgent'
  } else if (form.plate_details.order_type === 'rework') {
    activeCreateTab.value = 'rework'
    form.priority = 'urgent'
  }
}

function isActiveRoute(routeId?: string) {
  if (!routeId) return true
  return activeRoutes.value.some((route) => route.id === routeId)
}

function cleanObject<T extends Record<string, string>>(value: T) {
  return Object.fromEntries(Object.entries(value).filter(([, fieldValue]) => String(fieldValue ?? '').trim() !== ''))
}

function cleanColorRows() {
  return form.color_rows
    .map(({ uid: _uid, ...row }) => cleanObject(row))
    .filter((row) => Object.keys(row).length > 0)
}

function parseQuantity(value: string) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1
}

async function loadOrders() {
  const { data } = await apiClient.get<PageResponse<SalesOrder>>('/sales-orders', {
    params: {
      status_filter: statusFilter.value || undefined,
      order_type: orderTypeFilter.value || undefined,
      include_history: statusFilter.value ? historyStatuses.has(statusFilter.value) : false
    }
  })
  orders.value = data.items
}

async function loadOptions() {
  const [customerResponse, routeResponse, productResponse] = await Promise.all([
    apiClient.get<PageResponse<Customer>>('/customers', { params: { page_size: 100 } }),
    apiClient.get<ProcessRoute[]>('/process-routes'),
    apiClient.get<PageResponse<Product>>('/products', { params: { page_size: 100, status_filter: 'active' } })
  ])
  customers.value = customerResponse.data.items
  routes.value = routeResponse.data
  products.value = productResponse.data.items
}

async function loadCustomerMaterials(customerId: string) {
  try {
    const { data } = await apiClient.get<PageResponse<InventoryLot>>('/inventory/customer-materials', {
      params: { customer_id: customerId, page_size: 20 }
    })
    customerMaterials.value = data.items
  } catch {
    customerMaterials.value = []
  }
}

function openCreateDrawer() {
  resetForm()
  drawerVisible.value = true
  if (!customers.value.length || !routes.value.length || !products.value.length) {
    loadOptions()
  }
}

function applyCustomer() {
  const customer = customers.value.find((item) => item.id === form.customer_id)
  if (!customer) return
  form.plate_details.customer_text = customer.name
  if (!form.plate_details.address) {
    form.plate_details.address = customer.address || ''
  }
  if (!form.plate_details.salesman) {
    form.plate_details.salesman = customer.salesperson_name || ''
  }
  loadCustomerMaterials(customer.id)
}

function syncPlateToFirstItem() {
  const firstItem = form.items[0] || blankItem()
  if (!form.items.length) {
    form.items.push(firstItem)
  }
  if (form.plate_details.product_name && !firstItem.product_name) {
    firstItem.product_name = form.plate_details.product_name
  }
  if (form.plate_details.total_qty) {
    firstItem.quantity = parseQuantity(form.plate_details.total_qty)
  }
  if (form.plate_details.unit_l && !firstItem.specification) {
    firstItem.specification = `L ${form.plate_details.unit_l}`
  }
}

function applyProductTemplate(row: OrderItemForm) {
  const product = products.value.find((item) => item.id === row.product_id)
  if (!product) return
  row.product_name = product.name
  row.specification = product.specification || ''
  row.unit = product.unit || '件'
  row.unit_price = Number(product.reference_price || 0)
  if (!form.plate_details.product_name) {
    form.plate_details.product_name = product.name
  }
  if (product.default_route_id && isActiveRoute(product.default_route_id)) {
    row.route_id = product.default_route_id
  } else if (!row.route_id) {
    row.route_id = form.route_id
  }
  if (!form.route_id && product.default_route_id && isActiveRoute(product.default_route_id)) {
    form.route_id = product.default_route_id
  }
}

function addItem() {
  form.items.push(blankItem())
}

function duplicateItem(item: OrderItemForm) {
  form.items.push({ ...item, uid: newUid() })
}

function removeItem(index: number) {
  form.items.splice(index, 1)
}

function addColorRow() {
  form.color_rows.push(blankColorRow())
}

function removeColorRow(index: number) {
  form.color_rows.splice(index, 1)
}

function buildValidItems() {
  syncPlateToFirstItem()
  const validItems = form.items.filter((item) => item.product_name && item.quantity > 0)
  if (validItems.length) return validItems
  const productName = form.plate_details.product_name?.trim()
  if (!productName) return []
  return [
    {
      ...blankItem(),
      product_name: productName,
      specification: [form.plate_details.unit_l && `L ${form.plate_details.unit_l}`, form.plate_details.unit_w && `W ${form.plate_details.unit_w}`]
        .filter(Boolean)
        .join(' / '),
      quantity: parseQuantity(form.plate_details.total_qty || ''),
      route_id: form.route_id
    }
  ]
}

async function createOrder() {
  const validItems = buildValidItems()
  if (!form.customer_id || !form.due_date || validItems.length === 0) {
    ElMessage.warning('请填写客户、交期，并至少保留一条有效产品明细')
    return
  }
  if (!isActiveRoute(form.route_id) || validItems.some((item) => !isActiveRoute(item.route_id))) {
    ElMessage.warning('订单工艺路线必须是启用状态')
    return
  }
  saving.value = true
  try {
    const { data } = await apiClient.post<SalesOrder>('/sales-orders', {
      customer_id: form.customer_id,
      due_date: form.due_date,
      route_id: form.route_id || null,
      priority: form.priority,
      remark: form.remark,
      plate_details: cleanObject(form.plate_details),
      color_rows: cleanColorRows(),
      items: validItems.map((item) => ({
        product_id: item.product_id || null,
        product_name: item.product_name,
        specification: item.specification || null,
        quantity: item.quantity,
        unit: item.unit || '件',
        unit_price: item.unit_price,
        route_id: item.route_id || form.route_id || null,
        remark: item.remark || null
      }))
    })
    ElMessage.success('订单草稿已创建')
    drawerVisible.value = false
    statusFilter.value = ''
    await loadOrders()
    router.push(`/orders/${data.id}`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function deleteOrder(order: SalesOrder) {
  try {
    await ElMessageBox.confirm(
      `确定删除订单「${order.order_no}」吗？已生成工单的订单需要先处理工单。`,
      '删除订单',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await apiClient.delete(`/sales-orders/${order.id}`)
    ElMessage.success('订单已删除')
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(errorMessage(error))
    }
  }
}

async function exportOrders() {
  try {
    const response = await apiClient.get('/sales-orders/export', {
      params: {
        status_filter: statusFilter.value || undefined,
        order_type: orderTypeFilter.value || undefined,
        include_history: statusFilter.value ? historyStatuses.has(statusFilter.value) : false
      },
      responseType: 'blob'
    })
    const url = URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `sales-orders-${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function goDetail(row: SalesOrder) {
  router.push(`/orders/${row.id}`)
}

function goEntrust(row: SalesOrder) {
  router.push(`/orders/${row.id}/entrust`)
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

function printProductionOrder(row: SalesOrder) {
  openPrintable(`/plate-orders/${row.id}/production-order`)
}

watch([statusFilter, orderTypeFilter], loadOrders)
onMounted(() => {
  resetForm()
  loadOrders()
  loadOptions()
})
</script>

<style scoped>
.order-form {
  display: grid;
  gap: 16px;
}

.order-tabs {
  --el-border-radius-base: 6px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(180px, 1fr));
  gap: 12px 14px;
  align-items: start;
}

.wide-field {
  grid-column: span 2;
}

.table-tools,
.drawer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.table-tools > span {
  color: #667085;
  font-size: 13px;
}

.dense-table :deep(.el-input__wrapper),
.dense-table :deep(.el-select__wrapper) {
  min-height: 30px;
}

.drawer-actions {
  justify-content: flex-end;
  margin-bottom: 0;
}

.material-alert {
  margin-bottom: 14px;
}

.material-pill {
  display: inline-flex;
  margin-left: 8px;
  font-weight: 700;
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

  .table-tools,
  .drawer-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
