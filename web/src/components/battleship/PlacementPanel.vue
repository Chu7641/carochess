<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import BattleshipShip from '../BattleshipShip.vue'
import SeaBoard from './SeaBoard.vue'

const SHIP_DEFS = [
  { name: 'Tàu sân bay', len: 5 },
  { name: 'Thiết giáp hạm', len: 4 },
  { name: 'Tuần dương hạm', len: 3 },
  { name: 'Tàu ngầm', len: 3 },
  { name: 'Khu trục hạm', len: 2 },
]

const props = defineProps({
  iAmPlaced: { type: Boolean, default: false },
  myFleet: { type: Object, default: null },
})

const emit = defineEmits(['confirm'])

const placedShips = ref([])
const selectedDefIndex = ref(0)
const isVertical = ref(false)
const hoverPos = ref(null)

const unplacedDefs = computed(() => {
  const placedNames = new Set(placedShips.value.map((s) => s.name))
  return SHIP_DEFS.filter((d) => !placedNames.has(d.name))
})

const selectedShipDef = computed(() => {
  if (unplacedDefs.value.length === 0) return null
  const found = unplacedDefs.value.find((_, idx) => idx === selectedDefIndex.value)
  return found || unplacedDefs.value[0] || null
})

function selectShip(def) {
  const idx = unplacedDefs.value.findIndex((d) => d.name === def.name)
  if (idx !== -1) selectedDefIndex.value = idx
}

function toggleOrientation() {
  isVertical.value = !isVertical.value
}

