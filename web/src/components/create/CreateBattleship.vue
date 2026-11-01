<script setup>
import { reactive } from 'vue'
import { createRoom, state } from '../../game.js'

defineProps({
  info: { type: Object, default: () => ({ battleshipLevels: [] }) },
})

const bot = reactive({ level: 1, side: 1 })
const pvp = reactive({ side: 1 })

function startBot() {
  createRoom({
    game: 'battleship',
    mode: 'bot',
    level: bot.level,
    side: bot.side,
  })
}

function startPvp() {
  createRoom({
    game: 'battleship',
    mode: 'pvp',
    side: pvp.side,
  })
}
</script>

<template>
  <div class="create-forms">
    <div class="card subcard">
      <h2>🤖 Đấu với máy</h2>
      <div class="field">
        <span>Độ khó</span>
        <div class="segmented">
          <button
            v-for="level in info.battleshipLevels?.length ? info.battleshipLevels : [
              { id: 0, name: 'Dễ' },
              { id: 1, name: 'Vừa' },
              { id: 2, name: 'Khó' }
            ]"
            :key="level.id"
            :class="{ active: bot.level === level.id }"
            @click="bot.level = level.id"
          >
            {{ level.name }}
          </button>
        </div>
      </div>
      <div class="field">
        <span>Lượt bắn trước</span>
        <div class="segmented">
          <button :class="{ active: bot.side === 1 }" @click="bot.side = 1">
            🎯 Bạn bắn trước
          </button>
          <button :class="{ active: bot.side === 2 }" @click="bot.side = 2">
            🤖 Máy bắn trước
          </button>
        </div>
      </div>
      <button class="btn green block" :disabled="!state.connected" @click="startBot">
        Bắt đầu trận chiến với máy
      </button>
    </div>

    <div class="card subcard">
      <h2>👥 Đấu người qua LAN</h2>
      <div class="field">
        <span>Bên của bạn</span>
        <div class="segmented">
          <button :class="{ active: pvp.side === 1 }" @click="pvp.side = 1">
            🔵 Bên 1 (Xanh)
          </button>
          <button :class="{ active: pvp.side === 2 }" @click="pvp.side = 2">
            🔴 Bên 2 (Đỏ)
          </button>
        </div>
      </div>
      <button class="btn blue block" :disabled="!state.connected" @click="startPvp">
        Tạo phòng hải chiến mới
      </button>
    </div>
  </div>
</template>

<style scoped>
.create-forms { display: grid; gap: 14px; }
.subcard { background: var(--bg); border: 1px solid var(--panel-border); }
</style>

