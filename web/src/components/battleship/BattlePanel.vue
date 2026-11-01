<script setup>
import { computed } from 'vue'
import SeaBoard from './SeaBoard.vue'

const props = defineProps({
  room: { type: Object, required: true },
  you: { default: null },
  canShoot: { type: Boolean, default: false },
  lastShot: { type: Object, default: null },
})

const emit = defineEmits(['shoot'])

const opponentBoard = computed(() => props.room?.opponentBoard)
const myFleet = computed(() => props.room?.myFleet)
const player = (side) => props.room?.players?.[String(side)]

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

// Tàu của đối thủ hiển thị trên bàn
const opponentSunkShips = computed(() => opponentBoard.value?.sunkShips || [])

const opponentSurvivingShips = computed(() => {
  if (!props.room?.winner || !opponentBoard.value?.revealedShips) return []
  const sunkNames = new Set(opponentSunkShips.value.map((s) => s.name))
  return opponentBoard.value.revealedShips.filter((s) => !sunkNames.has(s.name))
})

const opponentBoardShips = computed(() => {
  const list = opponentSunkShips.value.map((s) => ({ ...s, sunk: true }))
  if (props.room?.winner) {
    for (const ship of opponentSurvivingShips.value) {
      list.push({ ...ship, sunk: false, revealed: true })
    }
  }
  return list
})

// Tàu của người chơi hiển thị trên bàn
const myBoardShips = computed(() => {
  if (!myFleet.value?.ships?.length) return []
  const sunkNames = new Set((myFleet.value.sunkShips || []).map((s) => s.name))
  return myFleet.value.ships.map((s) => ({
    ...s,
    sunk: sunkNames.has(s.name),
  }))
})

function hasOpponentVisibleShipAt(r, c) {
  return opponentBoardShips.value.some((ship) =>
    getShipCells(ship.r, ship.c, ship.len, ship.vertical).some((cell) => cell.r === r && cell.c === c)
  )
}

function hasMyShipAt(r, c) {
  return myBoardShips.value.some((ship) =>
    getShipCells(ship.r, ship.c, ship.len, ship.vertical).some((cell) => cell.r === r && cell.c === c)
  )
}

function isOpponentShot(r, c) {
  if (!opponentBoard.value) return false
  const inHits = opponentBoard.value.hits?.some(([hr, hc]) => hr === r && hc === c)
  const inMisses = opponentBoard.value.misses?.some(([mr, mc]) => mr === r && mc === c)
  return inHits || inMisses
}

function onOpponentCellClick(r, c) {
  if (!props.canShoot) return
  if (isOpponentShot(r, c)) return
  emit('shoot', r, c)
}

function getOpponentCellState(r, c) {
  if (!opponentBoard.value) return {}
  const isHit = opponentBoard.value.hits?.some(([hr, hc]) => hr === r && hc === c)
  const isMiss = opponentBoard.value.misses?.some(([mr, mc]) => mr === r && mc === c)
  let isSunk = false
  if (opponentBoard.value.sunkShips) {
    for (const ship of opponentBoard.value.sunkShips) {
      if (ship.cells?.some(([sr, sc]) => sr === r && sc === c)) {
        isSunk = true
        break
      }
    }
  }
  const isLast = props.lastShot?.side === props.you && props.lastShot?.r === r && props.lastShot?.c === c
  return {
    isHit,
    isMiss,
    isSunk,
    isLastShot: isLast,
    clickable: props.canShoot && !isHit && !isMiss,
    overShip: hasOpponentVisibleShipAt(r, c),
  }
}

function getMyCellState(r, c) {
  let isSunk = false
  if (myFleet.value?.sunkShips) {
    for (const ship of myFleet.value.sunkShips) {
      if (ship.cells?.some(([sr, sc]) => sr === r && sc === c)) {
        isSunk = true
        break
      }
    }
  }
  const isHit = myFleet.value?.hits?.some(([hr, hc]) => hr === r && hc === c)
  const isMiss = myFleet.value?.misses?.some(([mr, mc]) => mr === r && mc === c)
  const isLast = props.lastShot?.side !== props.you && props.lastShot?.r === r && props.lastShot?.c === c

  return {
    isHit,
    isMiss,
    isSunk,
    isLastShot: isLast,
    clickable: false,
    overShip: hasMyShipAt(r, c),
  }
}

