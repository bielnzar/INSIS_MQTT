import streamlit as st
import paho.mqtt.client as mqtt
import paho.mqtt.properties as props
from paho.mqtt.packettypes import PacketTypes
import json
import time
from datetime import datetime
import uuid
import pandas as pd
import os
from dotenv import load_dotenv
import queue 
import threading 

load_dotenv()

mqtt_log_queue = queue.Queue()

APP_TITLE = os.getenv("APP_TITLE", "Live Prakiraan Cuaca BMKG via MQTT")
AVAILABLE_ADM4_CODES_STR = os.getenv("AVAILABLE_ADM4_CODES_LIST", "")
AVAILABLE_ADM4_CODES = [code.strip() for code in AVAILABLE_ADM4_CODES_STR.split(',') if code.strip()] if AVAILABLE_ADM4_CODES_STR else []

MQTT_BROKER_HOST = os.getenv("DEFAULT_MQTT_BROKER_HOST", "localhost")
USE_TLS_DEFAULT_STR = os.getenv("USE_TLS_DEFAULT", "False").lower()
USE_TLS = USE_TLS_DEFAULT_STR == "true"

if USE_TLS:
    MQTT_PORT = int(os.getenv("DEFAULT_MQTT_PORT_TLS", 8883))
    CA_CERT_PATH = os.getenv("DEFAULT_CA_CERT_PATH")
else:
    MQTT_PORT = int(os.getenv("DEFAULT_MQTT_PORT_NORMAL", 1883))
    CA_CERT_PATH = None

STREAMLIT_USER = os.getenv("STREAMLIT_APP_USER", "admin")
STREAMLIT_PASSWORD = os.getenv("STREAMLIT_APP_PASSWORD", "streamlit")
REQUEST_TOPIC_TO_PUBLISHER = os.getenv("REQUEST_TOPIC_TO_PUBLISHER", "bmkg/control/request")
_response_base_prefix_from_env = os.getenv("RESPONSE_TOPIC_APP_BASE_PREFIX", "streamlit_app/response")
RESPONSE_TOPIC_APP_BASE = f"{_response_base_prefix_from_env}/{uuid.uuid4()}"

