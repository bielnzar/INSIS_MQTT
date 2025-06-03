<template>
  <div
    class="bg-white border border-slate-200 rounded-xl p-5 shadow-lg hover:shadow-xl transition-all duration-300 ease-in-out flex flex-col text-sm h-full transform hover:-translate-y-1"
  >
    <div class="flex justify-between items-center mb-3 pb-2 border-b border-slate-100">
      <h3 class="text-md font-semibold text-slate-700">
        {{ formattedLocalDateTime.time }}
      </h3>
      <span class="text-xs text-slate-500">{{ formattedLocalDateTime.date }}</span>
    </div>
    <div class="flex items-center mb-4">
      <img
        :src="weatherIconUrl"
        :alt="weatherDesc"
        class="w-14 h-14 mr-4 object-contain"
        @error="onImageError"
      />
      <span class="text-4xl font-bold text-blue-600">{{ temperature }}°C</span>
    </div>
    <p class="mb-1.5 text-slate-600">
      <strong class="font-medium text-slate-800">Kondisi:</strong>
      {{ weatherDesc }}
    </p>
    <div class="grid grid-cols-2 gap-x-4 gap-y-1 mt-auto pt-3 border-t border-slate-100">
      <p class="text-slate-600">
        <strong class="font-medium text-slate-800 block text-xs">Kelembapan:</strong>
        {{ humidity }} %
      </p>
      <p class="text-slate-600">
        <strong class="font-medium text-slate-800 block text-xs">Angin:</strong>
        {{ windInfo }}
      </p>
      <p class="text-slate-600">
        <strong class="font-medium text-slate-800 block text-xs">Tutupan Awan:</strong>
        {{ cloudCover }} %
      </p>
      <p class="text-slate-600">
        <strong class="font-medium text-slate-800 block text-xs">Jarak Pandang:</strong>
        {{ visibilityInfo }}
      </p>
    </div>
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
  created() {
    // Map struktur data BMKG ke format yang diharapkan oleh komponen
    const rawData = this.forecast;
    
    // Log data mentah untuk debugging
    console.log("Raw forecast data:", rawData);
    
    // Map properti dengan fallback ke default
    this.mappedData = {
      temperature: rawData.t || rawData.temp || rawData.temperature || null,
      weatherCode: rawData.weather || rawData.cuaca || 0,
      weatherDesc: rawData.weather_desc || rawData.cuaca_desc || "-",
      humidity: rawData.hu || rawData.humidity || rawData.kelembaban || "-",
      windSpeed: rawData.ws || rawData.wind_speed || rawData.kecepatan_angin || "-",
      datetime: rawData.datetime || rawData.local_datetime || "-"
    };
  },
  mounted() {
    console.log("WeatherCard received forecast:", this.forecast);
    if (!this.forecast || Object.keys(this.forecast).length === 0) {
        console.error("[WeatherCard] MOUNTED dengan data forecast KOSONG atau NULL.");
    }
  },
  updated() {
    // Ini akan log jika kartu diperbarui karena data berubah
    console.log("[WeatherCard] UPDATED. Forecast data:", this.forecast ? JSON.parse(JSON.stringify(this.forecast)) : "NULL");
  },
  computed: {
    temperature() {
      return this.forecast.t !== undefined ? Math.round(this.forecast.t) : "-";
    },
    weatherIconUrl() {
      // Debug untuk memeriksa image URL
      console.log("[WeatherCard] Image URL dari data:", this.forecast.image);
      
      // Langsung gunakan image URL jika tersedia
      if (this.forecast.image) {
        return this.forecast.image;
      }
      
      // Fallback jika tidak ada image
      return "https://placehold.co/64x64/4285F4/FFFFFF?text=BMKG";
    },
    formattedLocalDateTime() {
      // Coba beberapa properti tanggal yang mungkin
      let targetDateTimeStr =
        this.forecast.local_datetime ||
        this.forecast.datetime ||
        this.forecast.utc_datetime;

      if (!targetDateTimeStr) {
        return { time: "-", date: "(Error format)" };
      }

      // Perbaiki: Ganti spasi dengan 'T' jika perlu, agar bisa diparse oleh Date
      let dateStr = targetDateTimeStr.replace(" ", "T");
      // Jika masih gagal, coba langsung
      let dateObj = new Date(dateStr);
      if (isNaN(dateObj.getTime())) {
        // Coba parse manual jika format masih gagal
        // Format: "YYYY-MM-DD HH:mm:ss"
        const match = targetDateTimeStr.match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/);
        if (match) {
          dateObj = new Date(
            Number(match[1]),
            Number(match[2]) - 1,
            Number(match[3]),
            Number(match[4]),
            Number(match[5]),
            Number(match[6])
          );
        }
      }

      if (isNaN(dateObj.getTime())) {
        return { time: "-", date: "(Error format)" };
      }

      return {
        time: dateObj.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", hour12: false }),
        date: dateObj.toLocaleDateString("id-ID", { weekday: "short", day: "numeric", month: "short" })
      };
    },
    windInfo() {
      const speed = this.forecast.ws !== undefined ? this.forecast.ws : "-";
      const direction = this.forecast.wd_card || this.forecast.wd || "-"; // wd_card (mis: "N", "SW") lebih baik
      return `${speed} km/j ${direction}`;
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
      console.warn("[WeatherCard] Gagal memuat gambar dari URL:", this.forecast.image);
      // Gunakan placeholder yang lebih andal
      event.target.src = "https://placehold.co/64x64/4285F4/FFFFFF?text=BMKG";
    },
  },
};
</script>