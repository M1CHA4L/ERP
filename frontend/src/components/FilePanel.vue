<template>
  <div class="file-panel">
    <div class="file-panel-header">
      <div>
        <strong>{{ title }}</strong>
        <span>{{ files.length }} 个文件</span>
      </div>
      <el-upload
        :http-request="uploadFile"
        :show-file-list="false"
        :multiple="true"
        :accept="accept"
        v-permission="uploadPermission"
      >
        <el-button type="primary" :icon="Upload" :loading="uploading">上传</el-button>
      </el-upload>
    </div>

    <el-empty v-if="!loading && files.length === 0" description="暂无附件" />
    <div v-else class="file-list">
      <div v-for="file in files" :key="file.id" class="file-row">
        <div class="file-info">
          <el-icon><Paperclip /></el-icon>
          <div>
            <strong>{{ file.file_name }}</strong>
            <span>{{ file.file_type }} · {{ formatSize(file.size_bytes) }} · {{ formatDate(file.created_at) }}</span>
          </div>
        </div>
        <div class="file-actions">
          <el-button text type="primary" :icon="Download" @click="downloadFile(file)">下载</el-button>
          <el-button text type="danger" :icon="Delete" v-permission="deletePermission" @click="deleteFile(file)">删除</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type UploadRequestOptions } from 'element-plus'
import { Delete, Download, Paperclip, Upload } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { FileAsset } from '../api/types'

const props = withDefaults(
  defineProps<{
    ownerType: string
    ownerId: string
    title?: string
    defaultFileType?: string
    uploadPermission?: string
    deletePermission?: string
    accept?: string
  }>(),
  {
    title: '附件',
    defaultFileType: 'attachment',
    uploadPermission: 'order:update',
    deletePermission: 'system:permission',
    accept: '.pdf,.png,.jpg,.jpeg,.webp,.dwg,.dxf,.cdr,.ai,.psd,.xlsx,.xls,.doc,.docx,.zip'
  }
)

const emit = defineEmits<{
  uploaded: [file: FileAsset]
  deleted: [fileId: string]
}>()

const files = ref<FileAsset[]>([])
const loading = ref(false)
const uploading = ref(false)

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function formatSize(size?: number) {
  if (!size) return '0 KB'
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(value: string) {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

async function loadFiles() {
  if (!props.ownerId) return
  loading.value = true
  try {
    const { data } = await apiClient.get<FileAsset[]>('/files', {
      params: { owner_type: props.ownerType, owner_id: props.ownerId }
    })
    files.value = data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function uploadFile(options: UploadRequestOptions) {
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('owner_type', props.ownerType)
    formData.append('owner_id', props.ownerId)
    formData.append('file_type', props.defaultFileType)
    formData.append('file', options.file)
    const { data } = await apiClient.post<FileAsset>('/files/upload', formData)
    files.value.unshift(data)
    emit('uploaded', data)
    ElMessage.success('文件已上传')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    uploading.value = false
  }
}

async function downloadFile(file: FileAsset) {
  try {
    const response = await apiClient.get(`/files/${file.id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([response.data], { type: file.mime_type || undefined }))
    const link = document.createElement('a')
    link.href = url
    link.download = file.file_name
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function deleteFile(file: FileAsset) {
  await ElMessageBox.confirm(`确定删除 ${file.file_name}？`, '删除附件', { type: 'warning' })
  try {
    await apiClient.delete(`/files/${file.id}`)
    files.value = files.value.filter((item) => item.id !== file.id)
    emit('deleted', file.id)
    ElMessage.success('文件已删除')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

watch(() => [props.ownerType, props.ownerId], loadFiles)
onMounted(loadFiles)
</script>
