import pandas as pd
import numpy as np
import os

def apply_noise(series, noise_level=0.015, outlier_prob=0.005, outlier_range=(0, 200)):
    """Adds Gaussian noise and occasional sensor 'glitches' to mimic real hardware."""
    noise = np.random.normal(0, series.mean() * noise_level, len(series))
    series = series + noise
    
    mask = np.random.rand(len(series)) < outlier_prob
    series[mask] = np.random.uniform(outlier_range[0], outlier_range[1], sum(mask))
    return series

def generate_medical_data(patient_id, duration_min=120, scenario="normal"):
    t = np.arange(duration_min)
    
    # 🌟 UPGRADE: Patient Baseline Variance
    # Every patient now has a unique, realistic resting baseline
    base_hr = np.random.normal(75.0, 8.0)     # Mean 75, Standard Dev 8
    base_map = np.random.normal(85.0, 6.0)    # Mean 85, Standard Dev 6
    base_rr = np.random.normal(16.0, 2.0)     # Mean 16, Standard Dev 2
    base_spo2 = np.random.uniform(96.0, 100.0)# Healthy O2 range
    
    hr = np.full(duration_min, base_hr)
    map_val = np.full(duration_min, base_map)
    rr = np.full(duration_min, base_rr)
    spo2 = np.full(duration_min, base_spo2)
    
    # The perfect fix: 70% of safe patients are on baseline opioids
    base_opioid = 2.0 if np.random.rand() < 0.7 else 0.0
    opioid = np.full(duration_min, base_opioid)
    label = 0 # Safe
    
    if scenario == "bleeding":
        # MAP drops, HR spikes to compensate
        start = duration_min // 2
        hr[start:] += np.linspace(0, 45, duration_minutes := (duration_min - start))
        map_val[start:] -= np.linspace(0, 35, duration_minutes)
        label = 1
        
    elif scenario == "respiratory":
        # Opioid flow spikes, RR drops first, SpO2 lags then drops
        start = duration_min // 2
        opioid[start:] = 5.0 
        rr[start:] -= np.linspace(0, 10, duration_minutes := (duration_min - start))
        
        # Physiological lag for SpO2
        lag = 8
        spo2[start+lag:] -= np.linspace(0, 15, duration_min - (start+lag))
        label = 2

    # Apply Real-World Sensor Noise
    hr = apply_noise(hr, noise_level=0.01, outlier_range=(40, 160))
    map_val = apply_noise(map_val, noise_level=0.02, outlier_range=(30, 120))
    rr = apply_noise(rr, noise_level=0.05, outlier_range=(4, 30))
    spo2 = np.clip(apply_noise(spo2, noise_level=0.005, outlier_range=(70, 100)), 50, 100)

    return pd.DataFrame({
        "heart_rate": np.round(hr, 2),
        "map": np.round(map_val, 2),
        "resp_rate": np.round(rr, 2), 
        "spo2": np.round(spo2, 2),
        "opioid_flow": np.round(opioid, 2),
        "target": label
    })

# --- Execution ---
print("🚀 Scaling up to 10,000 patients for high-fidelity WardAI training...")

all_patients = [
    *[generate_medical_data(i, scenario="normal") for i in range(6000)],      # 60% Baseline
    *[generate_medical_data(i, scenario="bleeding") for i in range(2000)],    # 20% Hemorrhage
    *[generate_medical_data(i, scenario="respiratory") for i in range(2000)]  # 20% Overdose
]

data = pd.concat(all_patients, ignore_index=True)

# Added a random_state to the shuffle so your results are perfectly reproducible
print("🔀 Shuffling 1.2 million rows to prevent model bias...")
data = data.sample(frac=1, random_state=42).reset_index(drop=True)

output_path = "wardai_training_data.csv"
print(f"💾 Saving to {output_path}... (This might take a minute)")
data.to_csv(output_path, index=False)

print(f"✅ Success! Created {output_path} with {len(data)} rows.")
print(f"📊 Dataset Breakdown: {data['target'].value_counts().to_dict()}")