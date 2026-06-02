<template>
  <section class="page-stack">
    <div class="metric-grid">
      <el-card v-for="metric in metrics" :key="metric.label" shadow="never" class="metric-card">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <small>{{ metric.hint }}</small>
      </el-card>
    </div>

    <el-card v-if="quickEntries.length" shadow="never" class="panel-card">
      <template #header>
        <div class="panel-title">
          <span>{{ t('dashboard.quickEntries') }}</span>
          <el-tag size="small">{{ t('dashboard.quickHint') }}</el-tag>
        </div>
      </template>
      <div class="quick-entry-grid">
        <button v-for="entry in quickEntries" :key="entry.path" class="quick-entry" @click="go(entry.path)">
          <el-icon>
            <component :is="entry.icon" />
          </el-icon>
          <span>{{ t(entry.labelKey) }}</span>
        </button>
      </div>
    </el-card>

    <el-card shadow="never" class="panel-card">
      <template #header>
        <div class="toolbar">
          <div class="panel-title">
            <span>{{ t('dashboard.flowTitle') }}</span>
            <el-tag size="small">{{ t('dashboard.flowHint') }}</el-tag>
          </div>
          <el-button text type="primary" @click="loadSummary">{{ t('common.refresh') }}</el-button>
        </div>
      </template>

      <div class="flow-lane">
        <button v-for="stage in visibleFlowStages" :key="stage.title" class="flow-stage" @click="go(stage.path)">
          <span>{{ stage.title }}</span>
          <strong>{{ stage.count }}</strong>
          <small>{{ stage.subtitle }}</small>
        </button>
      </div>
      <el-empty v-if="visibleFlowStages.length === 0" :description="t('common.noFlowAccess')" />
    </el-card>

    <div class="content-grid">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="panel-title">
            <span>{{ t('dashboard.queue') }}</span>
            <el-tag type="info">{{ t('dashboard.queueSteps', { count: totalSteps }) }}</el-tag>
          </div>
        </template>
        <div class="queue-row">
          <span>{{ t('dashboard.pending') }}</span>
          <el-progress :percentage="pendingPercent" color="#0f766e" />
        </div>
        <div class="queue-row">
          <span>{{ t('dashboard.processing') }}</span>
          <el-progress :percentage="processingPercent" color="#2563eb" />
        </div>
        <div class="queue-row">
          <span>{{ t('dashboard.pendingInspection') }}</span>
          <el-progress :percentage="inspectionPercent" color="#d97706" />
        </div>
        <div class="queue-row">
          <span>{{ t('dashboard.reworking') }}</span>
          <el-progress :percentage="reworkPercent" color="#dc2626" />
        </div>
      </el-card>

      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="panel-title">
            <span>{{ t('dashboard.attention') }}</span>
            <el-tag type="warning">{{ t('dashboard.attentionCount', { count: summary.overdue_orders + summary.reworking_orders }) }}</el-tag>
          </div>
        </template>
        <div class="attention-list">
          <button v-for="item in visibleAttentionItems" :key="item.label" class="attention-item" @click="go(item.path)">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </button>
          <el-empty v-if="visibleAttentionItems.length === 0" :description="t('common.noAttentionAccess')" />
        </div>
      </el-card>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '../api/client'
import { canSeePath, visibleNavItems } from '../data/navigation'
import { t } from '../stores/language'
import { session } from '../stores/session'

const router = useRouter()

const summary = ref({
  draft_orders: 0,
  confirmed_orders: 0,
  in_production_orders: 0,
  pending_inspection_orders: 0,
  inspection_passed_orders: 0,
  pending_delivery_orders: 0,
  delivered_orders: 0,
  pending_payment_orders: 0,
  paid_orders: 0,
  reworking_orders: 0,
  overdue_orders: 0,
  pending_steps: 0,
  processing_steps: 0,
  pending_inspection_steps: 0,
  reworking_steps: 0
})

const metrics = computed(() => [
  { label: t('dashboard.metric.draft'), value: summary.value.draft_orders, hint: t('dashboard.metric.draftHint') },
  { label: t('dashboard.metric.confirmed'), value: summary.value.confirmed_orders, hint: t('dashboard.metric.confirmedHint') },
  { label: t('dashboard.metric.production'), value: summary.value.in_production_orders, hint: t('dashboard.metric.productionHint') },
  { label: t('dashboard.metric.delivery'), value: summary.value.pending_delivery_orders, hint: t('dashboard.metric.deliveryHint') },
  { label: t('dashboard.metric.payment'), value: summary.value.pending_payment_orders, hint: t('dashboard.metric.paymentHint') }
])

