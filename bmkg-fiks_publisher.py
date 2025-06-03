import requests
import json
import paho.mqtt.client as mqtt
import paho.mqtt.properties as props
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.client import CallbackAPIVersion
import time
import os
import ssl
import uuid
from dotenv import load_dotenv

load_dotenv() # Muat variabel dari .env

# Konfigurasi dari .env atau hardcode
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT_MQTT = int(os.getenv("MQTT_BROKER_PORT_MQTT", 1883))
MQTT_BROKER_PORT_MQTTS = int(os.getenv("MQTT_BROKER_PORT_MQTTS", 8883))
MQTT_USERNAME = os.getenv("MQTT_FETCHER_USERNAME") # Bisa None jika anonymous
MQTT_PASSWORD = os.getenv("MQTT_FETCHER_PASSWORD") # Bisa None jika anonymous
CA_CERT_PATH = os.getenv("CA_CERT_PATH", "C:/mosquitto_certs/ca.crt") # Sesuaikan
USE_MQTTS = os.getenv("USE_MQTTS", "true").lower() == "true"

KODE_WILAYAH_MONITOR = ["35.78.09.1001"]
API_BASE_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
FETCH_INTERVAL_SECONDS = 3600 # Ambil data setiap 1 jam
REGULAR_PUBLISH_QOS = 1 # QoS untuk publikasi reguler

# --- Fungsi untuk Fetcher ---
def fetch_bmkg_data(kode_wilayah):
    try:
        url = f"{API_BASE_URL}?adm4={kode_wilayah}"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[Fetcher] Error fetching BMKG data for {kode_wilayah}: {e}")
    except json.JSONDecodeError as e:
        print(f"[Fetcher] Error decoding JSON for {kode_wilayah}: {e}")
    return None

# --- Callback MQTT ---
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[Fetcher] Connected to MQTT Broker (TLS: {USE_MQTTS})!")
        # Subscribe ke topik request untuk MQTT 5.0 Request-Response
        # Struktur topik: bmkg/req/cuaca/{kode_wilayah}
        client.subscribe("bmkg/req/cuaca/+", qos=1)
        print("[Fetcher] Subscribed to bmkg/req/cuaca/+")
    else:
        print(f"[Fetcher] Failed to connect, return code {rc}\n")

def on_message(client, userdata, msg):
    print(f"[Fetcher] Received request on topic {msg.topic}")
    if msg.properties:
        properties = msg.properties
        response_topic = None
        correlation_data = None

        if hasattr(properties, 'ResponseTopic'):
            response_topic_list = getattr(properties, 'ResponseTopic')
            if response_topic_list: response_topic = response_topic_list[0]

        if hasattr(properties, 'CorrelationData'):
            correlation_data_list = getattr(properties, 'CorrelationData')
            if correlation_data_list: correlation_data = correlation_data_list[0]
        
        if response_topic:
            try:
                # Ekstrak kode_wilayah dari topic request
                # bmkg/req/cuaca/{kode_wilayah}
                parts = msg.topic.split('/')
                if len(parts) == 4 and parts[0] == "bmkg" and parts[1] == "req" and parts[2] == "cuaca":
                    kode_wilayah_req = parts[3]
                    print(f"[Fetcher] Processing request for {kode_wilayah_req}...")
                    
                    data_cuaca = fetch_bmkg_data(kode_wilayah_req)
                    payload_response = json.dumps(data_cuaca if data_cuaca else {"error": "Data not found or failed to fetch"})
                    
                    response_properties = props.Properties(PacketTypes.PUBLISH)
                    if correlation_data:
                        response_properties.CorrelationData = correlation_data
                    
                    client.publish(response_topic, payload_response, qos=1, properties=response_properties)
                    print(f"[Fetcher] Sent response to {response_topic} for {kode_wilayah_req}")
                else:
                    print(f"[Fetcher] Invalid request topic format: {msg.topic}")

            except Exception as e:
                print(f"[Fetcher] Error processing request: {e}")
                # Kirim pesan error jika mungkin
                error_payload = json.dumps({"error": str(e)})
                response_properties = props.Properties(PacketTypes.PUBLISH)
                if correlation_data:
                    response_properties.CorrelationData = correlation_data
                client.publish(response_topic, error_payload, qos=1, properties=response_properties)
        else:
            print("[Fetcher] No ResponseTopic in request properties.")


def setup_mqtt_client():
    client_id = f"bmkg-fetcher-{uuid.uuid4()}"
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv5)
    
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    if USE_MQTTS:
        if not os.path.exists(CA_CERT_PATH):
            print(f"[Fetcher] ERROR: CA Certificate not found at {CA_CERT_PATH}. MQTTS will likely fail.")
            # exit() # Atau handle lebih baik
        client.tls_set(ca_certs=CA_CERT_PATH, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        client.tls_insecure_set(False) # Pastikan hostname diverifikasi
        port = MQTT_BROKER_PORT_MQTTS
    else:
        port = MQTT_BROKER_PORT_MQTT

    client.on_connect = on_connect
    client.on_message = on_message # Untuk handle request-response

    try:
        client.connect(MQTT_BROKER_HOST, port, 60)
    except Exception as e:
        print(f"[Fetcher] MQTT Connection Error: {e}")
        return None
    return client

def regular_data_publish(client):
    print("[Fetcher] Performing regular data publish...")
    for kode_wilayah in KODE_WILAYAH_MONITOR:
        data_cuaca_array = fetch_bmkg_data(kode_wilayah)
        if data_cuaca_array:
            # Publish seluruh prakiraan 3 harian
            topic_3harian = f"bmkg/prakiraan-cuaca/{kode_wilayah}/3harian"
            payload_3harian = json.dumps(data_cuaca_array)
            client.publish(topic_3harian, payload_3harian, qos=REGULAR_PUBLISH_QOS, retain=True)
            print(f"[Fetcher] Published to {topic_3harian} (QoS {REGULAR_PUBLISH_QOS}, Retain=True)")

            # Publish prakiraan terdekat (ambil elemen pertama dari array)
            if isinstance(data_cuaca_array, list) and len(data_cuaca_array) > 0:
                topic_terdekat = f"bmkg/prakiraan-cuaca/{kode_wilayah}/terdekat"
                payload_terdekat = json.dumps(data_cuaca_array[0])
                client.publish(topic_terdekat, payload_terdekat, qos=REGULAR_PUBLISH_QOS, retain=True)
                print(f"[Fetcher] Published to {topic_terdekat} (QoS {REGULAR_PUBLISH_QOS}, Retain=True)")
        time.sleep(1.1) # Jaga-jaga rate limit BMKG jika banyak kode wilayah

def main():
    client = setup_mqtt_client()
    if not client:
        print("[Fetcher] Exiting due to MQTT connection failure.")
        return

    client.loop_start() # Handle network traffic, callbacks, dan reconnections

    last_fetch_time = 0
    try:
        while True:
            current_time = time.time()
            if current_time - last_fetch_time > FETCH_INTERVAL_SECONDS:
                regular_data_publish(client)
                last_fetch_time = current_time
            time.sleep(10) # Cek setiap 10 detik untuk fetch berikutnya atau untuk loop tetap aktif
    except KeyboardInterrupt:
        print("[Fetcher] Shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[Fetcher] Disconnected.")

if __name__ == "__main__":
    main()