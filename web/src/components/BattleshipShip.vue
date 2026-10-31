<script setup>
import { computed, ref } from 'vue'

let instanceCounter = 0

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  len: {
    type: Number,
    required: true,
  },
  vertical: {
    type: Boolean,
    default: false,
  },
  state: {
    type: String,
    default: 'normal', // 'normal' | 'preview-ok' | 'preview-bad' | 'sunk'
  },
})

// ID duy nhất cho mỗi instance để tránh trùng gradient/filter khi có nhiều tàu trên trang
const uid = ref(`bsship-${++instanceCounter}`)

const totalWidth = computed(() => props.len * 100)

const viewBox = computed(() => {
  return props.vertical
    ? `0 0 100 ${totalWidth.value}`
    : `0 0 ${totalWidth.value} 100`
})

const transformGroup = computed(() => {
  return props.vertical ? 'translate(100, 0) rotate(90)' : ''
})

// Chuẩn hóa tên tàu để nhận diện đúng loại
const shipType = computed(() => {
  const n = (props.name || '').toLowerCase()
  if (n.includes('sân bay') || props.len === 5) return 'carrier'
  if (n.includes('thiết giáp') || props.len === 4) return 'battleship'
  if (n.includes('ngầm')) return 'submarine'
  if (n.includes('tuần dương') || (props.len === 3 && !n.includes('ngầm'))) return 'cruiser'
  return 'destroyer'
})
</script>

