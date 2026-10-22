<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, showError, state } from '../game.js'

const users = ref([])
const busy = ref(null)       // id tài khoản đang xử lý
const newPassword = ref(null) // {username, password} sau khi reset

const pending = computed(() => users.value.filter((u) => !u.approved))
const members = computed(() => users.value.filter((u) => u.approved))

async function load() {
  try { users.value = await api('/api/admin/users') } catch (exc) { showError(exc.message) }
}

const CONFIRM = {
  reject: (u) => `Từ chối và xóa đăng ký của "${u.username}"?`,
  'make-admin': (u) => `Nâng "${u.username}" thành admin? Họ sẽ có toàn quyền quản trị.`,
  'reset-password': (u) => `Đặt lại mật khẩu cho "${u.username}"? Họ sẽ bị đăng xuất.`,
  delete: (u) => `Xóa vĩnh viễn tài khoản "${u.username}"? Không thể hoàn tác.`,
  'reset-elo': (u) => `Đưa elo của "${u.username}" (${u.elo}) về 1000?`,
}

async function act(user, action) {
  if (CONFIRM[action] && !confirm(CONFIRM[action](user))) return
  busy.value = user.id
  try {
    const res = await api(`/api/admin/users/${user.id}/${action}`, {})
    if (res.password) newPassword.value = { username: user.username, password: res.password }
    await load()
  } catch (exc) {
    showError(exc.message)
  } finally {
    busy.value = null
  }
}

const date = (seconds) => new Date(seconds * 1000).toLocaleString('vi-VN')
onMounted(load)
</script>

<template>
  <section class="admin">
    <div v-if="newPassword" class="card notice" role="status">
      Mật khẩu mới của <strong>{{ newPassword.username }}</strong>:
      <code>{{ newPassword.password }}</code>
      <span class="small muted">Gửi mật khẩu này cho người dùng; trang sẽ không hiện lại.</span>
      <button class="btn small" @click="newPassword = null">Đã ghi lại</button>
    </div>

    <div class="card">
      <h2>Chờ phê duyệt <span class="count">{{ pending.length }}</span></h2>
      <p v-if="!pending.length" class="small muted">Không có đăng ký nào đang chờ.</p>
      <table v-else>
        <thead><tr><th>Tên đăng nhập</th><th>Đăng ký lúc</th><th></th></tr></thead>
        <tbody>
          <tr v-for="u in pending" :key="u.id">
            <td>{{ u.username }}</td>
            <td class="muted">{{ date(u.created) }}</td>
            <td class="actions">
              <button class="btn green small" :disabled="busy === u.id" @click="act(u, 'approve')">Duyệt</button>
              <button class="btn red small" :disabled="busy === u.id" @click="act(u, 'reject')">Từ chối</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>Người dùng <span class="count">{{ members.length }}</span></h2>
      <table>
        <thead><tr><th>Tên đăng nhập</th><th>Vai trò</th><th>Elo</th><th>Tạo lúc</th><th></th></tr></thead>
        <tbody>
          <tr v-for="u in members" :key="u.id">
            <td>{{ u.username }} <em v-if="u.id === state.user.id" class="small muted">(bạn)</em></td>
            <td><span class="role" :class="{ admin: u.isAdmin }">{{ u.isAdmin ? 'Admin' : 'Người chơi' }}</span></td>
            <td>{{ u.elo }}</td>
            <td class="muted">{{ date(u.created) }}</td>
            <td class="actions">
              <button v-if="!u.isAdmin" class="btn blue small" :disabled="busy === u.id"
                      @click="act(u, 'make-admin')">Nâng lên admin</button>
              <button class="btn small" :disabled="busy === u.id" @click="act(u, 'reset-password')">
                Reset mật khẩu
              </button>
              <button class="btn small" :disabled="busy === u.id || u.elo === 1000"
                      @click="act(u, 'reset-elo')">Reset elo</button>
              <button v-if="u.id !== state.user.id" class="btn red small" :disabled="busy === u.id"
                      @click="act(u, 'delete')">Xóa</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.admin { max-width: 920px; margin: 0 auto; display: grid; gap: 16px; }
.count { font-size: 0.8rem; background: var(--grey); color: #fff; border-radius: 999px; padding: 1px 8px; vertical-align: middle; }
.notice { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; border-color: var(--accent); }
.notice code { font-size: 1.1rem; font-weight: 700; padding: 2px 8px; border-radius: 6px; background: var(--bg); user-select: all; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; font-size: 0.8rem; color: var(--muted); font-weight: 600; }
th, td { padding: 8px 6px; border-bottom: 1px solid var(--panel-border); }
.actions { display: flex; gap: 6px; justify-content: flex-end; flex-wrap: wrap; }
.btn.small { padding: 5px 10px; font-size: 0.85rem; }
.role { font-size: 0.8rem; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--panel-border); }
.role.admin { background: var(--accent); border-color: var(--accent); color: #2b2a27; font-weight: 700; }
@media (max-width: 640px) {
  th:nth-child(4), td:nth-child(4) { display: none; }
}
</style>
