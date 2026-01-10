import streamlit as st
import pandas as pd
import numpy as np
import json
import threading
import time
import paho.mqtt.client as mqtt
from math import sqrt
import joblib

@st.cache_resource
def load_ml_model():
    try:
        # Pastikan nama file sama dengan yang kamu download dari Colab
        model = joblib.load('model_jatuh.pkl')
        return model
    except Exception as e:
        return None

rf_model = load_ml_model()

if rf_model is None:
    st.error("⚠️ File 'model_jatuh.pkl' tidak ditemukan! Pastikan file berada di folder yang sama dengan app.py")
    st.stop()

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC_Ruangan = "devovation/ruangan"
MQTT_TOPIC_Pergerakan = "devovation/pergerakan"
MQTT_TOPIC_Permintaan = "devovation/permintaan"

latest_values = {
    "Suhu": 0.0, "Hum": 0.0, "Permintaan": "Tidak ada", "Last_Update_Permintaan": "None",
    "Ax": 0.0, "Ay": 0.0, "Az": 0.0, "Gx": 0.0, "Gy": 0.0, "Gz": 0.0
}

mqtt_connected = False
fall_detected_flag = False
current_confidence = 0.0

def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        # Subscribe to both topics
        client.subscribe([(MQTT_TOPIC_Ruangan, 0), (MQTT_TOPIC_Pergerakan, 0), (MQTT_TOPIC_Permintaan, 0)])
    else:
        mqtt_connected = False

def on_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False

def on_message(client, userdata, msg):
    global latest_values, fall_detected_flag

    try:
        payload = json.loads(msg.payload.decode())
        
        # Check which topic sent the data and update only those keys
        if msg.topic == MQTT_TOPIC_Ruangan:
            latest_values["Suhu"] = float(payload.get("Suhu", latest_values["Suhu"]))
            latest_values["Hum"] = float(payload.get("Hum", latest_values["Hum"]))
            
        elif msg.topic == MQTT_TOPIC_Pergerakan:
            latest_values["Ax"] = float(payload.get("Ax", latest_values["Ax"]))
            latest_values["Ay"] = float(payload.get("Ay", latest_values["Ay"]))
            latest_values["Az"] = float(payload.get("Az", latest_values["Az"]))
            latest_values["Gx"] = float(payload.get("Gx", latest_values["Gx"]))
            latest_values["Gy"] = float(payload.get("Gy", latest_values["Gy"]))
            latest_values["Gz"] = float(payload.get("Gz", latest_values["Gz"]))

            acc_magnitude = np.sqrt((latest_values['Ax']**2 + latest_values['Ay']**2 + latest_values['Az']**2))
            gyro_magnitude = np.sqrt((latest_values['Gx']**2 + latest_values['Gy']**2 + latest_values['Gz']**2))

            input_data = pd.DataFrame([[latest_values['Ax'], latest_values['Ay'], latest_values['Az'], latest_values['Gx'], latest_values['Gy'], latest_values['Gz'], acc_magnitude, gyro_magnitude]], columns=['ax', 'ay', 'az', 'gx', 'gy', 'gz', 'acc_magnitude', 'gyro_magnitude'])
        
            prediction = rf_model.predict(input_data)[0]
            proba = rf_model.predict_proba(input_data)[0]

            if prediction == 1:
                fall_detected_flag = True
                current_confidence = proba[1] * 100
                print(f"🚨 JATUH TERDETEKSI! (Confidence: {current_confidence:.1f}%)")
            else:
                fall_detected_flag = False
                current_confidence = proba[0] * 100

        elif msg.topic == MQTT_TOPIC_Permintaan:
            latest_values["Permintaan"] = payload.get("Permintaan", latest_values["Permintaan"])
            latest_values["Last_Update_Permintaan"] = payload.get("Time", latest_values["Last_Update_Permintaan"])
    except Exception as e:
        print(f"Error parsing {msg.topic}: {e}")

# === Streamlit App ===
st.set_page_config(page_title="Fall Detection", layout="centered")
st.title("Dashboard Monitoring Lansia")

if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Time", "Suhu", "Kelembaban"])

@st.cache_resource
def start_mqtt():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    thread = threading.Thread(target=client.loop_forever, daemon=True)
    thread.start()
    return client

client_instance = start_mqtt()

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

    d = latest_values.copy()

    with condition.container():
        if fall_detected_flag:
            st.markdown(
                f"""
                <div style="
                    background-color: #FFCDC9;
                    color: #5A0E24;
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
        else:
            st.markdown(
                f"""
                <div style="
                    background-color: #EBF4DD;
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
                    <h4 style="margin: 0;">       {d['Suhu']} °C</h4>
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
                    <p style="margin: 0;">Kelembapan Ruangan</p>
                    <h4 style="margin: 0;">       {d['Hum']} %</h4>
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
                <p style="margin: 0; font-size: 15px;">Permintaan Bantuan dari Lansia:</p>
                <p style="margin: 0; padding-bottom: 5px;color: #57595B; font-size: 12px;">Last Update: {d['Last_Update_Permintaan']}</p>
                <p style="margin: 0;" font-size: 15px;><strong>{d['Permintaan']}</strong></p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with chart_title.container():
        if "chart_header_created" not in st.session_state:
            st.markdown("---")
            st.subheader("📉 Grafik Suhu dan Kelembapan")
            st.session_state.chart_header_created = True

    with chart_placeholder.container():
        new_time = pd.Timestamp.now()
        new_row = pd.DataFrame({"Time": [pd.Timestamp.now()], "Suhu": [d["Suhu"]], "Kelembaban": [d["Hum"]]})
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
            st.text(f"X: {d['Ax']:.2f}\nY: {d['Ay']:.2f}\nZ: {d['Az']:.2f}")
            mag_acc = np.sqrt(d['Ax']**2 + d['Ay']**2 + d['Az']**2)
            st.markdown(f"**Total G-Force:** `{mag_acc:.2f} g`")
        
        with col_gyro:
            st.info("**Gyroscope (rad/s)**")
            st.text(f"X: {d['Gx']:.2f}\nY: {d['Gy']:.2f}\nZ: {d['Gz']:.2f}")
            mag_gyro = np.sqrt(d['Gx']**2 + d['Gy']**2 + d['Gz']**2)
            st.markdown(f"**Total Rotasi:** `{mag_gyro:.2f} rad/s`")