from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
import asyncio
from models import Ward, Bed, Nurse, StaffStatus, PatientStatus
from ml_engine import predict_risk
from allocator import TriageAllocator

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- THE DATA STORE (The "Single Source of Truth") ---
allocator = TriageAllocator()

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
        
        # 1. Update Vitals (Simulating real-time noise & the Bed B2 crash at tick 15)
        for ward in wards.values():
            for bed in ward.beds:
                # Add slight noise to everyone
                bed.vitals["hr"] += (0.5 - (0.5 * (tick % 2))) 
                
                # CRASH TRIGGER: Bed B2 starts bleeding at tick 15
                if bed.id == "B2" and tick >= 15:
                    bed.vitals["map"] -= 2.1
                    bed.vitals["hr"] += 3.5

                # 2. RUN THE BRAIN (Get Risk & Deltas)
                # predict_risk will now return (score, deltas)
                score, deltas = predict_risk(bed.id, bed.vitals)
                bed.risk_score = score
                bed.deltas = deltas

                # 3. TRIGGER ALLOCATOR (If Risk > 75% and no one is assigned)
                if bed.risk_score > 75 and not bed.assigned_nurse_id:
                    best_nurse, reason = allocator.find_best_nurse(bed, wards, nurses)
                    
                    if best_nurse:
                        # In 'Manual Mode', we just propose it to the queue
                        allocator.propose_move(best_nurse, bed, reason)

# Start simulation on boot
@app.on_event("startup")
async def startup():
    asyncio.create_task(run_hospital_simulation())

# --- THE ENDPOINTS ---

@app.get("/api/status")
async def get_status():
    return {"wards": wards, "nurses": nurses, "pending": allocator.pending_actions}

@app.post("/api/allocate/approve/{action_id}")
async def approve_allocation(action_id: str):
    # 1. Find the proposed action in the queue
    action = next((a for a in allocator.pending_actions if a["id"] == action_id), None)
    
    if not action:
        raise HTTPException(status_code=404, detail="Proposed action not found or already processed.")

    nurse_id = None
    # Find the nurse ID from the name (in a real app, use IDs in the action object)
    for nid, n in nurses.items():
        if n.name == action["nurse_name"]:
            nurse_id = nid
            break

    if nurse_id:
        target_bed_id = action["target_bed"]
        target_ward_id = action["target_ward"]
        
        # 2. EXECUTE THE SWAP
        # If the nurse was already with a patient, unassign that patient first
        old_bed_id = nurses[nurse_id].assigned_bed_id
        if old_bed_id:
            for b in wards[nurses[nurse_id].ward_id].beds:
                if b.id == old_bed_id:
                    b.assigned_nurse_id = None
                    b.status = PatientStatus.WARNING # Mark as unmonitored!

        # 3. ASSIGN TO NEW CRISIS
        nurses[nurse_id].status = StaffStatus.DISPATCHED
        nurses[nurse_id].assigned_bed_id = target_bed_id
        
        for b in wards[target_ward_id].beds:
            if b.id == target_bed_id:
                b.assigned_nurse_id = nurse_id
                b.status = PatientStatus.CRITICAL

        # 4. REMOVE FROM QUEUE
        allocator.pending_actions = [a for a in allocator.pending_actions if a["id"] != action_id]
        
        return {"message": f"Successfully dispatched {action['nurse_name']} to Bed {target_bed_id}"}

    return {"error": "Could not execute dispatch."}