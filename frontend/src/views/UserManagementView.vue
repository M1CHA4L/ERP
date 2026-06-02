<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-switch v-model="includeDisabled" active-text="显示已禁用" />
        <el-button :icon="Refresh" @click="loadUsers">刷新</el-button>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="panel-title">
          <span>权限测试账号</span>
          <el-tag type="info">演示环境</el-tag>
        </div>
      </template>
      <el-table :data="roleTestAccounts" stripe>
        <el-table-column prop="role" label="岗位" min-width="130" />
        <el-table-column prop="username" label="用户名" width="130" />
        <el-table-column prop="password" label="密码" width="120" />
        <el-table-column prop="entry" label="默认入口" min-width="150" />
        <el-table-column prop="scope" label="适合验证" min-width="260" />
      </el-table>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table :data="users" stripe>
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

    <el-drawer v-model="drawerVisible" :title="editingUser ? '编辑用户' : '新增用户'" size="460px">
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
        <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
      </el-form>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { RoleOption, UserOption } from '../api/types'

const includeDisabled = ref(false)
const drawerVisible = ref(false)
const saving = ref(false)
const users = ref<UserOption[]>([])
const roles = ref<RoleOption[]>([])
const editingUser = ref<UserOption | null>(null)
const roleTestAccounts = [
  { role: '管理员', username: 'admin', password: 'admin123', entry: '工作台', scope: '完整菜单、用户权限、基础数据清理、所有业务操作' },
  { role: '老板', username: 'boss01', password: 'admin123', entry: '工作台', scope: '经营看板、业务全流程查看，不进入用户权限管理' },
  { role: '销售/跟单', username: 'sales01', password: 'admin123', entry: '订单管理', scope: '客户、产品、订单创建与确认，查看送货/应收' },
  { role: '设计人员', username: 'design01', password: 'admin123', entry: '生产工单', scope: '查看订单、产品、工艺路线和工单' },
  { role: '生产主管', username: 'pm01', password: 'admin123', entry: '生产看板', scope: '工艺维护、生成工单、派工、生产看板' },
  { role: '操作员', username: 'op01', password: 'admin123', entry: '我的任务', scope: '只看本人任务，开始加工和报工' },
  { role: '质检员', username: 'qc01', password: 'admin123', entry: '质检返工', scope: '查看待检任务、提交质检、发起返工' },
  { role: '送货人员', username: 'delivery01', password: 'admin123', entry: '送货管理', scope: '可送货、签收，不看财务和系统设置' },
  { role: '财务人员', username: 'finance01', password: 'admin123', entry: '财务应收', scope: '应收、收款、成本利润和导出' }
]

const form = reactive({
  username: '',
  password: '',
  real_name: '',
  department: '',
  phone: '',
  email: '',
  status: 'active',
  roles: [] as string[]
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
    roles: []
  })
}

function roleName(code: string) {
  return roles.value.find((role) => role.code === code)?.name || code
}

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
    roles: [...user.roles]
  })
  drawerVisible.value = true
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

watch(includeDisabled, loadUsers)
onMounted(() => {
  loadRoles()
  loadUsers()
})
</script>
