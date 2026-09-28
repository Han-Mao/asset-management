<template>
  <el-card shadow="never">
    <template #header>{{ isEdit ? '编辑资产' : '新增资产' }}</template>
    <el-form :model="form" label-width="100px" style="max-width: 620px">
      <el-form-item label="设备名称" required>
        <el-input v-model="form.asset_name" />
      </el-form-item>
      <el-form-item label="资产类型" required>
        <el-select v-model="form.category_id" style="width: 100%">
          <el-option v-for="c in categories" :key="c.id" :label="c.category_name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="品牌">
        <el-input v-model="form.brand" />
      </el-form-item>
      <el-form-item label="型号">
        <el-input v-model="form.model" />
      </el-form-item>
      <el-form-item label="序列号">
        <el-input v-model="form.serial_number" />
      </el-form-item>
      <el-form-item label="采购日期">
        <el-date-picker v-model="form.purchase_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="采购价格">
        <el-input-number v-model="form.purchase_price" :min="0" :precision="2" :step="100" style="width: 200px" />
      </el-form-item>
      <el-form-item label="保修截止">
        <el-date-picker v-model="form.warranty_expire_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="存放位置">
        <el-input v-model="form.location" />
      </el-form-item>
      <el-form-item label="供应商">
        <el-input v-model="form.supplier" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="save">保存</el-button>
        <el-button @click="router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const route = useRoute()
const router = useRouter()
const categories = ref([])
const isEdit = computed(() => !!route.params.id)
const form = reactive({
  asset_name: '',
  category_id: null,
  brand: '',
  model: '',
  serial_number: '',
  purchase_date: '',
  purchase_price: null,
  warranty_expire_date: '',
  location: '',
  supplier: '',
  remark: '',
})

async function save() {
  if (!form.asset_name || !form.category_id) return ElMessage.warning('设备名称和类型必填')
  const payload = { ...form }
  if (payload.purchase_price === null) payload.purchase_price = undefined
  if (isEdit.value) {
    await api.updateAsset(route.params.id, payload)
    ElMessage.success('已保存')
  } else {
    const created = await api.createAsset(payload)
    ElMessage.success(`已新增，资产编号 ${created.asset_code}`)
  }
  router.push('/assets')
}

onMounted(async () => {
  categories.value = await api.categories()
  if (isEdit.value) {
    const data = await api.asset(route.params.id)
    Object.assign(form, {
      ...data,
      purchase_price: data.purchase_price === null ? null : Number(data.purchase_price),
      purchase_date: data.purchase_date || '',
      warranty_expire_date: data.warranty_expire_date || '',
    })
  }
})
</script>
