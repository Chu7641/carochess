<script setup>
import { reactive } from 'vue'
import { createRoom, state } from '../../game.js'

defineProps({
  info: { type: Object, default: () => ({ xiangqiLevels: [] }) },
})

const emit = defineEmits(['created'])

const bot = reactive({ level: 1, side: 1 })
const pvp = reactive({ side: 1 })

function startBot() {
  createRoom({
    game: 'xiangqi',
    mode: 'bot',
    level: bot.level,
    side: bot.side,
  })
  emit('created')
}

function startPvp() {
  createRoom({
    game: 'xiangqi',
    mode: 'pvp',
    side: pvp.side,
  })
  emit('created')
}
</script>

<template>
  <div class="create-forms">
    <div class="card subcard">
      <h2>🤖 Chơi với máy</h2>
      <div class="field">
        <span>Độ khó</span>
        <div class="segmented">
          <button
            v-for="level in info.xiangqiLevels?.length ? info.xiangqiLevels : [
              { id: 0, name: 'Dễ' },
              { id: 1, name: 'Vừa' },
              { id: 2, name: 'Khó' }
            ]"
            :key="level.id"
            :class="{ active: bot.level === level.id }"
            @click="bot.level = level.id"
          >
            {{ level.name }} <small v-if="level.seconds" class="muted-on">· {{ level.seconds }}s</small>
          </button>
        </div>
      </div>
      <div class="field">
        <span>Bạn cầm quân</span>
        <div class="segmented">
          <button :class="{ active: bot.side === 1 }" @click="bot.side = 1">🔴 Đỏ · đi trước</button>
          <button :class="{ active: bot.side === 2 }" @click="bot.side = 2">⚫ Đen · máy đi trước</button>
        </div>
      </div>
      <button class="btn green block" :disabled="!state.connected" @click="startBot">
        Bắt đầu ván với máy
      </button>
    </div>

    <div class="card subcard">
      <h2>👥 Chơi với người (mạng LAN)</h2>
      <div class="field">
        <span>Bên bạn chọn cầm</span>
        <div class="segmented">
          <button :class="{ active: pvp.side === 1 }" @click="pvp.side = 1">🔴 Đỏ · đi trước</button>
          <button :class="{ active: pvp.side === 2 }" @click="pvp.side = 2">⚫ Đen · đi sau</button>
        </div>
      </div>
      <button class="btn blue block" :disabled="!state.connected" @click="startPvp">
        Tạo phòng mới
      </button>
    </div>
  </div>
</template>

<style scoped>
.create-forms { display: grid; gap: 14px; }
.subcard { background: var(--bg); border: 1px solid var(--panel-border); }
.muted-on { opacity: 0.75; font-size: 0.75rem; }
</style>

