<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button :icon="ArrowLeft" @click="router.push('/orders')">返回订单</el-button>
        <strong>{{ order?.order_no || '订单中控台' }}</strong>
        <el-tag v-if="order">{{ statusLabel(orderStatusMap, order.status) }}</el-tag>
        <el-tag v-if="order?.priority === 'urgent'" type="danger">加急</el-tag>
      </div>
      <div class="toolbar-left">
        <el-button :icon="Refresh" :loading="loading" @click="reloadAll">刷新</el-button>
        <el-button v-if="order" :icon="Printer" @click="goEntrust">查看委托书</el-button>
        <el-button v-if="order" :icon="Printer" @click="printProductionOrder">生产单</el-button>
        <el-button v-if="order && canEditEngraving" :icon="Edit" @click="openEngravingDialog">电雕录入</el-button>
        <el-button
          v-if="canConfirmOrder"
          type="primary"
          :loading="confirming"
          @click="confirmOrder"
        >
          确认订单
        </el-button>
        <el-button
          v-if="canGenerateWorkOrders"
          type="success"
          :loading="generating"
          @click="generateWorkOrders"
        >
          生成工单
        </el-button>
      </div>
    </div>

    <template v-if="order">
      <div class="command-grid">
        <el-card shadow="never" class="panel-card order-command-card">
          <template #header>
            <div class="panel-title">
              <span>订单概览</span>
              <el-tag :type="dueRiskType">{{ dueRiskLabel }}</el-tag>
            </div>
          </template>
          <div class="order-command">
            <div>
              <span class="muted-label">产品摘要</span>
              <h3>{{ order.product_summary }}</h3>
              <p>{{ customerName }} · {{ order.items.length }} 项明细</p>
            </div>
            <div class="order-metrics">
              <div>
                <span>订单金额</span>
                <strong>{{ formatCurrency(order.total_amount) }}</strong>
              </div>
              <div>
                <span>生产进度</span>
                <strong>{{ productionProgress }}%</strong>
              </div>
              <div>
                <span>已收款</span>
                <strong>{{ formatCurrency(receivedAmount) }}</strong>
              </div>
              <div>
                <span>{{ commandMetricLabel }}</span>
                <strong>{{ commandMetricValue }}</strong>
              </div>
            </div>
          </div>
        </el-card>

        <el-card shadow="never" class="panel-card next-action-card">
          <template #header>
            <div class="panel-title">
              <span>当前推进</span>
              <el-tag>{{ currentStageLabel }}</el-tag>
            </div>
          </template>
          <div class="next-action">
            <strong>{{ nextAction.title }}</strong>
            <p>{{ nextAction.description }}</p>
            <div class="next-action-buttons">
              <el-button
                v-if="canConfirmOrder"
                type="primary"
                :loading="confirming"
                @click="confirmOrder"
              >
                确认订单
              </el-button>
              <el-button
                v-if="canGenerateWorkOrders"
                type="success"
                :loading="generating"
                @click="generateWorkOrders"
              >
                生成工单
              </el-button>
              <el-button v-if="canViewWorkOrders && workOrders.length" @click="router.push('/work-orders')">查看生产</el-button>
              <el-button v-if="canViewDelivery" @click="router.push('/deliveries')">查看送货</el-button>
              <el-button v-if="canUseFinanceModule" @click="router.push('/finance')">查看应收</el-button>
            </div>
          </div>
        </el-card>
      </div>

      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="panel-title">
            <span>闭环进度</span>
            <el-tag>{{ completedStageCount }} / {{ controlStages.length }}</el-tag>
          </div>
        </template>
        <div class="stage-strip">
          <div
            v-for="stage in controlStages"
            :key="stage.key"
            class="stage-chip"
            :class="[`stage-${stage.state}`]"
          >
            <small>{{ stage.index }}</small>
            <div>
              <strong>{{ stage.label }}</strong>
              <span>{{ stage.detail }}</span>
            </div>
          </div>
        </div>
      </el-card>

      <div class="control-grid">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-title">
              <span>客户与交付</span>
            </div>
          </template>
          <div class="detail-grid control-detail-grid">
            <div><span>客户</span><strong>{{ customerName }}</strong></div>
            <div><span>联系人</span><strong>{{ customer?.contact_name || '-' }}</strong></div>
            <div><span>电话</span><strong>{{ customer?.phone || '-' }}</strong></div>
            <div><span>账期</span><strong>{{ customer ? `${customer.payment_terms_days} 天` : '-' }}</strong></div>
            <div><span>下单日期</span><strong>{{ order.order_date }}</strong></div>
            <div><span>交期</span><strong>{{ order.due_date }}</strong></div>
            <div><span>送货状态</span><strong>{{ deliverySummary }}</strong></div>
            <div><span>地址</span><strong>{{ customer?.address || '-' }}</strong></div>
          </div>
        </el-card>

        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-title">
              <span>工艺与生产</span>
              <el-tag v-if="workOrders.length" type="success">{{ workOrders.length }} 张工单</el-tag>
            </div>
          </template>
          <div class="detail-grid control-detail-grid">
            <div><span>工单数量</span><strong>{{ workOrders.length }}</strong></div>
            <div><span>工序总数</span><strong>{{ totalStepCount }}</strong></div>
            <div><span>已完成工序</span><strong>{{ finishedStepCount }}</strong></div>
            <div><span>待检工序</span><strong>{{ pendingInspectionCount }}</strong></div>
            <div><span>返工异常</span><strong>{{ reworkStepCount }}</strong></div>
            <div><span>质检记录</span><strong>{{ inspections.length }}</strong></div>
            <div><span>最新质检</span><strong>{{ latestInspectionLabel }}</strong></div>
          </div>
        </el-card>

        <el-card v-if="canViewFinance || canViewCosts" shadow="never" class="panel-card">
          <template #header>
            <div class="panel-title">
              <span>{{ canViewCosts ? '财务与成本' : '财务应收' }}</span>
            </div>
          </template>
          <div class="detail-grid control-detail-grid">
            <div v-if="canViewFinance"><span>订单金额(Tk)</span><strong>{{ formatCurrency(order.total_amount) }}</strong></div>
            <div v-if="canViewFinance"><span>应收金额(Tk)</span><strong>{{ formatCurrency(receivableAmount) }}</strong></div>
            <div v-if="canViewFinance"><span>已收款(Tk)</span><strong>{{ formatCurrency(receivedAmount) }}</strong></div>
            <div v-if="canViewFinance"><span>未收款(Tk)</span><strong>{{ formatCurrency(balanceAmount) }}</strong></div>
            <div v-if="canViewFinance"><span>财务状态</span><strong>{{ financeSummary }}</strong></div>
            <div v-if="canViewCosts"><span>总成本</span><strong>{{ formatCurrency(totalCost) }}</strong></div>
            <div v-if="canViewCosts"><span>毛利</span><strong>{{ formatCurrency(grossProfit) }}</strong></div>
            <div v-if="canViewCosts"><span>毛利率</span><strong>{{ grossMargin }}%</strong></div>
          </div>
        </el-card>
      </div>

      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="panel-title">
            <span>制版参数 / 电雕信息</span>
            <el-tag>{{ orderTypeLabel }}</el-tag>
          </div>
        </template>
        <div class="detail-grid control-detail-grid">
          <div><span>版号</span><strong>{{ plateDetails.cylinder_id || plateDetails.no || '-' }}</strong></div>
          <div><span>原版号</span><strong>{{ plateDetails.original_no || '-' }}</strong></div>
          <div><span>C</span><strong>{{ plateDetails.c_value || '-' }}</strong></div>
          <div><span>L</span><strong>{{ plateDetails.l_value || '-' }}</strong></div>
          <div><span>Dia</span><strong>{{ plateDetails.dia || '-' }}</strong></div>
          <div><span>印刷方式</span><strong>{{ plateDetails.printing_method || '-' }}</strong></div>
          <div><span>生产位置</span><strong>{{ plateDetails.production_position || '-' }}</strong></div>
          <div><span>电雕更新</span><strong>{{ engravingRecord?.updated_at || '-' }}</strong></div>
        </div>
        <el-table v-if="engravingRecord?.rows?.length" :data="engravingRecord.rows" stripe class="engraving-preview">
          <el-table-column prop="color_order" label="色序" width="80" />
          <el-table-column prop="color_no" label="颜色" min-width="120" />
          <el-table-column prop="curve" label="曲线" min-width="120" />
          <el-table-column prop="grid_line" label="网线" min-width="120" />
          <el-table-column prop="screen_angle" label="角度" min-width="120" />
          <el-table-column prop="makeup_man" label="制版人" min-width="120" />
          <el-table-column prop="remarks" label="备注" min-width="180" />
        </el-table>
      </el-card>

      <el-card shadow="never" class="table-card">
        <template #header>
          <div class="panel-title">
            <span>订单明细</span>
            <el-tag>共 {{ order.items.length }} 项</el-tag>
          </div>
        </template>
        <el-table :data="order.items" stripe>
          <el-table-column prop="product_name" label="产品名称" min-width="180" />
          <el-table-column prop="specification" label="规格" min-width="160" />
          <el-table-column prop="quantity" label="数量" width="100" />
          <el-table-column prop="unit" label="单位" width="80" />
          <el-table-column prop="unit_price" label="单价" width="120">
            <template #default="{ row }">{{ formatCurrency(row.unit_price) }}</template>
          </el-table-column>
          <el-table-column prop="amount" label="金额" width="120">
            <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="canViewWorkOrders" shadow="never" class="table-card">
        <template #header>
          <div class="panel-title">
            <span>生产工单</span>
            <el-tag>{{ workOrders.length }} 张</el-tag>
          </div>
        </template>
        <el-table :data="workOrders" empty-text="暂无工单" stripe>
          <el-table-column prop="work_order_no" label="工单编号" min-width="190" />
          <el-table-column prop="product_name" label="产品" min-width="160" />
          <el-table-column prop="quantity" label="数量" width="100" />
          <el-table-column label="工序进度" min-width="170">
            <template #default="{ row }">{{ workOrderStepProgress(row) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="130">
            <template #default="{ row }">
              <el-tag>{{ statusLabel(workOrderStatusMap, row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button text type="primary" @click="router.push(`/work-orders/${row.id}`)">查看工单</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <div class="related-grid">
        <el-card v-if="materialUses.length || isSelfBringOrder" shadow="never" class="table-card">
          <template #header>
            <div class="panel-title">
              <span>Customer Material Used</span>
              <el-tag>{{ materialUses.length }} batch</el-tag>
            </div>
          </template>
          <el-table :data="materialUses" empty-text="No customer material used" max-height="300">
            <el-table-column prop="lot_no" label="Lot" min-width="150" />
            <el-table-column prop="product_name" label="Product" min-width="150" />
            <el-table-column prop="specification" label="Spec" min-width="130" />
            <el-table-column label="Used Qty" width="120">
              <template #default="{ row }">{{ row.quantity_used }} {{ row.unit }}</template>
            </el-table-column>
            <el-table-column prop="warehouse_name" label="Warehouse" min-width="140" />
            <el-table-column prop="movement_date" label="Date" width="120" />
            <el-table-column prop="cylinder_no" label="Cylinder" min-width="130" />
            <el-table-column prop="remark" label="Remark" min-width="160" />
          </el-table>
        </el-card>

        <el-card v-if="canViewInspections" shadow="never" class="table-card">
          <template #header>
            <div class="panel-title">
              <span>质检记录</span>
              <el-tag>{{ inspections.length }} 条</el-tag>
            </div>
          </template>
          <el-table :data="inspections" empty-text="暂无质检记录" max-height="300">
            <el-table-column prop="inspection_no" label="质检编号" min-width="150" />
            <el-table-column prop="result" label="结果" width="110">
              <template #default="{ row }"><el-tag>{{ inspectionResultLabel(row.result) }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="inspected_qty" label="检验数量" width="100" />
            <el-table-column prop="inspected_at" label="检验时间" min-width="170" />
          </el-table>
        </el-card>

        <el-card v-if="canViewDelivery" shadow="never" class="table-card">
          <template #header>
            <div class="panel-title">
              <span>送货记录</span>
              <el-tag>{{ deliveries.length }} 单</el-tag>
            </div>
          </template>
          <el-table :data="deliveries" empty-text="暂无送货单" max-height="300">
            <el-table-column prop="delivery_no" label="送货单号" min-width="160" />
            <el-table-column prop="status" label="状态" width="110">
              <template #default="{ row }"><el-tag>{{ deliveryStatusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="signed_by" label="签收人" width="110" />
            <el-table-column prop="signed_at" label="签收时间" min-width="170" />
          </el-table>
        </el-card>

        <el-card v-if="canViewFinance" shadow="never" class="table-card">
          <template #header>
            <div class="panel-title">
              <span>应收账款</span>
              <el-tag>{{ receivables.length }} 笔</el-tag>
            </div>
          </template>
          <el-table :data="receivables" empty-text="暂无应收" max-height="300">
            <el-table-column prop="receivable_no" label="应收编号" min-width="160" />
            <el-table-column prop="amount" label="应收金额(Tk)" width="130">
              <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
            </el-table-column>
            <el-table-column prop="balance_amount" label="未收(Tk)" width="120">
              <template #default="{ row }">{{ formatCurrency(row.balance_amount) }}</template>
            </el-table-column>
            <el-table-column prop="finance_status" label="状态" width="120">
              <template #default="{ row }"><el-tag>{{ financeStatusLabel(row.finance_status) }}</el-tag></template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card v-if="canViewCosts" shadow="never" class="table-card">
          <template #header>
            <div class="panel-title">
              <span>成本记录</span>
              <el-tag>{{ costRecords.length }} 条</el-tag>
            </div>
          </template>
          <el-table :data="costRecords" empty-text="暂无成本记录" max-height="300">
            <el-table-column prop="cost_date" label="日期" width="130" />
            <el-table-column prop="cost_type" label="类型" width="120" />
            <el-table-column prop="amount" label="金额" width="130">
              <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="150" />
          </el-table>
        </el-card>
      </div>

      <div class="related-grid">
        <el-card shadow="never" class="panel-card">
          <FilePanel
            owner-type="sales_order"
            :owner-id="order.id"
            title="订单附件 / 图纸 / 样品图"
            default-file-type="drawing"
            :upload-permission="orderFilePermission"
            :delete-permission="orderFilePermission"
          />
        </el-card>

        <el-card shadow="never" class="panel-card">
          <TimelinePanel
            title="订单进度时间线"
            subtitle="从接单、生产、质检、送货到财务收款的完整记录"
            :items="timeline"
            :loading="timelineLoading"
            @refresh="loadTimeline"
          />
        </el-card>
      </div>
    </template>

    <el-dialog v-model="engravingVisible" title="电雕录入" width="94%">
      <el-form :model="engravingForm" label-position="top">
        <div class="form-grid">
          <el-form-item label="Cylinder NO.">
            <el-input v-model="engravingForm.cylinder_no" />
          </el-form-item>
          <el-form-item label="ProductName">
            <el-input v-model="engravingForm.product_name" />
          </el-form-item>
          <el-form-item label="Salesman">
            <el-input v-model="engravingForm.salesman" />
          </el-form-item>
          <el-form-item label="Phone">
            <el-input v-model="engravingForm.phone" />
          </el-form-item>
          <el-form-item label="Printed Material">
            <el-input v-model="engravingForm.printed_material" />
          </el-form-item>
          <el-form-item label="Printing Method">
            <el-input v-model="engravingForm.printing_method" />
          </el-form-item>
          <el-form-item label="Cylinder C">
            <el-input-number v-model="engravingForm.cylinder_circumference" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="Cylinder L">
            <el-input-number v-model="engravingForm.cylinder_length" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="Carving W">
            <el-input-number v-model="engravingForm.carving_width" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="Edge">
            <el-input-number v-model="engravingForm.edge" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="H Size">
            <el-input-number v-model="engravingForm.h_size" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="Testing Block">
            <el-input v-model="engravingForm.testing_block" />
          </el-form-item>
          <el-form-item label="Testing Position">
            <el-input v-model="engravingForm.testing_position" />
          </el-form-item>
          <el-form-item label="Keyway Position">
            <el-input v-model="engravingForm.keyway_position" />
          </el-form-item>
          <el-form-item label="Note" class="wide-field">
            <el-input v-model="engravingForm.note" type="textarea" :rows="2" />
          </el-form-item>
        </div>
        <div class="table-tools">
          <span>每个颜色一行，记录曲线、网线、深浅、通透、高光和文件保存状态</span>
          <el-button :icon="Plus" @click="addEngravingRow">新增颜色</el-button>
        </div>
        <el-table :data="engravingForm.rows" stripe class="dense-table">
          <el-table-column label="Date" width="150">
            <template #default="{ row }"><el-date-picker v-model="row.date" value-format="YYYY-MM-DD" type="date" /></template>
          </el-table-column>
          <el-table-column label="色序" width="90">
            <template #default="{ row }"><el-input-number v-model="row.color_order" :min="1" /></template>
          </el-table-column>
          <el-table-column label="Color NO." width="120">
            <template #default="{ row }"><el-input v-model="row.color_no" /></template>
          </el-table-column>
          <el-table-column label="Color Cylinder NO." width="150">
            <template #default="{ row }"><el-input v-model="row.color_cylinder_no" /></template>
          </el-table-column>
          <el-table-column label="Curve" width="120">
            <template #default="{ row }"><el-input v-model="row.curve" /></template>
          </el-table-column>
          <el-table-column label="Grid Lin" width="120">
            <template #default="{ row }"><el-input v-model="row.grid_line" /></template>
          </el-table-column>
          <el-table-column label="Angle" width="110">
            <template #default="{ row }"><el-input v-model="row.screen_angle" /></template>
          </el-table-column>
          <el-table-column label="Stitch" width="110">
            <template #default="{ row }"><el-input v-model="row.stitch" /></template>
          </el-table-column>
          <el-table-column label="File Save" width="110">
            <template #default="{ row }"><el-switch v-model="row.file_saved" /></template>
          </el-table-column>
          <el-table-column label="Shade" min-width="210">
            <template #default="{ row }">
              <div class="triple-input"><el-input v-model="row.shade_front" /><el-input v-model="row.shade_middle" /><el-input v-model="row.shade_back" /></div>
            </template>
          </el-table-column>
          <el-table-column label="Thorough" min-width="210">
            <template #default="{ row }">
              <div class="triple-input"><el-input v-model="row.thorough_front" /><el-input v-model="row.thorough_middle" /><el-input v-model="row.thorough_back" /></div>
            </template>
          </el-table-column>
          <el-table-column label="Highlight" min-width="210">
            <template #default="{ row }">
              <div class="triple-input"><el-input v-model="row.highlight_front" /><el-input v-model="row.highlight_middle" /><el-input v-model="row.highlight_back" /></div>
            </template>
          </el-table-column>
          <el-table-column label="Makeup Man" width="140">
            <template #default="{ row }"><el-input v-model="row.makeup_man" /></template>
          </el-table-column>
          <el-table-column label="Remarks" width="180">
            <template #default="{ row }"><el-input v-model="row.remarks" /></template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ $index }"><el-button text type="danger" @click="removeEngravingRow($index)">删除</el-button></template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="engravingVisible = false">取消</el-button>
        <el-button type="primary" :loading="engravingSaving" @click="saveEngravingRecord">保存电雕录入</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Edit, Plus, Printer, Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import FilePanel from '../components/FilePanel.vue'
import TimelinePanel from '../components/TimelinePanel.vue'
import type {
  CostRecord,
  Customer,
  DeliveryOrder,
  EngravingColorRow,
  EngravingRecord,
  InspectionRecord,
  PageResponse,
  Receivable,
  SalesOrder,
  TimelineItem,
  WorkOrder,
} from '../api/types'
import { hasPermission } from '../stores/session'
import { canUse, roleGroups } from '../utils/access'
import { formatCurrency } from '../utils/format'
import { orderStatusMap, statusLabel, stepStatusMap, workOrderStatusMap } from '../utils/status'

const route = useRoute()
const router = useRouter()
const order = ref<SalesOrder | null>(null)
const customer = ref<Customer | null>(null)
const confirming = ref(false)
const generating = ref(false)
const loading = ref(false)
const workOrders = ref<WorkOrder[]>([])
const deliveries = ref<DeliveryOrder[]>([])
const receivables = ref<Receivable[]>([])
const costRecords = ref<CostRecord[]>([])
const inspections = ref<InspectionRecord[]>([])
const materialUses = ref<SalesOrderMaterialUse[]>([])
const timeline = ref<TimelineItem[]>([])
const timelineLoading = ref(false)
const engravingVisible = ref(false)
const engravingSaving = ref(false)

interface EngravingRowForm extends EngravingColorRow {
  uid: string
}

interface SalesOrderMaterialUse {
  movement_no: string
  lot_id?: string
  lot_no?: string
  product_name: string
  specification?: string
  quantity_used: number
  unit: string
  warehouse_name: string
  movement_date: string
  cylinder_no?: string
  remark?: string
  status: string
}

const engravingForm = ref<EngravingRecord & { rows: EngravingRowForm[] }>({
  rows: []
})

const finishedStepStatuses = new Set(['completed', 'inspection_passed', 'skipped'])
const canConfirmOrder = computed(() => Boolean(order.value && order.value.status === 'draft' && canUse('order:confirm', roleGroups.orderOperators)))
const canGenerateWorkOrders = computed(() =>
  Boolean(order.value && order.value.status === 'confirmed' && canUse('work_order:create', roleGroups.productionOperators))
)
const canManageOrderFiles = computed(() => canUse('order:update', roleGroups.orderOperators))
const canViewWorkOrders = computed(() => hasPermission('work_order:view'))
const canViewDelivery = computed(() => hasPermission('delivery:view'))
const canViewFinance = computed(() => hasPermission('finance:receivable:view'))
const canUseFinanceModule = computed(() => canUse('finance:receivable:view', roleGroups.financeOperators))
const canViewCosts = computed(() => hasPermission('cost:view'))
const canViewInspections = computed(() => hasPermission('inspection:view'))
const canEditEngraving = computed(() => hasPermission('step:report'))
const orderFilePermission = computed(() => (canManageOrderFiles.value ? 'order:update' : '__order_file_readonly__'))
const plateDetails = computed(() => order.value?.plate_details || {})
const isSelfBringOrder = computed(() => {
  const materialMode = String(plateDetails.value.new_material || plateDetails.value.material || plateDetails.value.material_new || '')
  return materialMode === 'self-bring'
})
const engravingRecord = computed(() => plateDetails.value.engraving_record as EngravingRecord | undefined)
const orderTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    new_cylinder: 'New Cylinder',
    old_cylinder: 'Revision / Remake',
    dechrome: 'Dechrome (Chargeable / Free)',
    rework: 'Rework (Chargeable / Free)'
  }
  return labels[String(plateDetails.value.order_type || 'new_cylinder')] || 'New Cylinder'
})
const commandMetricLabel = computed(() => {
  if (canViewCosts.value) return '毛利'
  if (canViewFinance.value) return '未收款'
  return '交期'
})
const commandMetricValue = computed(() => {
  if (canViewCosts.value) return formatCurrency(grossProfit.value)
  if (canViewFinance.value) return formatCurrency(balanceAmount.value)
  return order.value?.due_date || '-'
})

