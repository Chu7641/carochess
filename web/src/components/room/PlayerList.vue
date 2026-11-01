<script setup>
const props = defineProps({
  sides: { type: Array, required: true },
  room: { type: Object, required: true },
  you: { default: null },
  turnLeft: { type: Number, default: null },
  playing: { type: Boolean, default: false },
  needReady: { type: Boolean, default: false },
  getSideDot: { type: Function, default: (s) => ({ label: String(s), class: '' }) },
})

const player = (side) => props.room?.players?.[String(side)]
</script>

<template>
  <ul class="players">
    <li v-for="side in sides" :key="side" :class="{ turn: playing && room.current === side }">
      <span class="dot" :class="getSideDot(side).class">{{ getSideDot(side).label }}</span>
      <span class="pname">
        {{ player(side)?.name ?? 'Đang chờ…' }}
        <em v-if="side === you" class="small muted">(bạn)</em>
      </span>

      <slot name="status" :side="side" :player="player(side)">
        <span v-if="needReady && room.ready?.includes(side)" class="ready small">✓ Sẵn sàng</span>
      </slot>

      <span
        v-if="turnLeft != null && room.current === side"
        class="clock"
        :class="{ low: turnLeft <= 10 }"
        :title="`Mỗi lượt ${room.turnSeconds || 30} giây`"
      >
        ⏱ {{ turnLeft }}s
      </span>

      <span v-if="player(side)?.elo != null" class="elo small">
        {{ player(side).elo }}
        <b v-if="player(side).eloDelta" :class="player(side).eloDelta > 0 ? 'up' : 'down'">
          {{ player(side).eloDelta > 0 ? '+' : '' }}{{ player(side).eloDelta }}
        </b>
      </span>

      <span
        v-if="player(side) && !player(side).bot"
        class="online"
        :class="{ off: !player(side).online }"
        :title="player(side).online ? 'Đang kết nối' : 'Mất kết nối'"
      ></span>
    </li>
  </ul>
</template>

