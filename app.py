import streamlit as st
import pandas as pd
import numpy as np
import json
import time
import paho.mqtt.client as mqtt
from math import sqrt
import joblib

# -------------------------------------------------------------
# MODEL SETUP
# -------------------------------------------------------------
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

# -------------------------------------------------------------
# Fall Detection Calculation
# -------------------------------------------------------------
class FallDetection:
    def __init__(self, amp_threshold_1=2, amp_threshold_2=12, angle_change_min=30, angle_change_max=400, trigger3_count_threshold=10, angle_change_threshold=10, trigger1_count_limit=6, trigger2_count_limit=6):
        """
        Initializes the FallDetection class with sensor offsets and thresholds.

        Args:
            amp_threshold_1 (float): Threshold for the amplitude in trigger 1.
            amp_threshold_2 (float): Threshold for the amplitude in trigger 2.
            angle_change_min (int): Minimum angle change for trigger 3.
            angle_change_max (int): Maximum angle change for trigger 3.
            trigger3_count_threshold (int): Threshold for trigger 3 count.
            angle_change_threshold (int):  Angle change threshold for trigger 3.
            trigger1_count_limit (int): Trigger 1 count limit.
            trigger2_count_limit (int): Trigger 2 count limit.
        """
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
        angleChange = 0
        self.amp_threshold_1 = amp_threshold_1
        self.amp_threshold_2 = amp_threshold_2
        self.angle_change_min = angle_change_min
        self.angle_change_max = angle_change_max
        self.trigger3_count_threshold = trigger3_count_threshold
        self.angle_change_threshold = angle_change_threshold
        self.trigger1_count_limit = trigger1_count_limit
        self.trigger2_count_limit = trigger2_count_limit


    def process_sensor_data(self, ax, ay, az, gx, gy, gz):
        """
        Processes sensor data to detect potential falls.

        Args:
            ax (float): Accelerometer X-axis value.
            ay (float): Accelerometer Y-axis value.
            az (float): Accelerometer Z-axis value.
            gx (float): Gyroscope X-axis value.
            gy (float): Gyroscope Y-axis value.
            gz (float): Gyroscope Z-axis value.

        Returns:
            bool: True if a fall is detected, False otherwise.
        """
        self.ax = ax
        self.ay = ay
        self.az = az
        self.gx = gx
        self.gy = gy
        self.gz = gz

        Raw_Amp = sqrt(self.ax * self.ax + self.ay * self.ay + self.az * self.az)
        Amp = Raw_Amp * 10  # Assuming the same scaling as the Arduino code.

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
            angleChange = sqrt(self.gx * self.gx + self.gy * self.gy + self.gz * self.gz)
            print("AngleChange: " + (angleChange));
            if self.angle_change_min <= angleChange <= self.angle_change_max:
                self.trigger3 = True
                self.trigger2 = False
                self.trigger2count = 0
                print("TRIGGER 3 ACTIVATED")
        if self.trigger3:
            self.trigger3count += 1
            if self.trigger3count >= self.trigger3_count_threshold:
                angleChange = sqrt(self.gx * self.gx + self.gy * self.gy + self.gz * self.gz)
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
        self.fall = False  # Reset for the next iteration
        return fall_detected

# -------------------------------------------------------------
# MANUAL MQTT SETTINGS (Laptop)
# -------------------------------------------------------------
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC_Ruangan = "devovation/ruangan"
MQTT_TOPIC_Pergerakan = "devovation/pergerakan"
MQTT_TOPIC_Permintaan = "devovation/permintaan"
MQTT_TOPIC_BuzzerOn = "devovation/alert"
MQTT_TOPIC_BuzzerOff = "devovation/reset"

# -------------------------------------------------------------
# SESSION STATE INIT (WAJIB — AGAR TIDAK ERROR)
# -------------------------------------------------------------
if "on_fall" not in st.session_state:
    st.session_state.on_fall = False

if "connected" not in st.session_state:
    st.session_state.connected = False

if "logs" not in st.session_state:
    st.session_state.logs = []

if "last_data" not in st.session_state:
    st.session_state.last_data = None

if "mqtt" not in st.session_state:
    st.session_state.mqtt = None

if "last_data" not in st.session_state or st.session_state.last_data is None:
    st.session_state.last_data = {
        "temp_hum": {"Suhu": 0, "Hum": 0}, 
        "gyro": {"Ax": 0, "Ay": 0, "Az": 0, "Gx": 0, "Gy": 0, "Gz": 0},
        "request": {"Permintaan": "Tidak Ada", "Last_Update_Permintaan": "-"}
    }

