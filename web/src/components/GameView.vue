<script setup>
import { computed, ref, watch } from 'vue'
import { move, respond, showError, sideName, toggleReady, undo, X, O } from '../game.js'
import { useRoomView } from '../room.js'
import CaroBoard from './CaroBoard.vue'
import PlayerList from './room/PlayerList.vue'
import RequestBox from './room/RequestBox.vue'
import InviteBox from './room/InviteBox.vue'
import ResultPopup from './room/ResultPopup.vue'

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
  result,
  closeResult,
} = useRoomView({ sideName })

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
    return {
      text: you.value ? (mine ? 'Bạn thắng! 🎉' : `${who?.name ?? sideName(r.winner)} thắng`)
                      : `${sideName(r.winner)} thắng`,
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
  if (r.current === you.value) return { text: `Lượt của bạn (${sideName(you.value)})`, tone: 'green' }
  return { text: `Lượt ${sideName(r.current)} · ${other?.name ?? ''}`, tone: 'muted' }
})

const stats = computed(() => {
  const s = room.value?.stats
  if (!isBot.value || !s || (!s.depth && !s.proven)) return ''
  if (s.proven && s.forcingPlies) return `Máy tìm thấy chuỗi ép thắng ${s.forcingPlies} nước`
  return `Độ sâu ${s.depth} · ${s.nodes.toLocaleString('vi-VN')} nút · ${s.elapsed}s`
})
</script>

<template>
  <section v-if="room" class="game room-view">
    <div class="board-wrap">
      <CaroBoard :room="room" :can-play="canPlay" :ghost-side="you || X" @play="move" />
    </div>

    <aside class="card side">
      <div class="status" :class="status.tone">{{ status.text }}</div>

      <button v-if="needReady && you" class="btn block" :class="iAmReady ? '' : 'green'"
              @click="toggleReady">
        {{ iAmReady ? 'Hủy sẵn sàng (đang chờ đối thủ)' : 'Sẵn sàng' }}
      </button>

      <RequestBox :request="request" @respond="respond" />

      <PlayerList
        :sides="[X, O]"
        :room="room"
        :you="you"
        :turn-left="turnLeft"
        :playing="playing"
        :need-ready="needReady"
        :get-side-dot="(s) => ({ label: sideName(s), class: s === X ? 'x' : 'o' })"
      />
      <p v-if="!you" class="small muted">Bạn đang xem ván này.</p>

      <dl class="meta small">
        <div><dt>Phòng</dt><dd><strong>{{ room.code }}</strong></dd></div>
        <div><dt>Bàn</dt><dd>{{ room.rows }} × {{ room.cols }} · thắng {{ room.winLength }}</dd></div>
        <div><dt>Luật</dt><dd>{{ room.strict ? 'Chặn hai đầu không thắng' : 'Tự do' }}</dd></div>
        <div v-if="isBot"><dt>Độ khó</dt><dd>{{ room.levelName }}</dd></div>
        <div><dt>Đã đánh</dt><dd>{{ room.moves }} nước</dd></div>
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
        Ván đấu người được tính elo. Mỗi lượt có {{ room.turnSeconds }} giây; hết giờ, rời phòng hoặc
        bấm "Ván mới" khi ván chưa xong thì bị tính thua. Mỗi ván mới hai bên đổi quân.
      </p>
    </aside>

    <ResultPopup :result="result" @close="closeResult" @new-game="closeResult(); handleNewGame()" />
  </section>
</template>
