<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>基础数据清理</strong>
        <el-tag type="info">停用、未引用、可恢复资料</el-tag>
      </div>
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadCleanup">刷新</el-button>
    </div>

    <div class="metric-grid cleanup-metrics">
      <el-card v-for="card in summaryCards" :key="card.label" shadow="never" class="metric-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.hint }}</small>
      </el-card>
    </div>

    <el-card shadow="never" class="table-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="工序模板" name="templates">
          <el-table :data="cleanup?.templates || []" stripe>
            <el-table-column prop="code" label="编码" width="120" />
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="引用" min-width="180">
              <template #default="{ row }">
                路线 {{ row.route_step_count }} / 工单 {{ row.work_order_step_count }}
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="清理原因" min-width="160" />
            <el-table-column label="操作" width="210" fixed="right">
              <template #default="{ row }">
                <el-button v-if="!row.enabled" size="small" type="primary" @click="restoreTemplate(row.id)">
                  重新启用
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  plain
                  :disabled="!row.can_delete"
                  @click="deleteTemplate(row.id)"
                >
                  删除未引用
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && cleanup && cleanup.templates.length === 0" description="暂无需要清理的工序模板" />
        </el-tab-pane>

        <el-tab-pane label="工艺路线" name="routes">
          <el-table :data="cleanup?.routes || []" stripe>
            <el-table-column prop="route_code" label="编码" width="120" />
            <el-table-column prop="name" label="路线名称" min-width="150" />
            <el-table-column prop="version" label="版本" width="90" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="routeStatusType(row.status)">{{ routeStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="引用" min-width="210">
              <template #default="{ row }">
                产品 {{ row.product_count }} / 订单 {{ row.sales_order_count }} / 工单 {{ row.work_order_count }}
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="清理原因" min-width="160" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.can_restore" size="small" type="primary" @click="restoreRoute(row.id)">
                  恢复草稿
                </el-button>
                <el-button
                  v-if="row.status !== 'disabled'"
                  size="small"
                  type="danger"
                  plain
                  @click="disableRoute(row.id)"
                >
                  禁用
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && cleanup && cleanup.routes.length === 0" description="暂无需要清理的工艺路线" />
        </el-tab-pane>

        <el-tab-pane label="产品档案" name="products">
          <el-table :data="cleanup?.products || []" stripe>
            <el-table-column prop="product_code" label="编码" width="150" />
            <el-table-column prop="name" label="产品名称" min-width="160" />
            <el-table-column prop="specification" label="规格" min-width="150" />
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="row.deleted_at || row.status !== 'active' ? 'info' : 'success'">
                  {{ row.deleted_at ? '已删除' : productStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="引用" min-width="180">
              <template #default="{ row }">
                订单 {{ row.sales_order_item_count }} / 工单 {{ row.work_order_count }}
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="清理原因" min-width="160" />
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.can_restore" size="small" type="primary" @click="restoreProduct(row.id)">
                  恢复
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && cleanup && cleanup.products.length === 0" description="暂无需要清理的产品档案" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { MasterDataCleanup } from '../api/types'

const loading = ref(false)
const cleanup = ref<MasterDataCleanup | null>(null)
const activeTab = ref('templates')

const summaryCards = computed(() => {
  const summary = cleanup.value?.summary
  return [
    { label: '停用工序', value: summary?.inactive_templates || 0, hint: '可重新启用或删除未引用项' },
    { label: '未用工序', value: summary?.unused_templates || 0, hint: '尚未进入路线/工单' },
    { label: '异常路线', value: summary?.inactive_routes || 0, hint: '草稿或已禁用路线' },
    { label: '未用产品', value: summary?.unused_products || 0, hint: '尚未被订单引用' },
    { label: '停用产品', value: summary?.inactive_products || 0, hint: '可从这里恢复误删档案' }
  ]
})

async function loadCleanup() {
  loading.value = true
  try {
    const { data } = await apiClient.get<MasterDataCleanup>('/maintenance/master-data-cleanup')
    cleanup.value = data
  } finally {
    loading.value = false
  }
}

async function restoreTemplate(id: string) {
  await apiClient.post(`/maintenance/master-data-cleanup/templates/${id}/restore`)
  ElMessage.success('工序模板已重新启用')
  await loadCleanup()
}

async function restoreRoute(id: string) {
  await apiClient.post(`/maintenance/master-data-cleanup/routes/${id}/restore`)
  ElMessage.success('工艺路线已恢复为草稿')
  await loadCleanup()
}

async function restoreProduct(id: string) {
  await apiClient.post(`/maintenance/master-data-cleanup/products/${id}/restore`)
  ElMessage.success('产品档案已恢复')
  await loadCleanup()
}

async function deleteTemplate(id: string) {
  await ElMessageBox.confirm('确定删除这个未引用的工序模板吗？删除后不能被路线选择。', '删除确认', {
    type: 'warning'
  })
  await apiClient.delete(`/process-routes/templates/${id}`)
  ElMessage.success('工序模板已删除')
  await loadCleanup()
}

async function disableRoute(id: string) {
  await ElMessageBox.confirm('确定禁用这条工艺路线吗？已被引用的历史订单和工单不会被删除。', '禁用确认', {
    type: 'warning'
  })
  await apiClient.delete(`/process-routes/${id}`)
  ElMessage.success('工艺路线已禁用')
  await loadCleanup()
}

function routeStatusLabel(status: string) {
  return status === 'active' ? '启用' : status === 'draft' ? '草稿' : status === 'disabled' ? '禁用' : status
}

function routeStatusType(status: string) {
  if (status === 'active') return 'success'
  if (status === 'draft') return 'warning'
  return 'info'
}

function productStatusLabel(status: string) {
  return status === 'active' ? '启用' : status === 'disabled' ? '停用' : status
}

onMounted(loadCleanup)
</script>

<style scoped>
.cleanup-metrics {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

@media (max-width: 960px) {
  .cleanup-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
