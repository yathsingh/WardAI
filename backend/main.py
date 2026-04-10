from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from ml_engine import predict_risk
from allocator import handle_critical_alert

app = FastAPI(title="PACU Command Center API")

class PatientVitals(BaseModel):
    bed_id: str
    heart_rate: float
    map: float
    resp_rate: float
    spo2: float
    opioid_flow: float

def pipeline_worker(vitals_data: dict):
    risk_score = predict_risk(vitals_data)
    if risk_score > 70:
        handle_critical_alert(vitals_data["bed_id"], risk_score)

@app.post("/api/vitals")
async def receive_vitals(vitals: PatientVitals, background_tasks: BackgroundTasks):
    print(f"\n[API] Received data payload from {vitals.bed_id}")
    background_tasks.add_task(pipeline_worker, vitals.model_dump())
    return {"status": "success"}