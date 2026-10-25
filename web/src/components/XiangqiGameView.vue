<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  leaveRoom,
  movePiece,
  respond,
  restart,
  showError,
  state,
  toggleReady,
  undo,
} from '../game.js'
import XiangqiBoard from './XiangqiBoard.vue'

const room = computed(() => state.room)
const you = computed(() => room.value?.you)
const isBot = computed(() => room.value?.mode === 'bot')
const playing = computed(() => room.value?.winner === 0 && !room.value?.waiting && room.value?.started)
const needReady = computed(() => !isBot.value && room.value?.winner === 0 && !room.value?.waiting && !room.value?.started)
const iAmReady = computed(() => room.value?.ready?.includes(you.value))
const canPlay = computed(() => playing.value && you.value === room.value?.current && (!isBot.value || !room.value?.botThinking))

const lanIps = ref([])
const copied = ref(false)
const now = ref(Date.now())
let ticker = null

onMounted(async () => {
  ticker = setInterval(() => { now.value = Date.now() }, 200)
  try {
    lanIps.value = (await (await fetch('/api/info')).json()).lan
  } catch { /* dùng mặc định */ }
})
onUnmounted(() => clearInterval(ticker))

watch(() => room.value?.notice, (notice) => {
  if (notice && notice !== 'Chiếu tướng!') {
    showError(notice)
  }
})

const request = computed(() => {
  const r = room.value?.request
  if (!r) return null
  const mine = r.side === you.value
  return {
    mine,
    canAnswer: !mine && you.value != null,
    text: mine ? 'Đang chờ đối thủ đồng ý cho bạn đi lại…'
               : `${player(r.side)?.name ?? sideName(r.side)} xin đi lại.`,
  }
})

const turnLeft = computed(() => {
  const r = room.value
  if (!r || r.turnLeft == null) return null
  return Math.max(0, Math.ceil(r.turnLeft - (now.value - (r.receivedAt || now.value)) / 1000))
})

const inviteLink = computed(() => {
  const local = ['localhost', '127.0.0.1', '::1', '[::1]'].includes(location.hostname)
  const host = local && lanIps.value.length
    ? `${lanIps.value[0]}${location.port ? `:${location.port}` : ''}`
    : location.host
  return `${location.protocol}//${host}/?room=${room.value?.code}`
})

async function copyLink() {
  try {
    await navigator.clipboard.writeText(inviteLink.value)
  } catch {
    const input = document.createElement('textarea')
    input.value = inviteLink.value
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    input.remove()
  }
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}

function handleNewGame() {
  const r = room.value
  if (!isBot.value && playing.value && r?.moves
      && !confirm('Ván cờ chưa kết thúc. Mở ván mới giữa ván sẽ bị tính là bạn thua (trừ Elo). Bạn chắc chắn?')) {
    return
  }
  restart()
}

function handleLeave() {
  const r = room.value
  if (!isBot.value && playing.value && r?.moves
      && !confirm('Ván cờ chưa kết thúc. Rời phòng giữa ván sẽ bị tính là bạn thua (trừ Elo). Bạn chắc chắn?')) {
    return
  }
  leaveRoom()
}

const player = (side) => room.value?.players?.[String(side)]
const sideName = (side) => (side === 1 ? 'Đỏ' : 'Đen')

const status = computed(() => {
  const r = room.value
  if (!r) return { text: '', tone: 'muted' }
  if (r.winner) {
    if (r.winner === -1) {
      return { text: 'Ván cờ kết thúc: Hòa cờ (Lặp lại 3 lần)', tone: 'blue' }
    }
    const who = player(r.winner)
    const mine = r.winner === you.value
    const name = sideName(r.winner)
    return {
      text: you.value ? (mine ? 'Bạn thắng! 🎉' : `${who?.name ?? name} thắng!`)
                      : `${who?.name ?? name} thắng!`,
      tone: mine ? 'green' : 'red',
    }
  }
  if (r.waiting) return { text: 'Đang chờ người chơi thứ hai…', tone: 'muted' }
  if (!r.started) return { text: 'Chờ hai bên bấm Sẵn sàng…', tone: 'muted' }
  if (r.botThinking) return { text: 'Bot cờ tướng đang tính toán…', tone: 'blue' }
  if (r.inCheck) {
    if (canPlay.value) return { text: 'BẠN ĐANG BỊ CHIẾU TƯỚNG!', tone: 'red' }
    return { text: 'Chiếu tướng!', tone: 'red' }
  }
  const other = player(r.current)
  if (other && !other.online) return { text: `${other.name} mất kết nối, đang chờ quay lại…`, tone: 'muted' }
  if (canPlay.value) return { text: `Lượt của bạn (${sideName(you.value)})`, tone: 'green' }
  return { text: `Lượt ${sideName(r.current)} · ${player(r.current)?.name ?? ''}`, tone: 'muted' }
})

const stats = computed(() => {
  const s = room.value?.stats
  if (!isBot.value || !s || !s.nodes) return ''
  return `Độ sâu ${s.depth} · ${s.nodes.toLocaleString('vi-VN')} nút · ${s.elapsed}s`
})

function onMovePiece(fr, fc, tr, tc) {
  movePiece(fr, fc, tr, tc)
}
</script>