<template>
  <svg
    :viewBox="viewBox"
    class="battleship-svg"
    :class="[
      `state-${state}`,
      `ship-${shipType}`,
      { 'is-vertical': vertical }
    ]"
    xmlns="http://www.w3.org/2000/svg"
  >
    <defs>
      <!-- Gradient bóng đổ thân tàu -->
      <filter :id="`${uid}-shadow`" x="-5%" y="-10%" width="115%" height="130%">
        <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#0b1726" flood-opacity="0.45" />
      </filter>

      <!-- Gradient thân tàu thép chuẩn (sáng ở giữa, tối ở mép mạn) -->
      <linearGradient :id="`${uid}-hull`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#556272" />
        <stop offset="18%" stop-color="#738396" />
        <stop offset="50%" stop-color="#8b9cb0" />
        <stop offset="82%" stop-color="#738396" />
        <stop offset="100%" stop-color="#4a5563" />
      </linearGradient>

      <!-- Gradient mặt boong tàu (deck) sáng hơn thân -->
      <linearGradient :id="`${uid}-deck`" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#7d8c9e" />
        <stop offset="50%" stop-color="#9aabc0" />
        <stop offset="100%" stop-color="#8595a8" />
      </linearGradient>

      <!-- Gradient thân tàu ngầm (kim loại tối xám đen) -->
      <linearGradient :id="`${uid}-sub-hull`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#242c35" />
        <stop offset="25%" stop-color="#3d4957" />
        <stop offset="50%" stop-color="#4f5e70" />
        <stop offset="75%" stop-color="#3d4957" />
        <stop offset="100%" stop-color="#1f262e" />
      </linearGradient>

      <!-- Gradient tháp chỉ huy / thượng tầng -->
      <linearGradient :id="`${uid}-tower`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#647487" />
        <stop offset="50%" stop-color="#8394a8" />
        <stop offset="100%" stop-color="#526173" />
      </linearGradient>

      <!-- Gradient tháp pháo -->
      <radialGradient :id="`${uid}-turret`" cx="40%" cy="40%" r="60%">
        <stop offset="0%" stop-color="#9cb0c7" />
        <stop offset="70%" stop-color="#6d7d91" />
        <stop offset="100%" stop-color="#4d5968" />
      </radialGradient>
    </defs>

    <!-- Nhóm vẽ toạ độ nằm ngang chuẩn: x từ 0 tới len*100, y từ 0 tới 100 -->
    <g :transform="transformGroup">
      <!-- LỚP TÀU CHÌM: Nghiêng nhẹ nếu bị chìm -->
      <g :transform="state === 'sunk' ? `rotate(3.5 ${totalWidth / 2} 50)` : ''">
        <!-- 1. TÀU SÂN BAY (5 ô - 500x100) -->
        <g v-if="shipType === 'carrier'">
          <!-- Đáy thân tàu rẽ nước -->
          <path
            d="M 16,50 C 16,28 32,16 65,16 L 430,16 C 465,16 484,30 488,50 C 484,70 465,84 430,84 L 65,84 C 32,84 16,72 16,50 Z"
            :fill="`url(#${uid}-hull)`"
            stroke="#2e3844"
            stroke-width="2"
            :filter="`url(#${uid}-shadow)`"
          />

          <!-- Boong bay phẳng rộng (flight deck) -->
          <polygon
            points="24,24 42,14 465,14 485,35 485,65 465,86 42,86 24,76"
            :fill="`url(#${uid}-deck)`"
            stroke="#3a4654"
            stroke-width="1.5"
          />

          <!-- Kẻ vạch đường băng (runway markings) -->
          <line x1="45" y1="50" x2="465" y2="50" stroke="#f4eedb" stroke-width="3" stroke-dasharray="18 12" />
          <line x1="50" y1="28" x2="440" y2="28" stroke="#f4eedb" stroke-width="1.5" stroke-dasharray="8 8" opacity="0.75" />
          <line x1="50" y1="72" x2="440" y2="72" stroke="#f4eedb" stroke-width="1.5" stroke-dasharray="8 8" opacity="0.75" />

          <!-- Thang nâng máy bay (aircraft elevators) -->
          <rect x="175" y="19" width="36" height="20" fill="#697787" stroke="#eeb63d" stroke-width="1" stroke-dasharray="4 2" />
          <rect x="345" y="61" width="36" height="20" fill="#697787" stroke="#eeb63d" stroke-width="1" stroke-dasharray="4 2" />

          <!-- Đảo chỉ huy (island) lệch mạn trên -->
          <rect x="270" y="15" width="52" height="14" rx="3" :fill="`url(#${uid}-tower)`" stroke="#222b35" stroke-width="1.5" />
          <rect x="282" y="17" width="20" height="9" rx="2" fill="#323e4d" />
          <!-- Cột radar đảo chỉ huy -->
          <line x1="295" y1="15" x2="295" y2="7" stroke="#333f4d" stroke-width="2" />
          <line x1="290" y1="9" x2="300" y2="9" stroke="#333f4d" stroke-width="1.5" />

          <!-- 2 Máy bay tiêm kích nhỏ đậu trên boong -->
          <!-- Máy bay 1 ở mạn dưới phía sau -->
          <g transform="translate(85, 68) scale(0.9)">
            <!-- Cánh -->
            <polygon points="0,0 -8,-10 0,-10 6,0 0,10 -8,10" fill="#303a45" />
            <!-- Thân -->
            <ellipse cx="0" cy="0" rx="9" ry="2.5" fill="#20272f" />
            <!-- Cánh đuôi -->
            <polygon points="-7,0 -10,-4 -8,0 -10,4" fill="#303a45" />
          </g>
          <!-- Máy bay 2 ở mạn dưới giữa tàu -->
          <g transform="translate(135, 68) scale(0.9)">
            <polygon points="0,0 -8,-10 0,-10 6,0 0,10 -8,10" fill="#303a45" />
            <ellipse cx="0" cy="0" rx="9" ry="2.5" fill="#20272f" />
            <polygon points="-7,0 -10,-4 -8,0 -10,4" fill="#303a45" />
          </g>
        </g>

        <!-- 2. THIẾT GIÁP HẠM (4 ô - 400x100) -->
        <g v-else-if="shipType === 'battleship'">
          <!-- Thân tàu thon nhọn ở mũi, bo tròn ở đuôi -->
          <path
            d="M 16,50 C 16,30 35,18 70,18 L 270,18 C 315,18 355,30 388,50 C 355,70 315,82 270,82 L 70,82 C 35,82 16,70 16,50 Z"
            :fill="`url(#${uid}-hull)`"
            stroke="#2d3540"
            stroke-width="2"
            :filter="`url(#${uid}-shadow)`"
          />

          <!-- Boong tàu bên trong -->
          <path
            d="M 24,50 C 24,34 40,24 75,24 L 265,24 C 305,24 345,34 374,50 C 345,66 305,76 265,76 L 75,76 C 40,76 24,66 24,50 Z"
            :fill="`url(#${uid}-deck)`"
            stroke="#414c59"
            stroke-width="1.5"
          />

          <!-- Thượng tầng chỉ huy ở giữa -->
          <path
            d="M 140,32 L 225,32 L 235,42 L 235,58 L 225,68 L 140,68 L 132,58 L 132,42 Z"
            :fill="`url(#${uid}-tower)`"
            stroke="#222b35"
            stroke-width="1.5"
          />
          <rect x="160" y="38" width="46" height="24" rx="4" fill="#505f70" stroke="#25303c" stroke-width="1" />
          <!-- 2 Ống khói đôi (funnels) -->
          <ellipse cx="173" cy="50" rx="6" ry="4" fill="#20272f" stroke="#eeb63d" stroke-width="1" />
          <ellipse cx="193" cy="50" rx="6" ry="4" fill="#20272f" stroke="#eeb63d" stroke-width="1" />
          <!-- Cột tháp radar chỉ huy -->
          <line x1="216" y1="50" x2="228" y2="50" stroke="#1f2833" stroke-width="3" />
          <line x1="222" y1="42" x2="222" y2="58" stroke="#1f2833" stroke-width="2" />

          <!-- Tháp pháo 1 (phía trước mũi, 3 nòng) -->
          <g transform="translate(315, 50)">
            <!-- 3 Nòng pháo dài vươn về mũi -->
            <line x1="0" y1="-5" x2="28" y2="-5" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <line x1="0" y1="0" x2="29" y2="0" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <line x1="0" y1="5" x2="28" y2="5" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <!-- Mâm xoay tháp pháo tròn -->
            <circle cx="0" cy="0" r="14" :fill="`url(#${uid}-turret)`" stroke="#222b35" stroke-width="1.5" />
          </g>

          <!-- Tháp pháo 2 (trước thượng tầng, bậc nâng cao, 3 nòng) -->
          <g transform="translate(265, 50)">
            <line x1="0" y1="-5" x2="27" y2="-5" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <line x1="0" y1="0" x2="28" y2="0" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <line x1="0" y1="5" x2="27" y2="5" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <circle cx="0" cy="0" r="14" :fill="`url(#${uid}-turret)`" stroke="#222b35" stroke-width="1.5" />
          </g>

          <!-- Tháp pháo 3 (phía sau đuôi, 3 nòng hướng về đuôi) -->
          <g transform="translate(85, 50)">
            <line x1="0" y1="-5" x2="-28" y2="-5" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <line x1="0" y1="0" x2="-29" y2="0" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <line x1="0" y1="5" x2="-28" y2="5" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <circle cx="0" cy="0" r="14" :fill="`url(#${uid}-turret)`" stroke="#222b35" stroke-width="1.5" />
          </g>
        </g>

        <!-- 3. TUẦN DƯƠNG HẠM (3 ô - 300x100) -->
        <g v-else-if="shipType === 'cruiser'">
          <!-- Thân tàu thon thả, nhanh nhẹn -->
          <path
            d="M 14,50 C 14,33 30,22 65,22 L 205,22 C 242,22 272,33 290,50 C 272,67 242,78 205,78 L 65,78 C 30,78 14,67 14,50 Z"
            :fill="`url(#${uid}-hull)`"
            stroke="#2d3540"
            stroke-width="2"
            :filter="`url(#${uid}-shadow)`"
          />

          <!-- Boong tàu bên trong -->
          <path
            d="M 22,50 C 22,36 36,26 68,26 L 200,26 C 235,26 262,36 278,50 C 262,64 235,74 200,74 L 68,74 C 36,74 22,64 22,50 Z"
            :fill="`url(#${uid}-deck)`"
            stroke="#414c59"
            stroke-width="1.5"
          />

          <!-- Thượng tầng và cầu tàu -->
          <rect x="115" y="36" width="65" height="28" rx="4" :fill="`url(#${uid}-tower)`" stroke="#232b35" stroke-width="1.5" />
          <rect x="135" y="42" width="28" height="16" rx="2" fill="#505f70" />
          <!-- 1 Ống khói chính -->
          <ellipse cx="168" cy="50" rx="5" ry="3.5" fill="#20272f" stroke="#eeb63d" stroke-width="1" />
          <!-- Cột radar chữ thập -->
          <line x1="125" y1="50" x2="135" y2="50" stroke="#1f2833" stroke-width="2.5" />
          <line x1="130" y1="44" x2="130" y2="56" stroke="#1f2833" stroke-width="2" />

          <!-- Tháp pháo 1 (phía trước mũi, 2 nòng) -->
          <g transform="translate(232, 50)">
            <line x1="0" y1="-3.5" x2="24" y2="-3.5" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <line x1="0" y1="3.5" x2="24" y2="3.5" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <circle cx="0" cy="0" r="12" :fill="`url(#${uid}-turret)`" stroke="#222b35" stroke-width="1.5" />
          </g>

          <!-- Tháp pháo 2 (phía sau đuôi, 2 nòng hướng về đuôi) -->
          <g transform="translate(68, 50)">
            <line x1="0" y1="-3.5" x2="-24" y2="-3.5" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <line x1="0" y1="3.5" x2="-24" y2="3.5" stroke="#1c242d" stroke-width="2.5" stroke-linecap="round" />
            <circle cx="0" cy="0" r="12" :fill="`url(#${uid}-turret)`" stroke="#222b35" stroke-width="1.5" />
          </g>
        </g>

        <!-- 4. TÀU NGẦM (3 ô - 300x100) -->
        <g v-else-if="shipType === 'submarine'">
          <!-- Cánh lái đuôi chữ thập nhô ra ngoài -->
          <polygon points="12,50 35,32 42,35 24,50 42,65 35,68" fill="#1b2229" stroke="#11161b" stroke-width="1" />

          <!-- Thân hình điếu xì gà bo tròn đều hai đầu -->
          <path
            d="M 22,50 C 22,30 42,25 90,25 L 215,25 C 260,25 280,30 280,50 C 280,70 260,75 215,75 L 90,75 C 42,75 22,70 22,50 Z"
            :fill="`url(#${uid}-sub-hull)`"
            stroke="#182028"
            stroke-width="2"
            :filter="`url(#${uid}-shadow)`"
          />

          <!-- Rãnh thoát nước và sọc thân tàu ngầm -->
          <line x1="60" y1="36" x2="240" y2="36" stroke="#28333e" stroke-width="1.5" stroke-dasharray="10 4" />
          <line x1="60" y1="64" x2="240" y2="64" stroke="#28333e" stroke-width="1.5" stroke-dasharray="10 4" />

          <!-- Cánh lặn mạn trước (bow diving planes) -->
          <rect x="238" y="21" width="12" height="4" rx="1.5" fill="#202832" />
          <rect x="238" y="75" width="12" height="4" rx="1.5" fill="#202832" />

          <!-- Cửa nắp phóng lôi trước mũi (torpedo tubes) -->
          <ellipse cx="270" cy="45" rx="3" ry="2" fill="#151b22" />
          <ellipse cx="270" cy="55" rx="3" ry="2" fill="#151b22" />

          <!-- Tháp chỉ huy (conning tower / sail) ở giữa -->
          <rect x="132" y="38" width="46" height="24" rx="8" fill="#27323d" stroke="#161c23" stroke-width="1.5" />
          <!-- Kính tiềm vọng & ăng ten trên đỉnh tháp -->
          <line x1="148" y1="38" x2="148" y2="30" stroke="#4f5e70" stroke-width="2" />
          <circle cx="148" cy="29" r="2" fill="#eeb63d" />
          <line x1="162" y1="38" x2="162" y2="27" stroke="#4f5e70" stroke-width="2" />
          <line x1="158" y1="27" x2="166" y2="27" stroke="#4f5e70" stroke-width="1.5" />
        </g>

        <!-- 5. KHU TRỤC HẠM (2 ô - 200x100) -->
        <g v-else>
          <!-- Thân tàu mảnh dẻo, rẽ sóng -->
          <path
            d="M 12,50 C 12,36 24,25 50,25 L 135,25 C 160,25 180,36 190,50 C 180,64 160,75 135,75 L 50,75 C 24,75 12,64 12,50 Z"
            :fill="`url(#${uid}-hull)`"
            stroke="#2d3540"
            stroke-width="2"
            :filter="`url(#${uid}-shadow)`"
          />

          <!-- Boong tàu bên trong -->
          <path
            d="M 18,50 C 18,39 28,29 52,29 L 130,29 C 152,29 170,39 180,50 C 170,61 152,71 130,71 L 52,71 C 28,71 18,61 18,50 Z"
            :fill="`url(#${uid}-deck)`"
            stroke="#414c59"
            stroke-width="1.5"
          />

          <!-- Thượng tầng và cầu chỉ huy -->
          <rect x="80" y="38" width="42" height="24" rx="3" :fill="`url(#${uid}-tower)`" stroke="#222b35" stroke-width="1.5" />
          <rect x="92" y="43" width="18" height="14" rx="2" fill="#505f70" />
          <!-- Ống khói nhỏ -->
          <ellipse cx="114" cy="50" rx="4" ry="3" fill="#20272f" stroke="#eeb63d" stroke-width="0.8" />
          <!-- Cột ăng ten nhỏ -->
          <line x1="88" y1="50" x2="94" y2="50" stroke="#1f2833" stroke-width="2" />
          <line x1="91" y1="45" x2="91" y2="55" stroke="#1f2833" stroke-width="1.5" />

          <!-- 1 Tháp pháo phía trước (2 nòng) -->
          <g transform="translate(148, 50)">
            <line x1="0" y1="-3" x2="18" y2="-3" stroke="#1c242d" stroke-width="2" stroke-linecap="round" />
            <line x1="0" y1="3" x2="18" y2="3" stroke="#1c242d" stroke-width="2" stroke-linecap="round" />
            <circle cx="0" cy="0" r="10" :fill="`url(#${uid}-turret)`" stroke="#222b35" stroke-width="1.5" />
          </g>

          <!-- Bệ phóng ngư lôi ở sau (torpedo launcher) -->
          <g transform="translate(48, 50)">
            <rect x="-8" y="-7" width="16" height="14" rx="2" fill="#364352" stroke="#202933" stroke-width="1" />
            <line x1="-7" y1="-3" x2="7" y2="-3" stroke="#182029" stroke-width="1.5" />
            <line x1="-7" y1="3" x2="7" y2="3" stroke="#182029" stroke-width="1.5" />
          </g>
        </g>

        <!-- HIỆU ỨNG TÀU CHÌM (sunk state) -->
        <g v-if="state === 'sunk'">
          <!-- Vệt cháy đen trên thân tàu -->
          <ellipse :cx="totalWidth * 0.28" cy="48" rx="16" ry="10" fill="#15171a" opacity="0.85" />
          <ellipse :cx="totalWidth * 0.62" cy="52" rx="20" ry="12" fill="#15171a" opacity="0.85" />
          <ellipse :cx="totalWidth * 0.82" cy="45" rx="12" ry="8" fill="#15171a" opacity="0.8" />

          <!-- Vòng khói đen xám mờ ảo bốc lên -->
          <circle :cx="totalWidth * 0.3" cy="42" r="14" fill="#2d3238" opacity="0.6" />
          <circle :cx="totalWidth * 0.26" cy="34" r="10" fill="#4d535a" opacity="0.45" />
          <circle :cx="totalWidth * 0.64" cy="45" r="16" fill="#2d3238" opacity="0.6" />
          <circle :cx="totalWidth * 0.67" cy="35" r="12" fill="#4d535a" opacity="0.45" />
          <circle :cx="totalWidth * 0.82" cy="40" r="11" fill="#3a4047" opacity="0.5" />
        </g>
      </g>
    </g>

    <!-- VIỀN HIỆU ỨNG XEM TRƯỚC (preview state) -->
    <rect
      v-if="state === 'preview-ok'"
      x="2"
      y="2"
      :width="vertical ? 96 : totalWidth - 4"
      :height="vertical ? totalWidth - 4 : 96"
      rx="8"
      fill="none"
      stroke="var(--green, #387e57)"
      stroke-width="3"
      stroke-dasharray="8 4"
    />
    <rect
      v-else-if="state === 'preview-bad'"
      x="2"
      y="2"
      :width="vertical ? 96 : totalWidth - 4"
      :height="vertical ? totalWidth - 4 : 96"
      rx="8"
      fill="none"
      stroke="var(--red, #b8483e)"
      stroke-width="3"
      stroke-dasharray="8 4"
    />
  </svg>
</template>

<style scoped>
.battleship-svg {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.35));
}

/* Các trạng thái */
.state-preview-ok {
  opacity: 0.65;
  filter: drop-shadow(0 0 6px rgba(56, 126, 87, 0.8));
}

.state-preview-bad {
  opacity: 0.65;
  filter: drop-shadow(0 0 6px rgba(184, 72, 62, 0.8));
}

.state-sunk {
  opacity: 0.85;
  filter: grayscale(0.7) brightness(0.45) contrast(1.15) drop-shadow(0 2px 6px rgba(0, 0, 0, 0.6));
}
</style>

