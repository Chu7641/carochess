<script setup>
import { onMounted, ref, watch } from 'vue'
import { state } from '../game.js'

const activeTab = ref('elo') // 'elo' | 'minesweeper' | 'sudoku'
const soloLevel = ref('easy')

const eloData = ref({ elo: [], me: null })
const soloData = ref({ top: [], me: null })
const loading = ref(false)

async function fetchElo() {
  loading.value = true
  try {
    const res = await fetch('/api/leaderboard')
    if (res.ok) eloData.value = await res.json()
  } catch { /* lỗi kết nối */ }
  finally { loading.value = false }
}

async function fetchSolo() {
  loading.value = true
  try {
    const endpoint = activeTab.value === 'minesweeper' ? '/api/mines/leaderboard' : '/api/sudoku/leaderboard'
    const res = await fetch(`${endpoint}?level=${soloLevel.value}`)
    if (res.ok) soloData.value = await res.json()
  } catch { /* lỗi kết nối */ }
  finally { loading.value = false }
}

function loadCurrent() {
  if (activeTab.value === 'elo') fetchElo()
  else fetchSolo()
}

watch(activeTab, () => {
  soloLevel.value = 'easy'
  loadCurrent()
})

watch(soloLevel, () => {
  if (activeTab.value !== 'elo') fetchSolo()
})

onMounted(loadCurrent)

function formatSeconds(ms) {
  if (ms == null) return '-'
  return (ms / 1000).toFixed(3) + 's'
}
</script>

