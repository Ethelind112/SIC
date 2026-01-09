import streamlit as st
import json
import threading
import paho.mqtt.client as mqtt

# === Streamlit App ===
st.set_page_config(page_title="Fall Detection", layout="centered")
st.title("📡 Fall Detection (ESP32 via MQTT)")

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "devovation/streamlit"

# === Session State Init ===
if "incoming_data" not in st.session_state:
    st.session_state.incoming_data = []

if "mqtt_connected" not in st.session_state:
    st.session_state.mqtt_connected = False

if "mqtt_started" not in st.session_state:
    st.session_state.mqtt_started = False

# === MQTT CALLBACKS ===
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        st.session_state.mqtt_connected = True
        client.subscribe(MQTT_TOPIC)
        print("MQTT Connected")
    else:
        print("MQTT Connection failed:", rc)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())

        suhu = float(payload.get("Suhu", 0.0))
        hum = float(payload.get("Hum", 0.0))
        status = str(payload.get("Status", "Tidak Diketahui"))

        st.session_state.incoming_data.append([suhu, hum, status])

        # keep last 20 only
        st.session_state.incoming_data = st.session_state.incoming_data[-20:]

    except Exception as e:
        print("MQTT Error:", e)

# === MQTT THREAD ===
def mqtt_thread_function():
    client = mqtt.Client(callback_api_version=2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

# Start MQTT only once
if not st.session_state.mqtt_started:
    st.session_state.mqtt_started = True
    threading.Thread(target=mqtt_thread_function, daemon=True).start()

# === UI PLACEHOLDERS ===
status_placeholder = st.empty()
sensor_block = st.empty()
condition = st.empty()

data = st.session_state.incoming_data

# === UI UPDATE ===
if data:
    suhu, hum, status = data[-1]

    with sensor_block.container():
        st.subheader("📊 Keadaan Ruangan")

        col1, col2 = st.columns(2)

        with col1:
            st.info(f"🌡 **Suhu:** {suhu} °C")

        with col2:
            st.info(f"💧 **Kelembaban:** {hum} %")

    with condition.container():
        st.subheader("Keadaan Lansia")

        if status.lower() == "jatuh":
            st.error("⚠️ **Lansia Jatuh!** Segera Periksa!")
        elif status.lower() == "tidak diketahui":
            st.warning("⚠️ **Keadaan Lansia Tidak Diketahui!** Segera Periksa!")
        else:
            st.success("✅ **Lansia Baik-Baik Saja**")

elif st.session_state.mqtt_connected:
    # MQTT connected but no data yet
    status_placeholder.warning("📡 MQTT Connected. Waiting for data...")

else:
    # Not connected yet
    status_placeholder.info("⏳ Connecting to MQTT broker...")