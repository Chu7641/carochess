<script setup>
import { ref } from 'vue'
import { changePassword } from '../game.js'

const current = ref('')
const next = ref('')
const again = ref('')
const error = ref('')
const done = ref(false)
const busy = ref(false)

async function submit() {
  error.value = ''
  if (next.value !== again.value) {
    error.value = 'Hai lần nhập mật khẩu mới không khớp.'
    return
  }
  busy.value = true
  try {
    await changePassword(current.value, next.value)
    done.value = true
    current.value = next.value = again.value = ''
  } catch (exc) {
    error.value = exc.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="card password" @submit.prevent="submit">
    <h2>Đổi mật khẩu</h2>
    <label class="field">
      <span>Mật khẩu hiện tại</span>
      <input v-model="current" class="input" type="password" autocomplete="current-password" required />
    </label>
    <label class="field">
      <span>Mật khẩu mới (ít nhất 6 ký tự)</span>
      <input v-model="next" class="input" type="password" autocomplete="new-password" required minlength="6" />
    </label>
    <label class="field">
      <span>Nhập lại mật khẩu mới</span>
      <input v-model="again" class="input" type="password" autocomplete="new-password" required />
    </label>
    <p v-if="error" class="err" role="alert">{{ error }}</p>
    <p v-if="done" class="ok" role="status">Đã đổi mật khẩu. Các thiết bị khác đã bị đăng xuất.</p>
    <button class="btn green block" :disabled="busy">Đổi mật khẩu</button>
  </form>
</template>

<style scoped>
.password { max-width: 380px; margin: 24px auto; }
.err { color: var(--red); margin: 0 0 10px; }
.ok { color: var(--green); margin: 0 0 10px; }
</style>
