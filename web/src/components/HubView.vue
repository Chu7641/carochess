<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
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

// Hộp thoại tạo phòng
const showModal = ref(false)
const modalStep = ref(1) // 1: Chọn công cụ, 2: Thiết lập
const modalCardRef = ref(null)

function selectFilter(filter) {
  roomFilter.value = filter
  savePref('caro.hub_filter', filter)
}

function openModal() {
  modalStep.value = 1
  showModal.value = true
  nextTick(() => {
    modalCardRef.value?.focus()
  })
}

function closeModal() {
  showModal.value = false
}

function selectTool(id) {
  selectedGame.value = id
  savePref('caro.hub_game', id)
  modalStep.value = 2
}

function selectSolo(id) {
  closeModal()
  chooseGame(id)
}

function handleJoin() {
  const code = joinCode.value.trim().toUpperCase()
  if (code) {
    joinRoom(code)
  }
}

function onKeydown(e) {
  if (e.key === 'Escape' && showModal.value) {
    closeModal()
  }
}

let timer = null

async function refreshRooms() {
  try {
    const res = await fetch('/api/rooms')
    if (res.ok) rooms.value = await res.json()
  } catch { /* máy chủ đang bận */ }
}

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  try {
    const res = await fetch('/api/info')
    if (res.ok) info.value = await res.json()
  } catch { /* dùng mặc định */ }
  refreshRooms()
  timer = setInterval(refreshRooms, 3000)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  if (timer) clearInterval(timer)
})

const filteredRooms = computed(() => {
  if (roomFilter.value === 'all') return rooms.value
  return rooms.value.filter((r) => (r.game || 'caro') === roomFilter.value)
})

const mine = (r) => r.players?.includes(state.user?.username)

function roomRank(r) {
  if (mine(r)) return 0
  if (r.status === 'waiting') return 1
  if (r.status === 'playing') return 2
  if (r.status === 'bot') return 3
  return 4
}

// Sắp xếp: phòng có mình trước, rồi đang chờ, đang chơi, đấu máy (trong từng nhóm theo mã phòng)
const sortedRooms = computed(() => {
  const list = [...filteredRooms.value]
  list.sort((a, b) => {
    const diff = roomRank(a) - roomRank(b)
    if (diff !== 0) return diff
    return (a.code || '').localeCompare(b.code || '')
  })
  return list
})

function getGameDef(gameId) {
  return GAMES.find((g) => g.id === (gameId || 'caro')) || GAMES[0]
}

const currentTool = computed(() => getGameDef(selectedGame.value))
</script>

