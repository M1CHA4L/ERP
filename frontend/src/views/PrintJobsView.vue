<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>打印记录</strong>
        <el-tag type="info">只保留已打印单据的留痕</el-tag>
      </div>
      <div class="toolbar-left">
        <el-button :icon="Refresh" @click="loadPrintJobs">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>打印留痕</span>
          <el-tag>{{ printJobs.length }} 条</el-tag>
        </div>
      </template>

      <div class="table-tools print-filter-bar">
        <el-select v-model="documentType" placeholder="单据类型" clearable>
          <el-option label="制版委托书" value="entrust_sheet" />
          <el-option label="收据" value="money_receipt" />
          <el-option label="客户账单" value="customer_statement" />
          <el-option label="Delivery Note (Priced)" value="delivery_note_priced" />
          <el-option label="Delivery Note (No Unit Price)" value="delivery_note_no_unit_price" />
          <el-option label="Delivery Note (No Amount)" value="delivery_note_no_amount" />
          <el-option label="Quality Inspection Report" value="quality_report" />
          <el-option label="Quality Abnormality & Rework Report" value="quality_rework_report" />
          <el-option label="Self Inspection Card" value="self_inspection_card" />
          <el-option label="Process Task Sheet" value="process_task_sheet" />
          <el-option label="生产单" value="production_order" />
          <el-option label="车间任务单" value="workshop_daily" />
        </el-select>
        <el-date-picker v-model="dateFrom" value-format="YYYY-MM-DD" type="date" placeholder="开始日期" />
        <el-date-picker v-model="dateTo" value-format="YYYY-MM-DD" type="date" placeholder="结束日期" />
        <el-button type="primary" :icon="Search" @click="loadPrintJobs">查询</el-button>
      </div>

      <el-table :data="printJobs" stripe>
        <el-table-column prop="print_no" label="打印号" min-width="190" />
        <el-table-column label="单据类型" width="140">
          <template #default="{ row }">{{ documentLabel(row.document_type) }}</template>
        </el-table-column>
        <el-table-column prop="target_type" label="目标类型" width="150" />
        <el-table-column prop="target_id" label="目标 ID" min-width="260" />
        <el-table-column prop="printed_at" label="打印时间" min-width="190" />
        <el-table-column label="快照" min-width="320">
          <template #default="{ row }">
            <code>{{ compactSnapshot(row.snapshot) }}</code>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { PageResponse, PrintJob } from '../api/types'

const printJobs = ref<PrintJob[]>([])
const documentType = ref('')
const dateFrom = ref('')
const dateTo = ref('')

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function documentLabel(value: string) {
  const labels: Record<string, string> = {
    entrust_sheet: '制版委托书',
    money_receipt: '收据',
    customer_statement: '客户账单',
    delivery_note_priced: 'Delivery Note (Priced)',
    delivery_note_no_unit_price: 'Delivery Note (No Unit Price)',
    delivery_note_no_amount: 'Delivery Note (No Amount)',
    quality_report: 'Quality Inspection Report',
    quality_rework_report: 'Quality Abnormality & Rework Report',
    self_inspection_card: 'Self Inspection Card',
    process_task_sheet: 'Process Task Sheet',
    production_order: '生产单',
    workshop_daily: '车间任务单'
  }
  return labels[value] || value
}

function compactSnapshot(snapshot?: Record<string, unknown>) {
  if (!snapshot) return ''
  const keys = [
    'receipt_no',
    'statement_no',
    'delivery_no',
    'inspection_no',
    'order_no',
    'work_order_no',
    'cylinder_no',
    'customer_name',
    'step_name',
    'step_count',
    'result',
    'variant',
    'date_from',
    'date_to',
    'inspected_qty',
    'failed_qty',
    'total_amount',
    'due_amount'
  ]
  const picked = Object.fromEntries(keys.filter((key) => snapshot[key] !== undefined).map((key) => [key, snapshot[key]]))
  return JSON.stringify(Object.keys(picked).length ? picked : snapshot)
}

async function loadPrintJobs() {
  try {
    const { data } = await apiClient.get<PageResponse<PrintJob>>('/print-jobs', {
      params: {
        document_type: documentType.value || undefined,
        date_from: dateFrom.value || undefined,
        date_to: dateTo.value || undefined,
        page_size: 80
      }
    })
    printJobs.value = data.items
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

watch([documentType, dateFrom, dateTo], loadPrintJobs)
onMounted(loadPrintJobs)
</script>

<style scoped>
.print-filter-bar {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(140px, 0.8fr) minmax(140px, 0.8fr) auto;
  align-items: center;
  margin-bottom: 12px;
}

@media (max-width: 760px) {
  .print-filter-bar {
    grid-template-columns: 1fr;
  }
}
</style>
