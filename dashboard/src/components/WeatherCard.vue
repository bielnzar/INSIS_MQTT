<template>
  <div
    class="bg-white border border-gray-200 rounded-lg p-5 shadow-md hover:shadow-lg transition-shadow duration-200 flex flex-col text-sm"
  >
    <h3
      class="text-lg font-semibold text-slate-700 mb-3 pb-2 border-b border-gray-100"
    >
      {{ formattedLocalDateTime }}
    </h3>
    <div class="flex items-center mb-3">
      <img
        :src="forecast.image || 'https://via.placeholder.com/50x50?text=N/A'"
        :alt="forecast.weather_desc || 'ikon cuaca'"
        class="w-12 h-12 mr-4 object-contain"
        @error="onImageError"
      />
      <span class="text-3xl font-bold text-blue-600"
        >{{ forecast.t !== undefined ? forecast.t : "-" }} °C</span
      >
    </div>
    <p class="mb-1 text-slate-600">
      <strong class="font-semibold text-slate-800">Kondisi:</strong>
      {{ forecast.weather_desc || "-" }}
    </p>
    <p class="mb-1 text-slate-600">
      <strong class="font-semibold text-slate-800">Kelembapan:</strong>
      {{ forecast.hu !== undefined ? forecast.hu : "-" }} %
    </p>
    <p class="mb-1 text-slate-600">
      <strong class="font-semibold text-slate-800">Angin:</strong>
      {{ windInfo }}
    </p>
    <p class="mb-1 text-slate-600">
      <strong class="font-semibold text-slate-800">Tutupan Awan:</strong>
      {{ forecast.tcc !== undefined ? forecast.tcc : "-" }} %
    </p>
    <p class="text-slate-600">
      <strong class="font-semibold text-slate-800">Jarak Pandang:</strong>
      {{ visibilityInfo }}
    </p>
  </div>
</template>

<script>
export default {
  name: "WeatherCard",
  props: {
    forecast: {
      type: Object,
      required: true,
    },
  },
  computed: {
    formattedLocalDateTime() {
      if (!this.forecast.local_datetime) return "Waktu Tidak Tersedia";
      try {
        const [datePart, timePart] = this.forecast.local_datetime.split(" ");
        if (!datePart || !timePart) return this.forecast.local_datetime;

        const [year, month, day] = datePart.split("-");
        const [hour, minute] = timePart.split(":");
        if (!year || !month || !day || !hour || !minute)
          return this.forecast.local_datetime;

        const dateObj = new Date(
          Number(year),
          Number(month) - 1,
          Number(day),
          Number(hour),
          Number(minute)
        );

        return (
          dateObj.toLocaleTimeString("id-ID", {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          }) +
          ", " +
          dateObj.toLocaleDateString("id-ID", {
            weekday: "short",
            day: "numeric",
            month: "short",
          })
        );
      } catch (e) {
        console.warn(
          "Error memformat local_datetime:",
          this.forecast.local_datetime,
          e
        );
        return this.forecast.local_datetime;
      }
    },
    windInfo() {
      const speed = this.forecast.ws !== undefined ? this.forecast.ws : "-";
      const direction = this.forecast.wd || "-";
      return `${speed} km/jam dari ${direction}`;
    },
    visibilityInfo() {
      if (this.forecast.vs_text) return this.forecast.vs_text;
      if (this.forecast.vs !== undefined)
        return `${this.forecast.vs / 1000} km`;
      return "-";
    },
  },
  methods: {
    onImageError(event) {
      event.target.src = "https://via.placeholder.com/50x50?text=IconErr";
      console.warn("Gagal memuat ikon cuaca:", this.forecast.image);
    },
  },
};
</script>
