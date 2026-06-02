<template>
  <section class="page-stack">
    <div class="toolbar">
      <strong>工艺路线配置</strong>
      <div class="toolbar-left">
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
        <el-button type="primary" :icon="Plus" v-permission="'route:create'" @click="openRouteCreate">
          新增路线
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>工艺路线</span>
          <el-tag>{{ routes.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="routes" row-key="id">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="step-strip">
              <div v-for="step in row.steps" :key="step.id" class="step-chip">
                <small>{{ step.step_no }}</small>
                <span>{{ step.step_name }}</span>
                <el-tag v-if="step.is_optional" size="small" type="info">可跳过</el-tag>
                <el-tag v-if="step.requires_inspection" size="small" type="warning">需检验</el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="route_code" label="路线编码" width="120" />
        <el-table-column prop="name" label="路线名称" width="150" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column label="版本来源" width="150">
          <template #default="{ row }">
            <span>{{ row.source_route_code || '原始路线' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="使用情况" width="180">
          <template #default="{ row }">
            <div class="usage-tags">
              <el-tag size="small" :type="row.is_used ? 'warning' : 'success'">
                {{ row.is_used ? '已使用' : '未使用' }}
              </el-tag>
              <el-tag size="small" type="info">产品 {{ row.product_count }}</el-tag>
              <el-tag size="small" type="info">工单 {{ row.work_order_count }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ routeStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" :icon="Edit" v-permission="'route:update'" @click="openRouteEdit(row)">
              编辑
            </el-button>
            <el-button text type="primary" :icon="CopyDocument" v-permission="'route:create'" @click="openRouteCopy(row)">
              复制
            </el-button>
            <el-button text type="danger" :icon="Delete" v-permission="'route:delete'" @click="deleteRoute(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="toolbar">
          <div class="panel-title">
            <span>工序模板</span>
            <el-tag>{{ templates.length }} 个</el-tag>
          </div>
          <el-button type="primary" :icon="Plus" v-permission="'process:template:create'" @click="openTemplateCreate">
            新增工序
          </el-button>
        </div>
      </template>
      <el-table :data="templates" stripe>
        <el-table-column prop="code" label="工序编码" width="130" />
        <el-table-column prop="name" label="工序名称" min-width="160" />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column prop="requires_inspection" label="需要检验" width="110">
          <template #default="{ row }">
            <el-tag :type="row.requires_inspection ? 'warning' : 'info'">
              {{ row.requires_inspection ? '需要' : '不需要' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" :icon="Edit" v-permission="'process:template:update'" @click="openTemplateEdit(row)">
              编辑
            </el-button>
            <el-button text type="danger" :icon="Delete" v-permission="'process:template:delete'" @click="deleteTemplate(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer
      v-model="routeDrawerVisible"
      :title="routeDrawerTitle"
      size="760px"
    >
      <el-form :model="routeForm" label-position="top" class="route-form">
        <div class="form-grid">
          <el-form-item label="路线编码">
            <el-input v-model="routeForm.route_code" placeholder="如 RA / RB / R-CUSTOM" />
          </el-form-item>
          <el-form-item label="路线名称">
            <el-input v-model="routeForm.name" placeholder="如 标准机械加工路线" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="routeForm.status">
              <el-option label="启用" value="active" />
              <el-option label="草稿" value="draft" />
              <el-option label="禁用" value="disabled" />
            </el-select>
          </el-form-item>
          <el-form-item label="默认路线">
            <el-switch v-model="routeForm.is_default" />
          </el-form-item>
        </div>
        <el-form-item label="说明">
          <el-input v-model="routeForm.description" type="textarea" :rows="2" />
        </el-form-item>

        <el-alert
          v-if="stepsLocked"
          title="该路线已被产品、订单或工单使用，工序步骤已锁定。需要调整工序时，请先复制路线生成新版本。"
          type="warning"
          show-icon
          :closable="false"
        />

        <div class="route-builder">
          <div class="route-builder-header">
            <strong>工序步骤</strong>
            <el-button type="primary" plain :icon="Plus" :disabled="stepsLocked" @click="addRouteStep">添加工序</el-button>
          </div>

          <div v-for="(step, index) in routeForm.steps" :key="index" class="route-step-row">
            <div class="step-index">{{ index + 1 }}</div>
            <el-select
              v-model="step.process_template_id"
              filterable
              placeholder="选择工序模板"
              :disabled="stepsLocked"
              @change="applyTemplate(step)"
            >
              <el-option
                v-for="template in enabledTemplates"
                :key="template.id"
                :label="`${template.code} - ${template.name}`"
                :value="template.id"
              />
            </el-select>
            <el-input v-model="step.step_name" placeholder="工序显示名称" :disabled="stepsLocked" />
            <div class="step-options">
              <label class="step-switch">
                <span>可跳过</span>
                <el-switch v-model="step.is_optional" :disabled="stepsLocked" />
              </label>
              <label class="step-switch">
                <span>需检验</span>
                <el-switch v-model="step.requires_inspection" :disabled="stepsLocked" />
              </label>
              <el-input-number v-model="step.planned_hours" :min="0" :precision="2" :step="0.5" placeholder="工时" :disabled="stepsLocked" />
              <div class="step-actions">
                <el-button :disabled="stepsLocked || index === 0" @click="moveRouteStep(index, -1)">上移</el-button>
                <el-button :disabled="stepsLocked || index === routeForm.steps.length - 1" @click="moveRouteStep(index, 1)">下移</el-button>
                <el-button type="danger" plain :icon="Delete" :disabled="stepsLocked" @click="removeRouteStep(index)" />
              </div>
            </div>
          </div>
        </div>

        <div class="drawer-actions">
          <el-button @click="routeDrawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingRoute" @click="saveRoute">保存路线</el-button>
        </div>
      </el-form>
    </el-drawer>

    <el-drawer
      v-model="templateDrawerVisible"
      :title="editingTemplate ? '编辑工序模板' : '新增工序模板'"
      size="420px"
    >
      <el-form :model="templateForm" label-position="top">
        <el-form-item label="工序编码">
          <el-input v-model="templateForm.code" :disabled="Boolean(editingTemplate)" placeholder="如 P014" />
        </el-form-item>
        <el-form-item label="工序名称">
          <el-input v-model="templateForm.name" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="templateForm.category" />
        </el-form-item>
        <el-form-item label="是否需要检验">
          <el-switch v-model="templateForm.requires_inspection" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="templateForm.enabled" />
        </el-form-item>
        <div class="drawer-actions">
          <el-button @click="templateDrawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingTemplate" @click="saveTemplate">保存工序</el-button>
        </div>
      </el-form>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { ProcessRoute, ProcessTemplate } from '../api/types'

interface RouteStepForm {
  process_template_id: string
  step_name: string
  is_optional: boolean
  requires_inspection: boolean
  planned_hours: number | null
  remark?: string
}

interface RouteForm {
  route_code: string
  name: string
  description: string
  is_default: boolean
  status: string
  steps: RouteStepForm[]
}

const routes = ref<ProcessRoute[]>([])
const templates = ref<ProcessTemplate[]>([])

const routeDrawerVisible = ref(false)
const savingRoute = ref(false)
const editingRoute = ref<ProcessRoute | null>(null)
const copyingRoute = ref<ProcessRoute | null>(null)
const routeForm = ref<RouteForm>(createEmptyRouteForm())

const templateDrawerVisible = ref(false)
const savingTemplate = ref(false)
const editingTemplate = ref<ProcessTemplate | null>(null)
const templateForm = ref({
  code: '',
  name: '',
  category: '',
  requires_inspection: false,
  enabled: true
})

const enabledTemplates = computed(() => templates.value.filter((template) => template.enabled))
const templateById = computed(() => new Map(templates.value.map((template) => [template.id, template])))
const stepsLocked = computed(() => Boolean(editingRoute.value && !editingRoute.value.can_edit_steps))
const routeDrawerTitle = computed(() => {
  if (editingRoute.value) return '编辑工艺路线'
  if (copyingRoute.value) return '复制工艺路线'
  return '新增工艺路线'
})

function createEmptyRouteStep(): RouteStepForm {
  return {
    process_template_id: '',
    step_name: '',
    is_optional: false,
    requires_inspection: false,
    planned_hours: null
  }
}

function createEmptyRouteForm(): RouteForm {
  return {
    route_code: '',
    name: '',
    description: '',
    is_default: false,
    status: 'active',
    steps: [createEmptyRouteStep()]
  }
}

async function loadRoutes() {
  const { data } = await apiClient.get<ProcessRoute[]>('/process-routes')
  routes.value = data
}

async function loadTemplates() {
  const { data } = await apiClient.get<ProcessTemplate[]>('/process-routes/templates')
  templates.value = data
}

async function loadAll() {
  await Promise.all([loadRoutes(), loadTemplates()])
}

function routeStatusLabel(status: string) {
  const labels: Record<string, string> = {
    active: '启用',
    draft: '草稿',
    disabled: '禁用'
  }
  return labels[status] || status
}

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function openRouteCreate() {
  editingRoute.value = null
  copyingRoute.value = null
  routeForm.value = createEmptyRouteForm()
  routeDrawerVisible.value = true
}

function openRouteEdit(route: ProcessRoute) {
  editingRoute.value = route
  copyingRoute.value = null
  routeForm.value = {
    route_code: route.route_code,
    name: route.name,
    description: route.description || '',
    is_default: route.is_default,
    status: route.status,
    steps: route.steps.map((step) => ({
      process_template_id: step.process_template_id,
      step_name: step.step_name,
      is_optional: step.is_optional,
      requires_inspection: step.requires_inspection,
      planned_hours: step.planned_hours ?? null,
      remark: step.remark
    }))
  }
  routeDrawerVisible.value = true
}

function openRouteCopy(route: ProcessRoute) {
  editingRoute.value = null
  copyingRoute.value = route
  routeForm.value = {
    route_code: '',
    name: `${route.name} 复制`,
    description: route.description || '',
    is_default: false,
    status: 'active',
    steps: route.steps.map((step) => ({
      process_template_id: step.process_template_id,
      step_name: step.step_name,
      is_optional: step.is_optional,
      requires_inspection: step.requires_inspection,
      planned_hours: step.planned_hours ?? null,
      remark: step.remark
    }))
  }
  routeDrawerVisible.value = true
}

function addRouteStep() {
  routeForm.value.steps.push(createEmptyRouteStep())
}

function removeRouteStep(index: number) {
  if (routeForm.value.steps.length === 1) {
    ElMessage.warning('路线至少需要一个工序')
    return
  }
  routeForm.value.steps.splice(index, 1)
}

function moveRouteStep(index: number, direction: -1 | 1) {
  const targetIndex = index + direction
  if (targetIndex < 0 || targetIndex >= routeForm.value.steps.length) return
  const [step] = routeForm.value.steps.splice(index, 1)
  routeForm.value.steps.splice(targetIndex, 0, step)
}

function applyTemplate(step: RouteStepForm) {
  const template = templateById.value.get(step.process_template_id)
  if (!template) return
  step.step_name = template.name
  step.requires_inspection = template.requires_inspection
}

async function saveRoute() {
  if (!routeForm.value.route_code || !routeForm.value.name) {
    ElMessage.warning('请填写路线编码和路线名称')
    return
  }
  if (!stepsLocked.value && routeForm.value.steps.some((step) => !step.process_template_id)) {
    ElMessage.warning('请为每一步选择工序模板')
    return
  }
  savingRoute.value = true
  try {
    const stepPayload = routeForm.value.steps.map((step) => ({
      process_template_id: step.process_template_id,
      step_name: step.step_name || undefined,
      is_optional: step.is_optional,
      requires_inspection: step.requires_inspection,
      planned_hours: step.planned_hours ?? undefined,
      remark: step.remark || undefined
    }))
    const payload = {
      route_code: routeForm.value.route_code,
      name: routeForm.value.name,
      description: routeForm.value.description || undefined,
      is_default: routeForm.value.is_default,
      status: routeForm.value.status,
      steps: stepPayload
    }
    if (editingRoute.value) {
      const updatePayload = stepsLocked.value ? { ...payload, steps: undefined } : payload
      await apiClient.put(`/process-routes/${editingRoute.value.id}`, updatePayload)
      ElMessage.success('工艺路线已更新')
    } else if (copyingRoute.value) {
      await apiClient.post(`/process-routes/${copyingRoute.value.id}/copy`, payload)
      ElMessage.success('工艺路线新版本已复制')
    } else {
      await apiClient.post('/process-routes', payload)
      ElMessage.success('工艺路线已创建')
    }
    routeDrawerVisible.value = false
    copyingRoute.value = null
    await loadRoutes()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingRoute.value = false
  }
}

async function deleteRoute(route: ProcessRoute) {
  try {
    await ElMessageBox.confirm(
      `确定删除工艺路线「${route.name}」吗？历史工单仍会保留，后续新订单不能再选择该路线。`,
      '删除工艺路线',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await apiClient.delete(`/process-routes/${route.id}`)
    ElMessage.success('工艺路线已删除')
    await loadRoutes()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(errorMessage(error))
    }
  }
}

function resetTemplateForm() {
  templateForm.value = {
    code: '',
    name: '',
    category: '',
    requires_inspection: false,
    enabled: true
  }
}

function openTemplateCreate() {
  editingTemplate.value = null
  resetTemplateForm()
  templateDrawerVisible.value = true
}

function openTemplateEdit(template: ProcessTemplate) {
  editingTemplate.value = template
  templateForm.value = {
    code: template.code,
    name: template.name,
    category: template.category || '',
    requires_inspection: template.requires_inspection,
    enabled: template.enabled
  }
  templateDrawerVisible.value = true
}

async function saveTemplate() {
  if (!templateForm.value.code || !templateForm.value.name) {
    ElMessage.warning('请填写工序编码和名称')
    return
  }
  if (!editingTemplate.value && templates.value.some((template) => template.code === templateForm.value.code)) {
    ElMessage.warning('工序编码已存在，不能新增')
    return
  }
  savingTemplate.value = true
  try {
    const payload = {
      code: templateForm.value.code,
      name: templateForm.value.name,
      category: templateForm.value.category || undefined,
      requires_inspection: templateForm.value.requires_inspection,
      enabled: templateForm.value.enabled
    }
    if (editingTemplate.value) {
      await apiClient.put(`/process-routes/templates/${editingTemplate.value.id}`, payload)
      ElMessage.success('工序模板已更新')
    } else {
      await apiClient.post('/process-routes/templates', payload)
      ElMessage.success('工序模板已创建')
    }
    templateDrawerVisible.value = false
    await loadTemplates()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingTemplate.value = false
  }
}

async function deleteTemplate(template: ProcessTemplate) {
  try {
    await ElMessageBox.confirm(
      `确定删除工序模板「${template.name}」吗？如果该模板已被工艺路线或工单引用，系统会阻止删除。`,
      '删除工序模板',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await apiClient.delete(`/process-routes/templates/${template.id}`)
    ElMessage.success('工序模板已删除')
    await loadTemplates()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(errorMessage(error))
    }
  }
}

onMounted(loadAll)
</script>

<style scoped>
.route-form {
  display: grid;
  gap: 16px;
}

.route-builder {
  display: grid;
  gap: 12px;
}

.usage-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.route-builder-header,
.drawer-actions,
.step-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.route-builder-header,
.drawer-actions {
  justify-content: space-between;
}

.route-step-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  padding: 12px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #fbfdff;
}

.route-step-row :deep(.el-select),
.route-step-row :deep(.el-input),
.route-step-row :deep(.el-input-number) {
  width: 100%;
}

.step-options {
  grid-column: 2 / -1;
  display: grid;
  grid-template-columns: auto auto minmax(130px, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.step-actions {
  flex-wrap: wrap;
}

.step-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #667085;
  font-size: 13px;
  white-space: nowrap;
}

.step-index {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  color: #ffffff;
  background: #2563eb;
  font-size: 13px;
  font-weight: 700;
}

.drawer-actions {
  margin-top: 4px;
}

@media (max-width: 960px) {
  .route-step-row {
    grid-template-columns: 1fr;
  }

  .step-options {
    grid-column: auto;
    grid-template-columns: 1fr;
  }

  .step-actions {
    flex-wrap: wrap;
  }
}
</style>
