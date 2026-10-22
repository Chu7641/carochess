// Tài khoản + kết nối WebSocket dùng chung cho cả ứng dụng. Giao thức: xem server/app.py.
import { reactive } from 'vue'

export const X = 1
export const O = 2
export const sideName = (side) => (side === X ? 'X' : side === O ? 'O' : '')

function load(key) {
  try { return localStorage.getItem(key) } catch { return null }
}
function save(key, value) {
  try {
    if (value == null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch { /* chế độ ẩn danh: bỏ qua */ }
}

export const state = reactive({
  user: null,      // {id, username, isAdmin} sau khi đăng nhập
  checked: false,  // đã hỏi máy chủ xem còn phiên đăng nhập chưa
  game: load('caro.game'),  // trò chơi đang chọn; null: màn chọn trò chơi
  connected: false,
  code: null,   // mã phòng đang ở
  room: null,   // trạng thái phòng do máy chủ gửi
  error: '',
})

let ws = null
let retry = 0
let pending = []
let errorTimer = null

export function showError(message) {
  state.error = message
  clearTimeout(errorTimer)
  errorTimer = setTimeout(() => { state.error = '' }, 4000)
}

// ---------- tài khoản ----------
export async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Có lỗi xảy ra.')
  return data
}

export async function checkSession() {
  try { state.user = await api('/api/me') } catch { state.user = null }
  state.checked = true
  if (state.user) connect()
}

export async function login(username, password) {
  state.user = await api('/api/login', { username, password })
  connect()
}

export const changePassword = (current, next) => api('/api/password', { current, new: next })

// Tài khoản mới chờ admin duyệt, chưa đăng nhập được ngay.
export const register = (username, password) => api('/api/register', { username, password })

export async function logout() {
  await api('/api/logout', {}).catch(() => {})
  state.user = state.code = state.room = null
  ws?.close()
}

export function chooseGame(game) {
  state.game = game
  save('caro.game', game)
}

// ---------- WebSocket ----------
function url() {
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg))
  else pending.push(msg)
}

function setRoomInUrl(code) {
  const next = new URL(location.href)
  if (code) next.searchParams.set('room', code)
  else next.searchParams.delete('room')
  history.replaceState(null, '', next)
}

function handle(msg) {
  if (msg.type === 'joined') {
    state.code = msg.room
    setRoomInUrl(msg.room)
  } else if (msg.type === 'state') {
    msg.room.receivedAt = Date.now()  // turnLeft tính từ lúc nhận, đồng hồ máy chủ có thể lệch
    if (msg.room.code === state.code) state.room = msg.room
    const elo = msg.room.players[msg.room.you]?.elo  // elo mới sau mỗi ván
    if (elo != null && state.user) state.user.elo = elo
  } else if (msg.type === 'error') {
    showError(msg.message)
    // Vào phòng thất bại (mã sai, phòng đã bị xóa): quay lại sảnh.
    if (!state.room) { state.code = null; setRoomInUrl(null) }
  }
}

function connect() {
  if (ws) return
  ws = new WebSocket(url())
  ws.onopen = () => {
    state.connected = true
    retry = 0
    // Mất mạng rồi kết nối lại: vào lại phòng cũ (ghế gắn với tài khoản).
    const queued = pending
    pending = []
    if (state.code && !queued.some((m) => m.type === 'join' || m.type === 'create')) {
      joinRoom(state.code)
    }
    queued.forEach(send)
  }
  ws.onmessage = (event) => handle(JSON.parse(event.data))
  ws.onclose = (event) => {
    state.connected = false
    ws = null
    if (event.code === 4401) state.user = null  // phiên đăng nhập hết hạn
    if (state.user) setTimeout(connect, Math.min(5000, 500 * 2 ** retry++))
  }
}

// ---------- phòng ----------
export function createRoom(options) {
  state.room = null
  send({ type: 'create', ...options })
}

export function joinRoom(code) {
  code = String(code || '').trim().toUpperCase()
  if (!code) return
  if (code !== state.code) state.room = null
  state.code = code
  send({ type: 'join', room: code })
}

export function leaveRoom() {
  send({ type: 'leave' })
  state.code = state.room = null
  setRoomInUrl(null)
}

export const move = (r, c) => send({ type: 'move', r, c })
export const undo = () => send({ type: 'undo' })
export const restart = () => send({ type: 'restart' })
export const respond = (accept) => send({ type: 'respond', accept })
export const toggleReady = () => send({ type: 'ready' })