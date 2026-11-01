<script setup>
defineProps({
  inviteLink: { type: String, required: true },
  copied: { type: Boolean, default: false },
})
defineEmits(['copy'])
</script>

<template>
  <div class="invite">
    <span class="small muted">Gửi link này cho bạn cùng mạng LAN:</span>
    <div class="row">
      <input class="input small" readonly :value="inviteLink" @focus="$event.target.select()" />
      <button class="btn blue" @click="$emit('copy')">{{ copied ? 'Đã chép' : 'Chép' }}</button>
    </div>
  </div>
</template>

