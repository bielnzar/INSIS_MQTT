<template>
  <div class="w-full mt-5">
    <!-- Log untuk melihat apakah komponen ini dirender ulang dan nilai props -->
    <!-- {{ logProps() }}  DIHAPUS -->

    <div
      v-if="isLoading && (!internalForecasts || internalForecasts.length === 0)"
      class="text-center p-10 text-slate-500 bg-white border border-dashed border-slate-300 rounded-lg min-h-[200px] flex flex-col items-center justify-center shadow"
    >
      <!-- ... spinner ... -->
      <p class="text-lg">Sedang memuat data prakiraan cuaca...</p>
    </div>
    <div
      v-else-if="errorMessage"
      class="text-center p-10 text-red-600 bg-red-50 border border-dashed border-red-300 rounded-lg min-h-[200px] flex flex-col items-center justify-center shadow"
    >
      <!-- ... ikon error ... -->
      <p class="text-lg font-semibold">Oops! Terjadi Kesalahan</p>
      <p class="text-md">{{ errorMessage }}</p>
    </div>
    <div
      v-else-if="!isLoading && (!internalForecasts || internalForecasts.length === 0)"
      class="text-center p-10 text-slate-500 bg-white border border-dashed border-slate-300 rounded-lg min-h-[200px] flex flex-col items-center justify-center shadow"
    >
      <!-- ... ikon no data ... -->
      <p class="text-lg">Belum ada data prakiraan cuaca.</p>
      <p class="text-sm text-slate-400 mt-2">
        Silakan masukkan kode ADM4 dan klik "Tampilkan Cuaca". <br/>
        (Debug: Jumlah forecast diterima: {{ forecasts ? forecasts.length : 'null' }})
      </p>
    </div>
    <div
      v-else
      class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-5"
    >
      <!-- Log sebelum v-for -->
      <!-- <p v-if="showVForLog" style="display:none;">Rendering v-for, jumlah item: {{ sortedForecasts.length }}</p> DIHAPUS -->
      
      <!-- Kunci yang lebih unik -->
      <WeatherCard
        v-for="(item, index) in sortedForecasts"
        :key="item.datetime + '-' + index" 
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
    errorMessage: {
      type: String,
      default: null,
    }
  },
  data() {
    return {
      // showVForLog: true // DIHAPUS
    }
  },
  computed: {
    // Menggunakan nama internal untuk menghindari konflik nama dengan props jika ada lifecycle hook
    internalForecasts() {
      // Ini hanya untuk debugging agar kita bisa melihat apa yang diterima props
      // dan apakah computed property ini dipanggil ulang ketika props berubah.
      console.log("[WeatherDashboard] computed internalForecasts: props.forecasts diterima:", this.forecasts ? this.forecasts.length : 'null', JSON.parse(JSON.stringify(this.forecasts)));
      return this.forecasts;
    },
    sortedForecasts() {
      // Gunakan this.internalForecasts agar kita yakin computed property sebelumnya terpanggil
      if (!this.internalForecasts || this.internalForecasts.length === 0) {
        console.log("[WeatherDashboard] sortedForecasts: internalForecasts kosong, mengembalikan array kosong.");
        return [];
      }
      console.log("[WeatherDashboard] sortedForecasts: MEMULAI SORTING untuk", this.internalForecasts.length, "item.");
      const sorted = [...this.internalForecasts].sort((a, b) => {
        try {
          let timeA, timeB;
          const parseBMKGDate = (dtStr) => {
              if (!dtStr) return null;
              if (dtStr.includes('T')) { // ISO format "2025-06-03T01:00:00Z"
                return new Date(dtStr);
              } else if (dtStr.length === 12) { // YYYYMMDDHHMM "202506030100"
                  return new Date(
                      parseInt(dtStr.substring(0,4)),
                      parseInt(dtStr.substring(4,6)) - 1,
                      parseInt(dtStr.substring(6,8)),
                      parseInt(dtStr.substring(8,10)),
                      parseInt(dtStr.substring(10,12))
                  );
              } else if (dtStr.includes('-') && dtStr.includes(' ')) { // "YYYY-MM-DD HH:MM:SS"
                  return new Date(dtStr.replace(' ', 'T') + 'Z'); // Asumsi UTC jika tidak ada info timezone
              }
              console.warn("[WeatherDashboard] Format datetime tidak dikenal untuk sorting:", dtStr);
              return null;
          };
          
          // Prioritaskan datetime UTC, lalu local_datetime
          timeA = parseBMKGDate(a.datetime || a.local_datetime);
          timeB = parseBMKGDate(b.datetime || b.local_datetime);

          if (!timeA || !timeB || isNaN(timeA) || isNaN(timeB)) {
              console.warn("[WeatherDashboard] Gagal parse tanggal saat sorting:", a.datetime, b.datetime);
              return 0;
          }
          return timeA - timeB;
        } catch (e) {
          console.warn("[WeatherDashboard] Error saat sorting forecast:", e, a, b);
          return 0;
        }
      });
      console.log("[WeatherDashboard] sortedForecasts: HASIL SORTING (jumlah):", sorted.length, JSON.parse(JSON.stringify(sorted.slice(0,2)))); // Log 2 item pertama
      return sorted;
    }
  },
  methods: {
    // logProps() { // DIHAPUS
    //   // Metode ini akan dipanggil setiap kali komponen dirender ulang
    //   // Ini cara sederhana untuk melihat apakah props berubah
    //   console.log("[WeatherDashboard] METHOD logProps: isLoading:", this.isLoading, "errorMessage:", this.errorMessage, "forecasts count:", this.forecasts ? this.forecasts.length : 'null');
    //   // Untuk memicu console log di template, kita perlu mengembalikannya atau memanipulasi data
    //   if (this.showVForLog && this.sortedForecasts.length > 0) {
    //     this.showVForLog = false; // Hanya log v-for sekali saja
    //   }
    //   return ''; // Template tidak menampilkan apa-apa dari ini
    // }
  },
  watch: {
    forecasts(newVal, oldVal) {
      console.log("[WeatherDashboard] WATCHER: props.forecasts berubah. Jumlah baru:", newVal ? newVal.length : 'null', "Jumlah lama:", oldVal ? oldVal.length : 'null');
      // Reset showVForLog agar log di template bisa muncul lagi jika data berubah
      // if (newVal && newVal.length > 0) { // DIHAPUS
      //   this.showVForLog = true; // DIHAPUS
      // } // DIHAPUS
    }
  }
};
</script>