from models import StaffStatus, Nurse, Ward, Bed

class TriageAllocator:
    def __init__(self):
        self.pending_actions = []

    def find_best_nurse(self, target_bed: Bed, all_wards: Dict[str, Ward], all_nurses: Dict[str, Nurse]):
        target_ward_id = target_bed.ward_id
        
        # LEVEL 1: Local Ward Standby (Off-Process)
        local_standby = [n for n in all_nurses.values() 
                         if n.ward_id == target_ward_id and n.status == StaffStatus.OFF_PROCESS]
        if local_standby:
            return local_standby[0], "Local Standby Found"

        # LEVEL 2: Neighboring Ward Standby
        neighbor_standby = [n for n in all_nurses.values() 
                            if n.ward_id != target_ward_id and n.status == StaffStatus.OFF_PROCESS]
        if neighbor_standby:
            return neighbor_standby[0], "Neighbor Standby Imported"

        # LEVEL 3: Intra-Ward Risk Swap (Find nurse with lowest risk patient in SAME ward)
        # (This is where your 'In-Process' logic kicks in)
        # We will implement the 'Swap' math in the next iteration to keep it clean.
        
        return None, "No Resources Available"

    def propose_move(self, nurse: Nurse, bed: Bed, reason: str):
        action = {
            "id": f"move_{nurse.id}_{bed.id}",
            "nurse_name": nurse.name,
            "target_bed": bed.id,
            "target_ward": bed.ward_id,
            "reason": reason,
            "status": "Pending"
        }
        self.pending_actions.append(action)
        return action