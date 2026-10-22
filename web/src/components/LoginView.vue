<script setup>
import { ref } from 'vue'
import { login, register } from '../game.js'

const mode = ref('login')
const username = ref('')
const password = ref('')
const error = ref('')
const info = ref('')
const busy = ref(false)

async function submit() {
  error.value = info.value = ''
  busy.value = true
  try {
    if (mode.value === 'login') {
      await login(username.value, password.value)
    } else {
      await register(username.value, password.value)
      mode.value = 'login'
      password.value = ''
      info.value = 'Đã gửi đăng ký. Bạn đăng nhập được sau khi admin phê duyệt.'
    }
  } catch (exc) {
    error.value = exc.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="card login" @submit.prevent="submit">
    <div class="segmented">
      <button type="button" :class="{ active: mode === 'login' }" @click="mode = 'login'">Đăng nhập</button>
      <button type="button" :class="{ active: mode === 'register' }" @click="mode = 'register'">Đăng ký</button>
    </div>
    <label class="field">
      <span>Tên đăng nhập</span>
      <input v-model="username" class="input" autocomplete="username" required maxlength="20" />
    </label>
    <label class="field">
      <span>Mật khẩu</span>
      <input v-model="password" class="input" type="password" required
             :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" />
    </label>
    <p v-if="mode === 'register'" class="small muted">
      Tên 3–20 ký tự (chữ không dấu, số, dấu _), mật khẩu ít nhất 6 ký tự.
    </p>
    <p v-if="error" class="err" role="alert">{{ error }}</p>
    <p v-if="info" class="ok" role="status">{{ info }}</p>
    <button class="btn green block" :disabled="busy">
      {{ mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản' }}
    </button>
  </form>
</template>

<style scoped>
.login { max-width: 380px; margin: 40px auto; display: grid; gap: 4px; }
.segmented { margin-bottom: 14px; }
.err { color: var(--red); margin: 0 0 10px; }
.ok { color: var(--green); margin: 0 0 10px; }
</style>
