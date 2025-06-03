# publisher_bmkg_revised_final.py
import requests
import json
import time
import paho.mqtt.client as mqtt
import paho.mqtt.properties as mqtt_props
from paho.mqtt.packettypes import PacketTypes
import sys

BMKG_API_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"

MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_CLIENT_ID = "bmkg_responder_py_003" # Ganti client ID jika perlu

MQTT_REQUEST_TOPIC = "bmkg/weather/request"

DEFAULT_RESPONSE_QOS = 1

# Identifier Integer untuk Properti MQTT 5.0
MQTT_PROP_CORRELATION_DATA_ID = 9

def fetch_bmkg_data(api_url, adm4):
    full_url = f"{api_url}?adm4={adm4}"
    try:
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Responder: Meminta data dari BMKG API untuk ADM4 {adm4}: {full_url}")
        response = requests.get(full_url, timeout=20)
        response.raise_for_status()
        print(f"Responder: Status Respons BMKG API: {response.status_code}")
        return response.json()
    except requests.exceptions.Timeout:
        print(f"Error: Timeout saat menghubungi BMKG API {full_url}")
        return {"error": True, "message": "Timeout saat menghubungi BMKG API"}
    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP saat menghubungi BMKG API: {http_err} - Respons: {response.text if response else 'Tidak ada respons'}")
        return {"error": True, "message": f"Error HTTP dari BMKG: {http_err.response.status_code if http_err.response else 'N/A'}"}
    except requests.exceptions.RequestException as e:
        print(f"Error mengambil data dari BMKG: {e}")
        return {"error": True, "message": f"Error umum saat mengambil data BMKG: {e}"}
    except json.JSONDecodeError:
        print(f"Error decoding JSON dari BMKG. Teks Respons: {response.text if response else 'Tidak ada respons'}")
        return {"error": True, "message": "Error decoding JSON dari BMKG"}

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"Responder: Terhubung ke MQTT Broker ({MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}) dengan sukses (MQTTv5).")
        client.subscribe(MQTT_REQUEST_TOPIC, qos=1)
        print(f"Responder: Berlangganan ke topik request: {MQTT_REQUEST_TOPIC}")
    else:
        print(f"Responder: Gagal terhubung ke MQTT Broker, return code {rc}")

def on_disconnect(client, userdata, rc, properties=None):
    print(f"Responder: Terputus dari MQTT Broker dengan kode: {rc}.")