// Người xem
function getSpectatorShips(side) {
  const b = props.room?.boards?.[String(side)]
  if (!b) return []
  const list = (b.sunkShips || []).map((s) => ({ ...s, sunk: true }))
  if (props.room?.winner && b.revealedShips) {
    const sunkNames = new Set((b.sunkShips || []).map((s) => s.name))
    for (const ship of b.revealedShips) {
      if (!sunkNames.has(ship.name)) {
        list.push({ ...ship, sunk: false, revealed: true })
      }
    }
  }
  return list
}

function hasSpectatorVisibleShipAt(side, r, c) {
  return getSpectatorShips(side).some((ship) =>
    getShipCells(ship.r, ship.c, ship.len, ship.vertical).some((cell) => cell.r === r && cell.c === c)
  )
}

function getSpectatorCellState(side, r, c) {
  const b = props.room?.boards?.[String(side)]
  if (!b) return {}
  const isHit = b.hits?.some(([hr, hc]) => hr === r && hc === c)
  const isMiss = b.misses?.some(([mr, mc]) => mr === r && mc === c)
  let isSunk = false
  if (b.sunkShips) {
    for (const ship of b.sunkShips) {
      if (ship.cells?.some(([sr, sc]) => sr === r && sc === c)) {
        isSunk = true
        break
      }
    }
  }
  const isLast = props.lastShot?.side !== side && props.lastShot?.r === r && props.lastShot?.c === c
  return {
    isHit,
    isMiss,
    isSunk,
    isLastShot: isLast,
    clickable: false,
    overShip: hasSpectatorVisibleShipAt(side, r, c),
  }
}
</script>

<template>
  <div>
    <!-- MÀN CHƠI CỦA NGƯỜI TRONG PHÒNG -->
    <div v-if="you" class="battle-container">
      <!-- Vùng biển đối phương -->
      <div class="card battle-panel">
        <div class="panel-header">
          <h3>🎯 Vùng biển đối phương (Khai hỏa)</h3>
          <span v-if="canShoot" class="badge-turn you">Lượt bắn của bạn</span>
          <span v-else class="badge-turn wait">Chờ đối thủ…</span>
        </div>
        <SeaBoard
          :disabled="!canShoot"
          :ships="opponentBoardShips"
          :get-cell-state="getOpponentCellState"
          @cell-click="onOpponentCellClick"
        />
      </div>

      <!-- Vùng biển của bạn -->
      <div class="card battle-panel radar-panel">
        <div class="panel-header">
          <h3>🛡️ Vùng biển của bạn (Phòng thủ)</h3>
          <span class="small muted">Vị trí tàu & các phát bắn từ địch</span>
        </div>
        <SeaBoard
          :disabled="true"
          :ships="myBoardShips"
          :get-cell-state="getMyCellState"
        />
      </div>
    </div>

    <!-- MÀN CHƠI CỦA NGƯỜI XEM (SPECTATOR) -->
    <div v-else class="battle-container">
      <!-- Bàn của bên 1 -->
      <div class="card battle-panel">
        <div class="panel-header">
          <h3>⚓ Vùng biển của {{ player(1)?.name || 'Bên 1' }}</h3>
        </div>
        <SeaBoard
          :disabled="true"
          :ships="getSpectatorShips(1)"
          :get-cell-state="(r, c) => getSpectatorCellState(1, r, c)"
        />
      </div>

      <!-- Bàn của bên 2 -->
      <div class="card battle-panel">
        <div class="panel-header">
          <h3>⚓ Vùng biển của {{ player(2)?.name || 'Bên 2' }}</h3>
        </div>
        <SeaBoard
          :disabled="true"
          :ships="getSpectatorShips(2)"
          :get-cell-state="(r, c) => getSpectatorCellState(2, r, c)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.battle-container {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 16px;
}

.battle-panel {
  display: grid;
  gap: 12px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.panel-header h3 {
  margin: 0;
  font-size: 1.05rem;
}

.badge-turn {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 700;
}

.badge-turn.you {
  background: var(--green);
  color: #fff;
}

.badge-turn.wait {
  background: var(--grey);
  color: #fff;
}

.radar-panel {
  opacity: 0.95;
}

:deep(.radar-panel .sea-board) {
  background: #142841;
}

:deep(.radar-panel .sea-cell) {
  background: #1b3557;
}

:deep(.radar-panel .sea-cell.cell-over-ship) {
  background: transparent;
}

@media (max-width: 1050px) {
  .battle-container {
    grid-template-columns: 1fr;
  }
}
</style>