const customerName = computed(() => customer.value?.name || (order.value ? `客户 ${order.value.customer_id}` : '-'))
const totalStepCount = computed(() => workOrders.value.reduce((sum, item) => sum + item.steps.length, 0))
const finishedStepCount = computed(() =>
  workOrders.value.reduce((sum, item) => sum + item.steps.filter((step) => finishedStepStatuses.has(step.status)).length, 0)
)
const pendingInspectionCount = computed(() =>
  workOrders.value.reduce((sum, item) => sum + item.steps.filter((step) => step.status === 'pending_inspection').length, 0)
)
const reworkStepCount = computed(() =>
  workOrders.value.reduce(
    (sum, item) => sum + item.steps.filter((step) => ['inspection_failed', 'reworking'].includes(step.status)).length,
    0
  )
)
const productionProgress = computed(() => (totalStepCount.value ? Math.round((finishedStepCount.value / totalStepCount.value) * 100) : 0))
const receivableAmount = computed(() => receivables.value.reduce((sum, item) => sum + Number(item.amount || 0), 0))
const receivedAmount = computed(() => receivables.value.reduce((sum, item) => sum + Number(item.received_amount || 0), 0))
const balanceAmount = computed(() => receivables.value.reduce((sum, item) => sum + Number(item.balance_amount || 0), 0))
const totalCost = computed(() => costRecords.value.reduce((sum, item) => sum + Number(item.amount || 0), 0))
const grossProfit = computed(() => Number(order.value?.total_amount || 0) - totalCost.value)
const grossMargin = computed(() => {
  const revenue = Number(order.value?.total_amount || 0)
  return revenue ? ((grossProfit.value / revenue) * 100).toFixed(2) : '0.00'
})
const latestInspectionLabel = computed(() => {
  const latest = inspections.value[0]
  return latest ? inspectionResultLabel(latest.result) : '暂无'
})
const deliverySummary = computed(() => {
  const latest = deliveries.value[0]
  return latest ? `${latest.delivery_no} · ${deliveryStatusLabel(latest.status)}` : '暂无送货单'
})
const financeSummary = computed(() => {
  const latest = receivables.value[0]
  return latest ? financeStatusLabel(latest.finance_status) : '未生成应收'
})
const dueRiskLabel = computed(() => {
  if (!order.value) return '-'
  const due = new Date(order.value.due_date)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diffDays = Math.ceil((due.getTime() - today.getTime()) / 86400000)
  if (['paid', 'archived', 'cancelled'].includes(order.value.status)) return '已结束'
  if (diffDays < 0) return `逾期 ${Math.abs(diffDays)} 天`
  if (diffDays <= 3) return `${diffDays} 天内到期`
  return '交期正常'
})
const dueRiskType = computed(() => {
  if (dueRiskLabel.value.includes('逾期')) return 'danger'
  if (dueRiskLabel.value.includes('到期')) return 'warning'
  return 'success'
})
const currentStageLabel = computed(() => controlStages.value.find((stage) => stage.state === 'current')?.label || '归档')
const completedStageCount = computed(() => controlStages.value.filter((stage) => stage.state === 'done').length)
const controlStages = computed(() => {
  const status = order.value?.status || 'draft'
  const workOrderDone = workOrders.value.length > 0
  const productionDone = workOrders.value.length > 0 && workOrders.value.every((item) => item.status === 'completed')
  const qcDone = ['inspection_passed', 'pending_delivery', 'delivered', 'pending_payment', 'paid', 'archived'].includes(status)
  const deliveryDone = deliveries.value.some((item) => item.status === 'signed') || ['delivered', 'pending_payment', 'paid', 'archived'].includes(status)
  const financeDone = receivables.value.some((item) => item.finance_status === 'closed') || ['paid', 'archived'].includes(status)
  const definitions = [
    { key: 'order', label: '接单确认', done: status !== 'draft', current: status === 'draft', detail: statusLabel(orderStatusMap, status) },
    { key: 'work', label: '生成工单', done: workOrderDone, current: status === 'confirmed', detail: `${workOrders.value.length} 张工单` },
    { key: 'production', label: '生产流转', done: productionDone, current: ['in_production', 'reworking'].includes(status), detail: `${productionProgress.value}%` },
    { key: 'qc', label: '质检通过', done: qcDone, current: status === 'pending_inspection', detail: `${inspections.value.length} 条记录` },
    { key: 'delivery', label: '送货签收', done: deliveryDone, current: ['inspection_passed', 'pending_delivery', 'delivered'].includes(status), detail: deliverySummary.value },
    { key: 'finance', label: '财务结清', done: financeDone, current: status === 'pending_payment', detail: financeSummary.value },
  ]
  return definitions.map((stage, index) => ({
    ...stage,
    index: index + 1,
    state: stage.done ? 'done' : stage.current ? 'current' : 'todo',
  }))
})
const nextAction = computed(() => {
  const status = order.value?.status
  if (status === 'draft') {
    return { title: '等待确认订单', description: '确认订单资料后即可进入生产工单生成。' }
  }
  if (status === 'confirmed') {
    return { title: '等待生成工单', description: '按订单明细生成工单，之后进入工序派工。' }
  }
  if (['in_production', 'reworking', 'pending_inspection'].includes(status || '')) {
    return { title: '生产与质检推进中', description: '关注当前卡点、待检任务和返工异常，保证工序按顺序流转。' }
  }
  if (['inspection_passed', 'pending_delivery'].includes(status || '')) {
    return { title: '等待送货', description: '检验通过后可生成送货单并完成客户签收。' }
  }
  if (status === 'delivered') {
    return { title: '等待生成应收', description: '送货签收后由财务生成应收账款。' }
  }
  if (status === 'pending_payment') {
    return { title: '等待收款', description: '跟进账期、部分收款和尾款结清。' }
  }
  return { title: '订单已进入收尾', description: '订单闭环数据已沉淀，可用于利润和客户复盘。' }
})

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function newUid() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function todayString() {
  return new Date().toISOString().slice(0, 10)
}

