from collections import defaultdict, deque

# This dictionary acts as our AI's "Short-Term Memory".
# It stores up to 15 previous vital readings for each bed to calculate velocity.
patient_history = defaultdict(lambda: deque(maxlen=15))

def predict_risk(bed_id: str, current_vitals: dict):
    """
    Simulates an ML model evaluating patient risk based on 
    current vitals AND the velocity (delta) of those vitals over time.
    """
    # 1. Store the current vitals in memory
    patient_history[bed_id].append(current_vitals.copy())
    
    # 2. Retrieve the oldest vitals in our buffer (up to 15 ticks ago)
    past_vitals = patient_history[bed_id][0]
    
    # 3. Calculate VELOCITY (Deltas) - The core of our predictive engine
    hr_delta = current_vitals.get("hr", 80) - past_vitals.get("hr", 80)
    map_delta = current_vitals.get("map", 90) - past_vitals.get("map", 90)
    
    # 4. Calculate Base Risk
    risk = 5.0 # Base stable risk
    
    # Penalize dangerous absolute values
    current_map = current_vitals.get("map", 90)
    current_hr = current_vitals.get("hr", 80)

    if current_map < 65:
        risk += 40
    elif current_map < 75:
        risk += 15
        
    if current_hr > 120:
        risk += 25
    elif current_hr > 100:
        risk += 10
        
    # 5. The "Predictive" AI Component (Penalize Negative Velocity)
    # If MAP is dropping fast, spike the risk before they physically crash!
    if map_delta < -5:
        risk += 30
    if map_delta < -10:
        risk += 50  # Massive spike for rapid deterioration
        
    # 6. The "Recovery" AI Component (Reward Positive Velocity)
    # If a nurse is assigned and MAP is rising, lower the risk!
    if map_delta > 2:
        risk -= 20
        
    # Cap the risk score strictly between 1 and 99
    final_risk = min(max(int(risk), 1), 99)
    
    # Return both the score and the deltas for the frontend visualizer
    return final_risk, {"hr": hr_delta, "map": map_delta}