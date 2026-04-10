import time
import requests

API_URL = "http://127.0.0.1:8000/api/vitals"

print("Starting Bed 1 Hardware Simulator...")
current_vitals = {
    "bed_id": "Bed_1",
    "heart_rate": 75.0,
    "map": 85.0,
    "resp_rate": 16.0,
    "spo2": 98.0,
    "opioid_flow": 0.0
}

minute = 1
while True:
    print(f"--- Minute {minute} ---")
    try:
        requests.post(API_URL, json=current_vitals)
    except Exception:
        print("Failed to connect to API. Is main.py running?")
        break

    # SIMULATE CRASH at minute 3
    if minute == 3:
        print("\n>>> SIMULATING CRASH: MAP dropping, HR spiking <<<\n")
        current_vitals["map"] = 60.0  
        current_vitals["heart_rate"] = 115.0

    time.sleep(3) 
    minute += 1