<template>
  <section v-if="room" class="game">
    <div class="board-wrap">
      <XiangqiBoard :room="room" :can-play="canPlay" @move-piece="onMovePiece" />
    </div>

    <aside class="card side">
      <div class="status" :class="status.tone">{{ status.text }}</div>

      <button v-if="needReady && you" class="btn block" :class="iAmReady ? '' : 'green'"
              @click="toggleReady">
        {{ iAmReady ? 'Hủy sẵn sàng (đang chờ đối thủ)' : 'Sẵn sàng' }}
      </button>

      <div v-if="request" class="request" :class="{ ask: request.canAnswer }" role="status">
        <span>{{ request.text }}</span>
        <div v-if="request.canAnswer" class="row">
          <button class="btn green" @click="respond(true)">Đồng ý</button>
          <button class="btn red" @click="respond(false)">Từ chối</button>
        </div>
      </div>

      <ul class="players">
        <li v-for="side in [1, 2]" :key="side" :class="{ turn: playing && room.current === side }">
          <span class="dot" :class="side === 1 ? 'red' : 'black'">{{ side === 1 ? '帥' : '將' }}</span>
          <span class="pname">
            {{ player(side)?.name ?? 'Đang chờ…' }}
            <em v-if="side === you" class="small muted">(bạn)</em>
          </span>
          <span v-if="needReady && room.ready?.includes(side)" class="ready small">✓ Sẵn sàng</span>
          <span v-if="turnLeft != null && room.current === side" class="clock"
                :class="{ low: turnLeft <= 10 }" :title="`Mỗi lượt ${room.turnSeconds || 30} giây`">
            ⏱ {{ turnLeft }}s
          </span>
          <span v-if="player(side)?.elo != null" class="elo small">
            {{ player(side).elo }}
            <b v-if="player(side).eloDelta" :class="player(side).eloDelta > 0 ? 'up' : 'down'">
              {{ player(side).eloDelta > 0 ? '+' : '' }}{{ player(side).eloDelta }}
            </b>
          </span>
          <span v-if="player(side) && !player(side).bot" class="online"
                :class="{ off: !player(side).online }"
                :title="player(side).online ? 'Đang kết nối' : 'Mất kết nối'"></span>
        </li>
      </ul>
      <p v-if="!you" class="small muted">Bạn đang xem ván này.</p>

      <dl class="meta small">
        <div><dt>Phòng</dt><dd><strong>{{ room.code }}</strong></dd></div>
        <div><dt>Bàn cờ</dt><dd>10 hàng × 9 cột</dd></div>
        <div v-if="isBot"><dt>Độ khó</dt><dd>{{ room.levelName || 'Vừa' }}</dd></div>
        <div v-else><dt>Chế độ</dt><dd>Đấu người qua LAN</dd></div>
        <div><dt>Đã đánh</dt><dd>{{ room.moves || 0 }} nước</dd></div>
      </dl>
      <p v-if="stats" class="small muted stats">{{ stats }}</p>

      <div v-if="!isBot" class="invite">
        <span class="small muted">Gửi link này cho bạn cùng mạng LAN:</span>
        <div class="row">
          <input class="input small" readonly :value="inviteLink" @focus="$event.target.select()" />
          <button class="btn blue" @click="copyLink">{{ copied ? 'Đã chép' : 'Chép' }}</button>
        </div>
      </div>

      <div class="actions">
        <button class="btn green" :disabled="!you || !room.moves || request?.mine || (!isBot && !playing)"
                @click="undo">
          {{ isBot ? 'Hoàn tác' : 'Xin đi lại' }}
        </button>
        <button class="btn red" :disabled="!you" @click="handleNewGame">Ván mới</button>
        <button class="btn" @click="handleLeave">Rời phòng</button>
      </div>
      <p v-if="!isBot && you" class="small muted">
        Ván đấu người được tính elo. Mỗi lượt có {{ room.turnSeconds || 30 }} giây; hết giờ, rời phòng hoặc
        bấm "Ván mới" khi ván chưa xong thì bị tính thua. Mỗi ván mới hai bên đổi quân.
      </p>
    </aside>
  </section>
</template>

<style scoped>
.game {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
  align-items: start;
}
.board-wrap { min-width: 0; }
.side { display: grid; gap: 14px; position: sticky; top: 16px; }
.status { font-size: 1.15rem; font-weight: 700; text-align: center; padding: 6px 0; }
.status.green { color: var(--green); }
.status.red { color: var(--red); }
.status.blue { color: var(--blue); }
.status.muted { color: var(--muted); }
.request {
  display: grid;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px dashed var(--panel-border);
  color: var(--muted);
  text-align: center;
}
.request.ask { border: 2px solid var(--accent); color: var(--text); font-weight: 600; }
.players { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.players li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--panel-border);
}
.players li.turn { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }
.dot {
  width: 28px; height: 28px; border-radius: 50%;
  display: grid; place-items: center;
  color: #fff; font-weight: 700; font-size: 0.85rem; flex: none;
}
.dot.red { background: #c82323; }
.dot.black { background: #2b2a27; }
.pname { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ready { color: var(--green); font-weight: 700; white-space: nowrap; }
.clock { font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }
.clock.low { color: var(--red); }
.elo { color: var(--muted); white-space: nowrap; }
.elo .up { color: var(--green); }
.elo .down { color: var(--red); }
.online { width: 9px; height: 9px; border-radius: 50%; background: #2fae62; flex: none; }
.online.off { background: #b9b2a6; }
.meta { margin: 0; display: grid; gap: 4px; }
.meta div { display: flex; justify-content: space-between; gap: 8px; }
.meta dt { color: var(--muted); }
.meta dd { margin: 0; text-align: right; }
.stats { margin: 0; }
.invite { display: grid; gap: 6px; }
.invite .row > .btn { flex: none; }
.actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 8px; }
@media (max-width: 860px) {
  .game { grid-template-columns: 1fr; }
  .side { position: static; }
}
</style>