if "logs" not in st.session_state:
    st.session_state.logs = {
        "temp_hum": [],
        "gyro": [],
        "request": [],
    }

fall_detector = FallDetection()

# -------------------------------------------------------------
# MQTT CALLBACKS
# -------------------------------------------------------------
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        st.session_state.connected = True
        client.subscribe([(MQTT_TOPIC_Ruangan, 0), (MQTT_TOPIC_Pergerakan, 0), (MQTT_TOPIC_Permintaan, 0)])
        print("Connected to MQTT broker")
    else:
        st.session_state.connected = False
        print("MQTT connection failed")


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())

        if msg.topic == MQTT_TOPIC_Ruangan:
            row = {
                "Suhu": data.get("Suhu"),
                "Hum": data.get("Hum"),
            }
            st.session_state.last_data["temp_hum"] = row
            st.session_state.logs["temp_hum"].append(row)

        elif msg.topic == MQTT_TOPIC_Pergerakan:
            Ax = float(data["Ax"])
            Ay = float(data["Ay"])
            Az = float(data["Az"])
            Gx = float(data["Gx"])
            Gy = float(data["Gy"])
            Gz = float(data["Gz"])

            row = {
                "Ax": data.get("Ax"),
                "Ay": data.get("Ay"),
                "Az": data.get("Az"),
                "Gx": data.get("Gx"),
                "Gy": data.get("Gy"),
                "Gz": data.get("Gz")
            }
            st.session_state.last_data["gyro"] = row
            st.session_state.logs["gyro"].append(row)

        elif msg.topic == MQTT_TOPIC_Permintaan:
            row = {
                "Permintaan": data.get("Permintaan"),
                "Time": data.get("Time"),
            }

            st.session_state.last_data["request"] = row
            st.session_state.logs["request"].append(row)

    except Exception as e:
        print("Parse error:", e)


# -------------------------------------------------------------
# START MQTT CLIENT — TANPA THREAD (NO ERROR)
# -------------------------------------------------------------
if st.session_state.mqtt is None:
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    st.session_state.mqtt = client


# -------------------------------------------------------------
# STREAMLIT UI
# -------------------------------------------------------------
st.set_page_config(page_title="Fall Detection", layout="centered")
st.title("Dashboard Monitoring Lansia")


