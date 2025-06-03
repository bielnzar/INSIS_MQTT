<template>
  <div class="max-w-screen-xl mx-auto p-4 md:p-6 lg:p-8">
    <header class="text-center mb-8 pb-6 border-b-2 border-gray-200">
      <h1 class="text-3xl md:text-4xl font-bold text-slate-700 mb-2">
        Prakiraan Cuaca
        <span
          v-if="locationInfo.desa"
          class="text-xl text-slate-600 font-normal"
        >
          - {{ locationInfo.desa }}, {{ locationInfo.kotkab }}
        </span>
      </h1>
      <p class="text-sm text-gray-500">
        Sumber Data: BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)
      </p>

      <div
        class="mt-6 p-4 bg-gray-100 rounded-lg flex flex-wrap items-center justify-center gap-x-4 gap-y-2"
      >
        <label for="adm4-code-input" class="font-medium text-gray-700"
          >Kode Wilayah (ADM4):
        </label>
        <input
          type="text"
          id="adm4-code-input"
          v-model.trim="inputAdm4Code"
          @keyup.enter="applyAdm4CodeChange"
          placeholder="Contoh: 35.78.09.1001"
          class="p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-w-[220px]"
        />
        <button
          @click="applyAdm4CodeChange"
          :disabled="isLoadingData && currentAdm4Code !== inputAdm4Code"
          class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {{
            isLoadingData && currentAdm4Code !== inputAdm4Code
              ? "Memuat..."
              : "Tampilkan Cuaca"
          }}
        </button>
      </div>

      <p
        :class="[
          'text-sm mt-4 p-3 rounded-md font-medium min-h-[3.2em]',
          mqttConnectionStyling,
        ]"
      >
        {{ mqttStatusMessage }}
      </p>
    </header>

    <main class="mt-6">
      <WeatherDashboard
        :forecasts="allForecastsData"
        :is-loading="isLoadingData"
      />
    </main>

    <footer
      class="text-center mt-10 pt-6 border-t-2 border-gray-200 text-sm text-gray-500"
    >
      <p>
        Proyek Integrasi Sistem: Dashboard Cuaca BMKG dengan MQTT, Vue.js &
        Tailwind CSS
      </p>
    </footer>
  </div>
</template>

<script>
import Paho from "paho-mqtt";
import WeatherDashboard from "./components/WeatherDashboard.vue";

const DEFAULT_ADM4_CODE = "35.78.09.1001";

