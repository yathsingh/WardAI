from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio

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
simulation_mode = "Manual"  # Options: "Manual" or "Auto-Pilot"

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
        
        # SCENARIO SETUP: At Tick 5, occupy all nurses.
        if tick == 5:
            nurse_list = list(nurses.values())
            all_beds = wards["Ward_A"].beds + wards["Ward_B"].beds
            for i in range(len(nurse_list)):
                nurse = nurse_list[i]
                bed = all_beds[i]
                nurse.status = StaffStatus.IN_PROCESS
                nurse.assigned_bed_id = bed.id
                bed.assigned_nurse_id = nurse.id
            print("🚨 SCENARIO: All nurses now IN-PROCESS. Standby pool empty.")

        # 1. Update Vitals
        for ward in wards.values():
            for bed in ward.beds:
                # Add natural, alternating physiological noise
                if tick % 2 == 0:
                    bed.vitals["hr"] += 0.5
                    bed.vitals["map"] -= 0.2
                else:
                    bed.vitals["hr"] -= 0.5
                    bed.vitals["map"] += 0.2
                
                # CRASH TRIGGER: Bed B4 Bleed Scenario
                if bed.id == "B4" and tick >= 15:
                    if not bed.assigned_nurse_id:
                        # ACTIVE CRISIS: Patient is unmonitored, vitals plummet
                        bed.vitals["map"] -= 2.5
                        bed.vitals["hr"] += 4.0
                        bed.status = PatientStatus.WARNING
                    else:
                        # RECOVERY PHASE: Nurse assigned! Vitals begin to stabilize
                        if bed.vitals["map"] < 85.0:
                            bed.vitals["map"] += 1.5
                        if bed.vitals["hr"] > 80.0:
                            bed.vitals["hr"] -= 2.0
                        bed.status = PatientStatus.CRITICAL # Actively being treated

                # SAFETY BOUNDARIES: Prevent biologically impossible numbers
                bed.vitals["map"] = max(30.0, min(120.0, bed.vitals["map"]))
                bed.vitals["hr"] = max(40.0, min(200.0, bed.vitals["hr"]))

                # 2. RUN THE BRAIN
                score, deltas = predict_risk(bed.id, bed.vitals)
                bed.risk_score = score
                bed.deltas = deltas

                # 3. TRIGGER ALLOCATOR (Only trigger if high risk AND no nurse)
                if bed.risk_score > 75 and not bed.assigned_nurse_id:
                    best_nurse, reason = allocator.find_best_nurse(bed, wards, nurses)
                    
                    if best_nurse:
                        action = allocator.propose_move(best_nurse, bed, reason)
                        
                        # AUTO-PILOT: Execute immediately if enabled
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
        "mode": simulation_mode
    }

@app.post("/api/settings/mode")
async def toggle_mode(mode: str):
    global simulation_mode
    if mode in ["Manual", "Auto-Pilot"]:
        simulation_mode = mode
        return {"message": f"System switched to {mode}"}
    raise HTTPException(status_code=400, detail="Invalid mode")

@app.post("/api/allocate/approve/{action_id}")
async def approve_allocation(action_id: str):
    action = next((a for a in allocator.pending_actions if a["id"] == action_id), None)
    
    if not action:
        return {"error": "Action already processed"}

    nurse_id = None
    for nid, n in nurses.items():
        if n.name == action["nurse_name"]:
            nurse_id = nid
            break

    if nurse_id:
        target_bed_id = action["target_bed"]
        target_ward_id = action["target_ward"]
        
        # EXECUTE THE SWAP
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
                # Status is handled dynamically in the simulation loop now

        # Clear ALL pending actions for this target bed to clean up the UI
        allocator.pending_actions = [a for a in allocator.pending_actions if a["target_bed"] != target_bed_id]
        
        return {"message": f"Successfully dispatched {action['nurse_name']} to Bed {target_bed_id}"}

    raise HTTPException(status_code=400, detail="Dispatch failed")