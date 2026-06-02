<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>操作日志</strong>
        <el-select v-model="moduleFilter" placeholder="模块" clearable>
          <el-option label="客户" value="customer" />
          <el-option label="订单" value="order" />
          <el-option label="工单" value="work_order" />
          <el-option label="质检" value="inspection" />
          <el-option label="送货" value="delivery" />
          <el-option label="财务" value="finance" />
          <el-option label="成本" value="cost" />
          <el-option label="报表" value="report" />
        </el-select>
        <el-button :icon="Refresh" @click="loadLogs">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="logs" stripe>
        <el-table-column prop="created_at" label="时间" min-width="180" />
        <el-table-column prop="module" label="模块" width="120" />
        <el-table-column prop="action" label="动作" width="150" />
        <el-table-column prop="target_type" label="对象" width="150" />
        <el-table-column prop="target_id" label="对象 ID" min-width="260" />
        <el-table-column label="内容" min-width="260">
          <template #default="{ row }">
            <code>{{ JSON.stringify(row.after_data || row.before_data || {}) }}</code>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { OperationLog, PageResponse } from '../api/types'

const moduleFilter = ref('')
const logs = ref<OperationLog[]>([])

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

async function loadLogs() {
  try {
    const { data } = await apiClient.get<PageResponse<OperationLog>>('/operation-logs', {
      params: { module: moduleFilter.value || undefined }
    })
    logs.value = data.items
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

watch(moduleFilter, loadLogs)
onMounted(loadLogs)
</script>
