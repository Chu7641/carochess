<script setup>
defineProps({
  request: { type: Object, default: null },
})
defineEmits(['respond'])
</script>

<template>
  <div v-if="request" class="request" :class="{ ask: request.canAnswer }" role="status">
    <span>{{ request.text }}</span>
    <div v-if="request.canAnswer" class="row">
      <button class="btn green" @click="$emit('respond', true)">Đồng ý</button>
      <button class="btn red" @click="$emit('respond', false)">Từ chối</button>
    </div>
  </div>
</template>