function handleKeydown(e) {
  if (e.key === 'r' || e.key === 'R') {
    toggleOrientation()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

// Nếu vào lại phòng mà mình đã xếp tàu từ trước
watch(() => props.myFleet, (fleet) => {
  if (fleet?.ships?.length && !placedShips.value.length) {
    placedShips.value = fleet.ships.map((s) => ({
      name: s.name,
      len: s.len,
      r: s.r,
      c: s.c,
      vertical: s.vertical,
    }))
  }
}, { immediate: true })

function getShipCells(r, c, len, vertical) {
  const cells = []
  for (let i = 0; i < len; i++) {
    cells.push({
      r: vertical ? r + i : r,
      c: vertical ? c : c + i,
    })
  }
  return cells
}

function isPlacementValid(r, c, len, vertical) {
  const cells = getShipCells(r, c, len, vertical)
  for (const cell of cells) {
    if (cell.r < 0 || cell.r >= 10 || cell.c < 0 || cell.c >= 10) {
      return false
    }
  }
  for (const ship of placedShips.value) {
    const existingCells = getShipCells(ship.r, ship.c, ship.len, ship.vertical)
    for (const ec of existingCells) {
      for (const nc of cells) {
        if (ec.r === nc.r && ec.c === nc.c) {
          return false
        }
      }
    }
  }
  return true
}

function fitOnBoard(r, c, len, vertical) {
  return {
    r: Math.min(r, 10 - (vertical ? len : 1)),
    c: Math.min(c, 10 - (vertical ? 1 : len)),
  }
}

const previewShip = computed(() => {
  if (props.iAmPlaced) return null
  if (!hoverPos.value || !selectedShipDef.value) return null
  const len = selectedShipDef.value.len
  const vertical = isVertical.value
  const { r, c } = fitOnBoard(hoverPos.value.r, hoverPos.value.c, len, vertical)
  return {
    name: selectedShipDef.value.name,
    len,
    r,
    c,
    vertical,
    valid: isPlacementValid(r, c, len, vertical),
  }
})

function getPlacedShipAt(r, c) {
  for (const ship of placedShips.value) {
    const cells = getShipCells(ship.r, ship.c, ship.len, ship.vertical)
    if (cells.some((cell) => cell.r === r && cell.c === c)) {
      return ship
    }
  }
  return null
}

function onPlaceBoardClick(r, c) {
  if (props.iAmPlaced) return
  const existingShip = getPlacedShipAt(r, c)
  if (existingShip) {
    placedShips.value = placedShips.value.filter((s) => s.name !== existingShip.name)
    const def = SHIP_DEFS.find((d) => d.name === existingShip.name)
    if (def) selectShip(def)
    return
  }

  if (selectedShipDef.value) {
    const len = selectedShipDef.value.len
    const vertical = isVertical.value
    const pos = fitOnBoard(r, c, len, vertical)
    if (isPlacementValid(pos.r, pos.c, len, vertical)) {
      placedShips.value.push({
        name: selectedShipDef.value.name,
        len,
        r: pos.r,
        c: pos.c,
        vertical,
      })
      selectedDefIndex.value = 0
    }
  }
}

function removePlacedShip(shipName) {
  if (props.iAmPlaced) return
  placedShips.value = placedShips.value.filter((s) => s.name !== shipName)
  const def = SHIP_DEFS.find((d) => d.name === shipName)
  if (def) selectShip(def)
}

function resetPlacement() {
  if (props.iAmPlaced) return
  placedShips.value = []
  selectedDefIndex.value = 0
}

function confirmPlacement() {
  if (placedShips.value.length !== 5 || props.iAmPlaced) return
  emit('confirm', placedShips.value)
}

function handleAutoPlace() {
  if (props.iAmPlaced) return
  for (let attempt = 0; attempt < 100; attempt++) {
    placedShips.value = []
    const ok = SHIP_DEFS.every((def) => {
      for (let i = 0; i < 200; i++) {
        const vertical = Math.random() < 0.5
        const r = Math.floor(Math.random() * (vertical ? 11 - def.len : 10))
        const c = Math.floor(Math.random() * (vertical ? 10 : 11 - def.len))
        if (isPlacementValid(r, c, def.len, vertical)) {
          placedShips.value.push({ name: def.name, len: def.len, r, c, vertical })
          return true
        }
      }
      return false
    })
    if (ok) return
  }
  // Nếu thử 100 lần vẫn thất bại, emit confirm với null để server xếp
  emit('confirm', null)
}

const boardShips = computed(() => {
  const list = placedShips.value.map((s) => ({ ...s, preview: false }))
  if (previewShip.value) {
    list.push({
      key: 'preview',
      name: previewShip.value.name,
      len: previewShip.value.len,
      r: previewShip.value.r,
      c: previewShip.value.c,
      vertical: previewShip.value.vertical,
      preview: true,
      previewBad: !previewShip.value.valid,
    })
  }
  return list
})
</script>

<template>
  <div class="placing-container card">
    <div class="placing-header">
      <div class="placing-title">
        <h3>⚓ Bố trí hạm đội hải chiến</h3>
        <p v-if="!iAmPlaced" class="small muted">
          Nhấn ô để đặt tàu. Nhấn tàu đã đặt để gỡ ra. Phím <kbd>R</kbd> hoặc nút xoay để đổi hướng. Tàu được phép nằm sát nhau.
        </p>
        <p v-else class="small ready">
          ✓ Bạn đã xác nhận hạm đội! Đang chờ đối thủ xếp tàu xong…
        </p>
      </div>
      <div v-if="!iAmPlaced" class="placing-actions">
        <button class="btn" @click="toggleOrientation">
          {{ isVertical ? '↕ Dọc' : '↔ Ngang' }} (Phím R)
        </button>
        <button class="btn blue" @click="handleAutoPlace">
          🎲 Xếp ngẫu nhiên
        </button>
        <button class="btn" :disabled="!placedShips.length" @click="resetPlacement">
          Làm lại
        </button>
        <button class="btn green" :disabled="placedShips.length !== 5" @click="confirmPlacement">
          ✓ Xác nhận vào trận ({{ placedShips.length }}/5)
        </button>
      </div>
    </div>

    <div class="placing-body">
      <!-- Bàn cờ đặt tàu 10x10 -->
      <SeaBoard
        :disabled="iAmPlaced"
        :ships="boardShips"
        :get-cell-state="(r, c) => ({
          clickable: !iAmPlaced,
          overShip: !!getPlacedShipAt(r, c)
        })"
        @cell-click="onPlaceBoardClick"
        @cell-enter="(r, c) => hoverPos = { r, c }"
        @cell-leave="() => hoverPos = null"
      />

      <!-- Danh sách tàu để chọn và xếp -->
      <div class="ship-palette">
        <h4>Hạm đội của bạn</h4>
        <div
          v-for="def in SHIP_DEFS"
          :key="def.name"
          class="ship-card"
          :class="{
            active: selectedShipDef && selectedShipDef.name === def.name && !props.iAmPlaced,
            placed: placedShips.some((s) => s.name === def.name)
          }"
          @click="selectShip(def)"
        >
          <div class="ship-info">
            <strong>{{ def.name }}</strong>
            <span class="small muted">{{ def.len }} ô</span>
          </div>

          <!-- Hình vẽ thu nhỏ của tàu -->
          <div class="ship-mini-preview">
            <BattleshipShip
              :name="def.name"
              :len="def.len"
              :state="placedShips.some((s) => s.name === def.name) ? 'preview-ok' : 'normal'"
            />
          </div>

          <button
            v-if="placedShips.some((s) => s.name === def.name) && !props.iAmPlaced"
            class="btn red small"
            title="Gỡ tàu ra khỏi bàn"
            @click.stop="removePlacedShip(def.name)"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.placing-container {
  display: grid;
  gap: 16px;
}

.placing-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.placing-title h3 {
  margin: 0 0 4px;
}

.placing-title p {
  margin: 0;
}

.placing-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.placing-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 16px;
  align-items: start;
}

.ship-palette {
  display: grid;
  gap: 8px;
}

.ship-palette h4 {
  margin: 0 0 4px;
  font-size: 0.95rem;
  color: var(--muted);
}

.ship-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  cursor: pointer;
  background: var(--bg);
  transition: border-color 0.15s, background-color 0.15s;
}

.ship-card.active {
  border-color: var(--blue);
  box-shadow: 0 0 0 1px var(--blue);
}

.ship-card.placed {
  opacity: 0.65;
  border-style: dashed;
}

.ship-info {
  display: grid;
  gap: 2px;
}

.ship-mini-preview {
  width: 76px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

@media (max-width: 860px) {
  .placing-body {
    grid-template-columns: 1fr;
  }
}
</style>