const flowStages = computed(() => [
  {
    title: t('dashboard.stage.sales'),
    count: summary.value.draft_orders + summary.value.confirmed_orders,
    subtitle: t('dashboard.stage.salesSubtitle', { draft: summary.value.draft_orders, confirmed: summary.value.confirmed_orders }),
    path: '/orders'
  },
  {
    title: t('dashboard.stage.production'),
    count: summary.value.in_production_orders,
    subtitle: t('dashboard.stage.productionSubtitle', { steps: summary.value.pending_steps + summary.value.processing_steps }),
    path: '/production-board'
  },
  {
    title: t('dashboard.stage.qc'),
    count: summary.value.pending_inspection_orders + summary.value.reworking_orders,
    subtitle: t('dashboard.stage.qcSubtitle', { pending: summary.value.pending_inspection_steps, rework: summary.value.reworking_steps }),
    path: '/inspections'
  },
  {
    title: t('dashboard.stage.delivery'),
    count: summary.value.pending_delivery_orders + summary.value.delivered_orders,
    subtitle: t('dashboard.stage.deliverySubtitle', { pending: summary.value.pending_delivery_orders, delivered: summary.value.delivered_orders }),
    path: '/deliveries'
  },
  {
    title: t('dashboard.stage.finance'),
    count: summary.value.pending_payment_orders + summary.value.paid_orders,
    subtitle: t('dashboard.stage.financeSubtitle', { pending: summary.value.pending_payment_orders, paid: summary.value.paid_orders }),
    path: '/finance'
  }
])

const visibleFlowStages = computed(() => flowStages.value.filter((stage) => canSeePath(stage.path, session.user)))

const attentionItems = computed(() => [
  { label: t('dashboard.overdueOrders'), value: summary.value.overdue_orders, path: '/orders' },
  { label: t('dashboard.reworkOrders'), value: summary.value.reworking_orders, path: '/inspections' },
  { label: t('dashboard.reworkSteps'), value: summary.value.reworking_steps, path: '/production-board' }
])

const visibleAttentionItems = computed(() => attentionItems.value.filter((item) => canSeePath(item.path, session.user)))

const quickEntries = computed(() => visibleNavItems(session.user).filter((item) => item.path !== '/dashboard').slice(0, 6))

const totalSteps = computed(
  () =>
    summary.value.pending_steps +
      summary.value.processing_steps +
      summary.value.pending_inspection_steps +
      summary.value.reworking_steps || 1
)
const pendingPercent = computed(() => Math.round((summary.value.pending_steps / totalSteps.value) * 100))
const processingPercent = computed(() => Math.round((summary.value.processing_steps / totalSteps.value) * 100))
const inspectionPercent = computed(() => Math.round((summary.value.pending_inspection_steps / totalSteps.value) * 100))
const reworkPercent = computed(() => Math.round((summary.value.reworking_steps / totalSteps.value) * 100))

async function loadSummary() {
  const { data } = await apiClient.get('/dashboard/summary')
  summary.value = data
}

function go(path: string) {
  router.push(path)
}

onMounted(loadSummary)
</script>

<style scoped>
.flow-lane {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.quick-entry-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.quick-entry {
  min-height: 72px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #fbfdff;
  color: #18212f;
  cursor: pointer;
}

.quick-entry:hover {
  border-color: #0f766e;
  background: #f7fffd;
}

.flow-stage,
.attention-item {
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #fbfdff;
  color: #18212f;
  cursor: pointer;
  text-align: left;
}

.flow-stage {
  min-height: 112px;
  display: grid;
  align-content: center;
  gap: 8px;
  padding: 16px;
}

.flow-stage:hover,
.attention-item:hover {
  border-color: #0f766e;
  background: #f7fffd;
}

.flow-stage span,
.flow-stage small,
.attention-item span {
  color: #667085;
}

.flow-stage strong {
  font-size: 28px;
  line-height: 1;
}

.attention-list {
  display: grid;
  gap: 12px;
}

.attention-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 58px;
  padding: 12px 14px;
}

.attention-item strong {
  color: #dc2626;
  font-size: 22px;
}

@media (max-width: 960px) {
  .flow-lane,
  .quick-entry-grid {
    grid-template-columns: 1fr;
  }
}
</style>
