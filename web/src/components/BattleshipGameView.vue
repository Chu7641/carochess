<script setup>
import { computed, watch } from 'vue'
import { fire, placeRandom, placeShips, showError } from '../game.js'
import { useRoomView } from '../room.js'
import BattleshipShip from './BattleshipShip.vue'
import PlacementPanel from './battleship/PlacementPanel.vue'
import BattlePanel from './battleship/BattlePanel.vue'
import PlayerList from './room/PlayerList.vue'
import InviteBox from './room/InviteBox.vue'
import ResultPopup from './room/ResultPopup.vue'

const {
  room,
  you,
  isBot,
  turnLeft,
  inviteLink,
  copied,
  copyLink,
  player,
  handleNewGame,
  handleLeave,
  result,
  closeResult,
} = useRoomView({
  isPlaying: (r) => r?.phase === 'playing',
  confirmNewGame: 'Trận chiến chưa kết thúc. Mở ván mới giữa trận sẽ bị tính là bạn thua (trừ Elo). Bạn chắc chắn?',
  confirmLeave: 'Trận chiến chưa kết thúc. Rời phòng giữa trận sẽ bị tính là bạn thua (trừ Elo). Bạn chắc chắn?',
})

const phase = computed(() => room.value?.phase)
const myFleet = computed(() => room.value?.myFleet)
const opponentBoard = computed(() => room.value?.opponentBoard)
const lastShot = computed(() => room.value?.lastShot)

const canShoot = computed(() =>
  phase.value === 'playing' &&
  you.value != null &&
  you.value === room.value?.current &&
  (!isBot.value || !room.value?.botThinking)
)

const iAmPlaced = computed(() => {
  if (!you.value) return false
  return room.value?.placed?.includes(you.value) || room.value?.ready?.includes(you.value)
})

watch(() => room.value?.notice, (notice) => {
  if (notice && !notice.includes('Trúng') && !notice.includes('trúng') &&
      !notice.includes('Đánh chìm') && !notice.includes('đánh chìm') &&
      !notice.includes('Trượt') && !notice.includes('trượt') &&
      !notice.includes('bắt đầu') && !notice.includes('Bắt đầu')) {
    showError(notice)
  }
})

function onConfirmPlacement(ships) {
  if (ships) {
    placeShips(ships)
  } else {
    placeRandom()
  }
}

function onShoot(r, c) {
  fire(r, c)
}

const playerStats = computed(() => {
  if (!opponentBoard.value) return { shots: 0, hits: 0, accuracy: 0 }
  const hits = opponentBoard.value.hits?.length || 0
  const misses = opponentBoard.value.misses?.length || 0
  const shots = hits + misses
  const accuracy = shots > 0 ? Math.round((hits / shots) * 100) : 0
  return { shots, hits, accuracy }
})

const myShipsList = computed(() => {
  if (room.value?.shipsLeft && you.value) {
    return room.value.shipsLeft[String(you.value)] || []
  }
  return []
})

const opponentShipsList = computed(() => {
  if (room.value?.shipsLeft && you.value) {
    return room.value.shipsLeft[String(3 - you.value)] || []
  }
  return []
})

const status = computed(() => {
  const r = room.value
  if (!r) return { text: '', tone: 'muted' }
  if (r.winner) {
    if (you.value) {
      const mine = r.winner === you.value
      return {
        text: mine ? 'Bạn toàn thắng! 🎉 Tiêu diệt hạm đội địch' : 'Thất trận! Hạm đội của bạn đã chìm',
        tone: mine ? 'green' : 'red',
      }
    }
    const who = player(r.winner)
    const name = who?.name ?? `Bên ${r.winner}`
    return {
      text: `${name} toàn thắng! 🎉`,
      tone: 'green',
    }
  }
  if (r.waiting) {
    return { text: 'Đang chờ người chơi thứ hai…', tone: 'muted' }
  }
  if (phase.value === 'placing') {
    if (!you.value) {
      return { text: 'Đang chờ hai bên xếp hạm đội…', tone: 'muted' }
    }
    if (iAmPlaced.value) {
      return { text: 'Bạn đã xếp tàu xong, đang chờ đối thủ…', tone: 'blue' }
    }
    return { text: 'Giai đoạn dàn quân: Xếp 5 tàu vào vị trí', tone: 'blue' }
  }
  if (r.botThinking) {
    return { text: 'Bot đang ngắm bắn…', tone: 'blue' }
  }
  if (canShoot.value) {
    return { text: 'Lượt của bạn — bắn đi!', tone: 'green' }
  }
  const curPlayer = player(r.current)
  const curName = curPlayer?.name ?? `Bên ${r.current}`
  return { text: `Lượt của ${curName}`, tone: 'muted' }
})
</script>

