<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input v-model="keyword" :prefix-icon="Search" placeholder="搜索账号 / 姓名 / 部门" clearable class="user-search" />
        <el-select v-model="roleFilter" clearable placeholder="角色筛选" class="role-filter">
          <el-option v-for="role in roles" :key="role.code" :label="role.name" :value="role.code" />
        </el-select>
        <el-switch v-model="attentionOnly" active-text="只看待检查" />
        <el-switch v-model="includeDisabled" active-text="显示已禁用" />
        <el-button :icon="Refresh" @click="loadUsers">刷新</el-button>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
    </div>

    <div class="audit-strip">
      <div>
        <span>当前显示</span>
        <strong>{{ filteredUsers.length }}</strong>
      </div>
      <div>
        <span>启用账号</span>
        <strong>{{ activeUsers.length }}</strong>
      </div>
      <div>
        <span>待检查</span>
        <strong>{{ attentionUsers.length }}</strong>
      </div>
      <div>
        <span>系统权限账号</span>
        <strong>{{ systemUsers.length }}</strong>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="filteredUsers" stripe>
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="real_name" label="姓名" min-width="140" />
        <el-table-column prop="department" label="部门" min-width="130" />
        <el-table-column prop="phone" label="电话" min-width="140" />
        <el-table-column label="角色" min-width="220">
          <template #default="{ row }">
            <div class="tag-list">
              <el-tag v-for="role in row.roles" :key="role" size="small">{{ roleName(role) }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="权限" width="110">
          <template #default="{ row }">
            <div class="permission-count">
              <el-button text type="primary" @click="openPermissionPreview(row)">
                {{ row.permissions?.length || 0 }} 项
              </el-button>
              <div v-if="row.extra_permissions?.length || row.disabled_permissions?.length" class="override-flags">
                <el-tag v-if="row.extra_permissions?.length" size="small" type="success">+{{ row.extra_permissions.length }}</el-tag>
                <el-tag v-if="row.disabled_permissions?.length" size="small" type="danger">-{{ row.disabled_permissions.length }}</el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="岗位检查" min-width="180">
          <template #default="{ row }">
            <div class="tag-list">
              <el-tag v-for="issue in accountIssues(row)" :key="issue" type="warning" size="small" effect="plain">
                {{ issue }}
              </el-tag>
              <el-tag v-if="!accountIssues(row).length" type="success" size="small" effect="plain">匹配</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="设备绑定" min-width="180">
          <template #default="{ row }">
            <el-tag v-if="row.device_mac_address" type="success" effect="plain">{{ shortDevice(row.device_mac_address) }}</el-tag>
            <el-tag v-else type="info" effect="plain">未绑定</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button text type="warning" :disabled="!row.device_mac_address" @click="clearDeviceBinding(row)">清绑定</el-button>
            <el-button text type="danger" :disabled="row.status !== 'active'" @click="deleteUser(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="permissionDialogVisible" title="权限预览" width="760px">
      <div v-if="permissionPreviewUser" class="permission-preview">
        <div class="preview-header">
          <div>
            <strong>{{ permissionPreviewUser.real_name }}</strong>
            <span>{{ permissionPreviewUser.username }} · {{ permissionPreviewUser.department || '未设置部门' }}</span>
          </div>
          <el-tag :type="permissionPreviewUser.status === 'active' ? 'success' : 'info'">
            {{ permissionPreviewUser.status === 'active' ? '启用' : '禁用' }}
          </el-tag>
        </div>

        <div class="preview-section">
          <span class="section-label">角色</span>
          <div class="tag-list">
            <el-tag v-for="role in permissionPreviewUser.roles" :key="role" size="small">
              {{ roleName(role) }}
            </el-tag>
          </div>
        </div>

        <div class="preview-section">
          <span class="section-label">账号单独调整</span>
          <div class="tag-list">
            <el-tag v-for="permission in permissionPreviewUser.extra_permissions || []" :key="`extra-${permission}`" type="success" size="small">
              + {{ permission }}
            </el-tag>
            <el-tag v-for="permission in permissionPreviewUser.disabled_permissions || []" :key="`disabled-${permission}`" type="danger" size="small">
              - {{ permission }}
            </el-tag>
            <el-tag
              v-if="!(permissionPreviewUser.extra_permissions?.length || permissionPreviewUser.disabled_permissions?.length)"
              type="info"
              size="small"
              effect="plain"
            >
              无单独调整
            </el-tag>
          </div>
        </div>

        <div class="preview-section">
          <span class="section-label">可见菜单</span>
          <div class="tag-list">
            <el-tag v-for="item in previewNavItems" :key="item.path" effect="plain">
              {{ item.label }}
            </el-tag>
            <el-empty v-if="!previewNavItems.length" description="暂无可见菜单" />
          </div>
        </div>

        <div class="preview-section">
          <span class="section-label">权限清单</span>
          <el-collapse>
            <el-collapse-item v-for="group in permissionGroups" :key="group.key" :title="`${group.label} · ${group.items.length} 项`">
              <div class="tag-list permission-tags">
                <el-tag v-for="permission in group.items" :key="permission" size="small" effect="plain">
                  {{ permission }}
                </el-tag>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
    </el-dialog>

    <el-drawer v-model="drawerVisible" :title="editingUser ? '编辑用户' : '新增用户'" size="620px">
      <el-form :model="form" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="Boolean(editingUser)" />
        </el-form-item>
        <el-form-item :label="editingUser ? '新密码（不填则不修改）' : '密码'">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="form.department" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio-button label="active">启用</el-radio-button>
            <el-radio-button label="disabled">禁用</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.roles" multiple filterable placeholder="选择角色">
            <el-option v-for="role in roles" :key="role.code" :label="role.name" :value="role.code" />
          </el-select>
        </el-form-item>
        <div class="permission-editor">
          <div class="permission-editor-header">
            <div>
              <strong>账号权限调整</strong>
              <span>角色作为默认模板；额外允许和手动禁用只作用于当前账号。</span>
            </div>
            <el-tag type="success">最终 {{ formEffectivePermissions.length }} 项</el-tag>
          </div>
          <el-form-item label="额外允许权限">
            <el-select
              v-model="form.extra_permissions"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择角色之外额外开放的权限"
            >
              <el-option-group v-for="group in permissionSelectGroups" :key="group.key" :label="group.label">
                <el-option
                  v-for="permission in group.items"
                  :key="permission.code"
                  :label="`${permission.name} · ${permission.code}`"
                  :value="permission.code"
                />
              </el-option-group>
            </el-select>
          </el-form-item>
          <el-form-item label="手动禁用权限">
            <el-select
              v-model="form.disabled_permissions"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择即使角色包含也要禁用的权限"
            >
              <el-option-group v-for="group in permissionSelectGroups" :key="group.key" :label="group.label">
                <el-option
                  v-for="permission in group.items"
                  :key="permission.code"
                  :label="`${permission.name} · ${permission.code}`"
                  :value="permission.code"
                />
              </el-option-group>
            </el-select>
          </el-form-item>
          <el-collapse>
            <el-collapse-item title="最终权限预览">
              <div class="tag-list permission-tags">
                <el-tag v-for="permission in formEffectivePermissions" :key="permission" size="small" effect="plain">
                  {{ permission }}
                </el-tag>
                <el-empty v-if="!formEffectivePermissions.length" description="暂无权限" />
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
        <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
      </el-form>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { PermissionOption, RoleOption, UserOption } from '../api/types'
import { navItems } from '../data/navigation'

const includeDisabled = ref(false)
const attentionOnly = ref(false)
const keyword = ref('')
const roleFilter = ref('')
const drawerVisible = ref(false)
const saving = ref(false)
const users = ref<UserOption[]>([])
const roles = ref<RoleOption[]>([])
const permissions = ref<PermissionOption[]>([])
const editingUser = ref<UserOption | null>(null)
const permissionDialogVisible = ref(false)
const permissionPreviewUser = ref<UserOption | null>(null)

const form = reactive({
  username: '',
  password: '',
  real_name: '',
  department: '',
  phone: '',
  email: '',
  status: 'active',
  roles: [] as string[],
  extra_permissions: [] as string[],
  disabled_permissions: [] as string[]
})

function resetForm() {
  Object.assign(form, {
    username: '',
    password: '',
    real_name: '',
    department: '',
    phone: '',
    email: '',
    status: 'active',
    roles: [],
    extra_permissions: [],
    disabled_permissions: []
  })
}

function roleName(code: string) {
  return roles.value.find((role) => role.code === code)?.name || code
}

function includesAny(value: string, keywords: string[]) {
  const normalized = value.toLowerCase()
  return keywords.some((keyword) => normalized.includes(keyword.toLowerCase()))
}

function accountIssues(user: UserOption) {
  const issues: string[] = []
  const userRoles = user.roles || []
  const department = user.department || ''
  const isSystemUser = userRoles.some((role) => ['admin', 'boss'].includes(role))
  const isCrossDepartmentManager = userRoles.includes('production_manager') && userRoles.includes('sales')
  if (!userRoles.length) issues.push('无角色')
  if (user.status !== 'active') return issues
  if (isSystemUser) return issues

  const productionDept = includesAny(department, [
    '生产',
    '制作',
    '电拼',
    '雕刻',
    '卷板',
    '车床',
    '磨',
    '镀',
    '打样',
    '机加工',
    'production',
    'proofing',
    'carving',
    'engraving',
    'lathe',
    'grinding',
    'bending'
  ])
  const financeDept = includesAny(department, ['财务', '会计', '出纳', '开票', '统计', 'finance', 'account'])
  const deliveryDept = includesAny(department, ['送货', '仓库', '仓储', '物流', 'delivery', 'warehouse'])
  const inspectionDept = includesAny(department, ['检验', '质检', 'inspection', 'qc'])
  const salesDept = includesAny(department, ['销售', '业务', 'sales'])

  if (productionDept && userRoles.includes('sales') && !isCrossDepartmentManager) issues.push('生产部门是销售角色')
  if (financeDept && !userRoles.includes('finance')) issues.push('财务部门缺 finance')
  if (deliveryDept && !userRoles.includes('delivery')) issues.push('仓储/物流缺 delivery')
  if (inspectionDept && !userRoles.includes('inspector')) issues.push('质检部门缺 inspector')
  if (salesDept && !userRoles.includes('sales')) issues.push('销售部门缺 sales')
  return issues
}

const activeUsers = computed(() => users.value.filter((user) => user.status === 'active'))
const attentionUsers = computed(() => users.value.filter((user) => accountIssues(user).length > 0))
const systemUsers = computed(() => users.value.filter((user) => (user.permissions || []).includes('system:permission')))
const filteredUsers = computed(() => {
  const term = keyword.value.trim().toLowerCase()
  return users.value.filter((user) => {
    if (attentionOnly.value && !accountIssues(user).length) return false
    if (roleFilter.value && !(user.roles || []).includes(roleFilter.value)) return false
    if (!term) return true
    const haystack = [
      user.username,
      user.real_name,
      user.department,
      user.phone,
      user.email,
      ...(user.roles || []).map((role) => `${role} ${roleName(role)}`)
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return haystack.includes(term)
  })
})

function permissionGroupLabel(key: string) {
  const labels: Record<string, string> = {
    dashboard: '工作台',
    customer: '客户',
    product: '产品/选项',
    order: '订单',
    route: '工艺路线',
    process: '工序模板',
    work_order: '工单',
    step: '工序任务',
    inspection: '质检',
    rework: '返工',
    delivery: '送货',
    finance: '财务',
    cylinder: '版号/版辊',
    inventory: '库存',
    cost: '成本',
    report: '报表',
    master_data: '基础数据',
    system: '系统',
    log: '日志',
    workflow_v2: '工作流程'
  }
  return labels[key] || key
}

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values)).sort()
}