function goEntrust() {
  if (!order.value) return
  router.push(`/orders/${order.value.id}/entrust`)
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

function printProductionOrder() {
  if (!order.value) return
  openPrintable(`/plate-orders/${order.value.id}/production-order`)
}

function blankEngravingRow(index = engravingForm.value.rows.length + 1): EngravingRowForm {
  return {
    uid: newUid(),
    date: todayString(),
    color_order: index,
    color_no: '',
    color_cylinder_no: '',
    curve: '',
    grid_line: '',
    screen_angle: '',
    stitch: '',
    file_saved: false,
    shade_front: '',
    shade_middle: '',
    shade_back: '',
    thorough_front: '',
    thorough_middle: '',
    thorough_back: '',
    highlight_front: '',
    highlight_middle: '',
    highlight_back: '',
    makeup_man: '',
    remarks: ''
  }
}

function seedEngravingRows() {
  const colorRows = order.value?.color_rows || []
  if (!colorRows.length) return [blankEngravingRow(1)]
  return colorRows.map((row, index) => ({
    ...blankEngravingRow(index + 1),
    color_order: index + 1,
    color_no: String(row.print_color || row.color_no || ''),
    color_cylinder_no: String(row.public_no || row.cylinder_no || '')
  }))
}

async function openEngravingDialog() {
  if (!order.value) return
  try {
    const { data } = await apiClient.get<EngravingRecord>(`/sales-orders/${order.value.id}/engraving`)
    engravingForm.value = {
      cylinder_no: data.cylinder_no || String(plateDetails.value.cylinder_id || plateDetails.value.no || ''),
      product_name: data.product_name || order.value.product_summary,
      salesman: data.salesman || String(plateDetails.value.salesman || ''),
      phone: data.phone || customer.value?.phone || '',
      printed_material: data.printed_material || String(plateDetails.value.new_material || plateDetails.value.material_model || ''),
      printing_method: data.printing_method || String(plateDetails.value.printing_method || ''),
      cylinder_circumference: data.cylinder_circumference || Number(plateDetails.value.c_value || 0),
      cylinder_length: data.cylinder_length || Number(plateDetails.value.l_value || 0),
      carving_width: data.carving_width || 0,
      edge: data.edge || 0,
      h_size: data.h_size || Number(plateDetails.value.dia || 0),
      testing_block: data.testing_block || '',
      testing_position: data.testing_position || '',
      keyway_position: data.keyway_position || String(plateDetails.value.key_way || ''),
      note: data.note || String(plateDetails.value.engraving_note || ''),
      rows: data.rows?.length ? data.rows.map((row, index) => ({ uid: newUid(), ...row, color_order: row.color_order || index + 1 })) : seedEngravingRows(),
      updated_at: data.updated_at
    }
    engravingVisible.value = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function addEngravingRow() {
  engravingForm.value.rows.push(blankEngravingRow())
}

function removeEngravingRow(index: number) {
  engravingForm.value.rows.splice(index, 1)
}

async function saveEngravingRecord() {
  if (!order.value) return
  engravingSaving.value = true
  try {
    const rows = engravingForm.value.rows.map(({ uid: _uid, ...row }) => row)
    const { data } = await apiClient.put<EngravingRecord>(`/sales-orders/${order.value.id}/engraving`, {
      ...engravingForm.value,
      rows
    })
    engravingVisible.value = false
    if (order.value.plate_details) {
      order.value.plate_details.engraving_record = data
    }
    ElMessage.success('电雕录入已保存')
    await Promise.all([loadOrder(), loadTimeline()])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    engravingSaving.value = false
  }
}

async function loadOrder() {
  const { data } = await apiClient.get<SalesOrder>(`/sales-orders/${route.params.id}`)
  order.value = data
}

async function loadTimeline() {
  timelineLoading.value = true
  try {
    const { data } = await apiClient.get<TimelineItem[]>(`/sales-orders/${route.params.id}/timeline`)
    timeline.value = data
  } finally {
    timelineLoading.value = false
  }
}

async function loadCustomer() {
  if (!order.value || !hasPermission('customer:view')) return
  const { data } = await apiClient.get<Customer>(`/customers/${order.value.customer_id}`)
  customer.value = data
}

async function loadRelated() {
  if (!order.value) return
  const orderId = order.value.id
  const requests: Promise<unknown>[] = []
  if (canViewWorkOrders.value) {
    requests.push(
      apiClient
        .get<PageResponse<WorkOrder>>('/work-orders', { params: { sales_order_id: orderId, page_size: 100 } })
        .then(({ data }) => {
          workOrders.value = data.items
        })
    )
  }
  if (canViewDelivery.value) {
    requests.push(
      apiClient
        .get<PageResponse<DeliveryOrder>>('/delivery-orders', { params: { sales_order_id: orderId, page_size: 100 } })
        .then(({ data }) => {
          deliveries.value = data.items
        })
    )
  }
  if (canViewFinance.value) {
    requests.push(
      apiClient
        .get<PageResponse<Receivable>>('/finance/receivables', { params: { sales_order_id: orderId, page_size: 100 } })
        .then(({ data }) => {
          receivables.value = data.items
        })
    )
  }
  if (canViewCosts.value) {
    requests.push(
      apiClient
        .get<PageResponse<CostRecord>>('/cost-records', { params: { sales_order_id: orderId, page_size: 100 } })
        .then(({ data }) => {
          costRecords.value = data.items
        })
    )
  }
  if (canViewInspections.value) {
    requests.push(
      apiClient
        .get<PageResponse<InspectionRecord>>('/inspections', { params: { sales_order_id: orderId, page_size: 100 } })
        .then(({ data }) => {
          inspections.value = data.items
        })
    )
  }
  requests.push(
    apiClient.get<SalesOrderMaterialUse[]>(`/sales-orders/${orderId}/material-uses`).then(({ data }) => {
      materialUses.value = data
    })
  )
  await Promise.allSettled(requests)
}

async function reloadAll() {
  loading.value = true
  try {
    customer.value = null
    workOrders.value = []
    deliveries.value = []
    receivables.value = []
    costRecords.value = []
    inspections.value = []
    materialUses.value = []
    await Promise.all([loadOrder(), loadTimeline()])
    await Promise.all([loadCustomer(), loadRelated()])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function confirmOrder() {
  if (!order.value) return
  confirming.value = true
  try {
    const { data } = await apiClient.post<SalesOrder>(`/sales-orders/${order.value.id}/confirm`, {
      route_id: null
    })
    order.value = data
    ElMessage.success('订单已确认，可以生成工单')
    await Promise.all([loadTimeline(), loadRelated()])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    confirming.value = false
  }
}

async function generateWorkOrders() {
  if (!order.value) return
  generating.value = true
  try {
    const { data } = await apiClient.post<WorkOrder[]>(`/sales-orders/${order.value.id}/work-orders`, {
      route_id: null
    })
    workOrders.value = data
    await Promise.all([loadOrder(), loadTimeline(), loadRelated()])
    ElMessage.success('生产工单已生成')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    generating.value = false
  }
}

function workOrderStepProgress(row: WorkOrder) {
  const done = row.steps.filter((step) => finishedStepStatuses.has(step.status)).length
  return `${done} / ${row.steps.length}`
}

function inspectionResultLabel(result: string) {
  const map: Record<string, string> = {
    passed: '通过',
    failed: '不通过',
    concession: '让步通过',
    rework: '返工',
  }
  return map[result] || result
}

function deliveryStatusLabel(status: string) {
  const map: Record<string, string> = { draft: '草稿', shipped: '已发货', signed: '已签收', cancelled: '已取消' }
  return map[status] || status
}

function financeStatusLabel(status: string) {
  const map: Record<string, string> = {
    pending_invoice: '待开票',
    invoiced: '已开票',
    partial_paid: '部分收款',
    paid: '已收款',
    closed: '已结清',
    overdue: '逾期',
  }
  return map[status] || status
}

onMounted(reloadAll)
</script>

<style scoped>
.command-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.55fr);
  gap: 18px;
}

.order-command {
  display: grid;
  gap: 18px;
}

.muted-label {
  color: #667085;
  font-size: 13px;
}

.order-command h3 {
  margin: 8px 0 6px;
  color: #0f172a;
  font-size: 24px;
  line-height: 1.25;
}

.order-command p,
.next-action p {
  margin: 0;
  color: #667085;
  line-height: 1.65;
}

.order-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.order-metrics > div {
  min-height: 82px;
  display: grid;
  align-content: center;
  gap: 8px;
  padding: 13px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #f8fafc;
}

.order-metrics span {
  color: #667085;
  font-size: 12px;
}

.order-metrics strong {
  color: #0f172a;
  font-size: 20px;
  overflow-wrap: anywhere;
}

.next-action {
  display: grid;
  gap: 12px;
}

.next-action strong {
  color: #0f172a;
  font-size: 18px;
}

.next-action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.stage-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.stage-chip {
  min-height: 92px;
  display: grid;
  grid-template-columns: 30px 1fr;
  gap: 10px;
  align-items: start;
  padding: 12px;
  border: 1px solid #dbe4ee;
  border-radius: 8px;
  background: #ffffff;
}

.stage-chip small {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  color: #ffffff;
  background: #94a3b8;
  font-size: 12px;
}

.stage-chip strong,
.stage-chip span {
  display: block;
}

.stage-chip strong {
  color: #0f172a;
  font-size: 14px;
}

.stage-chip span {
  margin-top: 7px;
  color: #667085;
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.stage-done {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.stage-done small {
  background: #16a34a;
}

.stage-current {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.stage-current small {
  background: #2563eb;
}

.control-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.control-detail-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.related-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.table-tools {
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

.triple-input {
  display: grid;
  grid-template-columns: repeat(3, minmax(62px, 1fr));
  gap: 6px;
}

.dense-table :deep(.el-input__wrapper),
.dense-table :deep(.el-select__wrapper) {
  min-height: 30px;
}

.engraving-preview {
  margin-top: 14px;
}

@media (max-width: 1180px) {
  .command-grid,
  .control-grid,
  .related-grid,
  .stage-strip {
    grid-template-columns: 1fr;
  }

  .order-metrics,
  .control-detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .order-metrics,
  .control-detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