<template>
  <section v-if="room" class="game room-view">
    <div class="board-wrap">
      <!-- Giai đoạn 1: Dàn quân / Xếp tàu -->
      <PlacementPanel
        v-if="phase === 'placing' && you"
        :i-am-placed="iAmPlaced"
        :my-fleet="myFleet"
        @confirm="onConfirmPlacement"
      />

      <!-- Người xem trong giai đoạn xếp tàu -->
      <div v-else-if="phase === 'placing' && !you" class="card placing-spectator">
        <h3>⚓ Giai đoạn xếp tàu</h3>
        <p class="muted">
          Hai bên đang tiến hành bố trí hạm đội vào vùng biển bí mật. Trận chiến sẽ bắt đầu khi cả hai bên sẵn sàng.
        </p>
      </div>

      <!-- Giai đoạn 2: Chiến đấu hoặc Người xem -->
      <BattlePanel
        v-else
        :room="room"
        :you="you"
        :can-shoot="canShoot"
        :last-shot="lastShot"
        @shoot="onShoot"
      />
    </div>

    <!-- Cột bên phải (aside 320px) -->
    <aside class="card side">
      <div class="status" :class="status.tone">{{ status.text }}</div>

      <!-- Thông báo diễn biến -->
      <div v-if="room.notice" class="notice-banner">
        <span>{{ room.notice }}</span>
      </div>

      <!-- Danh sách người chơi -->
      <PlayerList
        :sides="[1, 2]"
        :room="room"
        :you="you"
        :turn-left="phase === 'playing' ? turnLeft : null"
        :playing="phase === 'playing'"
        :get-side-dot="(s) => ({ label: String(s), class: s === 1 ? 'blue' : 'red' })"
      >
        <template #status="{ side }">
          <span v-if="phase === 'placing'" class="placed-status small">
            <template v-if="room.placed?.includes(side) || room.ready?.includes(side)">
              <span class="ready">✓ Đã xếp</span>
            </template>
            <template v-else-if="player(side)">
              <span class="muted">Đang xếp…</span>
            </template>
          </span>
        </template>
      </PlayerList>
      <p v-if="!you" class="small muted">Bạn đang xem ván này.</p>

      <!-- Hạm đội hai bên trong một bảng gọn, để nút Ván mới / Rời phòng không bị đẩy xuống -->
      <table v-if="you" class="fleet-table small">
        <thead>
          <tr><th>Tàu</th><th>Bạn</th><th>Đối thủ</th></tr>
        </thead>
        <tbody>
          <tr v-for="(ship, i) in myShipsList" :key="ship.name">
            <td>
              <span class="fleet-ship-mini">
                <BattleshipShip :name="ship.name" :len="ship.len" state="normal" />
              </span>
              {{ ship.name }} <span class="muted">({{ ship.len }})</span>
            </td>
            <td :class="ship.sunk ? 'sunk' : 'alive'">{{ ship.sunk ? '💥 Chìm' : 'Còn' }}</td>
            <td :class="opponentShipsList[i]?.sunk ? 'sunk' : 'alive'">
              {{ opponentShipsList[i]?.sunk ? '💥 Chìm' : 'Còn' }}
            </td>
          </tr>
        </tbody>
      </table>

      <dl class="meta small">
        <div><dt>Phòng</dt><dd><strong>{{ room.code }}</strong></dd></div>
        <div v-if="isBot"><dt>Độ khó bot</dt><dd>{{ room.levelName || 'Vừa' }}</dd></div>
        <div v-else><dt>Chế độ</dt><dd>Đấu người qua LAN</dd></div>
        <div v-if="you && phase !== 'placing'">
          <dt>Bạn đã bắn</dt>
          <dd>{{ playerStats.shots }} phát · trúng {{ playerStats.hits }} ({{ playerStats.accuracy }}%)</dd>
        </div>
        <div v-else><dt>Đã bắn</dt><dd>{{ room.moves || 0 }} phát</dd></div>
      </dl>

      <!-- Link mời qua LAN -->
      <InviteBox v-if="!isBot" :invite-link="inviteLink" :copied="copied" @copy="copyLink" />

      <!-- Các nút thao tác -->
      <div class="actions">
        <button class="btn red" :disabled="!you" @click="handleNewGame">
          Ván mới
        </button>
        <button class="btn" @click="handleLeave">
          Rời phòng
        </button>
      </div>

      <p v-if="!isBot && you" class="small muted">
        Ván đấu người được tính elo. Mỗi lượt có {{ room.turnSeconds || 30 }} giây; hết giờ, rời phòng hoặc
        bấm "Ván mới" khi ván chưa xong thì bị tính thua. Bắn trúng được bắn tiếp. Sau mỗi ván hai bên đổi bên.
      </p>
      <p v-else-if="isBot" class="small muted">
        Bắn trúng hoặc đánh chìm tàu được bắn tiếp! Bắn trượt sẽ mất lượt.
      </p>
    </aside>

    <ResultPopup :result="result" @close="closeResult" @new-game="closeResult(); handleNewGame()" />
  </section>
</template>

<style scoped>
.fleet-table { width: 100%; border-collapse: collapse; }
.fleet-table th { text-align: left; font-weight: 600; color: var(--muted); padding: 2px 4px; }
.fleet-table td { padding: 3px 4px; border-top: 1px solid var(--panel-border); white-space: nowrap; }
.fleet-table td:first-child { white-space: normal; }
.fleet-table td.alive { color: var(--green); }
.fleet-table td.sunk { color: var(--red); font-weight: 600; }
.fleet-table .fleet-ship-mini { display: inline-block; width: 40px; height: 12px; vertical-align: middle; margin-right: 4px; }
.placing-spectator {
  text-align: center;
  padding: 32px 16px;
}

.notice-banner {
  padding: 8px 12px;
  background: var(--bg);
  border-left: 4px solid var(--accent);
  border-radius: 4px;
  font-size: 0.9rem;
  font-weight: 600;
  text-align: center;
}

.placed-status {
  white-space: nowrap;
}
</style>
