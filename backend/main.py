from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
from datetime import datetime

# Absolute imports for running from the root directory
from backend.models import Ward, Bed, Nurse, StaffStatus, PatientStatus
from backend.ml_engine import predict_risk
from backend.allocator import TriageAllocator

app = FastAPI()

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

wards = {
    "Ward_A": Ward(id="Ward_A", name="North Wing", beds=[
        Bed(id=f"A{i}", ward_id="Ward_A") for i in range(1, 5)
    ]),
    "Ward_B": Ward(id="Ward_B", name="South Wing", beds=[
        Bed(id=f"B{i}", ward_id="Ward_B") for i in range(1, 5)
    ])
}

for ward in wards.values():
    for bed in ward.beds:
        bed.vitals["map"] -= random.uniform(0, 15)
        bed.vitals["hr"] += random.uniform(0, 20)

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
    while True:
        await asyncio.sleep(1)
        
        for ward in wards.values():
            for bed in ward.beds:
                nurse_is_active = False
                if bed.assigned_nurse_id:
                    status_val = getattr(nurses[bed.assigned_nurse_id].status, "value", nurses[bed.assigned_nurse_id].status)
                    if status_val not in ["In-Transit", "IN_TRANSIT"]:
                        nurse_is_active = True

                is_crashing = False
                drop_map = 0.0
                rise_hr = 0.0

                if active_scenario == "Baseline":
                    if not nurse_is_active:
                        drop_map = random.uniform(0.2, 0.5)
                        rise_hr = random.uniform(0.4, 0.8)
                    else:
                        drop_map = random.uniform(-1.0, -0.4)
                        rise_hr = random.uniform(-1.5, -0.8)
                elif active_scenario == "Bleed_B4" and bed.id == "B4":
                    is_crashing = True
                    drop_map = 3.0 
                    rise_hr = 5.0
                elif active_scenario == "MCE" and bed.id in ["B4", "A1", "A3"]:
                    is_crashing = True
                    drop_map = 1.1 
                    rise_hr = 2.0

                if is_crashing:
                    if not nurse_is_active:
                        bed.vitals["map"] -= drop_map
                        bed.vitals["hr"] += rise_hr
                        bed.status = PatientStatus.WARNING
                    else:
                        if bed.vitals["map"] < 85.0: bed.vitals["map"] += 1.5
                        if bed.vitals["hr"] > 80.0: bed.vitals["hr"] -= 2.0
                        bed.status = PatientStatus.CRITICAL 
                else:
                    bed.vitals["map"] -= drop_map
                    bed.vitals["hr"] += rise_hr
                
                if not is_crashing and bed.risk_score < 40:
                    bed.status = PatientStatus.STABLE

                bed.vitals["map"] = max(30.0, min(120.0, bed.vitals["map"]))
                bed.vitals["hr"] = max(40.0, min(200.0, bed.vitals["hr"]))

                score, deltas = predict_risk(bed.id, bed.vitals)
                bed.risk_score = score
                bed.deltas = deltas

                if active_scenario == "Baseline":
                    if nurse_is_active and bed.risk_score < 20:
                        if random.random() < 0.4:
                            nid = bed.assigned_nurse_id
                            nurses[nid].assigned_bed_id = None
                            nurses[nid].status = StaffStatus.OFF_PROCESS
                            bed.assigned_nurse_id = None
                    elif 25 < bed.risk_score < 75 and not bed.assigned_nurse_id:
                        if random.random() < 0.25:
                            free_nurses = [nid for nid, n in nurses.items() if n.status == StaffStatus.OFF_PROCESS and n.ward_id == bed.ward_id]
                            if not free_nurses: 
                                free_nurses = [nid for nid, n in nurses.items() if n.status == StaffStatus.OFF_PROCESS]
                            if free_nurses:
                                nid = free_nurses[0]
                                nurses[nid].status = StaffStatus.IN_PROCESS
                                nurses[nid].assigned_bed_id = bed.id
                                bed.assigned_nurse_id = nid

                if bed.risk_score >= 75 and not bed.assigned_nurse_id:
                    pending_nurse_names = [a["nurse_name"] for a in allocator.pending_actions]
                    safe_nurses = {nid: n for nid, n in nurses.items() if n.name not in pending_nurse_names}
                    best_nurse, reason = allocator.find_best_nurse(bed, wards, safe_nurses)
                    if best_nurse:
                        action = allocator.propose_move(best_nurse, bed, reason)
                        # AUTO-PILOT LOGIC: Calls the same endpoint logic
                        if simulation_mode == "Auto-Pilot":
                            await approve_allocation(action["id"])

