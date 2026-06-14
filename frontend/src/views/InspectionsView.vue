<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>质检返工</strong>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>待检验工序</span>
          <el-tag>{{ pendingTasks.length }} 项</el-tag>
        </div>
      </template>
      <el-table :data="pendingTasks" stripe>
        <el-table-column prop="work_order_no" label="工单编号" min-width="190" />
        <el-table-column prop="product_name" label="产品" min-width="160" />
        <el-table-column prop="step_name" label="工序" width="130" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" v-permission="'inspection:submit'" @click="openInspection(row)">
              检验
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>质检记录</span>
          <el-tag type="success">{{ records.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="records" stripe>
        <el-table-column prop="inspection_no" label="质检编号" min-width="190" />
        <el-table-column prop="result" label="结果" width="120">
          <template #default="{ row }">
            <el-tag :type="row.result === 'passed' || row.result === 'concession' ? 'success' : 'danger'">
              {{ resultLabel(row.result) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="inspected_qty" label="检验数量" width="110" />
        <el-table-column prop="failed_qty" label="不良数量" width="110" />
        <el-table-column prop="reason" label="原因" min-width="220" />
        <el-table-column prop="inspected_at" label="检验时间" min-width="180" />
        <el-table-column label="图片" width="100">
          <template #default="{ row }">
            <el-button text type="primary" @click="openInspectionFiles(row)">
              {{ inspectionFileCounts[row.id] || 0 }} 张
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="96" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :icon="Printer" @click="printInspection(row)">打印</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="提交质检" width="520px">
      <el-form :model="form" label-position="top">
        <el-form-item label="检验结果">
          <el-radio-group v-model="form.result">
            <el-radio-button label="passed">通过</el-radio-button>
            <el-radio-button label="concession">让步通过</el-radio-button>
            <el-radio-button label="failed">不通过</el-radio-button>
            <el-radio-button label="rework">返工</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="检验数量">
            <el-input-number v-model="form.inspected_qty" :min="0" />
          </el-form-item>
          <el-form-item label="通过数量">
            <el-input-number v-model="form.passed_qty" :min="0" />
          </el-form-item>
        </div>
        <el-form-item label="不良数量">
          <el-input-number v-model="form.failed_qty" :min="0" />
        </el-form-item>
        <el-form-item v-if="form.result === 'failed' || form.result === 'rework'" label="返工回到工序">
          <el-select v-model="form.rework_to_step_id" placeholder="选择返工目标工序">
            <el-option
              v-for="step in reworkStepOptions"
              :key="step.id"
              :label="`${step.step_no}. ${step.step_name}`"
              :value="step.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="原因/备注">
          <el-input v-model="form.reason" type="textarea" />
        </el-form-item>
        <el-form-item label="质检图片">
          <el-upload v-model:file-list="inspectionFileList" :auto-upload="false" multiple>
            <el-button :icon="UploadFilled">选择图片/附件</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitInspection">提交</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="inspectionFilesVisible" title="质检图片" size="520px">
      <FilePanel
        v-if="selectedInspectionForFiles"
        owner-type="inspection_record"
        :owner-id="selectedInspectionForFiles.id"
        :title="selectedInspectionForFiles.inspection_no"
        default-file-type="inspection_photo"
        upload-permission="inspection:submit"
        delete-permission="inspection:submit"
        @uploaded="loadInspectionFileCounts"
        @deleted="loadInspectionFileCounts"
      />
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadUserFile } from 'element-plus'
import { Printer, Refresh, UploadFilled } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import FilePanel from '../components/FilePanel.vue'
import type { FileAsset, InspectionRecord, PageResponse, PendingInspectionTask, WorkOrder } from '../api/types'

const pendingTasks = ref<PendingInspectionTask[]>([])
const records = ref<InspectionRecord[]>([])
const currentTask = ref<PendingInspectionTask | null>(null)
const currentWorkOrder = ref<WorkOrder | null>(null)
const dialogVisible = ref(false)
const submitting = ref(false)
const inspectionFileList = ref<UploadUserFile[]>([])
const inspectionFileCounts = ref<Record<string, number>>({})
const inspectionFilesVisible = ref(false)
const selectedInspectionForFiles = ref<InspectionRecord | null>(null)

const form = reactive({
  result: 'passed',
  inspected_qty: 0,
  passed_qty: 0,
  failed_qty: 0,
  reason: '',
  rework_to_step_id: ''
})

const reworkStepOptions = computed(() => {
  if (!currentTask.value || !currentWorkOrder.value) return []
  return currentWorkOrder.value.steps.filter((step) => step.step_no <= currentTask.value!.step_no)
})

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function resultLabel(result: string) {
  const map: Record<string, string> = {
    passed: '通过',
    failed: '不通过',
    concession: '让步通过',
    rework: '返工'
  }
  return map[result] || result
}

async function loadPending() {
  const { data } = await apiClient.get<PendingInspectionTask[]>('/inspections/pending')
  pendingTasks.value = data
}

async function loadRecords() {
  const { data } = await apiClient.get<PageResponse<InspectionRecord>>('/inspections')
  records.value = data.items
  await loadInspectionFileCounts()
}

async function loadAll() {
  await Promise.all([loadPending(), loadRecords()])
}

async function openInspection(task: PendingInspectionTask) {
  currentTask.value = task
  const { data } = await apiClient.get<WorkOrder>(`/work-orders/${task.work_order_id}`)
  currentWorkOrder.value = data
  Object.assign(form, {
    result: 'passed',
    inspected_qty: task.quantity,
    passed_qty: task.quantity,
    failed_qty: 0,
    reason: '',
    rework_to_step_id: ''
  })
  inspectionFileList.value = []
  dialogVisible.value = true
}

async function loadInspectionFileCounts() {
  const entries = await Promise.all(
    records.value.map(async (record) => {
      const { data } = await apiClient.get<FileAsset[]>('/files', {
        params: { owner_type: 'inspection_record', owner_id: record.id, file_type: 'inspection_photo' }
      })
      return [record.id, data.length] as const
    })
  )
  inspectionFileCounts.value = Object.fromEntries(entries)
}

function openInspectionFiles(record: InspectionRecord) {
  selectedInspectionForFiles.value = record
  inspectionFilesVisible.value = true
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

async function printInspection(record: InspectionRecord) {
  const popup = window.open('', '_blank')
  try {
    const { data } = await apiClient.get<string>(`/inspections/${record.id}/print`, { responseType: 'text' })
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

async function submitInspection() {
  if (!currentTask.value) return
  if ((form.result === 'failed' || form.result === 'rework') && (!form.reason || !form.rework_to_step_id)) {
    ElMessage.warning('不通过或返工时必须填写原因并选择返工工序')
    return
  }
  submitting.value = true
  try {
    const { data } = await apiClient.post<InspectionRecord>(`/inspections/work-order-steps/${currentTask.value.step_id}`, {
      result: form.result,
      inspected_qty: form.inspected_qty,
      passed_qty: form.passed_qty,
      failed_qty: form.failed_qty,
      reason: form.reason,
      rework_to_step_id: form.rework_to_step_id || null
    })
    await uploadQueuedFiles('inspection_record', data.id, 'inspection_photo', inspectionFileList.value)
    ElMessage.success('质检已提交')
    dialogVisible.value = false
    await loadAll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

onMounted(loadAll)
</script>
