<template>
  <div
    class="bg-white border border-slate-200 rounded-xl p-5 shadow-lg hover:shadow-xl transition-all duration-300 ease-in-out flex flex-col text-sm h-full transform hover:-translate-y-1"
  >
    <div
      class="flex justify-between items-center mb-3 pb-2 border-b border-slate-100"
    >
      <h3 class="text-md font-semibold text-slate-700">
        {{ formattedLocalDateTime.time }}
      </h3>
      <span class="text-xs text-slate-500">{{
        formattedLocalDateTime.date
      }}</span>
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
    <div
      class="grid grid-cols-2 gap-x-4 gap-y-1 mt-auto pt-3 border-t border-slate-100"
    >
      <p class="text-slate-600">
        <strong class="font-medium text-slate-800 block text-xs"
          >Kelembapan:</strong
        >
        {{ humidity }} %
      </p>
      <p class="text-slate-600">
        <strong class="font-medium text-slate-800 block text-xs">Angin:</strong>
        {{ windInfo }}
      </p>
      <p class="text-slate-600">
        <strong class="font-medium text-slate-800 block text-xs"
          >Tutupan Awan:</strong
        >
        {{ cloudCover }} %
      </p>
      <p class="text-slate-600">
        <strong class="font-medium text-slate-800 block text-xs"
          >Jarak Pandang:</strong
        >
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
  mounted() {
    console.log("WeatherCard received forecast:", this.forecast);
    if (!this.forecast || Object.keys(this.forecast).length === 0) {
      console.error(
        "[WeatherCard] MOUNTED dengan data forecast KOSONG atau NULL."
      );
    }
  },
  updated() {
    // Ini akan log jika kartu diperbarui karena data berubah
    console.log(
      "[WeatherCard] UPDATED. Forecast data:",
      this.forecast ? JSON.parse(JSON.stringify(this.forecast)) : "NULL"
    );
  },
  computed: {
    temperature() {
      return this.forecast.t !== undefined ? Math.round(this.forecast.t) : "-";
    },
    weatherDesc() {
      return this.forecast.weather_desc || this.forecast.cuaca_desc || "N/A";
    },
    humidity() {
      return this.forecast.hu !== undefined ? this.forecast.hu : "-";
    },
    cloudCover() {
      return this.forecast.tcc !== undefined ? this.forecast.tcc : "-";
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
        this.forecast.datetime || // Prioritaskan 'datetime' yang umum dari BMKG
        this.forecast.local_datetime ||
        this.forecast.utc_datetime;

      if (!targetDateTimeStr) {
        return { time: "-", date: "(No date)" };
      }

      let dateObj;

      // 1. Coba format YYYYMMDDHHMM (misal: "202405160000")
      if (
        typeof targetDateTimeStr === "string" &&
        targetDateTimeStr.length === 12 &&
        /^\d+$/.test(targetDateTimeStr)
      ) {
        dateObj = new Date(
          parseInt(targetDateTimeStr.substring(0, 4)),
          parseInt(targetDateTimeStr.substring(4, 6)) - 1, // Bulan (0-11)
          parseInt(targetDateTimeStr.substring(6, 8)),
          parseInt(targetDateTimeStr.substring(8, 10)),
          parseInt(targetDateTimeStr.substring(10, 12))
        );
      } else if (typeof targetDateTimeStr === "string") {
        // 2. Coba format "YYYY-MM-DD HH:MM:SS" (dengan mengganti spasi ke 'T')
        let dateStrToParse = targetDateTimeStr.replace(" ", "T");
        dateObj = new Date(dateStrToParse);

        // 3. Jika parsing gagal, dan formatnya "YYYY-MM-DD HH:MM:SS" (tanpa 'T' sebelumnya berhasil)
        //    Ini adalah fallback jika new Date(dateStr.replace(" ", "T")) gagal untuk beberapa kasus.
        if (isNaN(dateObj.getTime())) {
          const match = targetDateTimeStr.match(
            /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/
          );
          if (match) {
            dateObj = new Date(
              Number(match[1]),
              Number(match[2]) - 1, // Bulan (0-11)
              Number(match[3]),
              Number(match[4]),
              Number(match[5]),
              Number(match[6])
            );
          }
        }
      } else {
        // Jika targetDateTimeStr bukan string (misalnya sudah Date object, atau tidak dikenal)
        dateObj = new Date(targetDateTimeStr);
      }

      if (!dateObj || isNaN(dateObj.getTime())) {
        console.warn("[WeatherCard] Gagal parse tanggal:", targetDateTimeStr);
        return { time: "-", date: "(Invalid date)" };
      }

      return {
        time: dateObj.toLocaleTimeString("id-ID", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }),
        date: dateObj.toLocaleDateString("id-ID", {
          weekday: "short",
          day: "numeric",
          month: "short",
        }),
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
      console.warn(
        "[WeatherCard] Gagal memuat gambar dari URL:",
        this.forecast.image
      );
      // Gunakan placeholder yang lebih andal
      event.target.src = "https://placehold.co/64x64/4285F4/FFFFFF?text=BMKG";
    },
  },
};
</script>
