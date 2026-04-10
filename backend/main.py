from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from datetime import datetime

# Absolute imports for running from the root directory
from backend.models import Ward, Bed, Nurse, StaffStatus, PatientStatus
from backend.ml_engine import predict_risk
from backend.allocator import TriageAllocator

app = FastAPI()

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# --- THE DATA STORE ---
allocator = TriageAllocator()
simulation_mode = "Manual"  
active_scenario = "Baseline" 
audit_log = [] 

# Initialize 2 Wards with 4 Rooms each
wards = {
    "Ward_A": Ward(id="Ward_A", name="North Wing", beds=[
        Bed(id=f"A{i}", ward_id="Ward_A") for i in range(1, 5)
    ]),
    "Ward_B": Ward(id="Ward_B", name="South Wing", beds=[
        Bed(id=f"B{i}", ward_id="Ward_B") for i in range(1, 5)
    ])
}

# Initialize 3 Nurses per Ward
nurses = {
    "N1": Nurse(id="N1", name="Sarah RN", ward_id="Ward_A"),
    "N2": Nurse(id="N2", name="James RN", ward_id="Ward_A"),
    "N3": Nurse(id="N3", name="Elena RN", ward_id="Ward_A"),
    "N4": Nurse(id="N4", name="Priya RN", ward_id="Ward_B"),
    "N5": Nurse(id="N5", name="Marcus RN", ward_id="Ward_B"),
    "N6": Nurse(id="N6", name="Kofi RN", ward_id="Ward_B"),
}

# --- THE BACKGROUND SIMULATION ---

async def run_hospital_simulation():
    tick = 0
    while True:
        await asyncio.sleep(1)
        tick += 1
        
        # SCENARIO SETUP: At Tick 5, occupy all nurses to simulate 100% capacity.
        if tick == 5:
            nurse_list = list(nurses.values())
            all_beds = wards["Ward_A"].beds + wards["Ward_B"].beds
            for i in range(len(nurse_list)):
                nurse = nurse_list[i]
                bed = all_beds[i]
                nurse.status = StaffStatus.IN_PROCESS
                nurse.assigned_bed_id = bed.id
                bed.assigned_nurse_id = nurse.id

        # 1. Update Vitals
        for ward in wards.values():
            for bed in ward.beds:
                # Baseline physiological noise
                if tick % 2 == 0:
                    bed.vitals["hr"] += 0.5
                    bed.vitals["map"] -= 0.2
                else:
                    bed.vitals["hr"] -= 0.5
                    bed.vitals["map"] += 0.2
                
                # --- DYNAMIC SCENARIO LOGIC ---
                is_crashing = False
                if active_scenario == "Bleed_B4" and bed.id == "B4":
                    is_crashing = True
                elif active_scenario == "MCE" and bed.id in ["B4", "A1", "A3"]:
                    is_crashing = True

                if is_crashing:
                    if not bed.assigned_nurse_id:
                        # ACTIVE CRISIS: High velocity drop for demo impact
                        bed.vitals["map"] -= 3.0 
                        bed.vitals["hr"] += 5.0
                        bed.status = PatientStatus.WARNING
                    else:
                        # RECOVERY PHASE: Vitals stabilize when nurse is present
                        if bed.vitals["map"] < 85.0:
                            bed.vitals["map"] += 1.5
                        if bed.vitals["hr"] > 80.0:
                            bed.vitals["hr"] -= 2.0
                        bed.status = PatientStatus.CRITICAL 
                
                # Reset status if stable and scenario is cleared
                if active_scenario == "Baseline" and bed.risk_score < 40:
                    bed.status = PatientStatus.STABLE

                # Physical boundaries
                bed.vitals["map"] = max(30.0, min(120.0, bed.vitals["map"]))
                bed.vitals["hr"] = max(40.0, min(200.0, bed.vitals["hr"]))

                # 2. RUN THE BRAIN
                score, deltas = predict_risk(bed.id, bed.vitals)
                bed.risk_score = score
                bed.deltas = deltas

                # 3. TRIGGER ALLOCATOR 
                if bed.risk_score > 75 and not bed.assigned_nurse_id:
                    best_nurse, reason = allocator.find_best_nurse(bed, wards, nurses)
                    if best_nurse:
                        action = allocator.propose_move(best_nurse, bed, reason)
                        if simulation_mode == "Auto-Pilot":
                            await approve_allocation(action["id"])

