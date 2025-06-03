import os
import paho.mqtt.client as mqtt
import paho.mqtt.properties as props
from paho.mqtt.packettypes import PacketTypes
import requests
import json
import time
import schedule
from datetime import datetime
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file in the current directory
load_dotenv()

# --- Konfigurasi (diambil dari .env) ---
# MQTT Broker Settings
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT_NORMAL = int(os.getenv("MQTT_PORT_NORMAL", 1883))
MQTT_PORT_TLS = int(os.getenv("MQTT_PORT_TLS", 8883))
CA_CERT_PATH = os.getenv("CA_CERT_PATH")
USE_TLS_STR = os.getenv("USE_TLS", "False").lower()
USE_TLS = USE_TLS_STR == "true"

# BMKG API Settings
ADM4_CODES_STR = os.getenv("ADM4_CODES_LIST", "")
# ADM4_CODES berisi kode dengan format asli dari .env (mungkin dengan titik)
ADM4_CODES = [code.strip() for code in ADM4_CODES_STR.split(',') if code.strip()] if ADM4_CODES_STR else []
# ADM4_CODES_FOR_API berisi kode tanpa titik, untuk pemanggilan API BMKG
ADM4_CODES_FOR_API = [code.replace(".", "") for code in ADM4_CODES]

FETCH_INTERVAL_SECONDS = int(os.getenv("FETCH_INTERVAL_SECONDS", 3600))

# Publisher Settings
DATA_QOS_LEVEL = int(os.getenv("DATA_QOS_LEVEL", 1))
REQUEST_TOPIC_CONTROL = os.getenv("REQUEST_TOPIC_CONTROL", "bmkg/control/request")

API_BASE_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"

# --- Klien MQTT ---
publisher_id = f"bmkg-publisher-{uuid.uuid4()}"
client = mqtt.Client(client_id=publisher_id, protocol=mqtt.MQTTv5)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"Publisher Connected to MQTT Broker (rc: {rc})!")
        client.subscribe(REQUEST_TOPIC_CONTROL, qos=1)
        print(f"Subscribed to control topic: {REQUEST_TOPIC_CONTROL}")
    else:
        print(f"Publisher Failed to connect, return code {rc}")

def on_message_control(client, userdata, msg):
    print(f"Control message received on topic {msg.topic}")
    try:
        payload_str = msg.payload.decode()
        request_data = json.loads(payload_str)
        command = request_data.get("command")
        
        response_topic = None
        correlation_data = None

        if msg.properties:
            if msg.properties.ResponseTopic:
                response_topic = msg.properties.ResponseTopic
                print(f"  Response Topic: {response_topic}")
            if msg.properties.CorrelationData:
                correlation_data = msg.properties.CorrelationData
                print(f"  Correlation Data: {correlation_data.decode() if isinstance(correlation_data, bytes) else correlation_data}")

        if not response_topic:
            print("  No Response Topic in request, cannot reply.")
            return

        response_payload = {}
        if command == "status":
            response_payload = {"status": "Publisher is running", "timestamp": datetime.now().isoformat(), "monitoring_adm4": ADM4_CODES}
            print("  Responding to 'status' command")
        elif command == "force_refresh":
            adm4_to_refresh_with_dots = request_data.get("adm4") # Ini adalah kode dengan titik dari Streamlit
            adm4_to_refresh_api = adm4_to_refresh_with_dots.replace(".", "") if adm4_to_refresh_with_dots else None
            
            if adm4_to_refresh_with_dots and adm4_to_refresh_with_dots in ADM4_CODES:
                print(f"  Force refreshing data for {adm4_to_refresh_with_dots}")
                fetch_and_publish_weather_data(specific_adm4_original_format=adm4_to_refresh_with_dots)
                response_payload = {"status": f"Data refresh triggered for {adm4_to_refresh_with_dots}"}
            else:
                response_payload = {"error": f"Invalid or not monitored adm4 code for refresh: {adm4_to_refresh_with_dots}"}
        else:
            response_payload = {"error": "Unknown command"}

        response_properties = props.Properties(PacketTypes.PUBLISH)
        if correlation_data:
            response_properties.CorrelationData = correlation_data
        
        client.publish(response_topic, json.dumps(response_payload), qos=1, properties=response_properties)
        print(f"  Response sent to {response_topic}")

    except json.JSONDecodeError:
        print("  Error decoding JSON payload from control message.")
    except Exception as e:
        print(f"  Error processing control message: {e}")

