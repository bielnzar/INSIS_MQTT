<template>
  <header class="mb-8 text-center">
    <h1 class="text-4xl font-bold tracking-tight">Prakiraan Cuaca MQTT</h1>
    <p class="text-xl text-sky-200 mt-1">{{ locationName }}</p>
    <p class="text-sm mt-2">
      Sumber Data: BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)
    </p>
  </header>
</template>

<script setup>
defineProps({
  locationName: String,
});
</script>
