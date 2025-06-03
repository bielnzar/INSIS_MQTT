<template>
  <div class="w-full mt-5">
    <div
      v-if="isLoading && (!forecasts || forecasts.length === 0)"
      class="text-center p-10 text-gray-500 bg-gray-50 border border-dashed border-gray-300 rounded-lg min-h-[150px] flex flex-col items-center justify-center"
    >
      <p>Sedang memuat data prakiraan cuaca...</p>
      <p class="text-xs text-gray-400 mt-2">
        (Pastikan Mosquitto & Publisher berjalan)
      </p>
    </div>
    <div
      v-else-if="!isLoading && (!forecasts || forecasts.length === 0)"
      class="text-center p-10 text-gray-500 bg-gray-50 border border-dashed border-gray-300 rounded-lg min-h-[150px] flex flex-col items-center justify-center"
    >
      <p>Belum ada data prakiraan cuaca untuk lokasi ini.</p>
      <p class="text-xs text-gray-400 mt-2">
        Pastikan Publisher Python telah mengirim data untuk kode ADM4 yang
        dipilih, dan Broker MQTT berjalan.
      </p>
    </div>
    <div
      v-else
      class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
    >
      <WeatherCard
        v-for="item in sortedForecasts"
        :key="item.datetime"
        :forecast="item"
      />
    </div>
  </div>
</template>

<script>
import WeatherCard from "./WeatherCard.vue";

export default {
  name: "WeatherDashboard",
  components: {
    WeatherCard,
  },
  props: {
    forecasts: {
      type: Array,
      default: () => [],
    },
    isLoading: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    sortedForecasts() {
      return [...this.forecasts].sort((a, b) => {
        try {
          const timeA = new Date(a.datetime);
          const timeB = new Date(b.datetime);
          return timeA - timeB;
        } catch (e) {
          console.warn("Error saat sorting forecast:", e, a, b);
          return 0;
        }
      });
    },
  },
};
</script>