# Start simulation on boot
@app.on_event("startup")
async def startup():
    asyncio.create_task(run_hospital_simulation())

# --- THE ENDPOINTS ---

@app.get("/api/status")
async def get_status():
    return {
        "wards": wards, 
        "nurses": nurses, 
        "pending": allocator.pending_actions,
        "audit_log": audit_log,
        "mode": simulation_mode,
        "scenario": active_scenario
    }

@app.post("/api/settings/mode")
async def toggle_mode(mode: str):
    global simulation_mode
    if mode in ["Manual", "Auto-Pilot"]:
        simulation_mode = mode
        return {"message": f"System switched to {mode}"}
    raise HTTPException(status_code=400, detail="Invalid mode")

@app.post("/api/scenarios/trigger/{scenario_name}")
async def trigger_scenario(scenario_name: str):
    global active_scenario
    if scenario_name in ["Baseline", "Bleed_B4", "MCE"]:
        active_scenario = scenario_name
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 🚨 NEW: CRITICAL MCE LOGIC
        # If MCE starts, we must unassign nurses from the target beds 
        # so the AI actually has a "problem" to solve.
        if scenario_name == "MCE":
            target_ids = ["B4", "A1", "A3"]
            for ward in wards.values():
                for bed in ward.beds:
                    if bed.id in target_ids and bed.assigned_nurse_id:
                        # Find the nurse and kick them to "Off-Process" (Standby)
                        nid = bed.assigned_nurse_id
                        nurses[nid].assigned_bed_id = None
                        nurses[nid].status = StaffStatus.OFF_PROCESS
                        # Empty the bed
                        bed.assigned_nurse_id = None
        
        # Professionalized Reasonings
        reasons = {
            "Baseline": "Standard ward monitoring protocols active.",
            "Bleed_B4": "ADMIN_OVERRIDE: Internal trauma data stream engaged.",
            "MCE": "EXTERNAL_EVENT: Multiple casualty telemetry detected."
        }

        audit_log.insert(0, {
            "time": timestamp,
            "action": f"SYSTEM STATE: {scenario_name.upper()} INITIATED",
            "reason": reasons.get(scenario_name, "Manual state change."),
            "mode": simulation_mode
        })
        return {"message": f"Scenario changed to {scenario_name}"}
    raise HTTPException(status_code=400, detail="Invalid scenario")

@app.post("/api/allocate/approve/{action_id}")
async def approve_allocation(action_id: str):
    action = next((a for a in allocator.pending_actions if a["id"] == action_id), None)
    if not action: return {"error": "Action already processed"}

    nurse_id = None
    for nid, n in nurses.items():
        if n.name == action["nurse_name"]:
            nurse_id = nid
            break

    if nurse_id:
        target_bed_id = action["target_bed"]
        target_ward_id = action["target_ward"]
        old_bed_id = nurses[nurse_id].assigned_bed_id
        
        if old_bed_id:
            for w in wards.values():
                for b in w.beds:
                    if b.id == old_bed_id:
                        b.assigned_nurse_id = None
                        b.status = PatientStatus.WARNING

        nurses[nurse_id].status = StaffStatus.DISPATCHED
        nurses[nurse_id].assigned_bed_id = target_bed_id
        for b in wards[target_ward_id].beds:
            if b.id == target_bed_id:
                b.assigned_nurse_id = nurse_id

        timestamp = datetime.now().strftime("%H:%M:%S")
        audit_log.insert(0, {
            "time": timestamp,
            "action": f"Dispatched {action['nurse_name']} to Bed {target_bed_id}",
            "reason": action['reason'],
            "mode": simulation_mode
        })
        if len(audit_log) > 20: audit_log.pop()
        allocator.pending_actions = [a for a in allocator.pending_actions if a["target_bed"] != target_bed_id]
        return {"message": "Success"}
    raise HTTPException(status_code=400, detail="Dispatch failed")