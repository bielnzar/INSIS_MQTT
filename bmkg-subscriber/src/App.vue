<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import { createMqttClient } from "./services/mqttService"; // Import layanan MQTT
import LocationHeader from "./components/LocationHeader.vue";
import ConnectionStatus from "./components/ConnectionStatus.vue";
import WeatherCard from "./components/WeatherCard.vue";
import LoadingSpinner from "./components/LoadingSpinner.vue";

// --- Konfigurasi MQTT --- (Bisa juga dipindah ke file config terpisah jika makin kompleks)
const KODE_WILAYAH_ADM4_TARGET = "35.78.09.1001"; // Keputih, Surabaya
const MQTT_BROKER_URL = "ws://localhost:9001"; // Sesuaikan jika perlu
const MQTT_TOPIC_TO_SUBSCRIBE = `bmkg/prakiraan_cuaca/indonesia/${KODE_WILAYAH_ADM4_TARGET}/data`;
const MQTT_CLIENT_ID = `bmkg_vue_subscriber_${Math.random()
  .toString(16)
  .substring(2, 10)}`;

// --- State Aplikasi ---
const mqttClientInstance = ref(null); // Ganti nama agar tidak konflik dengan 'mqtt' dari library
const isConnected = ref(false);
const connectionError = ref(null);
const locationInfo = ref(null);
const weatherForecast = ref([]);
const lastUpdateTime = ref(null);
const isLoading = ref(true); // Awalnya loading

const displayedLocationName = computed(() => {
  if (locationInfo.value) {
    return `${locationInfo.value.desa}, ${locationInfo.value.kecamatan}, ${locationInfo.value.kotkab}`;
  }
  return `Prakiraan untuk ADM4: ${KODE_WILAYAH_ADM4_TARGET}`;
});

function formatDateTimeForDisplay(dateObj) {
  if (!dateObj) return "N/A";
  return dateObj.toLocaleString("id-ID", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// --- Handler untuk Callback MQTT ---
function handleMqttConnect() {
  isConnected.value = true;
  isLoading.value = false; // Selesai loading jika sudah connect
  connectionError.value = null;
  if (mqttClientInstance.value) {
    mqttClientInstance.value.subscribe(
      MQTT_TOPIC_TO_SUBSCRIBE,
      { qos: 1 },
      (err) => {
        if (err) {
          console.error("Gagal subscribe ke topik:", err);
          connectionError.value = `Gagal subscribe: ${err.message}`;
        } else {
          console.log(
            `Berhasil subscribe ke topik: ${MQTT_TOPIC_TO_SUBSCRIBE}`
          );
        }
      }
    );
  }
}

function handleMqttMessage(_topic, payload) {
  isLoading.value = false; // Selesai loading saat pesan pertama diterima
  try {
    const data = JSON.parse(payload.toString());
    if (data && typeof data === "object") {
      locationInfo.value = data.lokasi || null;
      weatherForecast.value = data.cuaca || [];
      lastUpdateTime.value = new Date(); // Catat waktu update
      console.log("Data cuaca diperbarui dari MQTT:", data);
    } else {
      console.warn("Format payload tidak sesuai:", data);
    }
  } catch (e) {
    console.error("Gagal parse JSON dari payload:", e);
    console.error("Payload mentah:", payload.toString());
  }
}

function handleMqttError(err) {
  isConnected.value = false;
  isLoading.value = false;
  connectionError.value = `Koneksi error: ${err.message}. Pastikan broker aktif dan URL websocket benar (mis. ws://localhost:9001).`;
}

function handleMqttClose() {
  isConnected.value = false;
  // Jika Anda ingin auto-reconnect, logikanya bisa ditambahkan di sini atau di mqttService
}
function handleMqttOffline() {
  isConnected.value = false;
}
function handleMqttReconnect() {
  isLoading.value = true; // Tampilkan loading saat reconnect
}

// --- Lifecycle Hooks ---
onMounted(() => {
  const options = {
    clientId: MQTT_CLIENT_ID,
    keepalive: 60,
    connectTimeout: 10000,
  };
  mqttClientInstance.value = createMqttClient(
    MQTT_BROKER_URL,
    options,
    handleMqttConnect,
    handleMqttMessage,
    handleMqttError,
    handleMqttClose,
    handleMqttOffline,
    handleMqttReconnect
  );
});

onBeforeUnmount(() => {
  if (mqttClientInstance.value) {
    mqttClientInstance.value.end(true); // true untuk force close
    console.log("Klien MQTT diakhiri.");
  }
});
</script>

<template>
  <div
    class="min-h-screen bg-gradient-to-br from-sky-500 to-indigo-600 text-white p-4 sm:p-8 font-sans"
  >
    <div
      class="container mx-auto max-w-4xl bg-white/10 backdrop-blur-md shadow-2xl rounded-xl p-6"
    >
      <LocationHeader :location-name="displayedLocationName" />

      <ConnectionStatus
        :is-connected="isConnected"
        :is-loading="isLoading"
        :connection-error="connectionError"
      />

      <div
        v-if="lastUpdateTime && isConnected"
        class="text-center text-xs mb-6 text-sky-100"
      >
        Data terakhir diperbarui: {{ formatDateTimeForDisplay(lastUpdateTime) }}
      </div>

      <div
        v-if="
          isLoading &&
          !weatherForecast.length &&
          !connectionError &&
          isConnected
        "
      >
        <LoadingSpinner>Memuat data prakiraan cuaca...</LoadingSpinner>
      </div>

      <div
        v-else-if="
          !isLoading &&
          !weatherForecast.length &&
          isConnected &&
          !connectionError
        "
        class="text-center py-10"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          class="h-16 w-16 text-sky-300 mx-auto"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          stroke-width="1"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <p class="mt-3 text-lg">
          Menunggu data prakiraan cuaca dari publisher...
        </p>
        <p class="text-sm text-sky-200">
          Pastikan publisher Python berjalan dan mengirim data.
        </p>
      </div>

      <div
        v-else-if="weatherForecast.length > 0"
        class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
      >
        <WeatherCard
          v-for="(period, index) in weatherForecast"
          :key="period.utc_datetime || index"
          :period="period"
        />
      </div>

      <div
        v-else-if="connectionError && !isLoading"
        class="text-center py-10 bg-red-700/50 rounded-lg"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          class="h-12 w-12 text-red-200 mx-auto"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          stroke-width="2"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
        <p class="mt-3 text-lg font-semibold">Gagal Terhubung ke MQTT Broker</p>
        <p class="text-red-200 text-sm">{{ connectionError }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped></style>