function sameStringArray(left: string[], right: string[]) {
  return left.length === right.length && left.every((value, index) => value === right[index])
}

function rolePermissionsFor(roleCodes: string[]) {
  const selected = new Set(roleCodes)
  return roles.value.flatMap((role) => (selected.has(role.code) ? role.permissions || [] : []))
}

const formRolePermissions = computed(() => uniqueSorted(rolePermissionsFor(form.roles)))
const formEffectivePermissions = computed(() => {
  const base = new Set([...formRolePermissions.value, ...form.extra_permissions])
  for (const permission of form.disabled_permissions) {
    base.delete(permission)
  }
  return Array.from(base).sort()
})

const permissionSelectGroups = computed(() => {
  const grouped = new Map<string, PermissionOption[]>()
  for (const permission of permissions.value) {
    const key = permission.code.split(':')[0] || 'other'
    grouped.set(key, [...(grouped.get(key) || []), permission])
  }
  return Array.from(grouped.entries())
    .map(([key, items]) => ({
      key,
      label: permissionGroupLabel(key),
      items: items.sort((a, b) => a.sort_no - b.sort_no || a.code.localeCompare(b.code))
    }))
    .sort((a, b) => a.label.localeCompare(b.label, 'zh-Hans-CN'))
})

const previewNavItems = computed(() => {
  const user = permissionPreviewUser.value
  if (!user) return []
  const permissions = user.permissions || []
  const userRoles = user.roles || []
  return navItems.filter((item) => {
    if (!permissions.includes(item.permission)) return false
    if (!item.roles?.length) return true
    return item.roles.some((role) => userRoles.includes(role))
  })
})

