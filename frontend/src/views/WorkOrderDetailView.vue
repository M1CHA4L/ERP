<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button :icon="ArrowLeft" @click="router.push('/work-orders')">返回工单</el-button>
        <strong>{{ workOrder?.work_order_no || '工单详情' }}</strong>
        <el-tag v-if="workOrder">{{ statusLabel(workOrderStatusMap, workOrder.status) }}</el-tag>
      </div>
      <el-button
        :icon="Printer"
        :disabled="!workOrder"
        @click="printProcessTaskSheet"
      >
        Process Task Sheet
      </el-button>
      <el-button
        :icon="Printer"
        :disabled="!workOrder"
        @click="printSelfInspectionCard"
      >
        Self Inspection Card
      </el-button>
      <el-button
        type="primary"
        :icon="UserFilled"
        v-permission="'work_order:dispatch'"
        :disabled="!workOrder"
        @click="openDispatch"
      >
        派工
      </el-button>
    </div>

    <el-card v-if="workOrder" shadow="never" class="panel-card">
      <template #header>
        <div class="panel-title">
          <span>工单信息</span>
          <el-tag :type="workOrder.priority === 'urgent' ? 'danger' : 'info'">{{ workOrder.priority }}</el-tag>
        </div>
      </template>
      <div class="detail-grid">
        <div><span>产品</span><strong>{{ workOrder.product_name }}</strong></div>
        <div><span>数量</span><strong>{{ workOrder.quantity }}</strong></div>
        <div><span>订单 ID</span><strong>{{ workOrder.sales_order_id }}</strong></div>
        <div><span>工序数量</span><strong>{{ workOrder.steps.length }}</strong></div>
      </div>
    </el-card>

    <el-card v-if="workOrder" shadow="never" class="panel-card">
      <FilePanel
        owner-type="work_order"
        :owner-id="workOrder.id"
        title="工单附件"
        default-file-type="work_order_attachment"
        upload-permission="work_order:dispatch"
        delete-permission="work_order:dispatch"
      />
    </el-card>

    <el-card v-if="workOrder" shadow="never" class="panel-card">
      <TimelinePanel
        title="工单进度时间线"
        subtitle="串联关联订单、工序报工、质检返工、送货与财务记录"
        :items="timeline"
        :loading="timelineLoading"
        @refresh="loadTimeline"
      />
    </el-card>

    <el-card v-if="workOrder" shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>工序流转</span>
          <el-tag>按顺序开工</el-tag>
        </div>
      </template>
      <el-table :data="workOrder.steps" row-key="id">
        <el-table-column prop="step_no" label="序号" width="80" />
        <el-table-column prop="step_name" label="工序" min-width="140" />
        <el-table-column prop="requires_inspection" label="检验" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.requires_inspection" type="warning">需要</el-tag>
            <span v-else>否</span>
          </template>
        </el-table-column>
        <el-table-column prop="assigned_user_id" label="负责人" min-width="140">
          <template #default="{ row }">{{ userName(row.assigned_user_id) || '未派工' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="130">
          <template #default="{ row }">
            <el-tag>{{ statusLabel(stepStatusMap, row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="现场照片" width="110">
          <template #default="{ row }">
            <el-button text type="primary" @click="openStepFiles(row)">
              {{ stepFileCounts[row.id] || 0 }} 张
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              :disabled="row.status !== 'pending_process'"
              :loading="busyStepId === row.id"
              v-permission="'step:start'"
              @click="startStep(row.id)"
            >
              开始
            </el-button>
            <el-button
              size="small"
              type="success"
              :disabled="row.status !== 'processing'"
              v-permission="'step:complete'"
              @click="openComplete(row)"
            >
              完成报工
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="dispatchVisible" title="工序派工" size="520px">
      <div v-if="workOrder" class="dispatch-list">
        <div v-for="assignment in dispatchAssignments" :key="assignment.step_id" class="dispatch-row">
          <span>{{ assignment.step_no }}. {{ assignment.step_name }}</span>
          <el-select v-model="assignment.assigned_user_id" filterable placeholder="选择操作员">
            <el-option
              v-for="user in users"
              :key="user.id"
              :label="`${user.real_name}（${user.department || user.username}）`"
              :value="user.id"
            />
          </el-select>
        </div>
        <el-button type="primary" :loading="dispatching" @click="submitDispatch">保存派工</el-button>
      </div>
    </el-drawer>

    <el-drawer v-model="stepFilesVisible" title="工序现场附件" size="520px">
      <FilePanel
        v-if="selectedStepForFiles"
        owner-type="work_order_step"
        :owner-id="selectedStepForFiles.id"
        :title="`${selectedStepForFiles.step_no}. ${selectedStepForFiles.step_name}`"
        default-file-type="site_photo"
        upload-permission="step:report"
        delete-permission="step:report"
        @uploaded="loadStepFileCounts"
        @deleted="loadStepFileCounts"
      />
    </el-drawer>

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
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type UploadUserFile } from 'element-plus'
import { ArrowLeft, Printer, UploadFilled, UserFilled } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import FilePanel from '../components/FilePanel.vue'
import TimelinePanel from '../components/TimelinePanel.vue'
import type { FileAsset, TimelineItem, UserOption, WorkOrder } from '../api/types'
import { hasPermission } from '../stores/session'
import { statusLabel, stepStatusMap, workOrderStatusMap } from '../utils/status'

const route = useRoute()
const router = useRouter()
const workOrder = ref<WorkOrder | null>(null)
const users = ref<UserOption[]>([])
const dispatchVisible = ref(false)
const dispatching = ref(false)
const busyStepId = ref('')
const completeVisible = ref(false)
const completing = ref(false)
const completingStepId = ref('')
const completeFileList = ref<UploadUserFile[]>([])
const stepFileCounts = ref<Record<string, number>>({})
const stepFilesVisible = ref(false)
const selectedStepForFiles = ref<WorkOrder['steps'][number] | null>(null)
const timeline = ref<TimelineItem[]>([])
const timelineLoading = ref(false)
const dispatchAssignments = ref<
  Array<{
    step_id: string
    step_no: number
    step_name: string
    assigned_user_id: string
  }>
>([])

const completeForm = reactive({
  processed_qty: 0,
  qualified_qty: 0,
  defective_qty: 0,
  work_hours: 0,
  remark: ''
})

async function loadWorkOrder() {
  const { data } = await apiClient.get<WorkOrder>(`/work-orders/${route.params.id}`)
  workOrder.value = data
  await loadStepFileCounts()
}

async function loadTimeline() {
  timelineLoading.value = true
  try {
    const { data } = await apiClient.get<TimelineItem[]>(`/work-orders/${route.params.id}/timeline`)
    timeline.value = data
  } finally {
    timelineLoading.value = false
  }
}

async function loadUsers() {
  if (!hasPermission('work_order:dispatch')) return
  const { data } = await apiClient.get<UserOption[]>('/users/options')
  users.value = data
}

function userName(userId?: string) {
  if (!userId) return ''
  return users.value.find((user) => user.id === userId)?.real_name || userId
}

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

async function loadStepFileCounts() {
  if (!workOrder.value) return
  const entries = await Promise.all(
    workOrder.value.steps.map(async (step) => {
      const { data } = await apiClient.get<FileAsset[]>('/files', {
        params: { owner_type: 'work_order_step', owner_id: step.id, file_type: 'site_photo' }
      })
      return [step.id, data.length] as const
    })
  )
  stepFileCounts.value = Object.fromEntries(entries)
}

function openStepFiles(step: WorkOrder['steps'][number]) {
  selectedStepForFiles.value = step
  stepFilesVisible.value = true
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

async function printSelfInspectionCard() {
  if (!workOrder.value) return
  const popup = window.open('', '_blank')
  try {
    const { data } = await apiClient.get<string>(`/work-orders/${workOrder.value.id}/self-inspection-card`, { responseType: 'text' })
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

async function printProcessTaskSheet() {
  if (!workOrder.value) return
  const popup = window.open('', '_blank')
  try {
    const { data } = await apiClient.get<string>(`/work-orders/${workOrder.value.id}/process-task-sheet`, { responseType: 'text' })
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

async function openDispatch() {
  if (!users.value.length) {
    await loadUsers()
  }
  dispatchAssignments.value = (workOrder.value?.steps || []).map((step) => ({
    step_id: step.id,
    step_no: step.step_no,
    step_name: step.step_name,
    assigned_user_id: step.assigned_user_id || ''
  }))
  dispatchVisible.value = true
}

async function submitDispatch() {
  if (!workOrder.value) return
  dispatching.value = true
  try {
    const assignments = dispatchAssignments.value
      .filter((assignment) => assignment.assigned_user_id)
      .map((assignment) => ({
        step_id: assignment.step_id,
        assigned_user_id: assignment.assigned_user_id
      }))
    await apiClient.post(`/work-orders/${workOrder.value.id}/dispatch`, { assignments })
    ElMessage.success('派工已保存')
    dispatchVisible.value = false
    await loadWorkOrder()
    await loadTimeline()
  } finally {
    dispatching.value = false
  }
}

async function startStep(stepId: string) {
  busyStepId.value = stepId
  try {
    await apiClient.post(`/work-orders/steps/${stepId}/start`)
    ElMessage.success('工序已开始')
    await loadWorkOrder()
    await loadTimeline()
  } finally {
    busyStepId.value = ''
  }
}

function openComplete(step: WorkOrder['steps'][number]) {
  completingStepId.value = step.id
  completeForm.processed_qty = workOrder.value?.quantity || 0
  completeForm.qualified_qty = workOrder.value?.quantity || 0
  completeForm.defective_qty = 0
  completeForm.work_hours = 0
  completeForm.remark = ''
  completeFileList.value = []
  completeVisible.value = true
}

async function submitComplete() {
  completing.value = true
  try {
    await apiClient.post(`/work-orders/steps/${completingStepId.value}/complete`, completeForm)
    await uploadQueuedFiles('work_order_step', completingStepId.value, 'site_photo', completeFileList.value)
    ElMessage.success('报工已提交')
    completeVisible.value = false
    await loadWorkOrder()
    await loadTimeline()
  } finally {
    completing.value = false
  }
}

onMounted(() => {
  loadWorkOrder()
  loadUsers()
  loadTimeline()
})
</script>
