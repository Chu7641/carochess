<script setup>
import { computed, ref, watch } from 'vue'
import {
  move,
  passTurn,
  respond,
  showError,
  toggleReady,
  undo,
} from '../game.js'
import { useRoomView } from '../room.js'
import GoBoard from './GoBoard.vue'
import PlayerList from './room/PlayerList.vue'
import RequestBox from './room/RequestBox.vue'
import InviteBox from './room/InviteBox.vue'

const {
  room,
  you,
  isBot,
  playing,
  needReady,
  iAmReady,
  now,
  turnLeft,
  inviteLink,
  copied,
  copyLink,
  player,
  request,
  handleNewGame,
  handleLeave,
} = useRoomView({
  sideName: (s) => (s === 1 ? 'Đen' : 'Trắng'),
})

const canPlay = computed(() => playing.value && you.value === room.value?.current)
const thinkingSince = ref(0)

watch(() => room.value?.botThinking, (on) => { if (on) thinkingSince.value = Date.now() },
      { immediate: true })
watch(() => room.value?.notice, (notice) => { if (notice) showError(notice) })

const status = computed(() => {
  const r = room.value
  if (!r) return { text: '', tone: 'muted' }
  if (r.winner === -1) return { text: 'Ván cờ hòa', tone: 'blue' }
  if (r.winner) {
    const who = player(r.winner)
    const mine = r.winner === you.value
    const name = r.winner === 1 ? 'Đen' : 'Trắng'
    return {
      text: you.value ? (mine ? 'Bạn thắng! 🎉' : `${who?.name ?? name} thắng`)
                      : `${who?.name ?? name} thắng`,
      tone: mine ? 'green' : 'red',
    }
  }
  if (r.waiting) return { text: 'Đang chờ người chơi thứ hai…', tone: 'muted' }
  if (!r.started) return { text: 'Chờ hai bên bấm Sẵn sàng…', tone: 'muted' }
  if (r.botThinking) {
    const seconds = Math.max(0, (now.value - thinkingSince.value) / 1000)
    return { text: `Máy đang tính… ${seconds.toFixed(1)}s`, tone: 'blue' }
  }
  const other = player(r.current)
  if (other && !other.online) return { text: `${other.name} mất kết nối, đang chờ quay lại…`, tone: 'muted' }
  const currentName = r.current === 1 ? 'Đen' : 'Trắng'
  if (r.current === you.value) return { text: `Lượt của bạn (${currentName})`, tone: 'green' }
  return { text: `Lượt ${currentName} · ${other?.name ?? ''}`, tone: 'muted' }
})

const stats = computed(() => {
  const s = room.value?.stats
  if (!isBot.value || !s || !s.nodes) return ''
  return `Đã duyệt ${s.nodes.toLocaleString('vi-VN')} nút · ${s.elapsed}s`
})

function onPlay(r, c) {
  move(r, c)
}

function onPass() {
  if (confirm('Bạn có chắc chắn muốn bỏ lượt? (Nếu cả hai bên cùng bỏ lượt, ván cờ sẽ kết thúc để tính điểm)')) {
    passTurn()
  }
}
</script>

<template>
  <section v-if="room" class="game room-view">
    <div class="board-wrap">
      <GoBoard :room="room" :can-play="canPlay" :ghost-side="you || 1" @play="onPlay" />
    </div>

    <aside class="card side">
      <div class="status" :class="status.tone">{{ status.text }}</div>

      <button v-if="needReady && you" class="btn block" :class="iAmReady ? '' : 'green'"
              @click="toggleReady">
        {{ iAmReady ? 'Hủy sẵn sàng (đang chờ đối thủ)' : 'Sẵn sàng' }}
      </button>

      <RequestBox :request="request" @respond="respond" />

      <PlayerList
        :sides="[1, 2]"
        :room="room"
        :you="you"
        :turn-left="turnLeft"
        :playing="playing"
        :need-ready="needReady"
        :get-side-dot="(s) => ({ label: s === 1 ? 'Đ' : 'T', class: s === 1 ? 'black' : 'white' })"
      />
      <p v-if="!you" class="small muted">Bạn đang xem ván này.</p>

      <dl class="meta small">
        <div><dt>Phòng</dt><dd><strong>{{ room.code }}</strong></dd></div>
        <div><dt>Bàn</dt><dd>{{ room.size || room.rows }} × {{ room.size || room.cols }}</dd></div>
        <div><dt>Komi</dt><dd>{{ room.komi }}</dd></div>
        <div v-if="isBot"><dt>Độ khó</dt><dd>{{ room.levelName }}</dd></div>
        <div><dt>Đã đánh</dt><dd>{{ room.moves }} nước</dd></div>
        <div><dt>Tù binh Đen bắt</dt><dd>{{ room.captured?.['1'] ?? 0 }}</dd></div>
        <div><dt>Tù binh Trắng bắt</dt><dd>{{ room.captured?.['2'] ?? 0 }}</dd></div>
      </dl>

      <!-- Bảng tổng kết điểm Tromp-Taylor khi có kết quả tính điểm -->
      <div v-if="room.score" class="score-summary card small">
        <strong>Kết quả đếm điểm diện tích</strong>
        <div class="row">
          <span>Đen: <b>{{ room.score.black?.total }}</b></span>
          <span>Trắng: <b>{{ room.score.white?.total }}</b></span>
        </div>
        <span class="muted">{{ room.winner === 1 ? 'Đen' : 'Trắng' }} thắng cách biệt {{ room.score.margin }} mục</span>
      </div>

      <p v-if="stats" class="small muted stats">{{ stats }}</p>

      <InviteBox v-if="!isBot" :invite-link="inviteLink" :copied="copied" @copy="copyLink" />

      <div class="actions">
        <button class="btn green" :disabled="!you || !room.moves || request?.mine || (!isBot && !playing)"
                @click="undo">
          {{ isBot ? 'Hoàn tác' : 'Xin đi lại' }}
        </button>
        <button v-if="canPlay" class="btn blue" @click="onPass">Bỏ lượt</button>
        <button class="btn red" :disabled="!you" @click="handleNewGame">Ván mới</button>
        <button class="btn" @click="handleLeave">Rời phòng</button>
      </div>
      <p v-if="!isBot && you" class="small muted">
        Ván đấu người được tính elo. Mỗi lượt có {{ room.turnSeconds }} giây; hết giờ, rời phòng hoặc
        bấm "Ván mới" khi ván chưa xong thì bị tính thua. Mỗi ván mới hai bên đổi quân.
      </p>
    </aside>
  </section>
</template>

<style scoped>
.score-summary {
  display: grid;
  gap: 8px;
  background: var(--bg);
  padding: 10px 12px;
}
.score-summary strong { color: var(--text); }
</style>
