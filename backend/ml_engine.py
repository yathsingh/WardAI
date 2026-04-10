def predict_risk(vitals: dict) -> int:
    """
    MOCK ML MODEL: 
    Checks if MAP drops to trigger the allocator.
    """
    print(f"[ML Engine] Analyzing vitals for {vitals['bed_id']}...")
    
    if vitals['map'] < 65:
        print("[ML Engine] 🚨 CRITICAL PATTERN DETECTED! Risk Score: 90")
        return 90
    else:
        print("[ML Engine] ✅ Vitals normal. Risk Score: 15")
        return 15