export default {
  name: "App",
  components: { WeatherDashboard },
  data() {
    return {
      mqttBrokerHost: "localhost",
      mqttBrokerPort: 9001,
      mqttBaseClientId: "bmkg_vue_tailwind_client_",
      currentAdm4Code: DEFAULT_ADM4_CODE,
      inputAdm4Code: DEFAULT_ADM4_CODE,
      mqttClientInstance: null,
      mqttStatusMessage: "Menginisialisasi koneksi MQTT...",
      mqttConnectionState: "neutral", // 'neutral', 'connected', 'error'
      isLoadingData: true,
      locationInfo: { desa: "", kecamatan: "", kotkab: "", provinsi: "" },
      allForecastsData: [],
      isLoggedIn: false,
      loginUsername: "",
      loginPassword: "",
      loginError: "",
    };
  },
  computed: {
    currentMqttTopicToSubscribe() {
      return `bmkg/weather/forecast/${this.currentAdm4Code}/#`;
    },
    mqttConnectionStyling() {
      if (this.mqttConnectionState === "connected") {
        return "bg-green-100 text-green-700 border border-green-300";
      } else if (this.mqttConnectionState === "error") {
        return "bg-red-100 text-red-700 border border-red-300";
      }
      return "bg-blue-100 text-blue-700 border border-blue-300";
    },
  },
  mounted() {
    this.initializeMqttConnection();
  },
  methods: {
    updateMqttStatus(message, state = "neutral") {
      // state: 'neutral', 'connected', 'error'
      this.mqttStatusMessage = message;
      this.mqttConnectionState = state;
    },
    clearDataForNewLocation() {
      this.allForecastsData = [];
      this.locationInfo = { desa: "", kecamatan: "", kotkab: "", provinsi: "" };
    },
    applyAdm4CodeChange() {
      if (this.inputAdm4Code && this.inputAdm4Code !== this.currentAdm4Code) {
        this.currentAdm4Code = this.inputAdm4Code;
        this.reInitializeMqttForNewLocation();
      } else if (
        this.inputAdm4Code === this.currentAdm4Code &&
        this.mqttClientInstance &&
        !this.mqttClientInstance.isConnected()
      ) {
        this.updateMqttStatus(
          `Mencoba menyambung ulang untuk ${this.currentAdm4Code}...`
        );
        this.initializeMqttConnection();
      }
    },
    reInitializeMqttForNewLocation() {
      this.isLoadingData = true;
      this.clearDataForNewLocation();
      this.updateMqttStatus(`Mengubah lokasi ke ${this.currentAdm4Code}...`);
      if (this.mqttClientInstance && this.mqttClientInstance.isConnected()) {
        try {
          this.mqttClientInstance.disconnect();
          console.log(
            `MQTT: Disconnected (untuk ganti lokasi ke ${this.currentAdm4Code})`
          );
        } catch (e) {
          console.warn(
            "MQTT: Peringatan saat disconnect untuk ganti lokasi:",
            e
          );
        }
        setTimeout(() => this.initializeMqttConnection(), 300);
      } else {
        this.initializeMqttConnection();
      }
    },
    initializeMqttConnection() {
      this.isLoadingData = true;
      this.updateMqttStatus(
        `Menyambungkan ke MQTT Broker untuk ${this.currentAdm4Code}...`
      );
      if (typeof Paho === "undefined" || typeof Paho.Client === "undefined") {
        this.updateMqttStatus(
          "Error: Paho MQTT Client library tidak ditemukan/ter-load.",
          "error"
        );
        this.isLoadingData = false;
        return;
      }
      const uniqueClientId =
        this.mqttBaseClientId +
        Date.now() +
        "_" +
        Math.random().toString(16).substr(2, 8);
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
          this.updateMqttStatus(
            `Gagal terhubung ke MQTT Broker: ${res.errorMessage} (Lokasi: ${this.currentAdm4Code})`,
            "error"
          );
          this.isLoadingData = false;
        },
      };
      try {
        this.mqttClientInstance.connect(connectOptions);
      } catch (e) {
        this.updateMqttStatus(
          `Error saat memanggil Paho connect(): ${e.message}`,
          "error"
        );
        this.isLoadingData = false;
      }
    },
    onMqttConnectSuccess() {
      this.updateMqttStatus(
        `Terhubung! Berlangganan ke topik untuk ${this.currentAdm4Code}`,
        "connected"
      );
      console.log(
        "MQTT: Terhubung. Berlangganan ke:",
        this.currentMqttTopicToSubscribe
      );
      try {
        this.mqttClientInstance.subscribe(this.currentMqttTopicToSubscribe, {
          qos: 1,
        });
      } catch (e) {
        this.updateMqttStatus(`Error saat subscribe: ${e.message}`, "error");
      }
      setTimeout(() => {
        if (
          this.isLoadingData &&
          this.allForecastsData.length === 0 &&
          this.mqttClientInstance &&
          this.mqttClientInstance.isConnected()
        ) {
          this.isLoadingData = false;
          this.updateMqttStatus(
            `Terhubung, menunggu data untuk ${this.currentAdm4Code}...`,
            "connected"
          );
        } else if (this.isLoadingData && this.allForecastsData.length === 0) {
          this.isLoadingData = false;
        }
      }, 5000);
    },
    onMqttConnectionLost(responseObject) {
      if (responseObject.errorCode !== 0 && !this.isLoadingData) {
        this.updateMqttStatus(
          `Koneksi MQTT terputus: ${responseObject.errorMessage} (Kode: ${responseObject.errorCode})`,
          "error"
        );
      } else {
        console.log(
          "MQTT: Koneksi terputus (kemungkinan normal).",
          responseObject
        );
      }
    },
    onMqttMessageArrived(message) {
      try {
        const weatherDataPayload = JSON.parse(message.payloadString);
        this.isLoadingData = false;
        if (
          (!this.locationInfo.desa ||
            weatherDataPayload.adm4_code === this.currentAdm4Code) &&
          weatherDataPayload.desa
        ) {
          this.locationInfo = {
            desa: weatherDataPayload.desa,
            kecamatan: weatherDataPayload.kecamatan,
            kotkab: weatherDataPayload.kotkab,
            provinsi: weatherDataPayload.provinsi,
          };
        }
        if (weatherDataPayload.adm4_code === this.currentAdm4Code) {
          const existingIdx = this.allForecastsData.findIndex(
            (f) => f.datetime === weatherDataPayload.datetime
          );
          if (existingIdx > -1)
            this.allForecastsData.splice(existingIdx, 1, weatherDataPayload);
          else this.allForecastsData.push(weatherDataPayload);
        }
      } catch (e) {
        console.error(
          "MQTT: Error memproses pesan JSON:",
          e,
          "Payload:",
          message.payloadString
        );
      }
    },
    handleLogin() {
      // Ganti username/password sesuai kebutuhan
      const validUser = "nabiel";
      const validPass = "nabiel123";
      if (
        this.loginUsername === validUser &&
        this.loginPassword === validPass
      ) {
        this.isLoggedIn = true;
        this.loginError = "";
      } else {
        this.loginError = "Username atau password salah!";
      }
    },
  },
  beforeUnmount() {
    if (this.mqttClientInstance && this.mqttClientInstance.isConnected()) {
      try {
        this.mqttClientInstance.disconnect();
        console.log("App unmount: MQTT disconnected.");
      } catch (e) {
        console.error("Error saat disconnect MQTT di beforeUnmount:", e);
      }
    }
  },
};
</script>

<style>
/* Tambahkan style di sini jika diperlukan */
</style>
