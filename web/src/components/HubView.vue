<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { chooseGame, joinRoom, state } from '../game.js'
import { GAMES } from '../games.js'
import CreateCaro from './create/CreateCaro.vue'
import CreateGo from './create/CreateGo.vue'
import CreateXiangqi from './create/CreateXiangqi.vue'
import CreateBattleship from './create/CreateBattleship.vue'

const ROOM_GAMES = GAMES.filter((g) => g.kind === 'room')
const SOLO_GAMES = GAMES.filter((g) => g.kind === 'solo')

const STATUS = { waiting: 'Đang chờ', playing: 'Đang chơi', bot: 'Đấu máy' }

function loadPref(key, fallback) {
  try {
    return localStorage.getItem(key) || fallback
  } catch {
    return fallback
  }
}

function savePref(key, val) {
  try {
    localStorage.setItem(key, val)
  } catch { /* ẩn danh */ }
}

const selectedGame = ref(loadPref('caro.hub_game', 'caro'))
const roomFilter = ref(loadPref('caro.hub_filter', 'all'))
const joinCode = ref('')
const info = ref({})
const rooms = ref([])

function selectGame(id) {
  selectedGame.value = id
  savePref('caro.hub_game', id)
}

function selectFilter(filter) {
  roomFilter.value = filter
  savePref('caro.hub_filter', filter)
}

let timer = null

async function refreshRooms() {
  try {
    const res = await fetch('/api/rooms')
    if (res.ok) rooms.value = await res.json()
  } catch { /* máy chủ đang bận */ }
}