const permissionGroups = computed(() => {
  const grouped = new Map<string, string[]>()
  for (const permission of permissionPreviewUser.value?.permissions || []) {
    const key = permission.split(':')[0] || 'other'
    const current = grouped.get(key) || []
    current.push(permission)
    grouped.set(key, current)
  }
  return Array.from(grouped.entries())
    .map(([key, items]) => ({
      key,
      label: permissionGroupLabel(key),
      items: items.sort()
    }))
    .sort((a, b) => a.label.localeCompare(b.label, 'zh-Hans-CN'))
})

function shortDevice(value: string) {
  return value.length > 18 ? `${value.slice(0, 10)}...${value.slice(-6)}` : value
}

async function loadUsers() {
  const { data } = await apiClient.get<UserOption[]>('/users', {
    params: { include_disabled: includeDisabled.value }
  })
  users.value = data
}

async function loadRoles() {
  const { data } = await apiClient.get<RoleOption[]>('/users/roles')
  roles.value = data
}

async function loadPermissions() {
  const { data } = await apiClient.get<PermissionOption[]>('/users/permissions')
  permissions.value = data
}

function openCreate() {
  editingUser.value = null
  resetForm()
  drawerVisible.value = true
}

function openEdit(user: UserOption) {
  editingUser.value = user
  Object.assign(form, {
    username: user.username,
    password: '',
    real_name: user.real_name,
    department: user.department || '',
    phone: user.phone || '',
    email: user.email || '',
    status: user.status,
    roles: [...user.roles],
    extra_permissions: [...(user.extra_permissions || [])],
    disabled_permissions: [...(user.disabled_permissions || [])]
  })
  drawerVisible.value = true
}