def fetch_and_publish_weather_data(specific_adm4_original_format=None):
    print(f"\n[{datetime.now()}] Fetching BMKG data...")
    
    codes_to_fetch_original_format = []
    if specific_adm4_original_format:
        if specific_adm4_original_format in ADM4_CODES:
             codes_to_fetch_original_format = [specific_adm4_original_format]
        else:
            print(f"  Specific ADM4 {specific_adm4_original_format} not in monitored list. Skipping.")
            return
    else:
        codes_to_fetch_original_format = ADM4_CODES

    for adm4_original_code in codes_to_fetch_original_format:
        adm4_api_code = adm4_original_code.replace(".", "") # Hapus titik untuk URL API
        url = f"{API_BASE_URL}?adm4={adm4_api_code}"
        # Topik menggunakan format asli dari .env (mungkin dengan titik)
        topic_base = f"bmkg/prakiraan/{adm4_original_code}" 

        print(f"  Fetching for {adm4_original_code} (API code: {adm4_api_code}) from {url}")
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            weather_data_list = response.json()

            if not isinstance(weather_data_list, list) or not weather_data_list:
                print(f"    No data or unexpected format for {adm4_original_code}")
                continue
            
            payload = json.dumps(weather_data_list)
            pub_props = props.Properties(PacketTypes.PUBLISH)
            pub_props.MessageExpiryInterval = int(FETCH_INTERVAL_SECONDS * 1.5) # Pesan berlaku 1.5x interval fetch

            qos_to_use = DATA_QOS_LEVEL
            result = client.publish(topic_base, payload, qos=qos_to_use, properties=pub_props)
            
            # result.wait_for_publish(timeout=5) # Bisa digunakan untuk QoS 1 & 2
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"    Data for {adm4_original_code} published to {topic_base} with QoS {qos_to_use}")
            else:
                print(f"    Failed to publish data for {adm4_original_code} to {topic_base}, rc: {result.rc}")

            time.sleep(1.1) # Jeda antar request API (BMKG rate limit 60/menit)

        except requests.exceptions.RequestException as e:
            print(f"    Error fetching API data for {adm4_original_code}: {e}")
        except json.JSONDecodeError:
            print(f"    Error decoding JSON for {adm4_original_code}")
        except Exception as e:
            print(f"    Unexpected error for {adm4_original_code}: {e}")
    print(f"[{datetime.now()}] Data fetching cycle complete.")

if __name__ == "__main__":
    if not ADM4_CODES:
        print("ADM4_CODES_LIST tidak diset di file publisher/.env atau kosong. Publisher tidak akan mengambil data.")
        exit()

    if USE_TLS:
        if not CA_CERT_PATH or not os.path.exists(CA_CERT_PATH):
            print(f"USE_TLS is True, but CA_CERT_PATH '{CA_CERT_PATH}' is not set or file does not exist. Exiting.")
            exit()
        print(f"Connecting to {MQTT_BROKER_HOST}:{MQTT_PORT_TLS} using MQTTS (CA: {CA_CERT_PATH})")
        client.tls_set(ca_certs=CA_CERT_PATH)
        port_to_use = MQTT_PORT_TLS
    else:
        print(f"Connecting to {MQTT_BROKER_HOST}:{MQTT_PORT_NORMAL} using MQTT")
        port_to_use = MQTT_PORT_NORMAL

    client.on_connect = on_connect
    client.message_callback_add(REQUEST_TOPIC_CONTROL, on_message_control)
    
    try:
        client.connect(MQTT_BROKER_HOST, port_to_use, 60)
    except Exception as e:
        print(f"Could not connect to MQTT Broker: {e}")
        exit()

    client.loop_start()

    schedule.every(FETCH_INTERVAL_SECONDS).seconds.do(fetch_and_publish_weather_data)
    fetch_and_publish_weather_data() # Jalankan sekali saat start

    print(f"Publisher started. Monitoring ADM4: {ADM4_CODES}. Fetching every {FETCH_INTERVAL_SECONDS}s. QoS: {DATA_QOS_LEVEL}")
    print("Waiting for scheduled jobs or control messages. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nPublisher shutting down...")
    finally:
        if client.is_connected():
            client.loop_stop()
            client.disconnect()
        print("Publisher disconnected.")