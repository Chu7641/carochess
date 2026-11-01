import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { leaveRoom, restart, state } from './game.js'

/**
 * Composable dùng chung cho các màn chơi đối kháng (Caro, Cờ vây, Cờ tướng, Hải chiến).
 * Quản lý đồng hồ client, link mời, copy link, xác nhận rời phòng/ván mới, trạng thái sẵn sàng và xin đi lại.
 */
export function useRoomView(options = {}) {
  const room = computed(() => state.room)
  const you = computed(() => room.value?.you)
  const isBot = computed(() => room.value?.mode === 'bot')

  const playing = computed(() => {
    if (typeof options.isPlaying === 'function') {
      return options.isPlaying(room.value)
    }
    const r = room.value
    return !!(r && r.winner === 0 && !r.waiting && r.started)
  })

  const needReady = computed(() => {
    if (typeof options.isNeedReady === 'function') {
      return options.isNeedReady(room.value, isBot.value)
    }
    const r = room.value
    return !!(r && r.winner === 0 && !r.waiting && !r.started)
  })

  const iAmReady = computed(() => {
    return !!room.value?.ready?.includes(you.value)
  })

  const lanIps = ref([])
  const copied = ref(false)
  const now = ref(Date.now())
  let ticker = null

  onMounted(async () => {
    ticker = setInterval(() => { now.value = Date.now() }, 200)
    try {
      const res = await fetch('/api/info')
      const data = await res.json()
      lanIps.value = data.lan || []
    } catch {
      // Dùng địa chỉ mặc định
    }
  })

  onUnmounted(() => {
    if (ticker) clearInterval(ticker)
  })

  const turnLeft = computed(() => {
    const r = room.value
    if (!r || r.turnLeft == null) return null
    const received = r.receivedAt || now.value
    return Math.max(0, Math.ceil(r.turnLeft - (now.value - received) / 1000))
  })

  const inviteLink = computed(() => {
    const r = room.value
    if (!r?.code) return ''
    const local = ['localhost', '127.0.0.1', '::1', '[::1]'].includes(location.hostname)
    const host = local && lanIps.value.length
      ? `${lanIps.value[0]}${location.port ? `:${location.port}` : ''}`
      : location.host
    return `${location.protocol}//${host}/?room=${r.code}`
  })

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(inviteLink.value)
    } catch {
      const input = document.createElement('textarea')
      input.value = inviteLink.value
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      input.remove()
    }
    copied.value = true
    setTimeout(() => { copied.value = false }, 1500)
  }

  const player = (side) => room.value?.players?.[String(side)]

  const request = computed(() => {
    const r = room.value?.request
    if (!r) return null
    const mine = r.side === you.value
    const name = player(r.side)?.name ?? (options.sideName ? options.sideName(r.side) : `Bên ${r.side}`)
    return {
      mine,
      canAnswer: !mine && you.value != null,
      text: mine ? 'Đang chờ đối thủ đồng ý cho bạn đi lại…' : `${name} xin đi lại.`,
    }
  })

  // Popup kết quả: chỉ bật đúng lúc ván vừa kết thúc trong phòng đang xem (winner 0 -> khác 0),
  // không bật khi mới vào một phòng đã xong từ trước. Ván mới (winner về 0) thì tự đóng.
  const result = ref(null)
  watch(() => [room.value?.code, room.value?.winner], ([code, winner], [oldCode, oldWinner] = []) => {
    if (!winner) {
      result.value = null
      return
    }
    if (code !== oldCode || oldWinner !== 0) return
    const r = room.value
    const me = you.value
    const name = player(winner)?.name ?? (options.sideName ? options.sideName(winner) : `Bên ${winner}`)
    const delta = me != null ? player(me)?.eloDelta : null
    let title, tone
    if (winner === -1) {
      title = '🤝 Hòa!'
      tone = 'draw'
    } else if (me == null) {
      title = `🏆 ${name} thắng!`
      tone = 'info'
    } else if (winner === me) {
      title = '🎉 Bạn thắng!'
      tone = 'win'
    } else {
      title = '😞 Bạn thua'
      tone = 'lose'
    }
    result.value = {
      title,
      tone,
      detail: r.notice || '',
      elo: delta ? `${delta > 0 ? '+' : ''}${delta} elo` : '',
      canRestart: me != null,
    }
  })

  const confirmNewGameText = options.confirmNewGame ??
    'Ván chưa xong. Bắt đầu ván mới sẽ tính là bạn thua (trừ elo). Tiếp tục?'

  const confirmLeaveText = options.confirmLeave ??
    'Ván chưa xong. Rời phòng giữa ván sẽ bị tính là bạn thua (trừ elo). Tiếp tục?'

  function handleNewGame() {
    const r = room.value
    const hasMoves = Boolean(r?.moves)
    if (!isBot.value && playing.value && hasMoves && !confirm(confirmNewGameText)) {
      return
    }
    restart()
  }

  function handleLeave() {
    const r = room.value
    const hasMoves = Boolean(r?.moves)
    if (!isBot.value && playing.value && hasMoves && !confirm(confirmLeaveText)) {
      return
    }
    leaveRoom()
  }

  return {
    room,
    you,
    isBot,
    playing,
    needReady,
    iAmReady,
    now,
    lanIps,
    turnLeft,
    inviteLink,
    copied,
    copyLink,
    player,
    request,
    result,
    closeResult: () => { result.value = null },
    newGame: handleNewGame,
    handleNewGame,
    handleLeave,
  }
}

