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
st.title("Dashboard Sistem Lansia")

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "devovation/streamlit"

incoming_data = []
mqtt_connected = False

if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Time", "Suhu", "Kelembaban"])

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
        permintaan = str(payload.get("Permintaan", "Belum Ada Permintaan"))

        ax = float(payload.get("Ax", 0.0))
        ay = float(payload.get("Ay", 0.0))
        az = float(payload.get("Az", 0.0))
        gx = float(payload.get("Gx", 0.0))
        gy = float(payload.get("Gy", 0.0))
        gz = float(payload.get("Gz", 0.0))

        # === SIMPAN DATA KE LIST ===
        incoming_data.append([suhu, hum, status, permintaan, ax, ay, az, gx, gy, gz])

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
connection_status_placeholder = st.empty()
condition = st.empty()
sensor_block = st.empty()
permintaan_placeholder = st.empty()
chart_title = st.empty()
chart_placeholder = st.empty()
mpu_placeholder = st.empty()

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
            suhu, hum, status, permintaan, ax, ay, az, gx, gy, gz = last

            with condition.container():
                if status.lower() == "jatuh":
                    st.markdown(
                        f"""
                        <div style="
                            background-color: #EA7B7B;
                            color: white;
                            border-radius: 10px;
                            padding: 20px;
                            margin-bottom: 20px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            text-align: center;
                        ">
                            <h5 style="margin: 0;">⚠️ <strong>Lansia Jatuh!</strong> Segera Periksa!</h5>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                elif status.lower() == "tidak diketahui":
                    st.markdown(
                        f"""
                        <div style="
                            background-color: #FAD691;
                            color: #FA5C5C;
                            border-radius: 10px;
                            padding: 20px;
                            margin-bottom: 20px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            text-align: center;
                        ">
                            <h5 style="margin: 0;">⚠️ <strong>Keadaan Lansia Tidak Diketahui!</strong> Segera Periksa!</h5>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"""
                        <div style="
                            background-color: #C5D89D;
                            color: #1B211A;
                            border-radius: 10px;
                            padding: 20px;
                            margin-bottom: 20px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            text-align: center;
                        ">
                            <h5 style="margin: 0;">✅ <strong>Lansia Baik-Baik Saja</strong></h5>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            # === SENSOR INFO ===
            with sensor_block.container():

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(
                        f"""
                        <div style="
                            background-color: #37353E;
                            color: white;
                            border: 1px solid #ddd;
                            border-radius: 10px;
                            padding: 15px;
                            padding-top: 10px;
                            margin-bottom: 20px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            text-align: center;
                        ">
                            <p style="margin: 0;">Suhu Ruangan</p>
                            <h4 style="margin: 0;">       {suhu} °C</h4>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with col2:
                    st.markdown(
                        f"""
                        <div style="
                            border: 1px solid #ddd;
                            border-radius: 10px;
                            padding: 15px;
                            padding-top: 10px;
                            margin-bottom: 20px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            text-align: center;
                        ">
                            <p style="margin: 0;">Suhu Ruangan</p>
                            <h4 style="margin: 0;">       {hum}</h4>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            
            with permintaan_placeholder.container():
                st.markdown(
                    f"""
                    <div style="
                       border: 1px solid #ddd;
                            border-radius: 10px;
                            padding: 15px;
                            padding-top: 10px;
                            margin-bottom: 20px;
                            display: flex;
                            flex-direction: column;
                    ">
                        <p style="margin: 0;">Permintaan Bantuan dari Lansia:</p>
                        <p style="margin: 0;"><strong>{permintaan}</strong></p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with chart_title.container():
                if "chart_header_created" not in st.session_state:
                    st.subheader("📉 Grafik Suhu dan Kelembapan")
                    st.session_state.chart_header_created = True

            with chart_placeholder.container():
                new_time = pd.Timestamp.now()
                new_row = pd.DataFrame({"Time": [new_time], "Suhu": [suhu], "Kelembaban": [hum]})
                st.session_state.data = pd.concat([st.session_state.data, new_row], ignore_index=True)
                
                # Keep only the last 50 points for better visualization
                data_to_plot = st.session_state.data.tail(50).set_index("Time")
                
                # Update chart
                chart_placeholder.line_chart(data_to_plot)

            with mpu_placeholder.container():
                st.markdown("---")
                st.subheader("📉 Pergerak Lansia")
                
                col_acc, col_gyro = st.columns(2)
                
                with col_acc:
                    st.info("**Accelerometer (m/s²)**")
                    st.text(f"X: {ax:.2f}\nY: {ay:.2f}\nZ: {az:.2f}")
                    # Hitung magnitude untuk display
                    mag_acc = np.sqrt(ax**2 + ay**2 + az**2)
                    st.markdown(f"**Total G-Force:** `{mag_acc:.2f} g`")
                
                with col_gyro:
                    st.info("**Gyroscope (rad/s)**")
                    st.text(f"X: {gx:.2f}\nY: {gy:.2f}\nZ: {gz:.2f}")
                    mag_gyro = np.sqrt(gx**2 + gy**2 + gz**2)
                    st.markdown(f"**Total Rotasi:** `{mag_gyro:.2f} rad/s`")
    

        except Exception as e:
            status_placeholder.error(f"UI Update Error: {e}")