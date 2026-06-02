<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>生产看板</strong>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadBoard">刷新</el-button>
      </div>
    </div>

    <div class="metric-grid">
      <el-card v-for="metric in metrics" :key="metric.label" shadow="never" class="metric-card">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <small>{{ metric.note }}</small>
      </el-card>
    </div>

    <div class="content-grid">
      <el-card shadow="never" class="table-card">
        <template #header>
          <div class="panel-title">
            <span>工序队列</span>
            <el-tag type="info">{{ board?.queues.length || 0 }} 个工序</el-tag>
          </div>
        </template>
        <el-table :data="board?.queues || []" stripe>
          <el-table-column prop="step_name" label="工序" min-width="130" />
          <el-table-column prop="pending_count" label="待加工" width="90" />
          <el-table-column prop="processing_count" label="加工中" width="90" />
          <el-table-column prop="pending_inspection_count" label="待检" width="80" />
          <el-table-column prop="reworking_count" label="返工" width="80" />
          <el-table-column prop="overdue_count" label="逾期" width="80">
            <template #default="{ row }">
              <el-tag :type="row.overdue_count > 0 ? 'danger' : 'info'" size="small">{{ row.overdue_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="total_count" label="合计" width="80" />
        </el-table>
      </el-card>

      <el-card shadow="never" class="table-card">
        <template #header>
          <div class="panel-title">
            <span>当前卡点</span>
            <el-tag type="warning">{{ board?.active_tasks.length || 0 }} 条</el-tag>
          </div>
        </template>
        <el-table :data="board?.active_tasks || []" stripe @row-dblclick="goWorkOrder">
          <el-table-column prop="work_order_no" label="工单" min-width="150" />
          <el-table-column prop="product_name" label="产品" min-width="130" />
          <el-table-column prop="step_name" label="当前工序" width="110" />
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_overdue ? 'danger' : 'info'">{{ statusLabel(stepStatusMap, row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="assigned_user_name" label="负责人" width="110">
            <template #default="{ row }">{{ row.assigned_user_name || '未派工' }}</template>
          </el-table-column>
          <el-table-column prop="due_date" label="交期" width="120" />
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" :icon="View" @click="goWorkOrder(row)" />
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, View } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { ProductionBoard, WorkOrderStepTask } from '../api/types'
import { statusLabel, stepStatusMap } from '../utils/status'

const router = useRouter()
const loading = ref(false)
const board = ref<ProductionBoard | null>(null)

const metrics = computed(() => [
  { label: '待加工', value: board.value?.pending_steps || 0, note: '可开工任务' },
  { label: '加工中', value: board.value?.processing_steps || 0, note: '现场进行中' },
  { label: '待检验', value: board.value?.pending_inspection_steps || 0, note: '等待质检' },
  { label: '返工异常', value: board.value?.reworking_steps || 0, note: '需处理' },
  { label: '未派工', value: board.value?.unassigned_steps || 0, note: '需主管分配' },
  { label: '逾期风险', value: board.value?.overdue_steps || 0, note: `订单 ${board.value?.due_today_orders || 0}` }
])

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

async function loadBoard() {
  loading.value = true
  try {
    const { data } = await apiClient.get<ProductionBoard>('/work-orders/board')
    board.value = data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function goWorkOrder(row: WorkOrderStepTask) {
  router.push(`/work-orders/${row.work_order_id}`)
}

onMounted(loadBoard)
</script>