<template>
  <div class="hub-view">
    <!-- THANH CÔNG CỤ TRÊN CÙNG -->
    <div class="hub-toolbar">
      <div class="segmented hub-filter">
        <button
          type="button"
          :class="{ active: roomFilter === 'all' }"
          @click="selectFilter('all')"
        >
          Tất cả
        </button>
        <button
          type="button"
          :class="{ active: roomFilter === 'caro' }"
          @click="selectFilter('caro')"
        >
          Cờ caro
        </button>
        <button
          type="button"
          :class="{ active: roomFilter === 'go' }"
          @click="selectFilter('go')"
        >
          Cờ vây
        </button>
        <button
          type="button"
          :class="{ active: roomFilter === 'xiangqi' }"
          @click="selectFilter('xiangqi')"
        >
          Cờ tướng
        </button>
        <button
          type="button"
          :class="{ active: roomFilter === 'battleship' }"
          @click="selectFilter('battleship')"
        >
          Hải chiến
        </button>
      </div>

      <div class="hub-toolbar-actions">
        <!-- Vào bằng mã phòng -->
        <form class="hub-join-form" @submit.prevent="handleJoin">
          <input
            v-model="joinCode"
            class="input code hub-join-input"
            maxlength="4"
            placeholder="Mã"
            aria-label="Mã phòng"
          />
          <button
            type="submit"
            class="btn green hub-join-btn"
            :disabled="!state.connected || !joinCode.trim()"
          >
            Vào
          </button>
        </form>

        <!-- Nút Bảng xếp hạng -->
        <button
          type="button"
          class="btn hub-lb-btn"
          @click="chooseGame('leaderboard')"
        >
          🏆 Bảng xếp hạng
        </button>
      </div>
    </div>

    <!-- LƯỚI Ô -->
    <div class="hub-grid">
      <!-- Ô ĐẦU TIÊN: TẠO PHÒNG -->
      <button
        type="button"
        class="hub-tile hub-create-tile"
        @click="openModal"
      >
        <span class="hub-create-icon">➕</span>
        <strong class="hub-create-text">Tạo phòng</strong>
        <span class="hub-create-hint small muted">Chọn công cụ để bắt đầu</span>
      </button>

      <!-- CÁC Ô PHÒNG -->
      <button
        v-for="r in sortedRooms"
        :key="r.code"
        type="button"
        class="hub-tile hub-room-tile"
        :class="{ 'hub-room-tile-mine': mine(r) }"
        @click="joinRoom(r.code)"
      >
        <div class="hub-tile-header">
          <div class="hub-tile-game">
            <span class="hub-tile-icon">{{ getGameDef(r.game).icon }}</span>
            <span class="hub-tile-gamename">{{ getGameDef(r.game).name }}</span>
          </div>
          <span class="hub-status-chip" :class="r.status">
            {{ STATUS[r.status] || r.status }}
          </span>
        </div>

        <div class="hub-tile-code">#{{ r.code }}</div>

        <div class="hub-tile-players" :title="r.players?.join(' vs ')">
          {{ r.players?.length ? r.players.join(' vs ') : 'Đang chờ người chơi…' }}
        </div>

        <div class="hub-tile-meta small muted">
          <span v-if="r.rows && r.cols">{{ r.rows }}×{{ r.cols }}</span>
          <span v-else-if="r.size">{{ r.size }}×{{ r.size }}</span>
          <span v-if="r.spectators">👁️ {{ r.spectators }}</span>
        </div>

        <div class="hub-tile-footer">
          <span v-if="mine(r)" class="hub-action-text hub-action-mine">Vào lại →</span>
          <span v-else-if="r.status === 'waiting'" class="hub-action-text hub-action-waiting">Vào ngay →</span>
          <span v-else class="hub-action-text hub-action-view">Xem →</span>
        </div>
      </button>
    </div>

    <!-- Gợi ý khi không có phòng nào -->
    <p v-if="!sortedRooms.length" class="hub-empty-hint small muted">
      Chưa có phòng nào đang mở. Hãy bấm "Tạo phòng" để bắt đầu ván mới!
    </p>

    <!-- HỘP THOẠI TẠO PHÒNG (2 BƯỚC) -->
    <div
      v-if="showModal"
      class="hub-modal-overlay"
      @click.self="closeModal"
    >
      <div
        ref="modalCardRef"
        class="card hub-modal-card"
        role="dialog"
        aria-modal="true"
        tabindex="-1"
      >
        <!-- Tiêu đề hộp thoại -->
        <div class="hub-modal-header">
          <div class="hub-modal-title-wrap">
            <button
              v-if="modalStep === 2"
              type="button"
              class="btn hub-back-btn"
              title="Quay lại chọn công cụ"
              @click="modalStep = 1"
            >
              ← Chọn trò khác
            </button>
            <h2 class="hub-modal-title">
              <template v-if="modalStep === 1">Chọn công cụ</template>
              <template v-else>
                {{ currentTool.icon }} Thiết lập {{ currentTool.name }}
              </template>
            </h2>
          </div>
          <button
            type="button"
            class="hub-modal-close"
            title="Đóng (Esc)"
            aria-label="Đóng"
            @click="closeModal"
          >
            ✕
          </button>
        </div>

        <!-- BƯỚC 1: CHỌN CÔNG CỤ -->
        <div v-if="modalStep === 1" class="hub-modal-body">
          <div class="hub-tools-grid">
            <button
              v-for="g in ROOM_GAMES"
              :key="g.id"
              type="button"
              class="hub-tool-card"
              :class="{ 'hub-tool-highlight': selectedGame === g.id }"
              @click="selectTool(g.id)"
            >
              <span class="hub-tool-icon">{{ g.icon }}</span>
              <div class="hub-tool-info">
                <strong class="hub-tool-name">{{ g.name }}</strong>
                <p class="small muted hub-tool-desc">{{ g.desc }}</p>
              </div>
              <span class="hub-tool-arrow">→</span>
            </button>
          </div>

          <!-- Mục nhỏ: Chơi một mình -->
          <div class="hub-solo-section">
            <div class="hub-solo-heading small muted">Chơi một mình</div>
            <div class="hub-solo-grid">
              <button
                v-for="s in SOLO_GAMES"
                :key="s.id"
                type="button"
                class="hub-solo-card"
                @click="selectSolo(s.id)"
              >
                <span class="hub-solo-icon">{{ s.icon }}</span>
                <div class="hub-solo-info">
                  <strong>{{ s.name }}</strong>
                  <p class="small muted">{{ s.desc }}</p>
                </div>
                <span class="hub-solo-arrow">→</span>
              </button>
            </div>
          </div>
        </div>

        <!-- BƯỚC 2: THIẾT LẬP -->
        <div v-else-if="modalStep === 2" class="hub-modal-body">
          <CreateCaro
            v-if="selectedGame === 'caro'"
            :info="info"
            @created="closeModal"
          />
          <CreateGo
            v-else-if="selectedGame === 'go'"
            :info="info"
            @created="closeModal"
          />
          <CreateXiangqi
            v-else-if="selectedGame === 'xiangqi'"
            :info="info"
            @created="closeModal"
          />
          <CreateBattleship
            v-else-if="selectedGame === 'battleship'"
            :info="info"
            @created="closeModal"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hub-view {
  display: flex;
  flex-direction: column;
}

