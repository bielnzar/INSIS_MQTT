# dashboard.py

import streamlit as st
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion # Untuk Callback API V2
import paho.mqtt.properties as props
from paho.mqtt.packettypes import PacketTypes
import json
import time
import os
import ssl
import uuid
from datetime import datetime
from dotenv import load_dotenv
import yaml
from yaml.loader import SafeLoader

# -----------------------------------------------------------------------------
# 1. Konfigurasi Halaman Streamlit (HARUS PALING ATAS)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Info Cuaca MQTT (Plain Auth)", layout="wide", initial_sidebar_state="expanded")

# -----------------------------------------------------------------------------
# 2. Muat Konfigurasi dari .env dan credentials_plaintext.yaml
# -----------------------------------------------------------------------------
load_dotenv()

# Konfigurasi MQTT dari .env atau default
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT_MQTT = int(os.getenv("MQTT_BROKER_PORT_MQTT", 1883))
MQTT_BROKER_PORT_MQTTS = int(os.getenv("MQTT_BROKER_PORT_MQTTS", 8883))
MQTT_USERNAME_STREAMLIT = os.getenv("MQTT_STREAMLIT_USERNAME") # Untuk koneksi MQTT, bukan auth UI
MQTT_PASSWORD_STREAMLIT = os.getenv("MQTT_STREAMLIT_PASSWORD") # Untuk koneksi MQTT, bukan auth UI
CA_CERT_PATH = os.getenv("CA_CERT_PATH", "C:/mosquitto_certs/ca.crt")
USE_MQTTS_STREAMLIT = os.getenv("USE_MQTTS_STREAMLIT", "true").lower() == "true"

# Muat konfigurasi pengguna dari credentials_plaintext.yaml
try:
    with open('credentials_plaintext.yaml') as file:
        config_users = yaml.load(file, Loader=SafeLoader)
except FileNotFoundError:
    st.error("FATAL: File 'credentials_plaintext.yaml' tidak ditemukan! Aplikasi tidak dapat berjalan.")
    st.stop()
except yaml.YAMLError as e:
    st.error(f"FATAL: Error parsing 'credentials_plaintext.yaml': {e}. Aplikasi tidak dapat berjalan.")
    st.stop()

if config_users is None or not isinstance(config_users.get('credentials', {}).get('usernames'), dict):
    st.error("FATAL: 'credentials_plaintext.yaml' kosong atau format tidak valid (harus ada 'credentials.usernames').")
    st.stop()

USER_CREDENTIALS = config_users['credentials']['usernames']

# dashboard.py
# ... (import dan konfigurasi awal) ...

# -----------------------------------------------------------------------------
# 3. Inisialisasi State Aplikasi Streamlit (PASTIKAN HANYA SEKALI PER SESI)
# -----------------------------------------------------------------------------
# Gunakan fungsi untuk memastikan inisialisasi hanya sekali
def initialize_session_state():
    print("[StreamlitApp MainThread] Memeriksa inisialisasi session state...")
    if 'session_initialized' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""

        st.session_state.mqtt_client = None
        st.session_state.mqtt_connected_flag = False # Flag yang diatur oleh callback
        
        # client_response_topic dibuat sekali dan disimpan
        st.session_state.client_response_topic = f"streamlit_app/res/{uuid.uuid4()}"
        print(f"[StreamlitApp MainThread] client_response_topic diinisialisasi: {st.session_state.client_response_topic}")

        st.session_state.weather_data_subs = {}
        st.session_state.weather_data_req_res = {}
        st.session_state.pending_requests = {}
        st.session_state.current_subscribed_kw = None
        st.session_state.last_subscribe_qos = 1
        st.session_state.last_connect_attempt_time = 0 # Waktu upaya koneksi terakhir
        
        st.session_state.session_initialized = True
        print("[StreamlitApp MainThread] Session state telah diinisialisasi.")
    else:
        print("[StreamlitApp MainThread] Session state sudah diinisialisasi sebelumnya.")

initialize_session_state() # Panggil fungsi inisialisasi

# ... (USER_CREDENTIALS, verify_plaintext_password) ...

