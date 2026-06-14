<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="statusFilter" placeholder="工单状态" clearable>
          <el-option label="待排产" value="pending_schedule" />
          <el-option label="已排产" value="scheduled" />
          <el-option label="生产中" value="in_production" />
          <el-option label="返工中" value="reworking" />
        </el-select>
        <el-input v-model="keyword" placeholder="客户 / 订单 / 工单 / 产品" clearable :prefix-icon="Search" />
        <el-button type="primary" :icon="Refresh" @click="loadWorkOrders">刷新</el-button>
        <el-button type="success" :icon="Download" v-permission="'report:export'" @click="exportWorkOrders">
          导出 Excel
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="workOrders" row-key="id" @row-dblclick="goDetail">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="step-strip">
              <div v-for="step in row.steps" :key="step.id" class="step-chip">
                <small>{{ step.step_no }}</small>
                <span>{{ step.step_name }}</span>
                <el-tag size="small">{{ statusLabel(stepStatusMap, step.status) }}</el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="work_order_no" label="工单编号" min-width="190" />
        <el-table-column prop="product_name" label="产品" min-width="160" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="priority" label="优先级" width="110" />
        <el-table-column prop="status" label="状态" width="130">
          <template #default="{ row }">
            <el-tag>{{ statusLabel(workOrderStatusMap, row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="goDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Download, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { apiClient } from '../api/client'
import type { PageResponse, WorkOrder } from '../api/types'
import { statusLabel, stepStatusMap, workOrderStatusMap } from '../utils/status'

const router = useRouter()
const keyword = ref('')
const statusFilter = ref('')
const workOrders = ref<WorkOrder[]>([])

async function loadWorkOrders() {
  const { data } = await apiClient.get<PageResponse<WorkOrder>>('/work-orders', {
    params: { status_filter: statusFilter.value || undefined, keyword: keyword.value || undefined }
  })
  workOrders.value = data.items
}

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

async function exportWorkOrders() {
  try {
    const response = await apiClient.get('/work-orders/export', {
      params: { status_filter: statusFilter.value || undefined, keyword: keyword.value || undefined },
      responseType: 'blob'
    })
    const url = URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `work-orders-${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function goDetail(row: WorkOrder) {
  router.push(`/work-orders/${row.id}`)
}

watch([keyword, statusFilter], loadWorkOrders)
onMounted(loadWorkOrders)
</script>
