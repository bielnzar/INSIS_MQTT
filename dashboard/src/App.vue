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
      <p
        v-if="locationInfo.desa"
        class="text-xl text-slate-600 font-normal mb-2"
      >
        {{ locationInfo.desa }}, {{ locationInfo.kotkab }}
      </p>
      <p class="text-sm text-slate-500">
        Sumber Data: BMKG (via MQTT 5.0 Request/Response)
      </p>

      <div
        class="mt-6 p-6 bg-white rounded-xl shadow-lg flex flex-col md:flex-row items-center justify-between gap-x-6 gap-y-4"
      >
        <div class="flex-grow w-full md:w-auto">
          <label
            for="adm4-code-input"
            class="font-medium text-slate-700 block mb-1"
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

      <!-- Fitur Ping-Pong MQTT -->
      <div
        class="mt-4 p-4 bg-white rounded-xl shadow-md flex items-center justify-start gap-x-4"
      >
        <button
          @click="sendPing"
          :disabled="
            isPinging ||
            !mqttClientInstance ||
            !mqttClientInstance.isConnected()
          "
          class="px-4 py-2 bg-teal-500 text-white rounded-md hover:bg-teal-600 transition-colors disabled:bg-slate-400 disabled:cursor-not-allowed"
        >
          {{ isPinging ? "Pinging..." : "Ping Broker" }}
        </button>
        <div v-if="pingLatency !== null" class="text-sm text-slate-700">
          Latensi Ping-Pong Terakhir:
          <span class="font-semibold text-teal-600">{{ pingLatency }} ms</span>
        </div>
        <div v-else-if="isPinging" class="text-sm text-slate-500">
          Menunggu pong...
        </div>
      </div>
      <!-- Akhir Fitur Ping-Pong MQTT -->

      <div
        :class="[
          'text-sm mt-6 p-3 rounded-md font-medium min-h-[3.5em] text-center transition-all duration-300',
          mqttConnectionStyling,
        ]"
      >
        {{ mqttStatusMessage }}
      </div>
    </header>

    <main class="mt-6">
      <!-- Debug panel - hapus setelah debug selesai -->
      <div
        v-if="weatherForecasts && weatherForecasts.length > 0"
        class="mb-6 p-4 bg-gray-100 rounded-lg"
      >
        <h3 class="font-bold mb-2">
          Debug - Data Mentah ({{ weatherForecasts.length }} item):
        </h3>
        <pre class="text-xs overflow-auto max-h-40">{{
          JSON.stringify(weatherForecasts[0], null, 2)
        }}</pre>
      </div>

      <!-- Tambahkan sebelum WeatherDashboard -->
      <div class="p-4 bg-gray-100 rounded-lg mb-6">
        <h3 class="font-bold mb-2">Debug - Data Response:</h3>
        <button
          @click="showFullResponse = !showFullResponse"
          class="px-3 py-1 bg-blue-500 text-white text-sm rounded"
        >
          {{ showFullResponse ? "Sembunyikan Response" : "Tampilkan Response" }}
        </button>
        <pre
          v-if="showFullResponse"
          class="text-xs overflow-auto max-h-96 mt-2 p-2 bg-gray-800 text-green-400 rounded"
          >{{ lastResponsePayload }}</pre
        >
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
      <p>Proyek Dashboard Cuaca: MQTT 5.0, Vue.js & Tailwind CSS</p>
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
      mqttClientInstance: null, // Instance Paho MQTT Client
      inputAdm4Code: DEFAULT_ADM4_CODE,
      currentAdm4CodeForData: "",
      selectedQos: 1, // QoS yang dipilih pengguna untuk respons data cuaca
      mqttStatusMessage: "Menunggu tindakan...",
      mqttConnectionState: "neutral",
      isRequestingData: false, // Mencegah request cuaca beruntun (UI Flow Control)
      weatherDataError: null,
      locationInfo: { desa: "", kecamatan: "", kotkab: "", provinsi: "" },
      weatherForecasts: [], // Menyimpan data prakiraan cuaca yang sudah diproses
      // pendingRequests: untuk mencocokkan respons cuaca dengan request (Request/Response Pattern)
      pendingRequests: new Map(),
      showFullResponse: false,
      lastResponsePayload: null,

      // Data untuk Fitur Ping-Pong
      isPinging: false, // Mencegah ping beruntun (UI Flow Control)
      pingStartTime: null, // Timestamp saat ping terakhir dikirim
      pingLatency: null, // Latensi round-trip ping-pong terakhir dalam ms
      // pendingPingRequests: untuk mencocokkan respons pong dengan request ping
      pendingPingRequests: new Map(),
    };
  },
  computed: {
    mqttConnectionStyling() {
      const styles = {
        neutral: "bg-slate-100 text-slate-600 border border-slate-300",
        connecting:
          "bg-yellow-100 text-yellow-700 border border-yellow-300 animate-pulse",
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
      this.updateMqttStatus(
        "Autentikasi berhasil. Siap terhubung ke MQTT.",
        "neutral"
      );
      this.isPinging = false;
      this.pingLatency = null;
      this.pendingPingRequests.clear();
      this.initializeMqttConnection();
    },
    handleLogout() {
      this.isLoggedIn = false;
      this.inputAdm4Code = DEFAULT_ADM4_CODE;
      this.clearWeatherData();
      if (this.mqttClientInstance && this.mqttClientInstance.isConnected()) {
        // Unsubscribe dari semua topik respons (cuaca & pong) yang mungkin masih pending
        this.pendingRequests.forEach((req) => {
          try {
            this.mqttClientInstance.unsubscribe(req.responseTopic);
          } catch (e) {}
        });
        this.pendingRequests.clear();
        this.pendingPingRequests.forEach((req) => {
          try {
            this.mqttClientInstance.unsubscribe(req.responseTopic);
          } catch (e) {}
        });
        this.pendingPingRequests.clear();
        this.mqttClientInstance.disconnect();
      }
      this.mqttClientInstance = null;
      this.updateMqttStatus("Anda telah logout.", "disconnected");
      this.isPinging = false;
      this.pingLatency = null;
    },
    updateMqttStatus(message, state = "neutral") {
      this.mqttStatusMessage = message;
      this.mqttConnectionState = state;
      console.log(`[MQTT Status Update] ${state}: ${message}`);
    },
    clearWeatherData() {
      this.weatherForecasts = [];
      this.locationInfo = { desa: "", kecamatan: "", kotkab: "", provinsi: "" };
      this.weatherDataError = null;
      this.currentAdm4CodeForData = "";
    },
    generateUUID() {
      return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
        /[xy]/g,
        function (c) {
          var r = (Math.random() * 16) | 0,
            v = c == "x" ? r : (r & 0x3) | 0x8;
          return v.toString(16);
        }
      );
    },
    initializeMqttConnection() {
      if (!this.isLoggedIn) return;
      if (this.mqttClientInstance && this.mqttClientInstance.isConnected()) {
        this.updateMqttStatus("Sudah terhubung ke MQTT Broker.", "connected");
        return;
      }
      this.updateMqttStatus("Menyambungkan ke MQTT Broker...", "connecting");
      if (typeof Paho === "undefined" || typeof Paho.Client === "undefined") {
        this.updateMqttStatus(
          "Error: Paho MQTT Client library tidak ditemukan.",
          "error"
        );
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

      // --- Implementasi Fitur MQTT: Last Will and Testament (LWT) ---
      const lwtMessagePayload = JSON.stringify({
        clientId: uniqueClientId,
        status: "offline_unexpectedly",
        timestamp: new Date().toISOString(),
      });
      const lwtTopic = `client_status/${uniqueClientId}/lwt`;
      let lwtPahoMessage = null;
      try {
        lwtPahoMessage = new Paho.Message(lwtMessagePayload);
        lwtPahoMessage.destinationName = lwtTopic;
        lwtPahoMessage.qos = 1; // QoS untuk pesan LWT
        lwtPahoMessage.retained = true; // Pesan LWT akan disimpan broker (retained) agar status offline terakhir bisa dilihat
      } catch (e) {
        console.error(
          "[MQTT App.vue] Gagal membuat Paho.Message untuk LWT:",
          e
        );
      }
      // --- Akhir Implementasi LWT ---

      const connectOptions = {
        timeout: 10,
        useSSL: false,
        cleanSession: true,
        keepAliveInterval: 60,
        mqttVersion: 4,

        willMessage:
          lwtPahoMessage && lwtPahoMessage.payloadBytes.length > 0
            ? lwtPahoMessage
            : undefined,

        // Catatan Flow Control MQTT 5.0: 'properties: { receiveMaximum: N }' tidak digunakan karena error dengan Paho versi ini.
        // Jika Paho di-upgrade, ini bisa jadi opsi untuk flow control dari sisi broker ke klien.

        onSuccess: this.onMqttConnectSuccess,
        onFailure: (res) => {
          this.updateMqttStatus(
            `Gagal terhubung ke MQTT: ${res.errorMessage} (Kode: ${res.errorCode})`,
            "error"
          );
        },
      };

      try {
        this.mqttClientInstance.connect(connectOptions);
        console.log(
          `[MQTT App.vue] Mencoba terhubung dengan Client ID: ${uniqueClientId}, LWT ke: ${
            lwtPahoMessage ? lwtPahoMessage.destinationName : "N/A"
          }`
        );
      } catch (e) {
        this.updateMqttStatus(
          `Error saat memanggil Paho connect(): ${e.message}`,
          "error"
        );
      }
    },
    onMqttConnectSuccess() {
      this.updateMqttStatus(
        "Terhubung ke MQTT Broker. Siap menerima request.",
        "connected"
      );
    },
    onMqttConnectionLost(responseObject) {
      this.updateMqttStatus(
        `Koneksi MQTT terputus: ${responseObject.errorMessage} (Kode: ${responseObject.errorCode})`,
        "disconnected"
      );
      this.isRequestingData = false;
      this.isPinging = false; // Reset status ping jika koneksi putus
    },
    requestWeatherData() {
      if (!this.mqttClientInstance || !this.mqttClientInstance.isConnected()) {
        this.updateMqttStatus(
          "Tidak terhubung ke MQTT. Coba sambungkan ulang.",
          "error"
        );
        this.initializeMqttConnection();
        return;
      }
      if (!this.inputAdm4Code) {
        this.updateMqttStatus("Kode ADM4 tidak boleh kosong.", "error");
        return;
      }
      this.isRequestingData = true; // UI Flow Control: Mencegah request beruntun
      this.clearWeatherData();
      this.updateMqttStatus(
        `Meminta data cuaca untuk ADM4: ${this.inputAdm4Code}...`,
        "connecting"
      );

      const correlationId = this.generateUUID(); // ID unik untuk mencocokkan request dengan response
      const jsResponseTopicString = `client/${this.mqttClientInstance.clientId}/response/${correlationId}`;

      this.pendingRequests.set(correlationId, {
        adm4: this.inputAdm4Code,
        timestamp: Date.now(),
        responseTopic: jsResponseTopicString,
      });

      try {
        // QoS subscription (this.selectedQos) mempengaruhi bagaimana broker mengirim pesan ke klien ini (Flow Control & Keandalan)
        this.mqttClientInstance.subscribe(jsResponseTopicString, {
          qos: this.selectedQos,
        });
        console.log(
          `[MQTT App.vue] Berlangganan ke response topic cuaca: ${jsResponseTopicString} dengan QoS: ${this.selectedQos}`
        );
      } catch (e) {
        this.updateMqttStatus(
          `Error saat subscribe ke response topic cuaca: ${e.message}`,
          "error"
        );
        this.isRequestingData = false;
        this.pendingRequests.delete(correlationId);
        return;
      }

      const requestPayload = {
        adm4_code: this.inputAdm4Code,
        response_qos: this.selectedQos,
        response_topic_in_payload: jsResponseTopicString,
        correlation_id_in_payload: correlationId, // Opsional: kirim correlation ID juga di payload jika server memerlukannya
      };

      const message = new Paho.Message(JSON.stringify(requestPayload));
      message.destinationName = "bmkg/weather/request";
      message.qos = 1; // QoS untuk pesan permintaan cuaca (Flow Control & Keandalan)

      console.log(
        "[MQTT App.vue] Request Payload Cuaca yang akan dikirim:",
        JSON.parse(JSON.stringify(requestPayload))
      );

      try {
        this.mqttClientInstance.send(message);
        console.log(
          `[MQTT App.vue] Request cuaca dikirim ke '${message.destinationName}' dengan Correlation ID (via payload/topic): ${correlationId}`
        );
        this.updateMqttStatus(
          `Request data untuk ${this.inputAdm4Code} telah dikirim. Menunggu respons...`,
          "connecting"
        );
      } catch (e) {
        this.updateMqttStatus(
          `Gagal mengirim request cuaca: ${e.message}`,
          "error"
        );
        this.isRequestingData = false;
        this.pendingRequests.delete(correlationId);
        try {
          this.mqttClientInstance.unsubscribe(jsResponseTopicString);
        } catch (unsubError) {
          console.warn(
            "[MQTT App.vue] Gagal unsubscribe (cuaca) setelah send error:",
            unsubError
          );
        }
      }
    },

    // --- Metode untuk Fitur Ping-Pong --- //
    sendPing() {
      if (!this.mqttClientInstance || !this.mqttClientInstance.isConnected()) {
        this.updateMqttStatus(
          "Tidak terhubung ke MQTT untuk mengirim ping.",
          "error"
        );
        return;
      }
      if (this.isPinging) return; // UI Flow Control: Mencegah ping beruntun

      this.isPinging = true;
      this.pingLatency = null;
      const pingId = this.generateUUID();
      const startTime = Date.now();
      this.pingStartTime = startTime; // Simpan untuk perhitungan latensi alternatif jika diperlukan
      const pingRequestTopic = "system/ping/request";
      const pongResponseTopic = `client/${this.mqttClientInstance.clientId}/pong/${pingId}`;

      this.pendingPingRequests.set(pingId, {
        startTime: startTime,
        responseTopic: pongResponseTopic,
      });

      try {
        // Berlangganan ke topik pong SEBELUM mengirim ping. QoS 0 atau 1 cukup.
        this.mqttClientInstance.subscribe(pongResponseTopic, { qos: 0 });
        console.log(
          `[MQTT Ping] Berlangganan ke pong topic: ${pongResponseTopic}`
        );

        // Payload untuk Ping, mengirimkan ID dan topik respons di payload (kompatibel MQTT 3.1.1)
        const pingPayload = {
          ping_id: pingId,
          timestamp: startTime,
          response_topic: pongResponseTopic,
        };

        // Deklarasi message dipindahkan ke sini, SEBELUM penggunaan apa pun
        const message = new Paho.Message(JSON.stringify(pingPayload));
        message.destinationName = pingRequestTopic;
        message.qos = 1; // QoS 1 untuk memastikan ping sampai ke broker/server

        // 2. Message Expiry Interval (MQTT 5.0):
        // message.properties = { messageExpiryInterval: 300 };

        this.mqttClientInstance.send(message);
        console.log(
          `[MQTT Ping] Ping dikirim ke '${pingRequestTopic}' dengan Ping ID: ${pingId}`
        );
        this.updateMqttStatus("Ping dikirim, menunggu pong...", "connecting");
      } catch (e) {
        console.error(
          "[MQTT Ping] Error mengirim ping atau subscribe pong topic:",
          e
        );
        this.updateMqttStatus(`Gagal mengirim ping: ${e.message}`, "error");
        this.isPinging = false;
        this.pendingPingRequests.delete(pingId);
        try {
          this.mqttClientInstance.unsubscribe(pongResponseTopic);
        } catch (unsubError) {
          /* ignore */
        }
      }
    },

    onMqttMessageArrived(message) {
      // Callback utama saat menerima pesan dari broker
      console.log(
        "[MQTT App.vue] Pesan DITERIMA oleh onMqttMessageArrived. Topik:",
        message.destinationName
      );
      // Info Retained Message: Jika true, pesan ini adalah pesan terakhir yang disimpan broker untuk topik ini.
      console.log("[MQTT App.vue] Pesan retained?", message.retained);
      console.log(
        "[MQTT App.vue] Payload String (awal 200 char):",
        message.payloadString.substring(0, 200) + "..."
      );

      const topic = message.destinationName;

      // --- Penanganan Pesan PONG (Fitur Ping-Pong) --- //
      if (topic.includes("/pong/")) {
        try {
          const pongPayload = JSON.parse(message.payloadString);
          console.log("[MQTT Ping] Pesan Pong Diterima:", pongPayload);

          const receivedPingId = pongPayload.ping_id; // Server harus mengirim `ping_id` di payload pong

          if (receivedPingId && this.pendingPingRequests.has(receivedPingId)) {
            const requestDetails = this.pendingPingRequests.get(receivedPingId);
            const endTime = Date.now();
            this.pingLatency = endTime - requestDetails.startTime; // Hitung latensi

            console.log(
              `[MQTT Ping] Pong diterima untuk Ping ID: ${receivedPingId}. Latensi: ${this.pingLatency} ms`
            );
            this.updateMqttStatus(
              `Pong diterima. Latensi: ${this.pingLatency} ms.`,
              "connected"
            );

            this.isPinging = false;
            this.pendingPingRequests.delete(receivedPingId);
            try {
              this.mqttClientInstance.unsubscribe(requestDetails.responseTopic);
            } catch (e) {
              console.warn("[MQTT Ping] Gagal unsubscribe dari pong topic:", e);
            }
          } else {
            console.warn(
              "[MQTT Ping] Diterima pong dengan ID tidak dikenal atau tidak ada di pending list:",
              receivedPingId,
              Object.keys(this.pendingPingRequests)
            );
          }
        } catch (e) {
          console.error("[MQTT Ping] Error memproses pesan pong:", e);
          this.updateMqttStatus("Error memproses pesan pong.", "error");
          this.isPinging = false;
        }
        return;
      }

      // --- Penanganan Pesan CUACA --- //
      // Karena mqttVersion = 4 (MQTT 3.1.1), correlation ID untuk cuaca diharapkan dari TOPIK RESPONS.
      // Penggunaan `message.properties.correlationData` tidak standar untuk MQTT 3.1.1.
      const topicParts = topic.split("/");
      const correlationIdFromTopic =
        topicParts.length > 0 ? topicParts[topicParts.length - 1] : null;
      // console.log("[MQTT App.vue] Correlation ID dari TOPIK (untuk cuaca):", correlationIdFromTopic);

      // Gunakan correlationIdFromTopic untuk mencocokkan dengan pendingRequests
      if (
        !correlationIdFromTopic ||
        !this.pendingRequests.has(correlationIdFromTopic)
      ) {
        console.warn(
          `[MQTT App.vue] Pesan cuaca diterima, TAPI correlation ID dari TOPIK '${correlationIdFromTopic}' tidak ada di pendingRequests atau tidak valid. Daftar pending:`,
          Array.from(this.pendingRequests.keys())
        );
        // Jika tidak ada ID yang cocok, dan ini bukan pong, kita mungkin tidak tahu cara memprosesnya.
        // Pertimbangkan untuk tidak selalu set isRequestingData = false jika pesan tidak dikenali,
        // kecuali ada timeout mechanism untuk pending requests.
        // this.isRequestingData = false; // Hati-hati dengan ini jika pesan tidak dikenali
        return; // Tidak bisa mencocokkan, abaikan atau tangani sebagai error
      }

      const originalRequest = this.pendingRequests.get(correlationIdFromTopic);
      if (originalRequest) {
        console.log(
          "[MQTT App.vue] Ditemukan original request cuaca untuk correlation ID (dari topik):",
          correlationIdFromTopic
        );
        try {
          this.mqttClientInstance.unsubscribe(originalRequest.responseTopic);
          console.log(
            `[MQTT App.vue] Unsubscribed dari response topic cuaca: ${originalRequest.responseTopic}`
          );
        } catch (e) {
          console.warn(
            `[MQTT App.vue] Gagal unsubscribe dari ${originalRequest.responseTopic} (cuaca): ${e.message}`
          );
        }
        this.pendingRequests.delete(correlationIdFromTopic);
      } else {
        // Ini seharusnya tidak terjadi jika cek `pendingRequests.has()` di atas sudah benar
        console.warn(
          `[MQTT App.vue] Tidak ditemukan original request cuaca untuk correlation ID dari topik: ${correlationIdFromTopic}.`
        );
        // this.isRequestingData = false; // Hati-hati
        return;
      }

      try {
        console.log("[MQTT App.vue] Memulai parsing payload respons cuaca...");
        const responsePayload = JSON.parse(message.payloadString);
        this.lastResponsePayload = responsePayload;
        console.log(
          "[MQTT App.vue] Response Payload Cuaca Berhasil Diparse:",
          JSON.parse(JSON.stringify(responsePayload))
        );

        if (responsePayload.status === "success") {
          this.currentAdm4CodeForData = responsePayload.adm4_code_requested;

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

          let forecasts = [];
          if (
            responsePayload.data_bmkg &&
            responsePayload.data_bmkg.data &&
            Array.isArray(responsePayload.data_bmkg.data) &&
            responsePayload.data_bmkg.data.length > 0 &&
            responsePayload.data_bmkg.data[0].cuaca &&
            Array.isArray(responsePayload.data_bmkg.data[0].cuaca)
          ) {
            const cuacaArrays = responsePayload.data_bmkg.data[0].cuaca;
            forecasts = cuacaArrays.flat();
          } else if (
            responsePayload.forecasts &&
            Array.isArray(responsePayload.forecasts) &&
            responsePayload.forecasts.length > 0
          ) {
            forecasts = responsePayload.forecasts;
          } else if (
            responsePayload.data_bmkg &&
            responsePayload.data_bmkg.data &&
            Array.isArray(responsePayload.data_bmkg.data) &&
            responsePayload.data_bmkg.data.length > 0 &&
            typeof responsePayload.data_bmkg.data[0].datetime !== "undefined" &&
            typeof responsePayload.data_bmkg.data[0].t !== "undefined"
          ) {
            forecasts = responsePayload.data_bmkg.data;
          } else {
            console.warn(
              "[MQTT App.vue] Struktur data prakiraan cuaca tidak dikenali atau kosong dalam respons."
            );
          }

          if (forecasts.length > 0) {
            forecasts = forecasts.map((item) => ({
              ...item,
              adm4_code: this.currentAdm4CodeForData,
            }));
            this.weatherForecasts = forecasts;
            console.log(
              "[MQTT App.vue] Berhasil memproses",
              forecasts.length,
              "item prakiraan cuaca."
            );
            if (forecasts.length > 0) {
              console.log(
                "[MQTT App.vue] Contoh item forecast pertama setelah proses:",
                JSON.parse(JSON.stringify(forecasts[0]))
              );
            }
            this.weatherDataError = null;
            this.updateMqttStatus(
              `Data cuaca untuk ${this.currentAdm4CodeForData} berhasil diterima.`,
              "connected"
            );
          } else {
            console.warn(
              "[MQTT App.vue] Tidak ada data prakiraan yang berhasil diekstrak dari respons cuaca."
            );
            this.weatherDataError =
              "Data diterima tetapi tidak ada prakiraan cuaca yang dapat diekstrak atau format tidak sesuai.";
            this.weatherForecasts = [];
            this.updateMqttStatus(
              "Data cuaca diterima tetapi tidak ada prakiraan yang valid.",
              "warning"
            );
          }
        } else {
          this.weatherDataError =
            responsePayload.message || "Gagal memuat data cuaca dari server";
          this.updateMqttStatus(
            `Error dari server (cuaca): ${this.weatherDataError}`,
            "error"
          );
        }
      } catch (e) {
        console.error("[MQTT App.vue] Error memproses respons cuaca:", e);
        this.weatherDataError =
          "Format respons cuaca tidak valid atau error saat parsing";
        this.weatherForecasts = [];
      } finally {
        this.isRequestingData = false; // Pastikan ini diset false setelah pemrosesan selesai atau error
      }
      // --- Akhir Penanganan Pesan CUACA ---
    },
  },
  created() {},
  beforeUnmount() {
    if (this.mqttClientInstance && this.mqttClientInstance.isConnected()) {
      this.pendingRequests.forEach((req) => {
        try {
          this.mqttClientInstance.unsubscribe(req.responseTopic);
        } catch (e) {
          /* ignore */
        }
      });
      this.pendingRequests.clear();

      this.pendingPingRequests.forEach((req) => {
        try {
          this.mqttClientInstance.unsubscribe(req.responseTopic);
        } catch (e) {
          /* ignore */
        }
      });
      this.pendingPingRequests.clear();

      // Disconnect secara normal saat komponen unmount, LWT tidak akan terpicu
      this.mqttClientInstance.disconnect();
      console.log("App unmount: MQTT disconnected.");
    }
  },
};
</script>

<style>
/* Gaya khusus jika diperlukan, Tailwind sudah menangani sebagian besar */
.font-sans {
  /* Contoh: tambahkan <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"> di index.html jika belum ada */
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    Oxygen, Ubuntu, Cantarell, "Open Sans", "Helvetica Neue", sans-serif;
}
</style>