/* THANH CÔNG CỤ TRÊN CÙNG */
.hub-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.hub-filter {
  font-size: 0.85rem;
  flex-wrap: wrap;
}

.hub-filter button {
  padding: 6px 10px;
}

.hub-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.hub-join-form {
  display: flex;
  align-items: center;
  gap: 6px;
}

.hub-join-input {
  width: 90px;
  text-transform: uppercase;
  text-align: center;
  font-family: monospace;
  font-weight: 700;
  letter-spacing: 0.15em;
  padding: 6px 8px;
}

.hub-join-btn {
  padding: 6px 12px;
  white-space: nowrap;
}

.hub-lb-btn {
  background: transparent;
  color: var(--accent);
  border: 1px solid var(--accent);
  padding: 6px 12px;
  white-space: nowrap;
}

.hub-lb-btn:hover {
  background: var(--accent);
  color: #2b2a27;
}

/* LƯỚI Ô */
.hub-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}

.hub-tile {
  appearance: none;
  font: inherit;
  border: 1px solid var(--panel-border);
  background: var(--panel);
  border-radius: var(--radius);
  padding: 14px;
  cursor: pointer;
  color: var(--text);
  min-height: 175px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  text-align: left;
  transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.hub-tile:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* Ô TẠO PHÒNG */
.hub-create-tile {
  border: 2px dashed var(--panel-border);
  background: var(--panel);
  align-items: center;
  justify-content: center;
  text-align: center;
}

.hub-create-tile:hover {
  transform: translateY(-2px);
  border-color: var(--green);
  background: rgba(56, 126, 87, 0.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.hub-create-icon {
  font-size: 2.2rem;
  line-height: 1;
  margin-bottom: 6px;
}

.hub-create-text {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text);
}

.hub-create-hint {
  margin-top: 4px;
}

/* Ô PHÒNG ĐANG MỞ */
.hub-room-tile {
  justify-content: space-between;
}

.hub-room-tile:hover {
  transform: translateY(-2px);
  border-color: var(--accent);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.hub-room-tile.hub-room-tile-mine {
  border-color: var(--blue);
  background: rgba(67, 99, 145, 0.08);
}

.hub-tile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.hub-tile-game {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.hub-tile-icon {
  font-size: 1.1rem;
  flex: none;
}

.hub-tile-gamename {
  font-size: 0.95rem;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hub-status-chip {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
  flex: none;
}

.hub-status-chip.waiting {
  background: var(--green);
  color: #fff;
}

.hub-status-chip.playing {
  background: var(--accent);
  color: #2b2a27;
}

.hub-status-chip.bot {
  background: var(--blue);
  color: #fff;
}

.hub-tile-code {
  font-family: monospace;
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--text);
  margin-top: 8px;
}

.hub-tile-players {
  font-size: 0.88rem;
  color: var(--text);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hub-tile-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 4px;
}

.hub-tile-footer {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px dashed var(--panel-border);
  display: flex;
  justify-content: flex-end;
}

.hub-action-text {
  font-size: 0.85rem;
  font-weight: 700;
}

.hub-action-mine { color: var(--blue); }
.hub-action-waiting { color: var(--green); }
.hub-action-view { color: var(--muted); }

.hub-empty-hint {
  margin-top: 20px;
  text-align: center;
}

/* HỘP THOẠI TẠO PHÒNG */
.hub-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.hub-modal-card {
  width: 100%;
  max-width: 720px;
  max-height: 90vh;
  overflow-y: auto;
  outline: none;
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  padding: 20px;
  display: grid;
  gap: 16px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
}

.hub-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--panel-border);
}

.hub-modal-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.hub-back-btn {
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--panel-border);
  padding: 5px 10px;
  font-size: 0.85rem;
  cursor: pointer;
  border-radius: 6px;
  white-space: nowrap;
}

.hub-back-btn:hover {
  background: var(--panel-border);
}

.hub-modal-title {
  margin: 0;
  font-size: 1.15rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hub-modal-close {
  background: transparent;
  border: 0;
  color: var(--muted);
  font-size: 1.3rem;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.hub-modal-close:hover {
  background: var(--bg);
  color: var(--text);
}

.hub-modal-body {
  display: grid;
  gap: 14px;
}

/* BƯỚC 1: LƯỚI CÔNG CỤ */
.hub-tools-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.hub-tool-card {
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
  transition: transform 0.1s, border-color 0.15s, box-shadow 0.15s;
}

.hub-tool-card:hover {
  transform: translateY(-1px);
  border-color: var(--green);
}

.hub-tool-card.hub-tool-highlight {
  border-color: var(--green);
  box-shadow: 0 0 0 2px var(--green);
  background: rgba(56, 126, 87, 0.08);
}

.hub-tool-icon {
  font-size: 1.8rem;
  flex: none;
}

.hub-tool-info {
  flex: 1;
  min-width: 0;
}

.hub-tool-name {
  display: block;
  font-size: 1rem;
}

.hub-tool-desc {
  margin: 2px 0 0;
  line-height: 1.3;
}

.hub-tool-arrow {
  font-size: 1.2rem;
  color: var(--muted);
  flex: none;
}

/* CHƠI MỘT MÌNH TRONG MODAL */
.hub-solo-section {
  margin-top: 6px;
  padding-top: 14px;
  border-top: 1px dashed var(--panel-border);
}

.hub-solo-heading {
  margin-bottom: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.hub-solo-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.hub-solo-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  cursor: pointer;
  text-align: left;
  transition: transform 0.1s, border-color 0.15s;
}

.hub-solo-card:hover {
  transform: translateY(-1px);
  border-color: var(--blue);
}

.hub-solo-icon {
  font-size: 1.5rem;
  flex: none;
}

.hub-solo-info {
  flex: 1;
  min-width: 0;
}

.hub-solo-info strong {
  display: block;
  font-size: 0.95rem;
}

.hub-solo-info p {
  margin: 2px 0 0;
  line-height: 1.25;
}

.hub-solo-arrow {
  color: var(--muted);
  flex: none;
}

/* RESPONSIVE */
@media (max-width: 680px) {
  .hub-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .hub-toolbar-actions {
    justify-content: space-between;
  }
  .hub-tools-grid,
  .hub-solo-grid {
    grid-template-columns: 1fr;
  }
}
</style>
