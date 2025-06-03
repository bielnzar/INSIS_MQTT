<template>
  <div v-if="!isLoggedIn" class="font-sans">
    <LoginPage @loggedIn="onLoggedIn" />
  </div>
  <div v-else class="max-w-screen-xl mx-auto p-4 md:p-6 lg:p-8 font-sans">
    <header class="mb-8 pb-6 border-b-2 border-slate-200">
      <div class="flex justify-between items-center mb-4">
        <h1 class="text-3xl md:text-4xl font-bold text-slate-800">
          Prakiraan Cuaca BMKG
        </h1>
        <button
          @click="handleLogout"
          class="px-4 py-2 bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors text-sm"
        >
          Logout
        </button>
      </div>
      <p v-if="locationInfo.desa" class="text-xl text-slate-600 font-normal mb-2">
        {{ locationInfo.desa }}, {{ locationInfo.kotkab }}
      </p>
      <p class="text-sm text-slate-500">
        Sumber Data: BMKG (via MQTT 5.0 Request/Response)
      </p>

      <div
        class="mt-6 p-6 bg-white rounded-xl shadow-lg flex flex-col md:flex-row items-center justify-between gap-x-6 gap-y-4"
      >
        <div class="flex-grow w-full md:w-auto">
          <label for="adm4-code-input" class="font-medium text-slate-700 block mb-1"
            >Kode Wilayah (ADM4):
          </label>
          <input
            type="text"
            id="adm4-code-input"
            v-model.trim="inputAdm4Code"
            @keyup.enter="requestWeatherData"
            placeholder="Contoh: 35.78.09.1001"
            class="p-2.5 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 w-full"
          />
        </div>
        <div class="w-full md:w-auto">
          <label for="qos-select" class="font-medium text-slate-700 block mb-1"
            >QoS untuk Respons:</label
          >
          <select
            id="qos-select"
            v-model.number="selectedQos"
            class="p-2.5 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 w-full"
          >
            <option :value="0">0 (At most once)</option>
            <option :value="1">1 (At least once)</option>
            <option :value="2">2 (Exactly once)</option>
          </select>
        </div>
        <button
          @click="requestWeatherData"
          :disabled="isRequestingData || !inputAdm4Code"
          class="w-full md:w-auto mt-2 md:mt-0 px-6 py-2.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-slate-400 disabled:cursor-not-allowed self-end"
        >
          {{ isRequestingData ? "Meminta Data..." : "Tampilkan Cuaca" }}
        </button>
      </div>

      <div :class="['text-sm mt-6 p-3 rounded-md font-medium min-h-[3.5em] text-center transition-all duration-300', mqttConnectionStyling ]">
        {{ mqttStatusMessage }}
      </div>
    </header>

    <main class="mt-6">
      <!-- Debug panel - hapus setelah debug selesai -->
      <div v-if="weatherForecasts && weatherForecasts.length > 0" class="mb-6 p-4 bg-gray-100 rounded-lg">
        <h3 class="font-bold mb-2">Debug - Data Mentah ({{ weatherForecasts.length }} item):</h3>
        <pre class="text-xs overflow-auto max-h-40">{{ JSON.stringify(weatherForecasts[0], null, 2) }}</pre>
      </div>
      
      <!-- Tambahkan sebelum WeatherDashboard -->
      <div class="p-4 bg-gray-100 rounded-lg mb-6">
        <h3 class="font-bold mb-2">Debug - Data Response:</h3>
        <button @click="showFullResponse = !showFullResponse" class="px-3 py-1 bg-blue-500 text-white text-sm rounded">
          {{ showFullResponse ? 'Sembunyikan Response' : 'Tampilkan Response' }}
        </button>
        <pre v-if="showFullResponse" class="text-xs overflow-auto max-h-96 mt-2 p-2 bg-gray-800 text-green-400 rounded">{{ lastResponsePayload }}</pre>
      </div>

      <WeatherDashboard
        :forecasts="weatherForecasts"
        :is-loading="isRequestingData"
        :error-message="weatherDataError"
      />
    </main>

    <footer
      class="text-center mt-10 pt-6 border-t-2 border-slate-200 text-sm text-slate-500"
    >
      <p>
        Proyek Dashboard Cuaca: MQTT 5.0, Vue.js & Tailwind CSS
      </p>
    </footer>
  </div>
