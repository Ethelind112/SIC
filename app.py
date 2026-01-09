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
st.title("📡 Fall Detection (ESP32 via MQTT)")
st.write("Receiving real-time data on topic: `fall`")

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "devovation/streamlit"

incoming_data = []

def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global incoming_data, fall_detected_flag

    try:
        payload = json.loads(msg.payload.decode())

        # === SENSOR BARU ===
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

threading.Thread(target=mqtt_thread_function, daemon=True).start()

status_placeholder = st.empty()
sensor_block = st.empty()
condition = st.empty()

while True:
    time.sleep(2)

    if incoming_data:
        try:
            # Ambil data terbaru (sekarang termasuk status)
            last = incoming_data[-1]
            suhu, hum, status = last

            # === SENSOR INFO ===
            with sensor_block.container():
                st.subheader("📊 Sensor Real-Time Data")

                col1, col2 = st.columns(2)

                with col1:
                    st.info(f"🌡 **Suhu:** {suhu} °C")

                with col2:
                    st.info(f"💧 **Kelembaban:** {hum} %")

                st.markdown("---")

            with condition.container():
                st.subheader("Keadaan Lansia")
                st.info(f"**Status:** {status}")

                st.markdown("---")

            incoming_data = incoming_data[-20:]

        except Exception as e:
            status_placeholder.error(f"UI Update Error: {e}")

    else:
        status_placeholder.info("⏳ Waiting for data from MQTT...")

time.sleep(2)
st.rerun()