<template>
  <section class="leaderboard-view">
    <div class="card header-card">
      <div class="tabs-row">
        <div class="segmented tab-selector">
          <button :class="{ active: activeTab === 'elo' }" @click="activeTab = 'elo'">
            ⭐ Xếp hạng Elo
          </button>
          <button :class="{ active: activeTab === 'minesweeper' }" @click="activeTab = 'minesweeper'">
            💣 Dò mìn
          </button>
          <button :class="{ active: activeTab === 'sudoku' }" @click="activeTab = 'sudoku'">
            🔢 Sudoku
          </button>
        </div>

        <!-- Mức độ cho Dò mìn và Sudoku -->
        <div v-if="activeTab !== 'elo'" class="segmented level-selector">
          <button :class="{ active: soloLevel === 'easy' }" @click="soloLevel = 'easy'">Dễ</button>
          <button :class="{ active: soloLevel === 'medium' }" @click="soloLevel = 'medium'">Vừa</button>
          <button :class="{ active: soloLevel === 'hard' }" @click="soloLevel = 'hard'">Khó</button>
        </div>
      </div>
    </div>

    <!-- Bảng Elo -->
    <div v-if="activeTab === 'elo'" class="card content-card">
      <div class="card-title">
        <h2>🏆 Bảng xếp hạng điểm Elo đối kháng (Top 50)</h2>
        <span class="small muted">Tính theo các ván thắng/thua ở Caro, Cờ vây, Cờ tướng, Hải chiến</span>
      </div>

      <div v-if="loading" class="loading muted">Đang tải bảng xếp hạng…</div>
      <div v-else-if="!eloData.elo.length" class="empty muted">Chưa có dữ liệu xếp hạng.</div>
      <div v-else class="table-wrap">
        <table class="lb-table">
          <thead>
            <tr>
              <th class="col-rank">Hạng</th>
              <th>Người chơi</th>
              <th class="col-score">Điểm Elo</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in eloData.elo"
              :key="item.username"
              :class="{ 'my-row': item.username === state.user?.username }"
            >
              <td class="col-rank">
                <span v-if="item.rank === 1" class="medal gold">🥇 1</span>
                <span v-else-if="item.rank === 2" class="medal silver">🥈 2</span>
                <span v-else-if="item.rank === 3" class="medal bronze">🥉 3</span>
                <span v-else>{{ item.rank }}</span>
              </td>
              <td class="col-name">
                <strong>{{ item.username }}</strong>
                <span v-if="item.username === state.user?.username" class="badge-me">(Bạn)</span>
              </td>
              <td class="col-score">
                <span class="elo-val">{{ item.elo }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Dòng vị trí của bạn nếu nằm ngoài Top 50 -->
      <div
        v-if="eloData.me && !eloData.elo.some(u => u.username === state.user?.username)"
        class="my-outside-card"
      >
        <span>Thành tích của bạn:</span>
        <strong>Hạng #{{ eloData.me.rank }}</strong>
        <span class="elo-val">{{ eloData.me.elo }} Elo</span>
      </div>
    </div>

    <!-- Bảng Dò mìn / Sudoku -->
    <div v-else class="card content-card">
      <div class="card-title">
        <h2>
          {{ activeTab === 'minesweeper' ? '💣 Kỷ lục thời gian Dò mìn' : '🔢 Kỷ lục thời gian Sudoku' }}
        </h2>
        <span class="small muted">Thời gian giải nhanh nhất của mỗi người chơi</span>
      </div>

      <div v-if="loading" class="loading muted">Đang tải kỷ lục…</div>
      <div v-else-if="!soloData.top.length" class="empty muted">Chưa có ai hoàn thành cấp độ này. Hãy là người đầu tiên!</div>
      <div v-else class="table-wrap">
        <table class="lb-table">
          <thead>
            <tr>
              <th class="col-rank">Hạng</th>
              <th>Người chơi</th>
              <th class="col-score">Thời gian</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in soloData.top"
              :key="item.username"
              :class="{ 'my-row': item.username === state.user?.username }"
            >
              <td class="col-rank">
                <span v-if="item.rank === 1" class="medal gold">🥇 1</span>
                <span v-else-if="item.rank === 2" class="medal silver">🥈 2</span>
                <span v-else-if="item.rank === 3" class="medal bronze">🥉 3</span>
                <span v-else>{{ item.rank }}</span>
              </td>
              <td class="col-name">
                <strong>{{ item.username }}</strong>
                <span v-if="item.username === state.user?.username" class="badge-me">(Bạn)</span>
              </td>
              <td class="col-score">
                <span class="time-val">{{ formatSeconds(item.ms) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        v-if="soloData.me && !soloData.top.some(u => u.username === state.user?.username)"
        class="my-outside-card"
      >
        <span>Kỷ lục của bạn:</span>
        <strong>Hạng #{{ soloData.me.rank }}</strong>
        <span class="time-val">{{ formatSeconds(soloData.me.ms) }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.leaderboard-view {
  max-width: 920px;
  margin: 0 auto;
  display: grid;
  gap: 16px;
}

.header-card {
  padding: 12px 16px;
}

.tabs-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
  align-items: center;
}

.tab-selector {
  flex: 1;
  min-width: 280px;
}

.level-selector {
  width: 220px;
}

.content-card {
  display: grid;
  gap: 16px;
}

.card-title h2 {
  margin: 0 0 4px;
  font-size: 1.15rem;
}

.table-wrap {
  overflow-x: auto;
}

.lb-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.lb-table th {
  padding: 10px 14px;
  border-bottom: 2px solid var(--panel-border);
  color: var(--muted);
  font-size: 0.85rem;
}

.lb-table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--panel-border);
}

.col-rank {
  width: 90px;
  font-weight: 700;
}

.col-score {
  width: 140px;
  text-align: right;
}

.col-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.my-row {
  background: rgba(238, 182, 61, 0.12);
  font-weight: 600;
}

.badge-me {
  font-size: 0.75rem;
  color: var(--green);
  font-weight: 700;
}

.medal {
  font-weight: 700;
}

.elo-val {
  font-weight: 700;
  color: var(--green);
}

.time-val {
  font-family: monospace;
  font-weight: 700;
  color: var(--blue);
}

.my-outside-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg);
  border: 1px dashed var(--accent);
  border-radius: 8px;
  font-size: 0.95rem;
}

.empty, .loading {
  text-align: center;
  padding: 40px 0;
}
</style>