st.markdown("""
    <style>
    div.stButton > button {
        background-color: transparent !important;
        color: #1B3C53 !important;
        border: 0px solid #5A0E24 !important;
        border-radius: 15px 15px 15px 15px !important;
        width: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        text-align: center;
    }
    div.stButton > button:hover {
        color: #9E2A3A !important;
        background-color: transparent !important;
    }
    div.stButton > button:active {
        color: #9E2A3A !important;
        background-color: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------
# CONTAINER SETUP
# -------------------------------------------------------------
status_placeholder = st.empty()
connection_status_placeholder = st.empty()
condition = st.empty()
button_placeholder = st.empty()
sensor_block = st.empty()
permintaan_placeholder = st.empty()
mpu_placeholder = st.empty()
chart_title = st.empty()
chart_placeholder = st.empty()

# -------------------------------------------------------------
#  CONNECTION STATUS BAR
# -------------------------------------------------------------

if st.session_state.connected:
    connection_status_placeholder.info("✅ Connected to MQTT Broker")
else:
    connection_status_placeholder.info("🔄 Attempting to connect to MQTT Broker...")

# -------------------------------------------------------------
#  CONDITION STATUS BAR
# -------------------------------------------------------------

with condition.container():
    gyro = st.session_state.last_data.get("gyro")
    Ax = gyro.get("Ax")
    Ay = gyro.get("Ay")
    Az = gyro.get("Az")
    Gx = gyro.get("Gx")
    Gy = gyro.get("Gy")
    Gz = gyro.get("Gz")

    acc_magnitude = np.sqrt(Ax**2 + Ay**2 + Az**2)
    gyro_magnitude = np.sqrt(Gx**2 + Gy**2 + Gz**2)

    input_data = pd.DataFrame([[Ax, Ay, Az, Gx, Gy, Gz, acc_magnitude, gyro_magnitude]], columns=["ax", "ay", "az", "gx", "gy", "gz", "acc_magnitude", "gyro_magnitude"])

    prediction = rf_model.predict(input_data)[0]
    proba = rf_model.predict_proba(input_data)[0]

    print(f"Prediction: {prediction}, Probability: {proba}")

    fall_detected_flag = fall_detector.process_sensor_data(Ax, Ay, Az, Gx, Gy, Gz)

    print("Fall Detected Flag:", fall_detected_flag)

    if prediction == 1 and fall_detected_flag:
        st.session_state.mqtt.publish(MQTT_TOPIC_BuzzerOn, "FALL")
        st.session_state.on_fall = True

    if (prediction == 1 and fall_detected_flag) or st.session_state.on_fall:
        print("Displaying fall alert")

        st.markdown(
            f"""
            <div style="
                background-color: #FFCDC9;
                color: #5A0E24;
                border-radius: 10px;
                padding: 20px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                text-align: center;
            ">
                <h5 style="margin: 0;">⚠️ <strong>Lansia Jatuh!</strong> Segera periksa lokasi!</h5>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Button visually attached
        with button_placeholder:
            if st.button("Lansia Sudah Terbantu? Reset Status!"):
                st.session_state.on_fall = False
                st.session_state.mqtt.publish(MQTT_TOPIC_BuzzerOff, "RESET")
                st.session_state.last_data["gyro"]["Prediction"] = 0
                st.rerun()

    elif prediction == 0 or not fall_detected_flag:
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
    else:
        st.markdown(
            f"""
            <div style="
                background-color: #FEEAC9;
                color: #CF4B00;
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

# -------------------------------------------------------------
#  TEMP & HUM BAR
# -------------------------------------------------------------

with sensor_block.container():
    temp_hum = st.session_state.last_data.get("temp_hum")
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
                <h4 style="margin: 0;">       {temp_hum.get("Suhu")} °C</h4>
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
                <h4 style="margin: 0;">       {temp_hum.get("Hum")} %</h4>
            </div>
            """,
            unsafe_allow_html=True
        )

# -------------------------------------------------------------
#  REQUEST BAR
# -------------------------------------------------------------

with permintaan_placeholder.container():
    request = st.session_state.last_data.get("request")

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
            <p style="margin: 0; padding-bottom: 5px;color: #57595B; font-size: 12px;">Last Update: {request.get("Time")}</p>
            <p style="margin: 0;" font-size: 15px;><strong>{request.get("Permintaan")}</strong></p>
        </div>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------------------
#  GYRO INFO
# -------------------------------------------------------------

with mpu_placeholder.container():
    gyro = st.session_state.last_data.get("gyro")

    st.markdown("---")
    st.subheader("📉 Pergerak Lansia")
    
    col_acc, col_gyro = st.columns(2)
    
    with col_acc:
        st.info("**Accelerometer (m/s²)**")
        st.text(f"X: {gyro.get("Ax"):.2f}\nY: {gyro.get("Ay"):.2f}\nZ: {gyro.get("Az"):.2f}")
        mag_acc = np.sqrt(gyro.get("Ax")**2 + gyro.get("Ay")**2 + gyro.get("Az")**2)
        st.markdown(f"**Total G-Force:** `{mag_acc:.2f} g`")
    
    with col_gyro:
        st.info("**Gyroscope (rad/s)**")
        st.text(f"X: {gyro.get("Gx"):.2f}\nY: {gyro.get("Gy"):.2f}\nZ: {gyro.get("Gz"):.2f}")
        mag_gyro = np.sqrt(gyro.get("Gx")**2 + gyro.get("Gy")**2 + gyro.get("Gz")**2)
        st.markdown(f"**Total Rotasi:** `{mag_gyro:.2f} rad/s`")

# -------------------------------------------------------------
#  GRAPHIC TEMP & HUM
# -------------------------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Waktu", "Suhu", "Kelembaban"])

with chart_title.container():
    st.markdown("---")
    st.subheader("📉 Grafik Suhu dan Kelembapan")

with chart_placeholder.container():
    new_time = pd.Timestamp.now()
    temp_hum = st.session_state.last_data.get("temp_hum")
    new_row = pd.DataFrame({"Waktu": [pd.Timestamp.now()], "Suhu": [temp_hum.get("Suhu")], "Kelembaban": [temp_hum.get("Hum")]})
    st.session_state.data = pd.concat([st.session_state.data, new_row], ignore_index=True)
    
    # Keep only the last 50 points for better visualization
    data_to_plot = st.session_state.data.tail(50).set_index("Waktu")
    
    # Update chart
    chart_placeholder.line_chart(data_to_plot)

st.session_state.mqtt.loop(timeout=0.1)

# auto refresh
time.sleep(1)
st.rerun()
