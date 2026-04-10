# Mock Database State
hospital_state = {
    "off_process_nurses": 2,
    "active_alerts": []
}

def handle_critical_alert(bed_id: str, risk_score: int):
    """The Preemption Logic."""
    print(f"\n[Allocator] ⚡ EMERGENCY PROTOCOL TRIGGERED for {bed_id}")
    
    if hospital_state["off_process_nurses"] > 0:
        hospital_state["off_process_nurses"] -= 1
        print(f"[Allocator] 🟢 SUCCESS: Deployed OFF-Process nurse to {bed_id}.")
        print(f"[Allocator] Nurses remaining in float pool: {hospital_state['off_process_nurses']}\n")
    else:
        print(f"[Allocator] 🔴 WARNING: Float pool empty. Initiating IN-Process Preemption...")