<template>
  <el-container class="app-shell">
    <el-aside width="248px" class="app-aside">
      <div class="brand">
        <div class="brand-mark">BSPM</div>
      </div>

      <el-menu :default-active="activeMenuPath" router class="side-menu">
        <el-sub-menu v-for="group in groupedNav" :key="group.key" :index="group.key">
          <template #title>
            <span>{{ group.label }}</span>
          </template>
          <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
            <el-icon>
              <component :is="item.icon" />
            </el-icon>
            <span>{{ navLabel(item) }}</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <h2>{{ currentTitle }}</h2>
          <p>{{ t('app.subtitle') }}</p>
        </div>
        <div class="header-actions">
          <el-button plain class="language-toggle" @click="toggleLocale">
            {{ languageButtonLabel }}
          </el-button>
          <el-button :icon="Key" plain @click="passwordVisible = true">修改密码</el-button>
          <div class="user-badges">
            <el-tag type="success" effect="light">{{ session.user?.real_name || session.user?.username }}</el-tag>
            <el-tag v-for="role in roleNames" :key="role" effect="plain">{{ role }}</el-tag>
          </div>
          <el-button :icon="SwitchButton" plain @click="logout">{{ t('app.logout') }}</el-button>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <el-dialog v-model="passwordVisible" title="修改密码" width="420px">
    <el-form :model="passwordForm" label-position="top">
      <el-form-item label="当前密码">
        <el-input v-model="passwordForm.current_password" type="password" show-password autocomplete="current-password" />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="passwordForm.new_password" type="password" show-password autocomplete="new-password" />
      </el-form-item>
      <el-form-item label="确认新密码">
        <el-input v-model="passwordForm.confirm_password" type="password" show-password autocomplete="new-password" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="passwordVisible = false">取消</el-button>
      <el-button type="primary" :loading="passwordSaving" @click="changePassword">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Key, SwitchButton } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import { visibleNavGroups, visibleNavItems, type NavItem } from '../data/navigation'
import { languageButtonLabel, t, toggleLocale } from '../stores/language'
import { clearSession, session } from '../stores/session'

const route = useRoute()
const router = useRouter()
const passwordVisible = ref(false)
const passwordSaving = ref(false)
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: ''
})

const roleLabelMap: Record<string, string> = {
  admin: 'role.admin',
  boss: 'role.boss',
  sales: 'role.sales',
  designer: 'role.designer',
  production_manager: 'role.production_manager',
  operator: 'role.operator',
  inspector: 'role.inspector',
  delivery: 'role.delivery',
  finance: 'role.finance'
}

const visibleNav = computed(() => visibleNavItems(session.user))
const groupedNav = computed(() => visibleNavGroups(session.user))
const activeMenuPath = computed(() => visibleNav.value.find((item) => route.path.startsWith(item.path))?.path || route.path)
const currentTitle = computed(() => {
  const item = visibleNav.value.find((navItem) => route.path.startsWith(navItem.path))
  return item ? navLabel(item) : t('nav.dashboard')
})
const roleNames = computed(() => (session.user?.roles || []).map((role) => t(roleLabelMap[role] || role)))

function navLabel(item: NavItem) {
  const translated = t(item.labelKey)
  return translated === item.labelKey ? item.label : translated
}

function resetPasswordForm() {
  Object.assign(passwordForm, {
    current_password: '',
    new_password: '',
    confirm_password: ''
  })
}

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

async function changePassword() {
  if (!passwordForm.current_password || !passwordForm.new_password) {
    ElMessage.warning('请填写当前密码和新密码')
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  passwordSaving.value = true
  try {
    await apiClient.post('/auth/change-password', {
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password
    })
    ElMessage.success('密码已更新')
    passwordVisible.value = false
    resetPasswordForm()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    passwordSaving.value = false
  }
}

function logout() {
  clearSession()
  router.push('/login')
}
</script>

<style scoped>
.user-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.language-toggle {
  min-width: 56px;
  font-weight: 700;
}
</style>
