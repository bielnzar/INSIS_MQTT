<template>
  <div
    class="mb-6 p-3 rounded-lg text-center"
    :class="{
      'bg-green-500/80': isConnected,
      'bg-red-500/80': !isConnected && connectionError,
      'bg-yellow-500/80': !isConnected && !connectionError && isLoading,
    }"
  >
    <span v-if="isConnected">Terhubung ke Broker MQTT</span>
    <span v-else-if="isLoading && !connectionError"
      >Menghubungkan ke Broker MQTT...</span
    >
    <span v-else-if="connectionError">{{ connectionError }}</span>
    <span v-else>Terputus dari Broker MQTT</span>
  </div>
</template>

<script setup>
defineProps({
  isConnected: Boolean,
  isLoading: Boolean,
  connectionError: String,
});
</script>