</template>

<script>
import Paho from "paho-mqtt";
import LoginPage from "./components/Login.vue";
import WeatherDashboard from "./components/WeatherDashboard.vue";

const DEFAULT_ADM4_CODE = "35.78.09.1001";

export default {
  name: "App",
  components: { LoginPage, WeatherDashboard },
  data() {
    return {
      isLoggedIn: false,
      mqttBrokerHost: "localhost",
      mqttBrokerPort: 9001,
      mqttBaseClientId: "bmkg_vue_requester_",
      mqttClientInstance: null,
      inputAdm4Code: DEFAULT_ADM4_CODE,
      currentAdm4CodeForData: "",
      selectedQos: 1,
      mqttStatusMessage: "Menunggu tindakan...",
      mqttConnectionState: "neutral",
      isRequestingData: false,
      weatherDataError: null,
      locationInfo: { desa: "", kecamatan: "", kotkab: "", provinsi: "" },
      allForecastsData: [],
      pendingRequests: new Map(),
      showFullResponse: false,
      lastResponsePayload: null,
    };
  },
  computed: {
    mqttConnectionStyling() {
      const styles = {
        neutral: "bg-slate-100 text-slate-600 border border-slate-300",
        connecting: "bg-yellow-100 text-yellow-700 border border-yellow-300 animate-pulse",
        connected: "bg-green-100 text-green-700 border border-green-300",
        error: "bg-red-100 text-red-700 border border-red-300",
        disconnected: "bg-orange-100 text-orange-700 border border-orange-300",
      };
      return styles[this.mqttConnectionState] || styles.neutral;
    },
  },
  methods: {
    onLoggedIn() {
      this.isLoggedIn = true;
      this.updateMqttStatus("Autentikasi berhasil. Siap terhubung ke MQTT.", "neutral");
      this.initializeMqttConnection();
    },
    handleLogout() {
      this.isLoggedIn = false;
      this.inputAdm4Code = DEFAULT_ADM4_CODE;
      this.clearWeatherData();
      if (this.mqttClientInstance && this.mqttClientInstance.isConnected()) {
        this.mqttClientInstance.disconnect();
      }
      this.mqttClientInstance = null;
      this.updateMqttStatus("Anda telah logout.", "disconnected");
    },
    updateMqttStatus(message, state = "neutral") {
      this.mqttStatusMessage = message;
      this.mqttConnectionState = state;
      console.log(`[MQTT Status Update] ${state}: ${message}`);
    },
    clearWeatherData() {
      this.allForecastsData = [];
      this.locationInfo = { desa: "", kecamatan: "", kotkab: "", provinsi: "" };
      this.weatherDataError = null;
      this.currentAdm4CodeForData = "";
    },
    generateUUID() {
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
      });
    },
    initializeMqttConnection() {
      if (!this.isLoggedIn) return;
      if (this.mqttClientInstance && this.mqttClientInstance.isConnected()) {
         this.updateMqttStatus("Sudah terhubung ke MQTT Broker.", "connected");
         return;
      }
      this.updateMqttStatus("Menyambungkan ke MQTT Broker...", "connecting");
      if (typeof Paho === "undefined" || typeof Paho.Client === "undefined") {
        this.updateMqttStatus("Error: Paho MQTT Client library tidak ditemukan.", "error");
        return;
      }
      const uniqueClientId = this.mqttBaseClientId + Date.now();
      this.mqttClientInstance = new Paho.Client(
        this.mqttBrokerHost,
        Number(this.mqttBrokerPort),
        uniqueClientId
      );
      this.mqttClientInstance.onConnectionLost = this.onMqttConnectionLost;
      this.mqttClientInstance.onMessageArrived = this.onMqttMessageArrived;
      const connectOptions = {
        timeout: 10,
        useSSL: false,
        cleanSession: true,
        onSuccess: this.onMqttConnectSuccess,
        onFailure: (res) => {
          this.updateMqttStatus(`Gagal terhubung ke MQTT: ${res.errorMessage} (Kode: ${res.errorCode})`, "error");
        },
      };
      try {
        this.mqttClientInstance.connect(connectOptions);
      } catch (e) {
        this.updateMqttStatus(`Error saat memanggil Paho connect(): ${e.message}`, "error");
      }
    },
    onMqttConnectSuccess() {
      this.updateMqttStatus("Terhubung ke MQTT Broker. Siap menerima request.", "connected");
    },
    onMqttConnectionLost(responseObject) {
      this.updateMqttStatus(`Koneksi MQTT terputus: ${responseObject.errorMessage} (Kode: ${responseObject.errorCode})`, "disconnected");
      this.isRequestingData = false;
    },
    requestWeatherData() {
      if (!this.mqttClientInstance || !this.mqttClientInstance.isConnected()) {
        this.updateMqttStatus("Tidak terhubung ke MQTT. Coba sambungkan ulang.", "error");
        this.initializeMqttConnection();
        return;
      }
      if (!this.inputAdm4Code) {
        this.updateMqttStatus("Kode ADM4 tidak boleh kosong.", "error");
        return;
      }
      this.isRequestingData = true;
      this.clearWeatherData();
      this.updateMqttStatus(`Meminta data cuaca untuk ADM4: ${this.inputAdm4Code}...`, "connecting");
      
      const correlationId = this.generateUUID();
      const jsResponseTopicString = `client/${this.mqttClientInstance.clientId}/response/${correlationId}`;

      this.pendingRequests.set(correlationId, {
        adm4: this.inputAdm4Code,
        timestamp: Date.now(),
        responseTopic: jsResponseTopicString
      });

      try {
        this.mqttClientInstance.subscribe(jsResponseTopicString, { qos: this.selectedQos });
        console.log(`[MQTT App.vue] Berlangganan ke response topic: ${jsResponseTopicString}`);
      } catch (e) {
          this.updateMqttStatus(`Error saat subscribe ke response topic: ${e.message}`, "error");
          this.isRequestingData = false;
          this.pendingRequests.delete(correlationId);
          return;
      }

      const requestPayload = {
        adm4_code: this.inputAdm4Code,
        response_qos: this.selectedQos,
        response_topic_in_payload: jsResponseTopicString // Response topic DIKIRIM DALAM PAYLOAD
      };

      const message = new Paho.Message(JSON.stringify(requestPayload));
      message.destinationName = "bmkg/weather/request";
      message.qos = 1;

      message.properties = { // Hanya kirim CorrelationData sebagai properti MQTT 5.0
        correlationData: new TextEncoder().encode(correlationId)
      };
      
      console.log("[MQTT App.vue] Request Payload yang akan dikirim:", JSON.parse(JSON.stringify(requestPayload)));
      console.log("[MQTT App.vue] Request Properties yang akan dikirim:", message.properties ? JSON.parse(JSON.stringify(message.properties)) : "Tidak ada properti");


      try {
        this.mqttClientInstance.send(message);
        console.log(`[MQTT App.vue] Request dikirim ke 'bmkg/weather/request' dengan Correlation ID: ${correlationId}`);
        this.updateMqttStatus(`Request data untuk ${this.inputAdm4Code} telah dikirim. Menunggu respons...`, "connecting");
      } catch (e) {
        this.updateMqttStatus(`Gagal mengirim request: ${e.message}`, "error");
        this.isRequestingData = false;
        this.pendingRequests.delete(correlationId);
        this.mqttClientInstance.unsubscribe(jsResponseTopicString);
      }
    },
    onMqttMessageArrived(message) {
      console.log("[MQTT App.vue] Pesan DITERIMA oleh onMqttMessageArrived. Topik:", message.destinationName);
      console.log("[MQTT App.vue] Payload String (awal 200 char):", message.payloadString.substring(0, 200) + "...");
      console.log("[MQTT App.vue] Objek Message Utuh (clone):", JSON.parse(JSON.stringify(message)));
      console.log("[MQTT App.vue] Properti Pesan Diterima (clone):", message.properties ? JSON.parse(JSON.stringify(message.properties)) : "Objek Properti Tidak Ada");

      let correlationIdFromProp = null;
      if (message.properties && message.properties.correlationData) {
        try {
          // Pastikan message.properties.correlationData adalah ArrayBuffer atau TypedArray
          let cdBuffer = message.properties.correlationData;
          if (cdBuffer.buffer instanceof ArrayBuffer && typeof cdBuffer.byteLength !== 'undefined') { // Cek jika ini TypedArray seperti Uint8Array
             correlationIdFromProp = new TextDecoder().decode(cdBuffer);
          } else if (cdBuffer instanceof ArrayBuffer) { // Jika ini ArrayBuffer langsung
             correlationIdFromProp = new TextDecoder().decode(cdBuffer);
          } else {
            console.warn("[MQTT App.vue] Tipe correlationData tidak dikenali untuk TextDecoder:", typeof cdBuffer, cdBuffer);
          }

          if (correlationIdFromProp) {
            console.log("[MQTT App.vue] Correlation ID diterima dari PROPERTI:", correlationIdFromProp);
          }
        } catch (e) {
          console.error("[MQTT App.vue] Error decoding correlation data dari properti:", e, "Data mentah:", message.properties.correlationData);
        }
      } else {
        console.warn("[MQTT App.vue] Properti 'correlationData' TIDAK DITEMUKAN pada pesan respons atau objek message.properties tidak ada.");
      }

      const topicParts = message.destinationName.split('/');
      const correlationIdFromTopic = topicParts.length > 0 ? topicParts[topicParts.length - 1] : null;
      console.log("[MQTT App.vue] Correlation ID dari TOPIK:", correlationIdFromTopic);
      
      const finalCorrelationId = correlationIdFromTopic || correlationIdFromProp; // Prioritaskan dari topik karena lebih pasti
      console.log("[MQTT App.vue] Final Correlation ID yang digunakan untuk dicocokkan:", finalCorrelationId);

      if (!finalCorrelationId || !this.pendingRequests.has(finalCorrelationId)) {
        console.warn(`[MQTT App.vue] Pesan diterima, TAPI correlation ID '${finalCorrelationId}' tidak ada di pendingRequests atau tidak valid. Daftar pending:`, Array.from(this.pendingRequests.keys()));
        // Untuk memastikan tidak stuck, jika ini adalah pesan yang ditunggu, kita harus tetap set isRequestingData = false
        // Jika tidak ada ID yang cocok, kita tidak akan menghapus dari pendingRequests atau unsubscribe.
      }

      const originalRequest = this.pendingRequests.get(finalCorrelationId);
      if (originalRequest) {
          console.log("[MQTT App.vue] Ditemukan original request untuk correlation ID:", finalCorrelationId);
          try {
            this.mqttClientInstance.unsubscribe(originalRequest.responseTopic);
            console.log(`[MQTT App.vue] Unsubscribed dari response topic: ${originalRequest.responseTopic}`);
          } catch (e) {
            console.warn(`[MQTT App.vue] Gagal unsubscribe dari ${originalRequest.responseTopic}: ${e.message}`);
          }
          this.pendingRequests.delete(finalCorrelationId);
      } else {
          console.warn(`[MQTT App.vue] Tidak ditemukan original request untuk correlation ID: ${finalCorrelationId}.`);
      }

      try {
        console.log("[MQTT App.vue] Memulai parsing payload respons...");
        const responsePayload = JSON.parse(message.payloadString);
        this.lastResponsePayload = responsePayload;
        console.log("[MQTT App.vue] Response Payload Berhasil Diparse:", JSON.parse(JSON.stringify(responsePayload)));

        // BAGIAN YANG DIMODIFIKASI - Pemrosesan weather forecasts
        if (responsePayload.status === "success") {
          this.currentAdm4CodeForData = responsePayload.adm4_code_requested;
          
          // LOKASI - Periksa lokasi dari berbagai tempat yang mungkin
          if (responsePayload.data_bmkg && responsePayload.data_bmkg.lokasi) {
            this.locationInfo = {
              desa: responsePayload.data_bmkg.lokasi.desa || "N/A",
              kecamatan: responsePayload.data_bmkg.lokasi.kecamatan || "N/A",
              kotkab: responsePayload.data_bmkg.lokasi.kotkab || "N/A",
              provinsi: responsePayload.data_bmkg.lokasi.provinsi || "N/A",
            };
          } else if (responsePayload.location) {
            this.locationInfo = responsePayload.location;
          }
          
          // FORECASTS - Pemilihan array forecast dari berbagai kemungkinan struktur data
          let forecasts = [];
          
          // Opsi 1: Dari responsePayload.forecasts (yang sudah diekstrak oleh publisher)
          if (responsePayload.forecasts && Array.isArray(responsePayload.forecasts) && responsePayload.forecasts.length > 0) {
            console.log("[MQTT App.vue] Menggunakan forecasts dari responsePayload.forecasts");
            forecasts = responsePayload.forecasts;
          } 
          // Opsi 2: Dari data_bmkg.data
          else if (responsePayload.data_bmkg && responsePayload.data_bmkg.data && 
              Array.isArray(responsePayload.data_bmkg.data)) {
            console.log("[MQTT App.vue] Menggunakan forecasts dari data_bmkg.data");
            forecasts = responsePayload.data_bmkg.data;
          }
          // Opsi 3: Dari struktur nested (data_bmkg.data[0].cuaca)
          else if (
            responsePayload.data_bmkg &&
            responsePayload.data_bmkg.data &&
            Array.isArray(responsePayload.data_bmkg.data) &&
            responsePayload.data_bmkg.data.length > 0 &&
            responsePayload.data_bmkg.data[0].cuaca
          ) {
            let cuaca = responsePayload.data_bmkg.data[0].cuaca;
            // Jika cuaca adalah array of array, flatten dulu
            if (Array.isArray(cuaca) && Array.isArray(cuaca[0])) {
              forecasts = cuaca.flat();
            } else {
              forecasts = cuaca;
            }
            console.log("[MQTT App.vue] Menggunakan forecasts dari data_bmkg.data[0].cuaca, jumlah:", forecasts.length);
          }
          
          // Pastikan setiap item forecast memiliki informasi lokasi
          if (forecasts.length > 0) {
            forecasts = forecasts.map(item => ({
              ...item,
              adm4_code: this.currentAdm4CodeForData,
              desa: this.locationInfo.desa || "",
              kecamatan: this.locationInfo.kecamatan || "",
              kotkab: this.locationInfo.kotkab || "",
              provinsi: this.locationInfo.provinsi || ""
            }));
            
            // Update state dengan data forecast yang sudah diproses
            this.weatherForecasts = forecasts;
            console.log("[MQTT App.vue] Berhasil memproses", forecasts.length, "item prakiraan cuaca");
            
            this.weatherDataError = null;
            this.updateMqttStatus(`Data cuaca untuk ${this.currentAdm4CodeForData} berhasil diterima.`, "connected");
          } else {
            console.warn("[MQTT App.vue] Tidak ada forecast yang berhasil diproses");
            this.weatherDataError = "Data diterima tetapi tidak ada prakiraan cuaca yang dapat diekstrak";
            this.updateMqttStatus("Data diterima tetapi struktur tidak sesuai yang diharapkan", "warning");
          }
        } else {
          this.weatherDataError = responsePayload.message || "Gagal memuat data cuaca dari server";
          this.updateMqttStatus(`Error dari server: ${this.weatherDataError}`, "error");
        }
      } catch (e) {
        console.error("[MQTT App.vue] Error memproses respons:", e);
        this.weatherDataError = "Format respons tidak valid atau error saat parsing";
      } finally {
        this.isRequestingData = false;
      }
    },
  },
  created() {},
  beforeUnmount() {
    if (this.mqttClientInstance && this.mqttClientInstance.isConnected()) {
      this.pendingRequests.forEach(req => {
        try { this.mqttClientInstance.unsubscribe(req.responseTopic); } catch (e) { /* ignore */ }
      });
      this.pendingRequests.clear();
      this.mqttClientInstance.disconnect();
      console.log("App unmount: MQTT disconnected.");
    }
  },
};
</script>

<style>
/* Gaya khusus jika diperlukan, Tailwind sudah menangani sebagian besar */
.font-sans {
  /* Contoh: tambahkan <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"> di index.html jika belum ada */
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
}
</style>