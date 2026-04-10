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

            # LEVEL 2: Neighboring Ward Standby (Off-Process)
            neighbor_standby = [n for n in all_nurses.values() 
                                if n.ward_id != target_ward_id and n.status == StaffStatus.OFF_PROCESS]
            if neighbor_standby:
                return neighbor_standby[0], "Neighbor Standby Imported"

            # LEVEL 3: Intra-Ward Risk Swap (Dynamic Triage)
            # Find nurses in the same ward who are 'In-Process'
            local_active_nurses = [n for n in all_nurses.values() 
                                if n.ward_id == target_ward_id and n.status == StaffStatus.IN_PROCESS]
            
            if local_active_nurses:
                # We need to find which of these nurses is watching the 'safest' patient
                # We create a list of (Nurse, Patient_Risk) tuples
                candidates = []
                for nurse in local_active_nurses:
                    # Find the bed this nurse is currently assigned to
                    current_bed = next((b for b in all_wards[target_ward_id].beds if b.id == nurse.assigned_bed_id), None)
                    if current_bed:
                        candidates.append((nurse, current_bed.risk_score))
                
                # Sort by risk score (ascending - lowest risk first)
                candidates.sort(key=lambda x: x[1])
                
                # THE ETHICAL CHECK: Only swap if the target bed is significantly riskier 
                # than the nurse's current patient (e.g., a 40% gap)
                best_candidate, lowest_risk = candidates[0]
                if target_bed.risk_score > (lowest_risk + 40):
                    return best_candidate, f"Triage Swap: {best_candidate.name} moved from Low-Risk Bed {best_candidate.assigned_bed_id}"

            return None, "CRISIS: No safe resources to swap."

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