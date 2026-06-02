<template>
  <section class="page-stack">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索产品名称或编码" clearable :prefix-icon="Search" />
      <div class="toolbar-left">
        <el-button type="success" :icon="Download" v-permission="'report:export'" @click="exportProducts">
          导出 Excel
        </el-button>
        <el-button type="primary" :icon="Plus" v-permission="'product:create'" @click="openCreate">
          新增产品
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="products" stripe>
        <el-table-column prop="product_code" label="产品编码" min-width="150" />
        <el-table-column prop="name" label="产品名称" min-width="180" />
        <el-table-column prop="specification" label="规格" min-width="160" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="reference_price" label="参考价" width="120">
          <template #default="{ row }">
            {{ row.reference_price == null ? '-' : formatCurrency(row.reference_price) }}
          </template>
        </el-table-column>
        <el-table-column prop="default_route_id" label="默认路线" min-width="150">
          <template #default="{ row }">{{ routeName(row.default_route_id) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" v-permission="'product:update'" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" v-permission="'product:delete'" @click="deleteProduct(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" :title="editingProduct ? '编辑产品' : '新增产品'" size="460px">
      <el-form :model="form" label-position="top">
        <el-form-item label="产品编码">
          <el-input v-model="form.product_code" :disabled="Boolean(editingProduct)" placeholder="不填则自动生成" />
        </el-form-item>
        <el-form-item label="产品名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="form.specification" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="单位">
            <el-input v-model="form.unit" />
          </el-form-item>
          <el-form-item label="参考价">
            <el-input-number v-model="form.reference_price" :min="0" :precision="2" />
          </el-form-item>
        </div>
        <el-form-item label="默认工艺路线">
          <el-select v-model="form.default_route_id" clearable placeholder="选择路线">
            <el-option v-for="route in activeRoutes" :key="route.id" :label="route.name" :value="route.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio-button label="active">启用</el-radio-button>
            <el-radio-button label="disabled">禁用</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" />
        </el-form-item>
        <el-button type="primary" :loading="saving" @click="saveProduct">保存</el-button>
      </el-form>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Plus, Search } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { PageResponse, ProcessRoute, Product } from '../api/types'
import { formatCurrency } from '../utils/format'

const keyword = ref('')
const products = ref<Product[]>([])
const routes = ref<ProcessRoute[]>([])
const drawerVisible = ref(false)
const saving = ref(false)
const editingProduct = ref<Product | null>(null)
const form = reactive({
  product_code: '',
  name: '',
  specification: '',
  unit: '件',
  default_route_id: '',
  reference_price: 0,
  status: 'active',
  remark: ''
})

const activeRoutes = computed(() => routes.value.filter((route) => route.status === 'active'))

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function resetForm() {
  Object.assign(form, {
    product_code: '',
    name: '',
    specification: '',
    unit: '件',
    default_route_id: '',
    reference_price: 0,
    status: 'active',
    remark: ''
  })
}

function routeName(routeId?: string) {
  if (!routeId) return ''
  return routes.value.find((route) => route.id === routeId)?.name || routeId
}

async function loadProducts() {
  const { data } = await apiClient.get<PageResponse<Product>>('/products', {
    params: { keyword: keyword.value || undefined }
  })
  products.value = data.items
}

async function loadRoutes() {
  const { data } = await apiClient.get<ProcessRoute[]>('/process-routes')
  routes.value = data
}

function openCreate() {
  editingProduct.value = null
  resetForm()
  drawerVisible.value = true
}

function openEdit(product: Product) {
  editingProduct.value = product
  Object.assign(form, {
    product_code: product.product_code,
    name: product.name,
    specification: product.specification || '',
    unit: product.unit,
    default_route_id: product.default_route_id || '',
    reference_price: product.reference_price || 0,
    status: product.status,
    remark: product.remark || ''
  })
  drawerVisible.value = true
}

async function saveProduct() {
  if (!form.name) {
    ElMessage.warning('请填写产品名称')
    return
  }
  if (form.default_route_id && !activeRoutes.value.some((route) => route.id === form.default_route_id)) {
    ElMessage.warning('默认工艺路线必须是启用状态')
    return
  }
  saving.value = true
  try {
    const payload = {
      product_code: form.product_code || undefined,
      name: form.name,
      specification: form.specification || undefined,
      unit: form.unit,
      default_route_id: form.default_route_id || null,
      reference_price: form.reference_price,
      status: form.status,
      remark: form.remark || undefined
    }
    if (editingProduct.value) {
      await apiClient.put(`/products/${editingProduct.value.id}`, payload)
      ElMessage.success('产品已更新')
    } else {
      await apiClient.post('/products', payload)
      ElMessage.success('产品已创建')
    }
    drawerVisible.value = false
    await loadProducts()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function deleteProduct(product: Product) {
  try {
    await ElMessageBox.confirm(`确定删除产品「${product.name}」吗？`, '删除产品', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await apiClient.delete(`/products/${product.id}`)
    ElMessage.success('产品已删除')
    await loadProducts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(errorMessage(error))
    }
  }
}

async function exportProducts() {
  try {
    const response = await apiClient.get('/products/export', {
      params: { keyword: keyword.value || undefined },
      responseType: 'blob'
    })
    const url = URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `products-${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

watch(keyword, loadProducts)
onMounted(() => {
  loadRoutes()
  loadProducts()
})
</script>