# -----------------------------------------------------------------------------
# 5. Fungsi dan Callback MQTT
# -----------------------------------------------------------------------------
def streamlit_on_connect(client, userdata, flags, rc, properties=None):
    app_userdata = userdata if isinstance(userdata, dict) else {}
    client_response_topic_from_userdata = app_userdata.get('client_response_topic')
    current_kw_from_userdata = app_userdata.get('current_subscribed_kw')
    last_qos_from_userdata = app_userdata.get('last_subscribe_qos', 1)

    if rc == 0:
        print(f"[StreamlitApp CB] Terhubung ke MQTT Broker (TLS: {USE_MQTTS_STREAMLIT})!")
        st.session_state.mqtt_connected_flag = True # SET FLAG DARI CALLBACK

        if client_response_topic_from_userdata:
            client.subscribe(client_response_topic_from_userdata, qos=1)
            print(f"[StreamlitApp CB] Subscribe ke response topic: {client_response_topic_from_userdata}")
        else:
            print("[StreamlitApp CB] WARNING: client_response_topic tidak tersedia di userdata saat on_connect.")
            # Fallback jika userdata gagal (seharusnya tidak terjadi jika di-set benar)
            if hasattr(st.session_state, 'client_response_topic'):
                 client.subscribe(st.session_state.client_response_topic, qos=1)
                 print(f"[StreamlitApp CB] Fallback: Subscribe ke response topic dari st.session_state: {st.session_state.client_response_topic}")


        if current_kw_from_userdata:
            topic_to_resubscribe = f"bmkg/prakiraan-cuaca/{current_kw_from_userdata}/#"
            client.subscribe(topic_to_resubscribe, qos=last_qos_from_userdata)
            print(f"[StreamlitApp CB] Re-subscribed ke {topic_to_resubscribe} (QoS {last_qos_from_userdata})")
        
        # Jangan panggil st.rerun() dari sini. Main thread akan menangani update UI.
    else:
        print(f"[StreamlitApp CB] Gagal terhubung ke MQTT, return code {rc} ({mqtt.connack_string(rc)})")
        st.session_state.mqtt_connected_flag = False # SET FLAG DARI CALLBACK

def streamlit_on_message(client, userdata, msg):
    # ... (logika on_message tetap sama, JANGAN st.rerun() dari sini) ...
    print(f"[StreamlitApp CB] Pesan diterima di topic {msg.topic}. Data disimpan ke session_state.")
    payload_str = msg.payload.decode()
    # proses payload_str dan update st.session_state.weather_data_subs atau req_res
    # Tandai bahwa ada data baru jika perlu UI update segera di main thread
    # st.session_state.new_mqtt_data_received = True

def streamlit_on_disconnect(client, userdata, rc, properties=None):
    print(f"[StreamlitApp CB] Terputus dari MQTT dengan result code {rc}")
    st.session_state.mqtt_connected_flag = False # SET FLAG DARI CALLBACK
    if rc != 0:
        print("[StreamlitApp CB] Koneksi MQTT terputus secara tidak normal.")
    # Jangan st.rerun() dari sini.

