import requests
import json
import time
import paho.mqtt.client as mqtt
import sys

BMKG_API_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
ADM4_CODE = "35.78.09.1001"

MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_CLIENT_ID = "bmkg_publisher_continuous_py_002"

MQTT_TOPIC_BASE = "bmkg/weather/forecast"

FETCH_INTERVAL_SECONDS = 60

def fetch_bmkg_data(api_url, adm4):
    full_url = f"{api_url}?adm4={adm4}"
    try:
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Publisher: Meminta data dari BMKG API: {full_url}")
        response = requests.get(full_url, timeout=20) # Timeout lebih panjang untuk jaga-jaga
        response.raise_for_status() 
        print(f"Publisher: Status Respons BMKG API: {response.status_code}")
        return response.json()
    except requests.exceptions.Timeout:
        print(f"Error: Timeout saat menghubungi BMKG API {full_url}")
        return None
    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP saat menghubungi BMKG API: {http_err} - Respons: {response.text if response else 'Tidak ada respons'}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error mengambil data dari BMKG: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON dari BMKG. Teks Respons: {response.text if response else 'Tidak ada respons'}")
        return None

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Publisher: Terhubung ke MQTT Broker ({MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}) dengan sukses.")
    else:
        print(f"Publisher: Gagal terhubung ke MQTT Broker, return code {rc}")

def on_disconnect(client, userdata, rc):
    print(f"Publisher: Terputus dari MQTT Broker dengan kode: {rc}. Mencoba menghubungkan kembali...")

def on_publish(client, userdata, mid):
    pass

MQTT_QOS = 1

def process_and_publish_data(mqtt_client, weather_data_raw):
    if weather_data_raw and "data" in weather_data_raw and weather_data_raw["data"] and "lokasi" in weather_data_raw:
        print("Publisher: Data valid diterima dari BMKG, memproses untuk publikasi...")
        
        location_info = weather_data_raw.get("lokasi", {})
        adm4_code_from_data = location_info.get("adm4", ADM4_CODE)
        desa = location_info.get("desa", "N/A")
        kecamatan = location_info.get("kecamatan", "N/A")
        kotkab = location_info.get("kotkab", "N/A")
        provinsi = location_info.get("provinsi", "N/A")

        forecast_location_data = weather_data_raw["data"][0] 
        
        if "cuaca" in forecast_location_data:
            all_forecasts_for_location = []
            for daily_forecast_array in forecast_location_data["cuaca"]:
                for forecast_item_detail in daily_forecast_array:
                    all_forecasts_for_location.append(forecast_item_detail)
            
            if not all_forecasts_for_location:
                print("Publisher: Tidak ada item prakiraan di dalam array 'cuaca'.")
                return False

            print(f"Publisher: Ditemukan {len(all_forecasts_for_location)} periode prakiraan. Memulai publikasi...")
            published_count = 0
            for i, single_forecast_data in enumerate(all_forecasts_for_location):
                payload_to_send = single_forecast_data.copy()
                payload_to_send["adm4_code"] = adm4_code_from_data
                payload_to_send["desa"] = desa
                payload_to_send["kecamatan"] = kecamatan
                payload_to_send["kotkab"] = kotkab
                payload_to_send["provinsi"] = provinsi
                
                forecast_datetime_utc_str = single_forecast_data.get("datetime", f"unknown_time_index_{i}")
                dynamic_topic = f"{MQTT_TOPIC_BASE}/{adm4_code_from_data}/{forecast_datetime_utc_str}"
                payload_json_str = json.dumps(payload_to_send)
                
                if mqtt_client.is_connected():
                    publish_result = mqtt_client.publish(dynamic_topic, payload_json_str, qos=1)
                    if publish_result.rc == mqtt.MQTT_ERR_SUCCESS:
                        published_count += 1
                    else:
                        print(f"Publisher: Gagal publish ke {dynamic_topic}, error code: {publish_result.rc}")
                    # time.sleep(0.01) # Jeda sangat kecil jika diperlukan
                else:
                    print("Publisher: MQTT Client tidak terhubung. Pesan tidak dipublikasikan.")
                    return False # Berhenti memproses jika koneksi putus

            print(f"Publisher: {published_count} dari {len(all_forecasts_for_location)} data prakiraan berhasil diproses untuk publikasi.")
            return True # Sukses mempublish
        else:
            print("Publisher: Key 'cuaca' tidak ditemukan dalam respons data BMKG (di dalam 'data[0]').")
    else:
        print("Publisher: Data dari BMKG tidak valid atau kosong/tidak lengkap.")
    return False

def main_loop():
    mqtt_publisher = mqtt.Client(client_id=MQTT_CLIENT_ID)
    mqtt_publisher.on_connect = on_connect
    mqtt_publisher.on_disconnect = on_disconnect # callback on_disconnect
    mqtt_publisher.on_publish = on_publish

    # Mencoba terhubung terus menerus jika gagal
    while not mqtt_publisher.is_connected():
        try:
            print(f"Publisher: Mencoba terhubung ke MQTT Broker ({MQTT_BROKER_HOST}:{MQTT_BROKER_PORT})...")
            mqtt_publisher.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
            mqtt_publisher.loop_start() # Memulai network loop di thread terpisah
            time.sleep(1) # Beri waktu untuk koneksi
            if not mqtt_publisher.is_connected():
                print("Publisher: Gagal terhubung setelah mencoba, menunggu sebelum mencoba lagi...")
                mqtt_publisher.loop_stop() # Hentikan loop jika koneksi awal gagal total
                time.sleep(10) # Tunggu 10 detik sebelum mencoba lagi
        except Exception as e:
            print(f"Publisher: Exception saat mencoba terhubung ke MQTT Broker: {e}. Mencoba lagi dalam 10 detik...")
            time.sleep(10)
    
    print(f"Publisher: Terhubung dan memulai loop utama. Interval update: {FETCH_INTERVAL_SECONDS} detik.")
    
    try:
        while True:
            if not mqtt_publisher.is_connected():
                print("Publisher: Koneksi MQTT terputus. Mencoba menghubungkan kembali di iterasi berikutnya...")
                # Paho client dengan loop_start() akan mencoba reconnect otomatis
                try:
                    mqtt_publisher.reconnect()
                    print("Publisher: Reconnect attempt...")
                except Exception as e_reconnect:
                    print(f"Publisher: Gagal reconnect: {e_reconnect}")
                time.sleep(10) # Tunggu sebelum iterasi berikutnya jika reconnect gagal
                continue

            weather_data_raw = fetch_bmkg_data(BMKG_API_URL, ADM4_CODE)
            
            if weather_data_raw:
                process_and_publish_data(mqtt_publisher, weather_data_raw)
            else:
                print(f"Publisher: Tidak ada data dari BMKG pada iterasi ini. Tidak ada yang dipublish.")
            
            print(f"Publisher: Menunggu {FETCH_INTERVAL_SECONDS} detik untuk siklus berikutnya...")
            time.sleep(FETCH_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nPublisher: KeyboardInterrupt diterima. Menghentikan script...")
    except Exception as e_main:
        print(f"Publisher: Terjadi error tak terduga di main loop: {e_main}")
    finally:
        if mqtt_publisher and mqtt_publisher.is_connected():
            print("Publisher: Menghentikan network loop dan memutus koneksi MQTT.")
            mqtt_publisher.loop_stop()
            mqtt_publisher.disconnect()
        print("Publisher script telah dihentikan.")
        sys.exit(0)

if __name__ == "__main__":
    main_loop()