function openPermissionPreview(user: UserOption) {
  permissionPreviewUser.value = user
  permissionDialogVisible.value = true
}

async function saveUser() {
  if (!form.username || !form.real_name || (!editingUser.value && !form.password)) {
    ElMessage.warning('请填写用户名、姓名和密码')
    return
  }
  saving.value = true
  try {
    const payload = {
      real_name: form.real_name,
      department: form.department,
      phone: form.phone,
      email: form.email,
      status: form.status,
      roles: form.roles,
      extra_permissions: uniqueSorted(form.extra_permissions),
      disabled_permissions: uniqueSorted(form.disabled_permissions),
      ...(form.password ? { password: form.password } : {})
    }
    if (editingUser.value) {
      await apiClient.put(`/users/${editingUser.value.id}`, payload)
      ElMessage.success('用户已更新')
    } else {
      await apiClient.post('/users', {
        username: form.username,
        ...payload
      })
      ElMessage.success('用户已创建')
    }
    drawerVisible.value = false
    await loadUsers()
  } finally {
    saving.value = false
  }
}

async function clearDeviceBinding(user: UserOption) {
  try {
    await ElMessageBox.confirm(
      `清除「${user.real_name}」的设备绑定后，该账号下次登录会绑定新设备。确定继续？`,
      '清除设备绑定',
      { type: 'warning', confirmButtonText: '清除', cancelButtonText: '取消' }
    )
    await apiClient.post(`/users/${user.id}/clear-device-binding`)
    ElMessage.success('设备绑定已清除')
    await loadUsers()
  } catch {
    return
  }
}