def attempt_mqtt_connect():
    # ... (logika membersihkan client lama) ...
    if 'mqtt_client' in st.session_state and st.session_state.mqtt_client:
        try:
            st.session_state.mqtt_client.loop_stop(force=True)
            if hasattr(st.session_state.mqtt_client, '_sock') and st.session_state.mqtt_client._sock is not None: # Cek apakah socket ada
                 st.session_state.mqtt_client.disconnect()
            print("[StreamlitApp] Client MQTT lama dibersihkan.")
        except Exception as e:
            print(f"[StreamlitApp] Error saat membersihkan client MQTT lama: {e}")

    st.session_state.mqtt_client = None
    # Jangan set mqtt_connected_flag di sini, biarkan callback yang mengaturnya

    client_id = f"streamlit-app-{uuid.uuid4()}"
    
    current_app_userdata = {
        'client_response_topic': st.session_state.client_response_topic, # Ini HARUS sudah diinisialisasi
        'current_subscribed_kw': st.session_state.current_subscribed_kw,
        'last_subscribe_qos': st.session_state.last_subscribe_qos
    }
    if not current_app_userdata['client_response_topic']:
        print("FATAL ERROR di attempt_mqtt_connect: client_response_topic tidak ada di session_state!")
        st.error("Kesalahan Internal: Konfigurasi MQTT tidak lengkap.")
        return False

    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv5)
    client.user_data_set(current_app_userdata)

    # ... (logika username/password dan TLS tetap sama) ...
    if MQTT_USERNAME_STREAMLIT and MQTT_PASSWORD_STREAMLIT:
        client.username_pw_set(MQTT_USERNAME_STREAMLIT, MQTT_PASSWORD_STREAMLIT)
    if USE_MQTTS_STREAMLIT: # ... (konfigurasi TLS) ...
        if not os.path.exists(CA_CERT_PATH):
            st.error(f"Sertifikat CA tidak ditemukan di {CA_CERT_PATH}.")
            return False
        try:
            client.tls_set(ca_certs=CA_CERT_PATH, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
            client.tls_insecure_set(False)
            port_to_use = MQTT_BROKER_PORT_MQTTS
        except Exception as e:
            st.error(f"Error saat konfigurasi TLS: {e}")
            return False
    else:
        port_to_use = MQTT_BROKER_PORT_MQTT


    client.on_connect = streamlit_on_connect
    client.on_message = streamlit_on_message
    client.on_disconnect = streamlit_on_disconnect

    try:
        print(f"[StreamlitApp MainThread] Mencoba connect() ke {MQTT_BROKER_HOST}:{port_to_use}...")
        client.connect(MQTT_BROKER_HOST, port_to_use, 60)
        client.loop_start()
        st.session_state.mqtt_client = client
        print("[StreamlitApp MainThread] connect() dan loop_start() dipanggil. Menunggu callback...")
        return True # Berhasil memulai upaya koneksi
    except Exception as e:
        st.error(f"Gagal memulai koneksi MQTT awal: {e}")
        print(f"[StreamlitApp MainThread] Exception saat connect(): {e}")
        st.session_state.mqtt_client = None
        st.session_state.mqtt_connected_flag = False # Pastikan flag false jika error di sini
        return False

# ... (display_weather_data) ...

# -----------------------------------------------------------------------------
# 7. Logika Utama Aplikasi Streamlit
# -----------------------------------------------------------------------------

if not st.session_state.logged_in:
    # ... (logika form login tetap sama) ...
    if login_button:
        if verify_plaintext_password(input_username, input_password):
            st.session_state.logged_in = True
            st.session_state.username = input_username
            st.success(f"Login berhasil sebagai {input_username}!")
            st.rerun() # Rerun untuk masuk ke blok 'else'
        # ...
else: # Jika sudah login
    # --- Mencoba koneksi MQTT jika belum terhubung atau client hilang ---
    # Cek kondisi aktual koneksi client jika ada
    is_client_really_connected = False
    if st.session_state.mqtt_client and hasattr(st.session_state.mqtt_client, 'is_connected'):
        try:
            is_client_really_connected = st.session_state.mqtt_client.is_connected()
        except Exception as e:
            print(f"Error cek is_connected(): {e}")
            is_client_really_connected = False # Anggap tidak konek jika error

    # Kondisi untuk mencoba konek:
    # 1. Belum ada client ATAU
    # 2. Ada client tapi tidak konek (menurut is_connected()) ATAU
    # 3. Ada client tapi flag dari callback bilang tidak konek
    # DAN sudah lewat masa cooldown
    should_try_connect = (
        st.session_state.mqtt_client is None or
        not is_client_really_connected or
        not st.session_state.mqtt_connected_flag
    )

    if should_try_connect:
        current_time = time.time()
        if current_time - st.session_state.get('last_connect_attempt_time', 0) > 5: # Cooldown 5 detik
            print("[StreamlitApp MainThread] Kondisi koneksi MQTT tidak optimal, mencoba koneksi/re-koneksi...")
            attempt_mqtt_connect() # Fungsi ini sekarang hanya memulai upaya
            st.session_state.last_connect_attempt_time = current_time
            # Jangan rerun di sini, biarkan UI update berdasarkan flag di iterasi berikutnya
            # Atau jika attempt_mqtt_connect() sendiri memicu error yang butuh rerun UI.
            # Jika attempt_mqtt_connect() gagal (return False), UI akan menampilkan error dari sana.

    # --- Sidebar ---
    with st.sidebar:
        # ... (logout) ...
        # Tampilkan status berdasarkan flag dari callback, dan konfirmasi dengan is_connected()
        # Ini untuk mengatasi race condition antara callback dan UI update
        final_connected_status = st.session_state.mqtt_connected_flag and is_client_really_connected
        
        status_color = "green" if final_connected_status else "red"
        status_text = "Terhubung" if final_connected_status else "Terputus"
        st.markdown(f"**Status MQTT:** <font color='{status_color}'>**{status_text}**</font>", unsafe_allow_html=True)

        if not final_connected_status:
            if st.button("Hubungkan Manual ke MQTT", key="reconnect_mqtt_btn_plain_manual_v2"):
                print("[StreamlitApp MainThread] Tombol 'Hubungkan Manual ke MQTT' ditekan.")
                attempt_mqtt_connect()
                st.session_state.last_connect_attempt_time = time.time()
                st.rerun() # Rerun untuk segera mencoba merefleksikan upaya koneksi
        
        if final_connected_status:
            # ... (UI sidebar untuk QoS, Langganan) ...
    
    # --- Konten Utama Aplikasi ---
    st.title("☀️ Dashboard Cuaca Interaktif via MQTT 🛰️ (Auth Teks Biasa)")
    if final_connected_status:
        # ... (UI utama untuk data cuaca reguler dan on-demand) ...
    else:
        st.error("Koneksi ke MQTT Broker terputus atau belum berhasil. Fitur tidak tersedia. Coba hubungkan melalui sidebar.")