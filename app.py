import streamlit as st
import pandas as pd
import numpy as np
import json
import threading
import time
import paho.mqtt.client as mqtt
from math import sqrt

# === Fall Detection Algorithm (Python Implementation) ===
class FallDetection:
    def __init__(self, amp_threshold_1=2, amp_threshold_2=12, angle_change_min=30, angle_change_max=400,
                 trigger3_count_threshold=10, angle_change_threshold=10, trigger1_count_limit=6, trigger2_count_limit=6):

        self.ax = 0.0
        self.ay = 0.0
        self.az = 0.0
        self.gx = 0.0
        self.gy = 0.0
        self.gz = 0.0
        self.fall = False
        self.trigger1 = False
        self.trigger2 = False
        self.trigger3 = False
        self.trigger1count = 0
        self.trigger2count = 0
        self.trigger3count = 0

        self.amp_threshold_1 = amp_threshold_1
        self.amp_threshold_2 = amp_threshold_2
        self.angle_change_min = angle_change_min
        self.angle_change_max = angle_change_max
        self.trigger3_count_threshold = trigger3_count_threshold
        self.angle_change_threshold = angle_change_threshold
        self.trigger1_count_limit = trigger1_count_limit
        self.trigger2_count_limit = trigger2_count_limit

    def process_sensor_data(self, ax, ay, az, gx, gy, gz):
        self.ax = ax
        self.ay = ay
        self.az = az
        self.gx = gx
        self.gy = gy
        self.gz = gz

        Raw_Amp = sqrt(self.ax*self.ax + self.ay*self.ay + self.az*self.az)
        Amp = Raw_Amp * 10

        if Amp <= self.amp_threshold_1 and not self.trigger2:
            self.trigger1 = True
            print("TRIGGER 1 ACTIVATED")
        if self.trigger1:
            self.trigger1count += 1
            if Amp >= self.amp_threshold_2:
                self.trigger2 = True
                print("TRIGGER 2 ACTIVATED")
                self.trigger1 = False
                self.trigger1count = 0
        if self.trigger2:
            self.trigger2count += 1
            angleChange = sqrt(self.gx*self.gx + self.gy*self.gy + self.gz*self.gz)
            print("AngleChange:", angleChange)
            if self.angle_change_min <= angleChange <= self.angle_change_max:
                self.trigger3 = True
                self.trigger2 = False
                self.trigger2count = 0
                print("TRIGGER 3 ACTIVATED")
        if self.trigger3:
            self.trigger3count += 1
            if self.trigger3count >= self.trigger3_count_threshold:
                angleChange = sqrt(self.gx*self.gx + self.gy*self.gy + self.gz*self.gz)
                if 0 <= angleChange <= self.angle_change_threshold:
                    self.fall = True
                    self.trigger3 = False
                    self.trigger3count = 0
                else:
                    self.trigger3 = False
                    self.trigger3count = 0
                    print("TRIGGER 3 DEACTIVATED")

        if self.trigger2count >= self.trigger2_count_limit:
            self.trigger2 = False
            self.trigger2count = 0
            print("TRIGGER 2 DEACTIVATED")
        if self.trigger1count >= self.trigger1_count_limit:
            self.trigger1 = False
            self.trigger1count = 0
            print("TRIGGER 1 DEACTIVATED")

        fall_detected = self.fall
        self.fall = False
        return fall_detected

# === Streamlit App ===
st.set_page_config(page_title="Fall Detection", layout="centered")
st.title("📡 Fall Detection (ESP32 via MQTT)")
st.write("Receiving real-time data on topic: `fall`")

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "devovation/data"

incoming_data = []
fall_detected_flag = False

fall_detector = FallDetection()

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
        cahaya = str(payload.get("Cahaya", ""))
        ldr = int(payload.get("LDR", 0))

        # === FALL SENSOR ===
        ax = float(payload.get("Ax", 0.0))
        ay = float(payload.get("Ay", 0.0))
        az = float(payload.get("Az", 0.0))
        gx = float(payload.get("Gx", 0.0))
        gy = float(payload.get("Gy", 0.0))
        gz = float(payload.get("Gz", 0.0))

        fall_detected_flag = fall_detector.process_sensor_data(ax, ay, az, gx, gy, gz)

        status = str(payload.get("Status", "Tidak diketahui"))

        if fall_detected_flag:
            print("🚨 FALL DETECTED!")

        # === SIMPAN DATA KE LIST ===
        incoming_data.append([status, suhu, hum, cahaya, ldr, ax, ay, az, gx, gy, gz])

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

while True:
    time.sleep(2)

    if incoming_data:
        try:
            # Ambil data terbaru (sekarang termasuk status)
            last = incoming_data[-1]
            status, suhu, hum, cahaya, ldr, ax, ay, az, gx, gy, gz = last

            # === STATUS CARD ===
            if status == "Aman":
                status_placeholder.success("🟢 STATUS: AMAN")
            elif status == "Tergelincir":
                status_placeholder.warning("🟡 STATUS: TERGELINCIR")
            else:
                status_placeholder.error(f"🔴 STATUS: {status}")

            # === SENSOR INFO ===
            with sensor_block.container():
                st.subheader("📊 Sensor Real-Time Data")

                col1, col2 = st.columns(2)

                with col1:
                    st.info(f"🌡 **Suhu:** {suhu} °C")
                    st.info(f"💧 **Kelembaban:** {hum} %")
                    st.info(f"💡 **Cahaya:** {cahaya}")
                    st.info(f"🔦 **LDR:** {ldr}")

                with col2:
                    st.success(f"📈 **Ax / Ay / Az**\n{ax} / {ay} / {az}")
                    st.success(f"🔄 **Gx / Gy / Gz**\n{gx} / {gy} / {gz}")

                st.markdown("---")

            # Fall Detection Trigger
            if fall_detected_flag:
                st.error("🚨 FALL DETECTED!")
                fall_detected_flag = False

            incoming_data = incoming_data[-20:]

        except Exception as e:
            status_placeholder.error(f"UI Update Error: {e}")

    else:
        status_placeholder.info("⏳ Waiting for data from MQTT...")

time.sleep(2)
st.rerun()