def init_session_state():
    defaults = {
        'mqtt_client': None, 'connected': False, 'subscribed_topics': set(), # Ini adalah set topik yang *ingin* disubscribe oleh UI
        'weather_data': {}, 'pending_requests': {}, 'request_responses': {},
        'app_log': [], 'authenticated': False, 'attempted_connect': False,
        'login_error': None 
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

def log_to_streamlit_ui(message_text):
    if 'app_log' not in st.session_state: 
        st.session_state.app_log = []
    st.session_state.app_log.insert(0, message_text)
    st.session_state.app_log = st.session_state.app_log[:50]

def log_message_from_mqtt_thread(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_log_message = f"[{timestamp}] (MQTT) {message}"
    mqtt_log_queue.put(full_log_message)
    print(f"Q_LOG: {full_log_message}")

def log_message_from_main_thread(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_log_message = f"[{timestamp}] (Main) {message}"
    log_to_streamlit_ui(full_log_message)
    print(f"MAIN_LOG: {full_log_message}")

def display_login_form():
    st.sidebar.subheader("Login Aplikasi")
    with st.sidebar.form(key="login_form"):
        username = st.text_input("Username", key="auth_user_key_login_form")
        password = st.text_input("Password", type="password", key="auth_pass_key_login_form")
        login_button = st.form_submit_button("Login")
        if login_button:
            if username == STREAMLIT_USER and password == STREAMLIT_PASSWORD:
                st.session_state.authenticated = True
                st.session_state.login_error = None 
                return True 
            else:
                st.session_state.login_error = "Username atau password salah."
    return False 

# --- Fungsi Callback MQTT ---
def on_connect_subscriber(client, userdata, flags, rc, properties=None):
    if rc == 0:
        log_message_from_mqtt_thread(f"Connected to MQTT Broker ({MQTT_BROKER_HOST}:{MQTT_PORT}, rc: {rc})!")
        # Kirim status koneksi dan sinyal untuk resubscribe
        mqtt_log_queue.put({'type': 'connection_status', 'status': True, 'rc': rc})
        mqtt_log_queue.put({'type': 'resubscribe_topics_signal'}) # Sinyal untuk main thread
        
        # Subscribe ke topik response aplikasi tetap di sini karena ini adalah bagian dari setup koneksi client
        app_specific_response_topic_filter = f"{RESPONSE_TOPIC_APP_BASE}/#"
        client.subscribe(app_specific_response_topic_filter, qos=1)
        log_message_from_mqtt_thread(f"Subscribed (by client) to app response topic: {app_specific_response_topic_filter}")
    else:
        log_message_from_mqtt_thread(f"Failed to connect, return code {rc}")
        mqtt_log_queue.put({'type': 'connection_status', 'status': False, 'rc': rc})

def on_message_subscriber(client, userdata, msg): # Tetap sama
    topic = msg.topic
    payload_bytes = msg.payload
    log_message_from_mqtt_thread(f"Raw message received on {topic} (len: {len(payload_bytes)} B)")
    message_data_for_queue = {
        'type': 'mqtt_message', 'topic': topic, 'payload_bytes': payload_bytes,
        'properties': {'CorrelationData': msg.properties.CorrelationData if msg.properties and hasattr(msg.properties, 'CorrelationData') else None}
    }
    mqtt_log_queue.put(message_data_for_queue)

def on_disconnect_subscriber(client, userdata, rc, properties=None): # Tetap sama
    log_message_from_mqtt_thread(f"Disconnected from MQTT Broker (rc: {rc}).")
    mqtt_log_queue.put({'type': 'connection_status', 'status': False, 'rc': rc, 'event': 'disconnect'})

# --- Fungsi Proses Queue di Main Thread ---
def process_mqtt_queue():
    rerun_needed_from_queue = False
    while not mqtt_log_queue.empty():
        try:
            item = mqtt_log_queue.get_nowait()
            rerun_needed_from_queue = True 
            if isinstance(item, str):
                log_to_streamlit_ui(item)
            elif isinstance(item, dict) and 'type' in item:
                event_type = item['type']

                if event_type == 'connection_status':
                    st.session_state.connected = item['status']
                    log_msg = f"(Main) Event: {'Connected' if item['status'] else 'Disconnected/Failed'} to MQTT (rc: {item.get('rc')})"
                    log_to_streamlit_ui(log_msg)
                
                elif event_type == 'resubscribe_topics_signal':
                    if st.session_state.connected and st.session_state.mqtt_client:
                        log_to_streamlit_ui("(Main) Received resubscribe signal. Resubscribing to topics...")
                        # Akses st.session_state.subscribed_topics di sini (main thread)
                        # Ini adalah daftar topik yang *diinginkan* oleh UI
                        for topic_to_sub in list(st.session_state.subscribed_topics): 
                            st.session_state.mqtt_client.subscribe(topic_to_sub, qos=2)
                            log_to_streamlit_ui(f"(Main) Resubscribed (by main thread) to {topic_to_sub}")
                    else:
                        log_to_streamlit_ui("(Main) Received resubscribe signal, but not connected or client missing.")

                elif event_type == 'mqtt_message':
                    topic, payload_bytes, properties = item['topic'], item['payload_bytes'], item['properties']
                    try: payload_str = payload_bytes.decode()
                    except UnicodeDecodeError:
                        log_to_streamlit_ui(f"(Main) Error: Cannot decode payload from {topic} as UTF-8.")
                        continue
                    log_to_streamlit_ui(f"(Main) Processing message from {topic}")
                    if topic.startswith(_response_base_prefix_from_env):
                        correlation_data_bytes = properties.get('CorrelationData')
                        correlation_data = None
                        if correlation_data_bytes:
                            try: correlation_data = correlation_data_bytes.decode()
                            except: correlation_data = str(correlation_data_bytes)
                        if correlation_data and correlation_data in st.session_state.pending_requests:
                            log_to_streamlit_ui(f"(Main) Response for Correlation ID: {correlation_data}")
                            try: st.session_state.request_responses[correlation_data] = json.loads(payload_str)
                            except json.JSONDecodeError: st.session_state.request_responses[correlation_data] = {"error": "Failed to parse JSON response", "raw_payload": payload_str}
                            if correlation_data in st.session_state.pending_requests: del st.session_state.pending_requests[correlation_data]
                        else: log_to_streamlit_ui(f"(Main) Unmatched response on {topic} (CorrID: {correlation_data})")
                    elif topic.startswith("bmkg/prakiraan/"):
                        try:
                            data = json.loads(payload_str)
                            if isinstance(data, list):
                                st.session_state.weather_data[topic] = data
                                log_to_streamlit_ui(f"(Main) Weather data for {topic} updated ({len(data)} forecasts).")
                            else: log_to_streamlit_ui(f"(Main) Non-list data on weather topic {topic}: {type(data)}")
                        except json.JSONDecodeError: log_to_streamlit_ui(f"(Main) Error decoding JSON from weather topic {topic}")
                        except Exception as e: log_to_streamlit_ui(f"(Main) Error processing weather topic {topic}: {e}")
                    else: log_to_streamlit_ui(f"(Main) Message on unhandled topic: {topic}")
        except queue.Empty: break
        except Exception as e: log_to_streamlit_ui(f"(Main) Error processing queue item: {e}")
    return rerun_needed_from_queue

# --- Fungsi Koneksi MQTT (Tetap sama) ---
def connect_mqtt():
    if st.session_state.connected and st.session_state.mqtt_client:
        log_message_from_main_thread("Already connected.")
        return
    try:
        st.session_state.attempted_connect = True
        client_id = f"streamlit-subscriber-{uuid.uuid4()}"
        if st.session_state.mqtt_client:
            try: st.session_state.mqtt_client.loop_stop(force=True)
            except: pass
            st.session_state.mqtt_client = None
        st.session_state.mqtt_client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv5)
        st.session_state.mqtt_client.on_connect = on_connect_subscriber
        st.session_state.mqtt_client.on_message = on_message_subscriber
        st.session_state.mqtt_client.on_disconnect = on_disconnect_subscriber
        if USE_TLS:
            if not CA_CERT_PATH or not os.path.exists(CA_CERT_PATH):
                log_message_from_main_thread(f"MQTTS error: CA_CERT_PATH '{CA_CERT_PATH}' is not valid.")
                st.sidebar.error(f"MQTTS error: CA Cert Path '{CA_CERT_PATH}' tidak valid.")
                st.session_state.attempted_connect = False
                return
            st.session_state.mqtt_client.tls_set(ca_certs=CA_CERT_PATH)
        log_message_from_main_thread(f"Attempting to connect to {MQTT_BROKER_HOST}:{MQTT_PORT} {'with TLS' if USE_TLS else ''}...")
        st.session_state.mqtt_client.connect_async(MQTT_BROKER_HOST, MQTT_PORT, 60)
        st.session_state.mqtt_client.loop_start()
    except Exception as e:
        log_message_from_main_thread(f"Error during MQTT connection setup: {e}")
        if st.session_state.mqtt_client:
             try: st.session_state.mqtt_client.loop_stop(force=True)
             except: pass
        st.session_state.mqtt_client = None
        st.session_state.connected = False
        st.session_state.attempted_connect = False
        st.rerun() 

def disconnect_mqtt():
    if st.session_state.mqtt_client:
        log_message_from_main_thread("Requesting disconnect from MQTT Broker...")
        st.session_state.mqtt_client.disconnect()
        st.session_state.mqtt_client.loop_stop(force=True)
    st.session_state.connected = False
    # st.session_state.subscribed_topics.clear() # Jangan clear di sini, biarkan UI yang manage
    # Biarkan UI yang mengelola apa yang ingin disubscribe saat konek lagi
    # Tapi data yang ditampilkan bisa di-clear
    st.session_state.weather_data.clear()
    st.session_state.pending_requests.clear()
    st.session_state.request_responses.clear()
    st.session_state.attempted_connect = False
    log_message_from_main_thread("MQTT client disconnected and resources cleaned up.")
    st.rerun() 

st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
st.title(f"🛰️ {APP_TITLE}")

rerun_triggered_by_queue = process_mqtt_queue()

if not st.session_state.authenticated:
    login_successful_submit = display_login_form()
    if st.session_state.login_error:
        st.sidebar.error(st.session_state.login_error)
    if login_successful_submit:
        log_message_from_main_thread("Login form submitted successfully.")
        st.rerun() 
    st.info("Silakan login melalui sidebar untuk mengakses dashboard.")
    st.stop()

if st.session_state.authenticated and not st.session_state.connected and not st.session_state.attempted_connect:
    if not st.session_state.mqtt_client: 
        connect_mqtt()

st.sidebar.header("🔌 Koneksi MQTT")
connection_status_text = "🟢 Terhubung" if st.session_state.connected else "🔴 Terputus"
broker_info_text = f"{MQTT_BROKER_HOST}:{MQTT_PORT} ({'MQTTS' if USE_TLS else 'MQTT'})"
st.sidebar.markdown(f"**Status:** {connection_status_text}", unsafe_allow_html=True)
st.sidebar.caption(f"Broker: {broker_info_text}")

if not st.session_state.connected:
    if st.sidebar.button("Hubungkan ke MQTT Broker", key="connect_btn_main_key"):
        connect_mqtt()
else:
    if st.sidebar.button("Putuskan Koneksi MQTT", key="disconnect_btn_main_key"):
        disconnect_mqtt()

if st.session_state.connected:
    st.sidebar.header("🌍 Pilih Wilayah (Subscribe)")
    # 'subscribed_topics' di session_state adalah daftar topik yang *seharusnya* disubscribe.
    # Ini dikelola oleh UI.
    default_selection = [topic.split("/")[-1] for topic in st.session_state.subscribed_topics if topic.split("/")[-1] in AVAILABLE_ADM4_CODES]
    
    selected_adm4s_ui = st.sidebar.multiselect(
        "Pilih Kode Wilayah ADM4:", options=AVAILABLE_ADM4_CODES, default=default_selection, key="selected_adm4s_multiselect_key"
    )
    
    # Ini adalah set topik yang *diinginkan* oleh UI saat ini
    desired_topics_from_ui = {f"bmkg/prakiraan/{adm4}" for adm4 in selected_adm4s_ui}
    
    # Topik yang perlu ditambahkan (subscribe)
    topics_to_add_subscription = desired_topics_from_ui - st.session_state.subscribed_topics
    for topic_to_sub in topics_to_add_subscription:
        if st.session_state.mqtt_client and st.session_state.connected:
            st.session_state.mqtt_client.subscribe(topic_to_sub, qos=2)
            log_message_from_main_thread(f"Subscribing to {topic_to_sub}") 
            if topic_to_sub not in st.session_state.weather_data:
                 st.session_state.weather_data[topic_to_sub] = []
    
    # Topik yang perlu dihilangkan (unsubscribe)
    topics_to_remove_subscription = st.session_state.subscribed_topics - desired_topics_from_ui
    # Filter hanya topik data cuaca
    topics_to_remove_subscription = {t for t in topics_to_remove_subscription if t.startswith("bmkg/prakiraan/")}

    for topic_to_unsub in topics_to_remove_subscription:
        if st.session_state.mqtt_client and st.session_state.connected:
            st.session_state.mqtt_client.unsubscribe(topic_to_unsub)
        if topic_to_unsub in st.session_state.weather_data: # Hapus data dari UI juga
            del st.session_state.weather_data[topic_to_unsub]
        log_message_from_main_thread(f"Unsubscribing from {topic_to_unsub}")
    
    # Update st.session_state.subscribed_topics agar sesuai dengan UI
    st.session_state.subscribed_topics = desired_topics_from_ui

    if topics_to_add_subscription or topics_to_remove_subscription:
        if not rerun_triggered_by_queue: 
            st.rerun()

    if st.sidebar.button("Clear Displayed Weather Data", key="clear_weather_data_btn"):
        for topic_key in list(st.session_state.weather_data.keys()):
            if topic_key.startswith("bmkg/prakiraan/"): 
                 st.session_state.weather_data[topic_key] = []
        st.rerun() 

# Tampilan Data Cuaca (Sama)
st.header("📊 Prakiraan Cuaca Terkini")
if not st.session_state.connected:
    st.warning("Belum terhubung ke MQTT Broker. Coba klik 'Hubungkan' di sidebar.")
elif not st.session_state.subscribed_topics or not any(t.startswith("bmkg/prakiraan/") for t in st.session_state.subscribed_topics):
    st.info("Pilih wilayah di sidebar untuk menampilkan data cuaca.")
else:
    # Filter hanya topik prakiraan untuk ditampilkan
    sorted_weather_topics = sorted([t for t in st.session_state.subscribed_topics if t.startswith("bmkg/prakiraan/")])
    if not sorted_weather_topics:
         st.info("Tidak ada wilayah cuaca yang dipilih atau data belum diterima.")
    for topic_idx, topic in enumerate(sorted_weather_topics):
        adm4_code_display = topic.split("/")[-1]
        expander_expanded = topic_idx == 0 
        with st.expander(f"📍 Wilayah: {adm4_code_display}", expanded=expander_expanded):
            if topic in st.session_state.weather_data and st.session_state.weather_data[topic]:
                forecast_list = st.session_state.weather_data[topic]
                display_data = []
                for item in forecast_list:
                    try:
                        local_dt = datetime.strptime(item.get('local_datetime', ''), "%Y-%m-%d %H:%M:%S")
                        time_str = local_dt.strftime("%H:%M")
                        date_str = local_dt.strftime("%d %b %Y")
                    except ValueError:
                        time_str = item.get('local_datetime', 'N/A').split(" ")[-1][:5]
                        date_str = item.get('local_datetime', 'N/A').split(" ")[0]
                    display_data.append({
                        "Tanggal": date_str, "Jam": time_str,
                        "Cuaca": item.get('weather_desc', item.get('weather_desc_en', 'N/A')),
                        "Suhu (°C)": item.get('t', 'N/A'), "Kelembaban (%)": item.get('hu', 'N/A'),
                        "Angin (km/j)": item.get('ws', 'N/A'), "Arah Angin": item.get('wd', 'N/A')
                    })
                df = pd.DataFrame(display_data)
                st.dataframe(df, use_container_width=True, height=min(300, len(df) * 35 + 38))
            elif topic in st.session_state.weather_data: # Key ada, data kosong
                st.write(f"Menunggu data untuk {adm4_code_display}...")
            else: # Key topik belum ada di weather_data (seharusnya tidak terjadi jika subscribed_topics dikelola dgn benar)
                 st.write(f"Data untuk {adm4_code_display} belum tersedia (belum ada key di data store).")

# Fitur MQTT 5.0 Request/Response (Sama)
if st.session_state.connected:
    st.header("📡 Kontrol Publisher (MQTT 5.0)")
    col_req, col_resp = st.columns(2)
    with col_req:
        st.subheader("Kirim Perintah")
        with st.form("request_form_main"):
            command_type = st.selectbox("Pilih Perintah:", ["status", "force_refresh"], key="cmd_type_sel_main")
            adm4_for_refresh_cmd = ""
            if command_type == "force_refresh":
                adm4_for_refresh_cmd = st.selectbox(
                    "ADM4 untuk di-refresh:", options=AVAILABLE_ADM4_CODES, key="cmd_adm4_sel_main"
                )
            submit_request_btn = st.form_submit_button("Kirim Perintah ke Publisher")
            if submit_request_btn:
                if st.session_state.mqtt_client and st.session_state.connected:
                    correlation_id = str(uuid.uuid4())
                    response_topic_for_publisher_to_use = RESPONSE_TOPIC_APP_BASE 
                    req_properties = props.Properties(PacketTypes.PUBLISH)
                    req_properties.ResponseTopic = response_topic_for_publisher_to_use
                    req_properties.CorrelationData = correlation_id.encode('utf-8')
                    payload_dict = {"command": command_type}
                    if command_type == "force_refresh" and adm4_for_refresh_cmd:
                        payload_dict["adm4"] = adm4_for_refresh_cmd
                    payload_json = json.dumps(payload_dict)
                    result = st.session_state.mqtt_client.publish(
                        REQUEST_TOPIC_TO_PUBLISHER, payload_json, qos=1, properties=req_properties
                    )
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        st.session_state.pending_requests[correlation_id] = f"Perintah: {command_type}" + \
                            (f" untuk {adm4_for_refresh_cmd}" if command_type == "force_refresh" and adm4_for_refresh_cmd else "")
                        log_message_from_main_thread(f"Perintah '{command_type}' dikirim (CorrID: {correlation_id[:8]})")
                    else:
                        log_message_from_main_thread(f"Gagal mengirim perintah '{command_type}', rc: {result.rc}")
                    if not rerun_triggered_by_queue: st.rerun() 
                else:
                    st.error("Tidak terhubung ke MQTT Broker untuk mengirim perintah.")
    with col_resp:
        st.subheader("Respons Diterima")
        if st.session_state.pending_requests:
            st.caption("Menunggu respons untuk:")
            for cid, desc in st.session_state.pending_requests.items():
                st.markdown(f"<small>- {desc} (ID: `{cid[:8]}`)</small>", unsafe_allow_html=True)
        if st.session_state.request_responses:
            st.caption("Respons yang sudah diterima (terbaru di atas):")
            sorted_responses = sorted(st.session_state.request_responses.items(), key=lambda item: item[0], reverse=True) 
            for cid, resp_payload in sorted_responses:
                with st.container():
                    st.markdown(f"<small>Respons untuk ID: `{cid[:8]}`</small>", unsafe_allow_html=True)
                    st.json(resp_payload)
            if st.button("Clear Responses Diterima", key="clear_resp_btn_key"):
                st.session_state.request_responses.clear()
                st.rerun() 
        elif not st.session_state.pending_requests:
             st.caption("Tidak ada respons yang ditunggu atau diterima saat ini.")

# Log Aplikasi (Sama)
st.sidebar.header("📜 Log Aplikasi")
if st.sidebar.button("Clear Log", key="clear_log_btn_key"):
    if 'app_log' in st.session_state: st.session_state.app_log = []
    st.rerun() 

log_container = st.sidebar.expander("Tampilkan Log", expanded=True)
with log_container:
    if not st.session_state.get('app_log', []):
        st.caption("Log kosong.")
    for entry in st.session_state.get('app_log', []):
        st.caption(entry)

# Tidak perlu rerun eksplisit di akhir jika modifikasi state sudah terjadi
# dan rerun_triggered_by_queue sudah ditangani.