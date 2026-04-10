from pydantic import BaseModel
from typing import List, Optional, Dict
from enum import Enum

# 1. Define the States
class StaffStatus(str, Enum):
    OFF_PROCESS = "Off-Process"  # Standby
    IN_PROCESS = "In-Process"    # Active with a patient
    DISPATCHED = "Dispatched"    # En route to a crisis
    IN_TRANSIT = "In-Transit"

class PatientStatus(str, Enum):
    STABLE = "Stable"
    WARNING = "Warning"
    CRITICAL = "Critical"

# 2. The Nurse Object
class Nurse(BaseModel):
    id: str
    name: str
    status: StaffStatus = StaffStatus.OFF_PROCESS
    assigned_bed_id: Optional[str] = None
    ward_id: str

# 3. The Bed/Patient Object
class Bed(BaseModel):
    id: str
    ward_id: str
    status: PatientStatus = PatientStatus.STABLE
    vitals: Dict[str, float] = {
        "hr": 75.0, "map": 85.0, "rr": 16.0, "spo2": 98.0
    }
    deltas: Dict[str, float] = {"hr": 0.0, "map": 0.0, "rr": 0.0}
    risk_score: int = 0
    assigned_nurse_id: Optional[str] = None

# 4. The Ward Object
class Ward(BaseModel):
    id: str
    name: str
    beds: List[Bed]