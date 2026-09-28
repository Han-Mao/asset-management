<template>
  <div class="page-card">
    <div class="filter-bar">
      <el-select v-model="operationType" placeholder="操作类型" clearable filterable style="width: 200px" @change="load">
        <el-option v-for="t in types" :key="t" :label="t" :value="t" />
      </el-select>
      <el-select v-model="targetType" placeholder="对象类型" clearable style="width: 150px" @change="load">
        <el-option label="资产" value="ASSET" />
        <el-option label="申请" value="APPLICATION" />
        <el-option label="维修" value="REPAIR" />
        <el-option label="用户" value="USER" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="operator_name" label="操作人" width="110" />
      <el-table-column prop="operation_type" label="操作类型" width="190" />
      <el-table-column prop="target_type" label="对象" width="120" />
      <el-table-column prop="target_id" label="对象ID" width="90" />
      <el-table-column prop="operation_content" label="内容" min-width="240" />
      <el-table-column prop="ip_address" label="IP" width="140" />
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ String(row.created_at).replace('T', ' ').slice(0, 19) }}</template>
      </el-table-column>
    </el-table>

    <el-pagination
      style="margin-top: 12px; justify-content: flex-end"
      layout="total, sizes, prev, pager, next"
      :total="total"
      v-model:current-page="page.page"
      v-model:page-size="page.page_size"
      :page-sizes="[20, 50, 100]"
      @current-change="load"
      @size-change="load"
    />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const operationType = ref('')
const targetType = ref('')
const page = reactive({ page: 1, page_size: 20 })
const types = [
  'LOGIN', 'LOGOUT', 'ASSET_CREATE', 'ASSET_UPDATE', 'ASSET_DELETE', 'ASSET_IMPORT', 'ASSET_EXPORT',
  'ASSET_SCRAP', 'ASSET_PENDING_SCRAP', 'APPLICATION_CREATE', 'APPLICATION_CANCEL', 'APPLICATION_APPROVE',
  'APPLICATION_REJECT', 'ASSIGNMENT_RETURN', 'REPAIR_CREATE', 'REPAIR_START', 'REPAIR_COMPLETE',
  'REPAIR_CANCEL', 'USER_CREATE', 'USER_UPDATE', 'USER_DELETE', 'USER_STATUS', 'USER_RESET_PWD',
  'ROLE_CREATE', 'ROLE_UPDATE', 'ROLE_DELETE', 'DEPT_CREATE', 'DEPT_UPDATE', 'DEPT_DELETE',
  'CATEGORY_CREATE', 'CATEGORY_UPDATE', 'CATEGORY_DELETE',
]

async function load() {
  loading.value = true
  try {
    const data = await api.logs({
      operation_type: operationType.value || undefined,
      target_type: targetType.value || undefined,
      page: page.page,
      page_size: page.page_size,
    })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
