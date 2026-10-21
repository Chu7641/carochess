// Kết nối WebSocket dùng chung cho cả ứng dụng. Giao thức: xem server/app.py.
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
  connected: false,
  code: null,   // mã phòng đang ở
  side: null,   // X, O hoặc null (người xem)
  room: null,   // trạng thái phòng do máy chủ gửi
  error: '',
  name: load('caro.name') || '',
})

let ws = null
let retry = 0
let pending = []
let errorTimer = null

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

function showError(message) {
  state.error = message
  clearTimeout(errorTimer)
  errorTimer = setTimeout(() => { state.error = '' }, 4000)
}

function handle(msg) {
  if (msg.type === 'joined') {
    state.code = msg.room
    state.side = msg.side
    if (msg.token) save(`caro.seat.${msg.room}`, msg.token)
    setRoomInUrl(msg.room)
  } else if (msg.type === 'state') {
    if (msg.room.code === state.code) state.room = msg.room
  } else if (msg.type === 'error') {
    showError(msg.message)
    // Vào phòng thất bại (mã sai, phòng đã bị xóa): quay lại sảnh.
    if (!state.room) { state.code = null; setRoomInUrl(null) }
  }
}

export function connect() {
  ws = new WebSocket(url())
  ws.onopen = () => {
    state.connected = true
    retry = 0
    // Mất mạng rồi kết nối lại: vào lại phòng cũ bằng token đã lưu.
    const queued = pending
    pending = []
    if (state.code && !queued.some((m) => m.type === 'join' || m.type === 'create')) {
      joinRoom(state.code)
    }
    queued.forEach(send)
  }
  ws.onmessage = (event) => handle(JSON.parse(event.data))
  ws.onclose = () => {
    state.connected = false
    ws = null
    setTimeout(connect, Math.min(5000, 500 * 2 ** retry++))
  }
}

export function setName(name) {
  state.name = name
  save('caro.name', name.trim() || null)
}

const playerName = () => state.name.trim() || 'Người chơi'

export function createRoom(options) {
  state.room = null
  send({ type: 'create', name: playerName(), ...options })
}

export function joinRoom(code) {
  code = String(code || '').trim().toUpperCase()
  if (!code) return
  if (code !== state.code) state.room = null
  state.code = code
  send({ type: 'join', room: code, name: playerName(), token: load(`caro.seat.${code}`) })
}

export function leaveRoom() {
  send({ type: 'leave' })
  state.code = state.side = state.room = null
  setRoomInUrl(null)
}

export const move = (r, c) => send({ type: 'move', r, c })
export const undo = () => send({ type: 'undo' })
export const restart = () => send({ type: 'restart' })
