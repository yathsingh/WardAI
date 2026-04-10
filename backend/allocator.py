from backend.models import StaffStatus, Nurse, Ward, Bed
from typing import Dict

class TriageAllocator:
    def __init__(self):
        self.pending_actions = []

    def find_best_nurse(self, target_bed: Bed, all_wards: Dict[str, Ward], all_nurses: Dict[str, Nurse]):
        target_ward_id = target_bed.ward_id
        
        # LEVEL 1: Local Ward Standby (Off-Process)
        local_standby = [n for n in all_nurses.values() 
                         if n.ward_id == target_ward_id and n.status == StaffStatus.OFF_PROCESS]
        if local_standby:
            return local_standby[0], "Level 1: Local Standby Available."

        # LEVEL 2: Neighboring Ward Standby (Off-Process)
        neighbor_standby = [n for n in all_nurses.values() 
                            if n.ward_id != target_ward_id and n.status == StaffStatus.OFF_PROCESS]
        if neighbor_standby:
            return neighbor_standby[0], "Level 2: Neighbor Standby Imported."

        # --- HELPER FUNCTION FOR RISK SWAPPING ---
        def get_safest_swap_candidate(active_nurses):
            candidates = []
            for nurse in active_nurses:
                # Find the exact bed this nurse is currently watching
                for w in all_wards.values():
                    for b in w.beds:
                        if b.id == nurse.assigned_bed_id:
                            candidates.append((nurse, b.risk_score, b.id))
            
            if candidates:
                # Sort by risk score (ascending - lowest risk first)
                candidates.sort(key=lambda x: x[1])
                return candidates[0] # Returns (nurse_obj, risk_score, bed_id)
            return None, None, None

        # LEVEL 3: Local Intra-Ward Risk Swap
        local_active = [n for n in all_nurses.values() 
                        if n.ward_id == target_ward_id and n.status == StaffStatus.IN_PROCESS]
        
        if local_active:
            best_local, local_risk, safe_bed = get_safest_swap_candidate(local_active)
            # Ethical Check: Only swap if crashing patient is at least 40% riskier
            if best_local and target_bed.risk_score > (local_risk + 40):
                return best_local, f"Level 3: Local Swap. Redirected from Stable Bed {safe_bed} (Risk: {local_risk}%)."

        # LEVEL 4: Global Inter-Ward Risk Swap (Desperation Mode)
        global_active = [n for n in all_nurses.values() 
                         if n.ward_id != target_ward_id and n.status == StaffStatus.IN_PROCESS]
        
        if global_active:
            best_global, global_risk, global_bed = get_safest_swap_candidate(global_active)
            # Ethical Check: Cross-ward pulls are dangerous, require a 50% gap!
            if best_global and target_bed.risk_score > (global_risk + 50):
                return best_global, f"Level 4 (CRITICAL): Cross-Ward Swap. Pulled from Bed {global_bed} (Risk: {global_risk}%)."

        return None, "SYSTEM OVERLOAD: No mathematically safe resources to reallocate."

    def propose_move(self, nurse: Nurse, bed: Bed, reason: str):
        # 🛑 ANTI-SPAM LOGIC: Strict check for duplicates
        for existing_action in self.pending_actions:
            if existing_action["target_bed"] == bed.id:
                return existing_action  

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