import streamlit as st
import pandas as pd
import numpy as np
import json
import threading
import time
import paho.mqtt.client as mqtt
from math import sqrt

# === Streamlit App ===
st.set_page_config(page_title="Fall Detection", layout="centered")
st.title("📡 Fall Detection")

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "devovation/streamlit"

incoming_data = []
mqtt_connected = False

def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        client.subscribe(MQTT_TOPIC)
    else:
        mqtt_connected = False

def on_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False

def on_message(client, userdata, msg):
    global incoming_data, fall_detected_flag

    try:
        payload = json.loads(msg.payload.decode())

        suhu = float(payload.get("Suhu", 0.0))
        hum = float(payload.get("Hum", 0.0))
        status = str(payload.get("Status", "Tidak Diketahui"))

        # === SIMPAN DATA KE LIST ===
        incoming_data.append([suhu, hum, status])

    except Exception as e:
        print("Error:", e)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

def mqtt_thread_function():
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

if "mqtt_data_received" not in st.session_state:
    st.session_state.mqtt_data_received = False

threading.Thread(target=mqtt_thread_function, daemon=True).start()

status_placeholder = st.empty()
sensor_block = st.empty()
condition = st.empty()
connection_status_placeholder = st.empty()

while True:
    time.sleep(2)

    if mqtt_connected:
        connection_status_placeholder.info("✅ Connected to MQTT Broker")
    else:
        connection_status_placeholder.info("🔄 Attempting to connect to MQTT Broker...")

    if incoming_data:
        try:
            # Ambil data terbaru (sekarang termasuk status)
            last = incoming_data[-1]
            suhu, hum, status = last

            # === SENSOR INFO ===
            with sensor_block.container():
                st.subheader("📊 Keadaan Ruangan")

                col1, col2 = st.columns(2)

                with col1:
                    st.info(f"🌡 **Suhu:** {suhu} °C")

                with col2:
                    st.info(f"💧 **Kelembaban:** {hum} %")

                st.markdown("---")

            with condition.container():
                st.subheader("Keadaan Lansia")

                if status.lower() == "jatuh":
                    st.error("⚠️ **Lansia Jatuh!** Segera Periksa!")
                elif status.lower() == "tidak diketahui":
                    st.warning("⚠️ **Keadaan Lansia Tidak Diketahui!** Segera Periksa!")
                else:
                    st.success("✅ **Lansia Baik-Baik Saja**")

                st.markdown("---")

            incoming_data = incoming_data[-20:]
            st.markdown(
                """
                <style>
                .custom-container {
                    background-color: #f9f9f9;
                    padding: 1.5rem;
                    border-radius: 12px;
                    border-left: 6px solid #4CAF50;
                    margin-bottom: 1rem;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

        except Exception as e:
            status_placeholder.error(f"UI Update Error: {e}")