@app.on_event("startup")
async def startup():
    asyncio.create_task(run_hospital_simulation())

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
        if scenario_name == "MCE":
            target_ids = ["B4", "A1", "A3"]
            for ward in wards.values():
                for bed in ward.beds:
                    if bed.id in target_ids and bed.assigned_nurse_id:
                        nid = bed.assigned_nurse_id
                        nurses[nid].assigned_bed_id = None
                        nurses[nid].status = StaffStatus.OFF_PROCESS
                        bed.assigned_nurse_id = None
        
        audit_log.insert(0, {
            "time": timestamp,
            "action": f"SYSTEM STATE: {scenario_name.upper()} INITIATED",
            "reason": "Manual state change via dashboard.",
            "mode": simulation_mode.upper()
        })
        return {"message": f"Scenario changed to {scenario_name}"}
    raise HTTPException(status_code=400, detail="Invalid scenario")

@app.post("/api/allocate/approve/{action_id}")
async def approve_allocation(action_id: str):
    action = next((a for a in allocator.pending_actions if a["id"] == action_id), None)
    if not action: return {"error": "Action already processed"}

    nurse_id = next((nid for nid, n in nurses.items() if n.name == action["nurse_name"]), None)

    if nurse_id:
        target_bed_id = action["target_bed"]
        target_ward_id = action["target_ward"]
        old_bed_id = nurses[nurse_id].assigned_bed_id
        
        is_cross_ward = nurses[nurse_id].ward_id != target_ward_id
        transit_time = 8 if is_cross_ward else 2
        
        if old_bed_id:
            for w in wards.values():
                for b in w.beds:
                    if b.id == old_bed_id:
                        b.assigned_nurse_id = None

        nurses[nurse_id].status = "In-Transit"
        nurses[nurse_id].assigned_bed_id = target_bed_id
        for b in wards[target_ward_id].beds:
            if b.id == target_bed_id:
                b.assigned_nurse_id = nurse_id

        # LOG DISPATCH (Manual or Auto-Pilot)
        timestamp = datetime.now().strftime("%H:%M:%S")
        audit_log.insert(0, {
            "time": timestamp,
            "action": f"DISPATCHED: {action['nurse_name']} → {target_bed_id}",
            "reason": f"{action['reason']} (ETA: {transit_time}s)",
            "mode": simulation_mode.upper()
        })

        # LOG ARRIVAL
        async def nurse_arrival_timer(nid, bed_id, t_time):
            await asyncio.sleep(t_time)
            nurses[nid].status = StaffStatus.IN_PROCESS
            audit_log.insert(0, {
                "time": datetime.now().strftime("%H:%M:%S"),
                "action": f"ARRIVED: {nurses[nid].name} engaged at Bed {bed_id}",
                "reason": f"Transit complete ({t_time}s). Stabilization initiated.",
                "mode": simulation_mode.upper()
            })
            if len(audit_log) > 20: audit_log.pop()

        asyncio.create_task(nurse_arrival_timer(nurse_id, target_bed_id, transit_time))
        
        allocator.pending_actions = [a for a in allocator.pending_actions if a["target_bed"] != target_bed_id]
        if len(audit_log) > 20: audit_log.pop()
        return {"message": "Success"}
    
    raise HTTPException(status_code=400, detail="Dispatch failed")