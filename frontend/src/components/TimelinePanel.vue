<template>
  <div class="timeline-panel">
    <div class="timeline-header">
      <div>
        <strong>{{ title }}</strong>
        <span>{{ subtitle }}</span>
      </div>
      <el-button :icon="Refresh" plain :loading="loading" @click="$emit('refresh')">刷新</el-button>
    </div>

    <el-timeline v-if="items.length" class="erp-timeline">
      <el-timeline-item
        v-for="(item, index) in items"
        :key="`${item.category}-${item.entity_id || item.title}-${item.occurred_at || 'pending'}-${index}`"
        :timestamp="formatTime(item.occurred_at)"
        :type="timelineType(item.category, item.status)"
        placement="top"
      >
        <div class="timeline-card">
          <div class="timeline-card-title">
            <span>{{ item.title }}</span>
            <el-tag size="small" effect="plain">{{ categoryLabel(item.category) }}</el-tag>
            <el-tag v-if="item.status" size="small" :type="statusType(item.status)">
              {{ displayStatus(item) }}
            </el-tag>
          </div>
          <p v-if="item.description">{{ item.description }}</p>
        </div>
      </el-timeline-item>
    </el-timeline>
    <el-empty v-else-if="!loading" description="暂无进度记录" />
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import type { TimelineItem } from '../api/types'
import { orderStatusMap, statusLabel, stepStatusMap, workOrderStatusMap } from '../utils/status'

defineProps<{
  title: string
  subtitle: string
  items: TimelineItem[]
  loading?: boolean
}>()

defineEmits<{
  refresh: []
}>()

function formatTime(value?: string) {
  if (!value) return '待发生'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function categoryLabel(category: string) {
  const labels: Record<string, string> = {
    order: '订单',
    work_order: '工单',
    step: '工序',
    record: '报工',
    inspection: '质检',
    rework: '返工',
    material: '来料',
    delivery: '送货',
    finance: '财务'
  }
  return labels[category] || category
}

function displayStatus(item: TimelineItem) {
  if (!item.status) return ''
  if (item.category === 'order') return statusLabel(orderStatusMap, item.status)
  if (item.category === 'work_order') return statusLabel(workOrderStatusMap, item.status)
  if (item.category === 'step') return statusLabel(stepStatusMap, item.status)
  const labels: Record<string, string> = {
    pass: '通过',
    fail: '不通过',
    concession: '让步通过',
    rework: '返工',
    signed: '已签收',
    payment: '已收款',
    pending: '待处理',
    pending_invoice: '待开票',
    partial_paid: '部分收款',
    closed: '已结清'
  }
  return labels[item.status] || item.status
}

function statusType(status: string) {
  if (['fail', 'inspection_failed', 'reworking', 'cancelled'].includes(status)) return 'danger'
  if (['pending', 'pending_invoice', 'draft'].includes(status)) return 'warning'
  if (['pass', 'inspection_passed', 'completed', 'closed', 'paid', 'signed', 'payment'].includes(status)) return 'success'
  return 'info'
}

function timelineType(category: string, status?: string) {
  if (status && statusType(status) !== 'info') return statusType(status)
  if (category === 'finance') return 'success'
  if (category === 'material') return 'success'
  if (category === 'inspection') return 'warning'
  if (category === 'rework') return 'danger'
  return 'primary'
}
</script>

<style scoped>
.timeline-panel {
  display: grid;
  gap: 16px;
}

.timeline-header,
.timeline-card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.timeline-header span {
  display: block;
  margin-top: 4px;
  color: #667085;
  font-size: 12px;
}

.erp-timeline {
  padding-top: 8px;
}

.timeline-card {
  padding: 12px 14px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #fbfdff;
}

.timeline-card-title {
  justify-content: flex-start;
  flex-wrap: wrap;
}

.timeline-card-title span:first-child {
  font-weight: 700;
}

.timeline-card p {
  margin: 8px 0 0;
  color: #667085;
  line-height: 1.6;
}
</style>
