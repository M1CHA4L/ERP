<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>工序任务</strong>
        <el-select v-model="statusFilter" placeholder="任务状态" clearable>
          <el-option label="待加工" value="pending_process" />
          <el-option label="加工中" value="processing" />
          <el-option label="待检验" value="pending_inspection" />
          <el-option label="返工中" value="reworking" />
        </el-select>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadTasks">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="tasks" stripe @row-dblclick="goWorkOrder">
        <el-table-column prop="work_order_no" label="工单" min-width="160" />
        <el-table-column prop="product_name" label="产品" min-width="150" />
        <el-table-column prop="quantity" label="数量" width="90" />
        <el-table-column prop="step_name" label="工序" width="120">
          <template #default="{ row }">
            <span>{{ row.step_no }}. {{ row.step_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="row.is_overdue ? 'danger' : 'info'">{{ statusLabel(stepStatusMap, row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="planned_end_at" label="计划完成" min-width="170">
          <template #default="{ row }">{{ formatDateTime(row.planned_end_at) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="due_date" label="订单交期" width="120" />
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              :icon="VideoPlay"
              :disabled="row.status !== 'pending_process'"
              :loading="busyStepId === row.step_id"
              @click="startStep(row)"
            >
              开始
            </el-button>
            <el-button
              size="small"
              type="success"
              :icon="CircleCheck"
              :disabled="row.status !== 'processing'"
              @click="openComplete(row)"
            >
              报工
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && tasks.length === 0" description="暂无工序任务" />
    </el-card>

    <el-dialog v-model="completeVisible" title="完成报工" width="420px">
      <el-form :model="completeForm" label-position="top">
        <el-form-item label="加工数量">
          <el-input-number v-model="completeForm.processed_qty" :min="0" />
        </el-form-item>
        <el-form-item label="合格数量">
          <el-input-number v-model="completeForm.qualified_qty" :min="0" />
        </el-form-item>
        <el-form-item label="不良数量">
          <el-input-number v-model="completeForm.defective_qty" :min="0" />
        </el-form-item>
        <el-form-item label="工时">
          <el-input-number v-model="completeForm.work_hours" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="completeForm.remark" type="textarea" />
        </el-form-item>
        <el-form-item label="现场照片">
          <el-upload v-model:file-list="completeFileList" :auto-upload="false" multiple>
            <el-button :icon="UploadFilled">选择照片/附件</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeVisible = false">取消</el-button>
        <el-button type="primary" :loading="completing" @click="submitComplete">提交</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type UploadUserFile } from 'element-plus'
import { CircleCheck, Refresh, UploadFilled, VideoPlay } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { PageResponse, WorkOrderStepTask } from '../api/types'
import { statusLabel, stepStatusMap } from '../utils/status'

const router = useRouter()
const loading = ref(false)
const tasks = ref<WorkOrderStepTask[]>([])
const statusFilter = ref('')
const busyStepId = ref('')
const completing = ref(false)
const completeVisible = ref(false)
const completingTask = ref<WorkOrderStepTask | null>(null)
const completeFileList = ref<UploadUserFile[]>([])

const completeForm = reactive({
  processed_qty: 0,
  qualified_qty: 0,
  defective_qty: 0,
  work_hours: 0,
  remark: ''
})

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function formatDateTime(value?: string) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

async function loadTasks() {
  loading.value = true
  try {
    const { data } = await apiClient.get<PageResponse<WorkOrderStepTask>>('/work-orders/my-steps', {
      params: { status_filter: statusFilter.value || undefined, page_size: 50 }
    })
    tasks.value = data.items
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function startStep(task: WorkOrderStepTask) {
  busyStepId.value = task.step_id
  try {
    await apiClient.post(`/work-orders/steps/${task.step_id}/start`)
    ElMessage.success('工序已开始')
    await loadTasks()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    busyStepId.value = ''
  }
}

function openComplete(task: WorkOrderStepTask) {
  completingTask.value = task
  completeForm.processed_qty = task.quantity
  completeForm.qualified_qty = task.quantity
  completeForm.defective_qty = 0
  completeForm.work_hours = 0
  completeForm.remark = ''
  completeFileList.value = []
  completeVisible.value = true
}

async function uploadQueuedFiles(ownerType: string, ownerId: string, fileType: string, files: UploadUserFile[]) {
  for (const item of files) {
    if (!item.raw) continue
    const formData = new FormData()
    formData.append('owner_type', ownerType)
    formData.append('owner_id', ownerId)
    formData.append('file_type', fileType)
    formData.append('file', item.raw)
    await apiClient.post('/files/upload', formData)
  }
}

async function submitComplete() {
  if (!completingTask.value) return
  completing.value = true
  try {
    await apiClient.post(`/work-orders/steps/${completingTask.value.step_id}/complete`, completeForm)
    await uploadQueuedFiles('work_order_step', completingTask.value.step_id, 'site_photo', completeFileList.value)
    ElMessage.success('报工已提交')
    completeVisible.value = false
    await loadTasks()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    completing.value = false
  }
}

function goWorkOrder(row: WorkOrderStepTask) {
  router.push(`/work-orders/${row.work_order_id}`)
}

watch(statusFilter, loadTasks)
onMounted(loadTasks)
</script>