onMounted(async () => {
  try {
    const res = await fetch('/api/info')
    if (res.ok) info.value = await res.json()
  } catch { /* dùng mặc định */ }
  refreshRooms()
  timer = setInterval(refreshRooms, 3000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const filteredRooms = computed(() => {
  if (roomFilter.value === 'all') return rooms.value
  return rooms.value.filter((r) => (r.game || 'caro') === roomFilter.value)
})

const mine = (r) => r.players?.includes(state.user?.username)

function getGameDef(gameId) {
  return GAMES.find((g) => g.id === (gameId || 'caro')) || GAMES[0]
}
</script>

<template>
  <div class="hub-container">
    <!-- CỘT TRÁI: TẠO PHÒNG & CHƠI MỘT MÌNH -->
    <div class="hub-col">
      <!-- Tạo phòng mới -->
      <section class="card hub-card">
        <div class="section-header">
          <h2>Tạo phòng mới</h2>
          <span class="small muted">Chọn công cụ:</span>
        </div>

        <!-- Hàng nút chọn trò đối kháng -->
        <div class="segmented game-selector">
          <button
            v-for="g in ROOM_GAMES"
            :key="g.id"
            :class="{ active: selectedGame === g.id }"
            @click="selectGame(g.id)"
          >
            <span class="game-icon">{{ g.icon }}</span>
            <span class="game-name">{{ g.name }}</span>
          </button>
        </div>

        <!-- Form tạo phòng tương ứng của trò đang chọn -->
        <div class="form-wrapper">
          <CreateCaro v-if="selectedGame === 'caro'" :info="info" />
          <CreateGo v-else-if="selectedGame === 'go'" :info="info" />
          <CreateXiangqi v-else-if="selectedGame === 'xiangqi'" :info="info" />
          <CreateBattleship v-else-if="selectedGame === 'battleship'" :info="info" />
        </div>
      </section>

      <!-- Chơi một mình -->
      <section class="card hub-card">
        <div class="section-header">
          <h2>Chơi một mình</h2>
          <span class="small muted">Thử thách trí tuệ cá nhân</span>
        </div>

        <div class="solo-grid">
          <button
            v-for="s in SOLO_GAMES"
            :key="s.id"
            class="solo-card"
            @click="chooseGame(s.id)"
          >
            <span class="solo-icon">{{ s.icon }}</span>
            <div class="solo-info">
              <strong>{{ s.name }}</strong>
              <p class="small muted">{{ s.desc }}</p>
            </div>
            <span class="solo-arrow">→</span>
          </button>
        </div>
      </section>
    </div>

    <!-- CỘT PHẢI: PHÒNG ĐANG MỞ & VÀO PHÒNG -->
    <div class="hub-col">
      <!-- Phòng đang mở -->
      <section class="card hub-card">
        <div class="section-header with-link">
          <h2>Phòng đang mở</h2>
          <button class="btn link-btn" @click="chooseGame('leaderboard')">
            🏆 Bảng xếp hạng
          </button>
        </div>

        <!-- Bộ lọc trò chơi -->
        <div class="segmented filter-selector">
          <button :class="{ active: roomFilter === 'all' }" @click="selectFilter('all')">Tất cả</button>
          <button :class="{ active: roomFilter === 'caro' }" @click="selectFilter('caro')">Cờ caro</button>
          <button :class="{ active: roomFilter === 'go' }" @click="selectFilter('go')">Cờ vây</button>
          <button :class="{ active: roomFilter === 'xiangqi' }" @click="selectFilter('xiangqi')">Cờ tướng</button>
          <button :class="{ active: roomFilter === 'battleship' }" @click="selectFilter('battleship')">Hải chiến</button>
        </div>

        <!-- Danh sách phòng -->
        <div v-if="!filteredRooms.length" class="empty-rooms">
          <p class="small muted">Chưa có phòng nào đang mở. Hãy tạo phòng mới bên cạnh!</p>
        </div>
        <div v-else class="rooms-list">
          <div
            v-for="r in filteredRooms"
            :key="r.code"
            class="room-card"
            :class="{ 'my-room': mine(r) }"
          >
            <div class="room-main">
              <div class="room-title-line">
                <span class="room-game-icon">{{ getGameDef(r.game).icon }}</span>
                <strong>{{ getGameDef(r.game).name }}</strong>
                <span class="room-code">#{{ r.code }}</span>
                <span class="room-status-badge" :class="r.status">
                  {{ STATUS[r.status] || r.status }}
                </span>
              </div>
              <div class="room-details small muted">
                <span>{{ r.players?.join(' vs ') || 'Chưa có người' }}</span>
                <span v-if="r.rows && r.cols">· {{ r.rows }}×{{ r.cols }}</span>
                <span v-else-if="r.size">· {{ r.size }}×{{ r.size }}</span>
                <span v-if="r.spectators">· 👁️ {{ r.spectators }}</span>
              </div>
            </div>

            <div class="room-action">
              <button
                v-if="mine(r)"
                class="btn blue small"
                @click="joinRoom(r.code)"
              >
                Vào lại →
              </button>
              <button
                v-else-if="r.status === 'waiting'"
                class="btn green small"
                @click="joinRoom(r.code)"
              >
                Vào ngay →
              </button>
              <button
                v-else
                class="btn small"
                @click="joinRoom(r.code)"
              >
                Xem →
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Vào bằng mã phòng -->
      <section class="card hub-card">
        <h2>Vào bằng mã phòng</h2>
        <form class="row join-form" @submit.prevent="joinRoom(joinCode)">
          <input
            v-model="joinCode"
            class="input code"
            maxlength="4"
            placeholder="ABCD"
          />
          <button class="btn green" :disabled="!state.connected || !joinCode.trim()">
            Vào phòng
          </button>
        </form>
      </section>
    </div>
  </div>
</template>

<style scoped>
.hub-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}

.hub-col {
  display: grid;
  gap: 16px;
}

.hub-card {
  display: grid;
  gap: 14px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.section-header h2 {
  margin: 0;
  font-size: 1.15rem;
}

.with-link {
  align-items: center;
}

.link-btn {
  background: transparent;
  color: var(--accent);
  border: 1px solid var(--accent);
  padding: 5px 10px;
  font-size: 0.85rem;
}

.link-btn:hover {
  background: var(--accent);
  color: #2b2a27;
}

.game-selector button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 4px;
}

.game-icon {
  font-size: 1.1rem;
}

.form-wrapper {
  margin-top: 4px;
}

.solo-grid {
  display: grid;
  gap: 10px;
}

.solo-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  cursor: pointer;
  text-align: left;
  transition: transform 0.1s, border-color 0.15s;
}

.solo-card:hover {
  transform: translateY(-1px);
  border-color: var(--green);
}

.solo-icon {
  font-size: 1.8rem;
  flex: none;
}

.solo-info {
  flex: 1;
  min-width: 0;
}

.solo-info strong {
  display: block;
  font-size: 1rem;
}

.solo-info p {
  margin: 2px 0 0;
  line-height: 1.3;
}

.solo-arrow {
  font-size: 1.2rem;
  color: var(--muted);
  flex: none;
}

.filter-selector {
  font-size: 0.85rem;
}

.filter-selector button {
  padding: 6px 2px;
}

.rooms-list {
  display: grid;
  gap: 8px;
  max-height: 480px;
  overflow-y: auto;
  padding-right: 4px;
}

.room-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
}

.room-card.my-room {
  border-color: var(--blue);
  background: rgba(67, 99, 145, 0.08);
}

.room-main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.room-title-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.room-game-icon {
  font-size: 1rem;
}

.room-code {
  font-family: monospace;
  font-weight: 700;
  color: var(--text);
}

.room-status-badge {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.room-status-badge.waiting {
  background: var(--green);
  color: #fff;
}

.room-status-badge.playing {
  background: var(--accent);
  color: #2b2a27;
}

.room-status-badge.bot {
  background: var(--blue);
  color: #fff;
}

.room-action {
  flex: none;
}

.empty-rooms {
  text-align: center;
  padding: 32px 0;
}

.join-form input.code {
  letter-spacing: 0.25em;
  text-transform: uppercase;
  font-weight: 700;
  text-align: center;
  font-size: 1.1rem;
}

@media (max-width: 860px) {
  .hub-container {
    grid-template-columns: 1fr;
  }
}
</style>

