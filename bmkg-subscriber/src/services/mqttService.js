// src/services/mqttService.js
import * as mqtt from "mqtt/dist/mqtt.min";

export function createMqttClient(
  brokerUrl,
  options,
  onConnect,
  onMessage,
  onError,
  onClose,
  onOffline,
  onReconnect
) {
  console.log(`[mqttService] Mencoba terhubung ke MQTT Broker: ${brokerUrl}`);
  const client = mqtt.connect(brokerUrl, options);

  client.on("connect", () => {
    console.log("[mqttService] Berhasil terhubung ke MQTT Broker!");
    if (onConnect) onConnect();
  });

  client.on("message", (topic, payload) => {
    console.log(`[mqttService] Pesan diterima dari topik ${topic}`);
    if (onMessage) onMessage(topic, payload);
  });

  client.on("error", (err) => {
    console.error("[mqttService] Koneksi MQTT Error:", err);
    if (onError) onError(err);
  });

  client.on("close", () => {
    console.log("[mqttService] Koneksi MQTT ditutup.");
    if (onClose) onClose();
  });

  client.on("offline", () => {
    console.log("[mqttService] Klien MQTT offline.");
    if (onOffline) onOffline();
  });

  client.on("reconnect", () => {
    console.log("[mqttService] Mencoba reconnect ke MQTT...");
    if (onReconnect) onReconnect();
  });

  return client;
}
