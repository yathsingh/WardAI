import pandas as pd
import numpy as np

def apply_noise(series, noise_level=0.015, outlier_prob=0.005, outlier_range=(0, 200)):
    noise = np.random.normal(0, series.mean() * noise_level, len(series))
    series = series + noise
    mask = np.random.rand(len(series)) < outlier_prob
    series[mask] = np.random.uniform(outlier_range[0], outlier_range[1], sum(mask))
    return series

def generate_medical_data(patient_id, duration_min=120, scenario="normal"):
    t = np.arange(duration_min)
    
    # Unique Resting Baselines
    base_hr = np.random.normal(75.0, 8.0)
    base_map = np.random.normal(85.0, 6.0)
    base_rr = np.random.normal(16.0, 2.0)
    base_spo2 = np.random.uniform(96.0, 100.0)
    
    hr = np.full(duration_min, base_hr)
    map_val = np.full(duration_min, base_map)
    rr = np.full(duration_min, base_rr)
    spo2 = np.full(duration_min, base_spo2)
    
    # 🌟 THE PERFECTIONIST FIX: Array of Safe Labels
    target_labels = np.zeros(duration_min, dtype=int)
    
    if scenario == "bleeding":
        start = duration_min // 2
        hr[start:] += np.linspace(0, 45, duration_minutes := (duration_min - start))
        map_val[start:] -= np.linspace(0, 35, duration_minutes)
        # Flip to 1 ONLY when the bleeding actually starts
        target_labels[start:] = 1 
        
    elif scenario == "respiratory":
        start = duration_min // 2
        rr[start:] -= np.linspace(0, 10, duration_minutes := (duration_min - start))
        lag = 8
        spo2[start+lag:] -= np.linspace(0, 15, duration_min - (start+lag))
        # Flip to 2 ONLY when the respiratory failure starts
        target_labels[start:] = 2 

    # Apply Noise
    hr = apply_noise(hr, noise_level=0.01, outlier_range=(40, 160))
    map_val = apply_noise(map_val, noise_level=0.02, outlier_range=(30, 120))
    rr = apply_noise(rr, noise_level=0.05, outlier_range=(4, 30))
    spo2 = np.clip(apply_noise(spo2, noise_level=0.005, outlier_range=(70, 100)), 50, 100)

    # Compile the Chronological DataFrame
    df = pd.DataFrame({
        "heart_rate": np.round(hr, 2),
        "map": np.round(map_val, 2),
        "resp_rate": np.round(rr, 2), 
        "spo2": np.round(spo2, 2),
        "target": target_labels # <--- Using the time-accurate array
    })

    # Calculate 15-Minute Velocity
    df['map_delta'] = df['map'].diff(periods=15).fillna(0)
    df['hr_delta'] = df['heart_rate'].diff(periods=15).fillna(0)
    df['rr_delta'] = df['resp_rate'].diff(periods=15).fillna(0)
    
    # Zero out the first 15 minutes
    df.loc[:14, ['map_delta', 'hr_delta', 'rr_delta']] = 0

    return df

# --- Execution ---
print("🚀 Running the Perfectionist Option: Generating time-accurate labels...")
all_patients = [
    *[generate_medical_data(i, scenario="normal") for i in range(6000)],
    *[generate_medical_data(i, scenario="bleeding") for i in range(2000)],
    *[generate_medical_data(i, scenario="respiratory") for i in range(2000)]
]

data = pd.concat(all_patients, ignore_index=True)
data = data.sample(frac=1, random_state=42).reset_index(drop=True)

output_path = "wardai_training_data.csv"
data.to_csv(output_path, index=False)
print(f"✅ Success! Created {output_path} with {len(data)} rows.")