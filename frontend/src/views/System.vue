<template>
  <el-tabs v-model="tab" class="page-card">
    <el-tab-pane label="用户管理" name="users">
      <div class="filter-bar">
        <el-input v-model="userQuery.keyword" placeholder="账号/姓名" style="width: 180px" clearable @keyup.enter="loadUsers" />
        <el-select v-model="userQuery.department_id" placeholder="部门" clearable style="width: 150px" @change="loadUsers">
          <el-option v-for="d in departments" :key="d.id" :label="d.department_name" :value="d.id" />
        </el-select>
        <el-button type="primary" @click="loadUsers">查询</el-button>
        <el-button type="primary" @click="openUser()">新增用户</el-button>
      </div>
      <el-table :data="users" border v-loading="loading">
        <el-table-column prop="username" label="账号" width="130" />
        <el-table-column prop="real_name" label="姓名" width="110" />
        <el-table-column label="部门" width="120">
          <template #default="{ row }">{{ row.department_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="140">
          <template #default="{ row }">
            <el-tag v-for="r in row.roles" :key="r" size="small" style="margin-right: 4px">{{ r }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="邮箱" min-width="170">
          <template #default="{ row }">{{ row.email || '-' }}</template>
        </el-table-column>
        <el-table-column label="最后登录" width="150">
          <template #default="{ row }">{{ row.last_login_at ? String(row.last_login_at).slice(0, 16).replace('T', ' ') : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-switch :model-value="row.status === 1" @change="(v) => toggleStatus(row, v)" :disabled="!auth.hasPerm('user:update')" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button v-if="auth.hasPerm('user:update')" link type="primary" @click="openUser(row)">编辑</el-button>
            <el-button v-if="auth.hasPerm('user:update')" link type="primary" @click="reset(row)">重置密码</el-button>
            <el-button v-if="auth.hasPerm('user:delete')" link type="danger" @click="removeUser(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="角色权限" name="roles">
      <el-button type="primary" style="margin-bottom: 12px" @click="openRole()">新增角色</el-button>
      <el-table :data="roles" border>
        <el-table-column prop="role_name" label="角色名称" width="150" />
        <el-table-column prop="role_code" label="编码" width="130" />
        <el-table-column prop="description" label="说明" width="220" />
        <el-table-column label="权限">
          <template #default="{ row }">
            <el-tag v-for="p in row.permission_codes" :key="p" size="small" style="margin: 2px">{{ p }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openRole(row)">编辑</el-button>
            <el-button link type="danger" @click="removeRole(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="部门管理" name="departments">
      <el-button type="primary" style="margin-bottom: 12px" @click="openDept()">新增部门</el-button>
      <el-table :data="departments" border>
        <el-table-column prop="department_name" label="部门名称" />
        <el-table-column label="上级部门" width="160">
          <template #default="{ row }">{{ deptName(row.parent_id) }}</template>
        </el-table-column>
        <el-table-column prop="user_count" label="人数" width="100" />
        <el-table-column prop="asset_count" label="在领资产" width="110" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDept(row)">编辑</el-button>
            <el-button link type="danger" @click="removeDept(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="资产分类" name="categories">
      <el-button type="primary" style="margin-bottom: 12px" @click="openCat()">新增分类</el-button>
      <el-table :data="categories" border>
        <el-table-column prop="category_name" label="分类名称" />
        <el-table-column prop="category_code" label="编码" width="150" />
        <el-table-column prop="description" label="说明" />
        <el-table-column prop="asset_count" label="资产数" width="100" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="openCat(row)">编辑</el-button>
            <el-button link type="danger" @click="removeCat(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
  </el-tabs>

  <el-dialog v-model="userVisible" :title="userForm.id ? '编辑用户' : '新增用户'" width="520px">
    <el-form :model="userForm" label-width="90px">
      <el-form-item label="账号" required>
        <el-input v-model="userForm.username" :disabled="!!userForm.id" />
      </el-form-item>
      <el-form-item label="密码" v-if="!userForm.id">
        <el-input v-model="userForm.password" placeholder="至少 6 位" />
      </el-form-item>
      <el-form-item label="姓名" required><el-input v-model="userForm.real_name" /></el-form-item>
      <el-form-item label="邮箱"><el-input v-model="userForm.email" /></el-form-item>
      <el-form-item label="手机"><el-input v-model="userForm.phone" /></el-form-item>
      <el-form-item label="部门">
        <el-select v-model="userForm.department_id" clearable style="width: 100%">
          <el-option v-for="d in departments" :key="d.id" :label="d.department_name" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="userForm.role_codes" multiple style="width: 100%">
          <el-option v-for="r in roles" :key="r.id" :label="r.role_name" :value="r.role_code" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="userVisible = false">取消</el-button>
      <el-button type="primary" @click="saveUser">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="roleVisible" :title="roleForm.id ? '编辑角色' : '新增角色'" width="600px">
    <el-form :model="roleForm" label-width="90px">
      <el-form-item label="角色名称"><el-input v-model="roleForm.role_name" /></el-form-item>
      <el-form-item label="编码" v-if="!roleForm.id"><el-input v-model="roleForm.role_code" /></el-form-item>
      <el-form-item label="说明"><el-input v-model="roleForm.description" /></el-form-item>
      <el-form-item label="权限">
        <el-checkbox-group v-model="roleForm.permission_codes">
          <el-checkbox v-for="p in permissions" :key="p.permission_code" :label="p.permission_code">
            {{ p.permission_name }}
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="roleVisible = false">取消</el-button>
      <el-button type="primary" @click="saveRole">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="deptVisible" :title="deptForm.id ? '编辑部门' : '新增部门'" width="420px">
    <el-form :model="deptForm" label-width="90px">
      <el-form-item label="部门名称"><el-input v-model="deptForm.department_name" /></el-form-item>
      <el-form-item label="上级部门">
        <el-select v-model="deptForm.parent_id" clearable style="width: 100%">
          <el-option v-for="d in departments.filter((x) => x.id !== deptForm.id)" :key="d.id" :label="d.department_name" :value="d.id" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="deptVisible = false">取消</el-button>
      <el-button type="primary" @click="saveDept">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="catVisible" :title="catForm.id ? '编辑分类' : '新增分类'" width="420px">
    <el-form :model="catForm" label-width="90px">
      <el-form-item label="分类名称"><el-input v-model="catForm.category_name" /></el-form-item>
      <el-form-item label="编码"><el-input v-model="catForm.category_code" :disabled="!!catForm.id" /></el-form-item>
      <el-form-item label="说明"><el-input v-model="catForm.description" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="catVisible = false">取消</el-button>
      <el-button type="primary" @click="saveCat">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const tab = ref('users')
const loading = ref(false)
const users = ref([])
const roles = ref([])
const permissions = ref([])
const departments = ref([])
const categories = ref([])
const userQuery = reactive({ keyword: '', department_id: '' })

const userVisible = ref(false)
const roleVisible = ref(false)
const deptVisible = ref(false)
const catVisible = ref(false)
const userForm = reactive({ id: null, username: '', password: '', real_name: '', email: '', phone: '', department_id: null, role_codes: ['USER'] })
const roleForm = reactive({ id: null, role_name: '', role_code: '', description: '', permission_codes: [] })
const deptForm = reactive({ id: null, department_name: '', parent_id: null })
const catForm = reactive({ id: null, category_name: '', category_code: '', description: '' })

function deptName(id) {
  return departments.value.find((d) => d.id === id)?.department_name || '-'
}

async function loadUsers() {
  loading.value = true
  try {
    const data = await api.users({ keyword: userQuery.keyword || undefined, department_id: userQuery.department_id || undefined, page_size: 100 })
    users.value = data.items
  } finally {
    loading.value = false
  }
}

function openUser(row) {
  Object.assign(userForm, row ? { ...row, password: '' } : { id: null, username: '', password: '', real_name: '', email: '', phone: '', department_id: null, role_codes: ['USER'] })
  userVisible.value = true
}

async function saveUser() {
  if (userForm.id) {
    await api.updateUser(userForm.id, {
      real_name: userForm.real_name,
      email: userForm.email || null,
      phone: userForm.phone || null,
      department_id: userForm.department_id,
      role_codes: userForm.role_codes,
    })
  } else {
    await api.createUser({ ...userForm })
  }
  ElMessage.success('已保存')
  userVisible.value = false
  loadUsers()
}

async function toggleStatus(row, value) {
  await api.setUserStatus(row.id, value ? 1 : 0)
  row.status = value ? 1 : 0
  ElMessage.success(value ? '已启用' : '已禁用')
}

async function reset(row) {
  const { value } = await ElMessageBox.prompt(`为 ${row.real_name} 设置新密码`, '重置密码', { inputValue: '123456' })
  await api.resetPassword(row.id, value)
  ElMessage.success('密码已重置')
}

async function removeUser(row) {
  await ElMessageBox.confirm(`删除用户 ${row.username}？`, '删除确认', { type: 'warning' })
  await api.deleteUser(row.id)
  ElMessage.success('已删除')
  loadUsers()
}

function openRole(row) {
  Object.assign(roleForm, row ? { ...row, permission_codes: [...row.permission_codes] } : { id: null, role_name: '', role_code: '', description: '', permission_codes: [] })
  roleVisible.value = true
}

async function saveRole() {
  if (roleForm.id) await api.updateRole(roleForm.id, { role_name: roleForm.role_name, description: roleForm.description, permission_codes: roleForm.permission_codes })
  else await api.createRole({ ...roleForm })
  ElMessage.success('已保存')
  roleVisible.value = false
  roles.value = await api.roles()
}

async function removeRole(row) {
  await ElMessageBox.confirm(`删除角色 ${row.role_name}？`, '删除确认', { type: 'warning' })
  await api.deleteRole(row.id)
  ElMessage.success('已删除')
  roles.value = await api.roles()
}

function openDept(row) {
  Object.assign(deptForm, row ? { id: row.id, department_name: row.department_name, parent_id: row.parent_id } : { id: null, department_name: '', parent_id: null })
  deptVisible.value = true
}

async function saveDept() {
  if (deptForm.id) await api.updateDepartment(deptForm.id, { department_name: deptForm.department_name, parent_id: deptForm.parent_id })
  else await api.createDepartment({ department_name: deptForm.department_name, parent_id: deptForm.parent_id })
  ElMessage.success('已保存')
  deptVisible.value = false
  departments.value = await api.departments()
}

async function removeDept(row) {
  await ElMessageBox.confirm(`删除部门 ${row.department_name}？`, '删除确认', { type: 'warning' })
  await api.deleteDepartment(row.id)
  ElMessage.success('已删除')
  departments.value = await api.departments()
}

function openCat(row) {
  Object.assign(catForm, row ? { id: row.id, category_name: row.category_name, category_code: row.category_code, description: row.description } : { id: null, category_name: '', category_code: '', description: '' })
  catVisible.value = true
}

async function saveCat() {
  if (catForm.id) await api.updateCategory(catForm.id, { category_name: catForm.category_name, category_code: catForm.category_code, description: catForm.description })
  else await api.createCategory({ category_name: catForm.category_name, category_code: catForm.category_code.toUpperCase(), description: catForm.description })
  ElMessage.success('已保存')
  catVisible.value = false
  categories.value = await api.categories()
}

async function removeCat(row) {
  await ElMessageBox.confirm(`删除分类 ${row.category_name}？`, '删除确认', { type: 'warning' })
  await api.deleteCategory(row.id)
  ElMessage.success('已删除')
  categories.value = await api.categories()
}

onMounted(async () => {
  await loadUsers()
  roles.value = await api.roles()
  permissions.value = await api.permissions()
  departments.value = await api.departments()
  categories.value = await api.categories()
})
</script>