def on_message(client, userdata, msg):
    try:
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Responder: Menerima request pada topik: {msg.topic}")
        
        request_payload_str = msg.payload.decode()
        print(f"Responder: Payload Request: {request_payload_str}")
        request_data = json.loads(request_payload_str)
        
        adm4_code = request_data.get("adm4_code")
        client_requested_qos = request_data.get("response_qos", DEFAULT_RESPONSE_QOS)
        
        # Inisialisasi variabel
        response_topic_from_payload = None
        correlation_data_value = None  # Tambahkan ini
        
        # Check response_topic dalam payload
        response_topic_from_payload = request_data.get("response_topic_in_payload")
        if response_topic_from_payload:
            print(f"Responder: Response Topic dari PAYLOAD: {response_topic_from_payload}")
        else:
            print("Responder: response_topic_in_payload TIDAK DITEMUKAN di payload JSON")
            # Cek properti MQTTv5
            if hasattr(msg, 'properties') and msg.properties:
                print(f"Responder: Properti MQTTv5 ditemukan pada pesan. Tipe: {type(msg.properties)}")
                
                # Cek ResponseTopic dari properti
                if hasattr(msg.properties, 'ResponseTopic'):
                    response_topic_from_payload = msg.properties.ResponseTopic
                    print(f"Responder: Response Topic dari PROPERTI: {response_topic_from_payload}")
                else:
                    print("Responder: Objek Properties ADA, TAPI TIDAK memiliki atribut 'ResponseTopic'.")
                    return
                
                # Cek CorrelationData dari properti (tambahkan ini)
                if hasattr(msg.properties, 'CorrelationData'):
                    correlation_data_value = msg.properties.CorrelationData
                    print(f"Responder: CorrelationData ditemukan dalam properti pesan.")
                else:
                    print("Responder: Objek Properties ADA, TAPI TIDAK memiliki atribut 'CorrelationData'.")
            else:
                print("Responder: Tidak ada properti MQTT 5.0 yang ditemukan dalam pesan.")
                return
            
        # Jika tidak ada response topic valid
        if not response_topic_from_payload:
            print("Responder: Peringatan - Tidak ada Response Topic yang valid ditemukan dalam permintaan. Tidak bisa merespons.")
            return
            
        weather_data = fetch_bmkg_data(BMKG_API_URL, adm4_code)
        response_payload_content = {
            "adm4_code_requested": adm4_code,
            "timestamp_response": time.strftime('%Y-%m-%d %H:%M:%S %Z'),
        }

        if weather_data and not weather_data.get("error"):
            try:
                # Tambahkan logging lengkap untuk seluruh struktur data
                print(f"Responder: STRUKTUR LENGKAP weather_data: {json.dumps(weather_data, indent=2)}")
                
                # Cek struktur yang dibutuhkan frontend
                print(f"Responder: Tipe weather_data: {type(weather_data)}")
                if 'data' in weather_data:
                    print(f"Responder: Tipe weather_data['data']: {type(weather_data['data'])}")
                    if isinstance(weather_data['data'], list) and len(weather_data['data']) > 0:
                        print(f"Responder: Keys dalam weather_data['data'][0]: {list(weather_data['data'][0].keys() if isinstance(weather_data['data'][0], dict) else [])}")
                
                # Ekstraksi data lokasi
                location_info = {}
                if isinstance(weather_data, dict) and 'lokasi' in weather_data:
                    location_info = weather_data['lokasi']
                    print(f"Responder: Data lokasi ditemukan: {location_info}")
                else:
                    print(f"Responder: WARNING - 'lokasi' tidak ditemukan dalam weather_data")
                    
                # Coba berbagai kemungkinan nama properti untuk data forecast
                forecasts = []
                potential_forecast_keys = ['cuaca', 'forecast', 'forecasts', 'prakiraan', 'weather', 'isi']
                
                for key in potential_forecast_keys:
                    if isinstance(weather_data, dict) and key in weather_data and isinstance(weather_data[key], list):
                        forecasts = weather_data[key]
                        print(f"Responder: Menemukan data forecast dalam key '{key}', jumlah: {len(forecasts)}")
                        break
                
                # Jika masih belum menemukan forecast, coba lihat apakah weather_data sendiri adalah array forecast
                if not forecasts and isinstance(weather_data, list):
                    if len(weather_data) > 0 and isinstance(weather_data[0], dict):
                        # Jika item pertama memiliki properti tanggal/waktu, kemungkinan ini forecast
                        sample = weather_data[0]
                        time_indicators = ['timestamp', 'datetime', 'date', 'time', 'waktu', 'jam']
                        if any(indicator in sample for indicator in time_indicators):
                            forecasts = weather_data
                            print(f"Responder: weather_data sendiri tampaknya array forecast, jumlah: {len(forecasts)}")
                
                # Jika masih belum menemukan, coba lihat secara rekursif dalam weather_data
                if not forecasts and isinstance(weather_data, dict):
                    for key, value in weather_data.items():
                        if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                            # Ini kandidat kuat untuk data forecast
                            forecasts = value
                            print(f"Responder: Menemukan array dalam key '{key}' yang mungkin forecast, jumlah: {len(forecasts)}")
                            break
                
                # Tambahkan ke respons
                response_payload_content["status"] = "success"
                response_payload_content["data_bmkg"] = weather_data  # Data mentah
                response_payload_content["bmkg_data_keys"] = list(weather_data.keys()) if isinstance(weather_data, dict) else []
                response_payload_content["location"] = location_info
                response_payload_content["forecasts"] = forecasts
                
                if forecasts:
                    print(f"Responder: Berhasil mengekstrak {len(forecasts)} item prakiraan cuaca")
                    if len(forecasts) > 0:
                        print(f"Responder: Contoh item forecast pertama: {json.dumps(forecasts[0], indent=2)[:200]}...")
                else:
                    print("Responder: GAGAL menemukan array forecast dalam data BMKG")
            except Exception as e:
                print(f"Responder: ERROR saat memformat data cuaca: {e}")
                response_payload_content["status"] = "error"
                response_payload_content["message"] = f"Error memformat data cuaca: {str(e)}"
                import traceback
                traceback.print_exc()
        else:
            error_message = weather_data.get("message", "Error tidak diketahui") if weather_data else "Tidak ada data"
            print(f"Responder: Gagal mendapatkan data cuaca: {error_message}")
            response_payload_content["status"] = "error"
            response_payload_content["message"] = error_message
            
        response_properties_obj = mqtt_props.Properties(PacketTypes.PUBLISH)
        if correlation_data_value:
            response_properties_obj.CorrelationData = correlation_data_value
            print(f"Responder: Menambahkan CorrelationData ke properti respons.")
        else:
            print("Responder: Tidak ada CorrelationData dari request untuk ditambahkan ke respons.")

        response_payload_json = json.dumps(response_payload_content)
        
        print(f"Responder: Mengirim respons ke (dari payload): {response_topic_from_payload} dengan QoS {client_requested_qos}")
        
        publish_result = client.publish(
            response_topic_from_payload,
            payload=response_payload_json,
            qos=int(client_requested_qos),
            properties=response_properties_obj
        )
        
        if publish_result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Responder: Respons berhasil dikirim (MID: {publish_result.mid}).")
        else:
            print(f"Responder: Gagal mengirim respons, error code: {publish_result.rc}")

    except json.JSONDecodeError as e:
        print(f"Responder: Error decoding JSON dari payload request: {msg.payload.decode()} - Error: {e}")
    except Exception as e:
        print(f"Responder: Error tak terduga saat memproses pesan: {e}")
        import traceback
        traceback.print_exc()

def main():
    mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv5)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message

    print("Responder: Mencoba terhubung ke MQTT Broker...")
    try:
        mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    except Exception as e:
        print(f"Responder: Exception saat mencoba connect: {e}")
        sys.exit(1)

    print("Responder: Memulai network loop (blocking). Tekan Ctrl+C untuk keluar.")
    try:
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        print("\nResponder: KeyboardInterrupt diterima. Menghentikan script...")
    except Exception as e_main:
        print(f"Responder: Terjadi error tak terduga di main loop: {e_main}")
    finally:
        if mqtt_client.is_connected():
            print("Responder: Memutus koneksi MQTT.")
            mqtt_client.disconnect()
        print("Responder script telah dihentikan.")
        sys.exit(0)

if __name__ == "__main__":
    main()