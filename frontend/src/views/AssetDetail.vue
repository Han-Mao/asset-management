<template>
  <div v-if="asset">
    <el-card shadow="never">
      <div style="display: flex; justify-content: space-between; align-items: flex-start">
        <div>
          <h2 style="margin: 0 0 8px">{{ asset.asset_name }}</h2>
          <div class="muted">
            资产编号：{{ asset.asset_code }} ｜ 状态：
            <el-tag size="small" :type="asset.status === 'IN_STOCK' ? 'success' : 'primary'">{{ asset.status_name }}</el-tag>
          </div>
          <div class="muted" style="margin-top: 6px" v-if="asset.borrower_name">
            当前领用人：{{ asset.borrower_name }}，预计归还 {{ fmt(asset.expected_return_time) }}
            <span v-if="asset.days_left !== null && asset.days_left < 0" style="color: #f56c6c">（已逾期 {{ -asset.days_left }} 天）</span>
          </div>
        </div>
        <div style="display: flex; gap: 8px">
          <el-button v-if="auth.hasPerm('asset:update') && asset.status !== 'SCRAPPED'" @click="router.push(`/assets/${asset.id}/edit`)">编辑</el-button>
          <el-button @click="qrVisible = true">打印二维码</el-button>
          <el-button v-if="asset.status === 'IN_STOCK' || asset.borrower_id === auth.user?.id" type="warning" @click="repairVisible = true">申请维修</el-button>
          <el-button v-if="asset.status === 'IN_STOCK'" type="primary" @click="applyVisible = true">申请领用</el-button>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="tab" style="margin-top: 16px">
      <el-tab-pane label="基本信息" name="info">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="资产类型">{{ asset.category_name }}</el-descriptions-item>
          <el-descriptions-item label="品牌">{{ asset.brand || '-' }}</el-descriptions-item>
          <el-descriptions-item label="型号">{{ asset.model || '-' }}</el-descriptions-item>
          <el-descriptions-item label="序列号">{{ asset.serial_number || '-' }}</el-descriptions-item>
          <el-descriptions-item label="采购日期">{{ asset.purchase_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="采购价格">{{ asset.purchase_price ? `¥${asset.purchase_price}` : '-' }}</el-descriptions-item>
          <el-descriptions-item label="保修截止">{{ asset.warranty_expire_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="存放位置">{{ asset.location || '-' }}</el-descriptions-item>
          <el-descriptions-item label="供应商">{{ asset.supplier || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="3">{{ asset.remark || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>

      <el-tab-pane label="生命周期" name="lifecycle">
        <el-timeline>
          <el-timeline-item v-for="(e, i) in lifecycle" :key="i" :timestamp="fmt(e.time)" placement="top">
            <div class="timeline-title">{{ e.title }}</div>
            <div class="muted">{{ e.description }}</div>
          </el-timeline-item>
        </el-timeline>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="qrVisible" title="资产二维码" width="360px" align-center>
      <div style="text-align: center">
        <img :src="api.assetQrcodeUrl(asset.id) + '?t=' + Date.now()" style="width: 240px; height: 240px" />
        <p>{{ asset.asset_code }}</p>
      </div>
    </el-dialog>

    <el-dialog v-model="repairVisible" title="申请维修" width="460px">
      <el-input v-model="fault" type="textarea" :rows="3" placeholder="请描述故障现象" />
      <template #footer>
        <el-button @click="repairVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRepair">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="applyVisible" title="申请领用" width="460px">
      <el-form label-width="90px">
        <el-form-item label="使用原因">
          <el-input v-model="reason" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="预计归还">
          <el-date-picker v-model="expected" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyVisible = false">取消</el-button>
        <el-button type="primary" @click="submitApply">提交申请</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const asset = ref(null)
const lifecycle = ref([])
const tab = ref('info')
const qrVisible = ref(false)
const repairVisible = ref(false)
const applyVisible = ref(false)
const fault = ref('')
const reason = ref('')
const expected = ref('')

function fmt(v) {
  return v ? String(v).replace('T', ' ').slice(0, 16) : '-'
}

async function load() {
  asset.value = await api.asset(route.params.id)
  lifecycle.value = await api.assetLifecycle(route.params.id)
}

async function submitRepair() {
  if (!fault.value) return ElMessage.warning('请填写故障描述')
  await api.createRepair({ asset_id: asset.value.id, fault_description: fault.value })
  ElMessage.success('报修已提交')
  repairVisible.value = false
  load()
}

async function submitApply() {
  if (!reason.value) return ElMessage.warning('请填写使用原因')
  await api.createApplication({
    asset_id: asset.value.id,
    reason: reason.value,
    expected_return_time: expected.value + 'T18:00:00',
  })
  ElMessage.success('申请已提交')
  applyVisible.value = false
  load()
}

onMounted(load)
</script>