async function deleteUser(user: UserOption) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${user.real_name}」吗？系统会禁用该账号并保留历史业务记录。`,
      '删除用户',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await apiClient.delete(`/users/${user.id}`)
    ElMessage.success('用户已删除')
    await loadUsers()
  } catch {
    return
  }
}

watch(
  () => form.extra_permissions,
  (values) => {
    const selected = new Set(values)
    const nextDisabled = form.disabled_permissions.filter((permission) => !selected.has(permission))
    if (!sameStringArray(nextDisabled, form.disabled_permissions)) {
      form.disabled_permissions = nextDisabled
    }
  },
  { deep: true }
)

watch(
  () => form.disabled_permissions,
  (values) => {
    const selected = new Set(values)
    const nextExtra = form.extra_permissions.filter((permission) => !selected.has(permission))
    if (!sameStringArray(nextExtra, form.extra_permissions)) {
      form.extra_permissions = nextExtra
    }
  },
  { deep: true }
)

watch(includeDisabled, loadUsers)
onMounted(() => {
  loadRoles()
  loadPermissions()
  loadUsers()
})
</script>

<style scoped>
.user-search {
  width: 240px;
}

.role-filter {
  width: 160px;
}

.audit-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.audit-strip > div {
  min-height: 64px;
  display: grid;
  gap: 4px;
  align-content: center;
  padding: 12px 14px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #fbfdff;
}

.audit-strip span {
  color: #64748b;
}

.audit-strip strong {
  font-size: 22px;
  color: #0f172a;
}

.permission-preview {
  display: grid;
  gap: 18px;
}

.preview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.preview-header > div {
  display: grid;
  gap: 4px;
}

.preview-header strong {
  font-size: 18px;
}

.preview-header span,
.section-label {
  color: #64748b;
}

.preview-section {
  display: grid;
  gap: 10px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.permission-count {
  display: grid;
  justify-items: start;
  gap: 4px;
}

.override-flags {
  display: flex;
  gap: 4px;
}

.permission-tags {
  max-height: 220px;
  overflow: auto;
}

.permission-editor {
  display: grid;
  gap: 10px;
  margin: 10px 0 14px;
  padding: 12px;
  border: 1px solid #dbe4ee;
  border-radius: 8px;
  background: #f8fafc;
}

.permission-editor-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.permission-editor-header > div {
  display: grid;
  gap: 4px;
}

.permission-editor-header span {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}
</style>
