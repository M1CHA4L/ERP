<template>
  <main class="login-page">
    <el-button class="login-language-toggle" plain @click="toggleLocale">
      {{ languageButtonLabel }}
    </el-button>
    <section class="login-panel">
      <div>
        <h1>{{ t('login.title') }}</h1>
        <p>
          {{ t('brand.full') }}<br />
          <span v-if="locale === 'zh'">Bangladesh Shanghai Plate Making Co., Ltd.</span>
          <span v-else>Production workflow ERP</span>
        </p>
      </div>

      <el-form class="login-form" :model="form" label-position="top" @keyup.enter="submit" @submit.prevent="submit">
        <el-form-item :label="t('login.username')">
          <el-input v-model="form.username" size="large" autocomplete="username" />
        </el-form-item>
        <el-form-item :label="t('login.password')">
          <el-input
            v-model="form.password"
            size="large"
            type="password"
            autocomplete="current-password"
            show-password
          />
        </el-form-item>
        <el-button class="login-button" type="primary" size="large" native-type="submit" :loading="loading">
          {{ t('login.submit') }}
        </el-button>
      </el-form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiClient } from '../api/client'
import type { LoginResponse } from '../api/types'
import { preferredHomePath } from '../data/navigation'
import { languageButtonLabel, locale, t, toggleLocale } from '../stores/language'
import { getDeviceMacAddress, setSession } from '../stores/session'

const router = useRouter()
const loading = ref(false)
const form = reactive({
  username: '',
  password: ''
})

async function submit() {
  if (loading.value) return
  loading.value = true
  try {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', {
      ...form,
      mac_address: getDeviceMacAddress()
    })
    setSession(data.access_token, data.user)
    ElMessage.success(t('login.success'))
    router.push(preferredHomePath(data.user))
  } catch {
    ElMessage.error(t('login.failure'))
  } finally {
    loading.value = false
  }
}
</script>
