<script setup>
import { computed, watch } from 'vue'
import {
  movePiece,
  respond,
  showError,
  toggleReady,
  undo,
} from '../game.js'
import { useRoomView } from '../room.js'
import XiangqiBoard from './XiangqiBoard.vue'
import PlayerList from './room/PlayerList.vue'
import RequestBox from './room/RequestBox.vue'
import InviteBox from './room/InviteBox.vue'

const sideName = (s) => (s === 1 ? 'Đỏ' : 'Đen')

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
  sideName,
  isNeedReady: (r, isBotVal) => !isBotVal && r?.winner === 0 && !r?.waiting && !r?.started,
  confirmNewGame: 'Ván cờ chưa kết thúc. Mở ván mới giữa ván sẽ bị tính là bạn thua (trừ Elo). Bạn chắc chắn?',
  confirmLeave: 'Ván cờ chưa kết thúc. Rời phòng giữa ván sẽ bị tính là bạn thua (trừ Elo). Bạn chắc chắn?',
})

const canPlay = computed(() => playing.value && you.value === room.value?.current && (!isBot.value || !room.value?.botThinking))
watch(() => room.value?.notice, (notice) => {
  if (notice && notice !== 'Chiếu tướng!') {
    showError(notice)
  }
})

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
  <section v-if="room" class="game room-view">
    <div class="board-wrap">
      <XiangqiBoard :room="room" :can-play="canPlay" @move-piece="onMovePiece" />
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
        :get-side-dot="(s) => ({ label: s === 1 ? '帥' : '將', class: s === 1 ? 'red' : 'black' })"
      />
      <p v-if="!you" class="small muted">Bạn đang xem ván này.</p>

      <dl class="meta small">
        <div><dt>Phòng</dt><dd><strong>{{ room.code }}</strong></dd></div>
        <div><dt>Bàn cờ</dt><dd>10 hàng × 9 cột</dd></div>
        <div v-if="isBot"><dt>Độ khó</dt><dd>{{ room.levelName || 'Vừa' }}</dd></div>
        <div v-else><dt>Chế độ</dt><dd>Đấu người qua LAN</dd></div>
        <div><dt>Đã đánh</dt><dd>{{ room.moves || 0 }} nước</dd></div>
      </dl>

      <p v-if="stats" class="small muted stats">{{ stats }}</p>

      <InviteBox v-if="!isBot" :invite-link="inviteLink" :copied="copied" @copy="copyLink" />

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
