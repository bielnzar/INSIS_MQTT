<template>
  <div
    class="bg-white/20 p-4 rounded-lg shadow-lg hover:shadow-xl transition-shadow duration-300"
  >
    <div class="text-center mb-3">
      <img
        v-if="period.image"
        :src="period.image"
        :alt="period.weather_desc_en"
        class="h-16 w-16 mx-auto mb-2"
      />
      <p
        v-else
        class="h-16 w-16 flex items-center justify-center text-3xl mx-auto mb-2"
      >
        ?
      </p>
      <p class="font-semibold text-lg">{{ period.weather_desc }}</p>
      <p class="text-sm text-sky-100">
        {{ formatDateTime(period.local_datetime) }}
      </p>
    </div>
    <div class="space-y-1 text-sm">
      <div class="flex justify-between">
        <span>Suhu:</span>
        <span class="font-medium">{{ period.t }} °C</span>
      </div>
      <div class="flex justify-between">
        <span>Kelembaban:</span>
        <span class="font-medium">{{ period.hu }} %</span>
      </div>
      <div class="flex justify-between">
        <span>Angin:</span>
        <span class="font-medium">{{ period.ws }} km/j ({{ period.wd }})</span>
      </div>
      <div class="flex justify-between">
        <span>Tutupan Awan:</span>
        <span class="font-medium">{{ period.tcc }} %</span>
      </div>
      <div class="flex justify-between">
        <span>Jarak Pandang:</span>
        <span class="font-medium">{{ period.vs_text }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  period: Object,
});

function formatDateTime(isoString) {
  if (!isoString) return "N/A";
  try {
    const date = new Date(isoString);
    return date.toLocaleString("id-ID", {
      weekday: "short",
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (error) {
    return isoString;
  }
}
</script>
