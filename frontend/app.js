const API_BASE = "http://127.0.0.1:8000/api";
let currentMode = "Manual";

// 1. POLLING LOOP: Fetch data every second
async function updateDashboard() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();
        
        // Only update the mode from the server if we haven't just toggled it locally
        if (data.mode) {
            currentMode = data.mode;
            updateModeUI();
        }
        
        renderWards(data.wards, data.nurses);
        renderTriageTable(data.wards);
        renderPendingQueue(data.pending);
    } catch (err) {
        console.error("Connection lost to WardAI Backend", err);
    }
}

// 2. RENDER WARDS (Top Half)
function renderWards(wards, nurses) {
    ['Ward_A', 'Ward_B'].forEach(wardId => {
        const container = document.getElementById(wardId === 'Ward_A' ? 'ward-a-grid' : 'ward-b-grid');
        container.innerHTML = ''; // Clear previous state

        wards[wardId].beds.forEach(bed => {
            const isCritical = bed.risk_score > 75;
            const isUnmonitoredCrisis = !bed.assigned_nurse_id && bed.status === "Warning";
            
            // Dynamic styling based on the new backend statuses
            const card = document.createElement('div');
            card.className = `room-card p-4 rounded-xl border-2 bg-slate-50 transition-all ${
                isCritical ? 'pulse-red border-red-500 bg-red-50 shadow-md' : 
                isUnmonitoredCrisis ? 'border-amber-400 border-dashed bg-amber-50' : 'border-slate-100 bg-white'
            }`;

            card.innerHTML = `
                <div class="flex justify-between items-start mb-1">
                    <span class="font-bold text-slate-700">${bed.id}</span>
                    <span class="text-xs font-bold ${isCritical ? 'text-red-600' : 'text-slate-400'}">${bed.risk_score}% RISK</span>
                </div>
                <div class="flex justify-between items-center text-[10px] text-slate-400 font-mono mb-2 border-b border-slate-100 pb-1">
                    <span>MAP: ${bed.vitals.map.toFixed(1)}</span>
                    <span>HR: ${bed.vitals.hr.toFixed(1)}</span>
                </div>
                <div class="text-[10px] text-slate-500 uppercase tracking-wider">Assigned Staff</div>
                <div class="font-semibold text-sm text-slate-800">
                    ${bed.assigned_nurse_id ? nurses[bed.assigned_nurse_id].name : '<span class="text-amber-600 animate-pulse">UNASSIGNED</span>'}
                </div>
            `;
            container.appendChild(card);
        });
    });
}

// 3. RENDER TRIAGE TABLE (Bottom Left)
function renderTriageTable(wards) {
    const tableBody = document.getElementById('triage-body');
    const allBeds = [...wards.Ward_A.beds, ...wards.Ward_B.beds];
    
    // THE TRIAGE SORT: Highest risk first
    allBeds.sort((a, b) => b.risk_score - a.risk_score);

    tableBody.innerHTML = allBeds.map(bed => `
        <tr class="border-b border-slate-50 hover:bg-slate-50 transition-colors">
            <td class="py-3 px-2 font-bold">${bed.id}</td>
            <td class="py-3 px-2">
                <div class="w-full bg-slate-200 rounded-full h-2 w-24 overflow-hidden">
                    <div class="${bed.risk_score > 75 ? 'bg-red-500' : 'bg-blue-600'} h-2 rounded-full transition-all duration-500" style="width: ${bed.risk_score}%"></div>
                </div>
            </td>
            <td class="py-3 px-2 ${bed.deltas.map < -2 ? 'text-red-500 font-bold' : bed.deltas.map > 2 ? 'text-green-500' : 'text-slate-500'} font-mono text-xs">
                ${bed.deltas.map > 0 ? '+' : ''}${bed.deltas.map.toFixed(2)} Δ MAP
            </td>
            <td class="py-3 px-2 text-slate-600 text-xs font-semibold">${bed.assigned_nurse_id || '---'}</td>
        </tr>
    `).join('');
}

// 4. RENDER PENDING QUEUE (Bottom Right)
function renderPendingQueue(pending) {
    const queue = document.getElementById('pending-actions');
    document.getElementById('queue-count').innerText = pending.length;

    if (pending.length === 0) {
        queue.innerHTML = '<p class="text-slate-400 text-center py-10 italic text-sm">Waiting for AI triage signals...</p>';
        return;
    }

    queue.innerHTML = pending.map(action => {
        // Color-code the alerts based on severity
        const isCriticalSwap = action.reason.includes("CRITICAL");
        const borderColor = isCriticalSwap ? 'border-red-500' : 'border-blue-500';
        const textColor = isCriticalSwap ? 'text-red-600' : 'text-blue-600';
        const buttonColor = isCriticalSwap ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700';

        return `
        <div class="bg-white border-l-4 ${borderColor} shadow-sm p-3 rounded-r-lg border border-slate-200 animate-[slideInRight_0.3s_ease-out]">
            <div class="text-[10px] font-bold ${textColor} uppercase mb-1">Proposed Dispatch</div>
            <div class="text-sm font-bold text-slate-800">${action.nurse_name} → Bed ${action.target_bed}</div>
            <div class="text-[11px] text-slate-500 mb-3 mt-1 leading-tight">${action.reason}</div>
            <button onclick="approveAction('${action.id}')" 
                class="w-full ${buttonColor} text-white py-1.5 rounded text-xs font-bold transition-colors">
                APPROVE SWAP
            </button>
        </div>
        `;
    }).join('');
}

// 5. USER INTERACTIONS
async function approveAction(actionId) {
    try {
        await fetch(`${API_BASE}/allocate/approve/${actionId}`, { method: 'POST' });
        updateDashboard(); // Immediate refresh
    } catch (err) {
        console.error("Failed to approve action", err);
    }
}

async function toggleSystemMode() {
    // 1. Immediately toggle the local state so the UI feels instant
    currentMode = currentMode === "Manual" ? "Auto-Pilot" : "Manual";
    updateModeUI(); 

    // 2. Tell the backend
    try {
        await fetch(`${API_BASE}/settings/mode?mode=${currentMode}`, { method: 'POST' });
    } catch (err) {
        console.error("Failed to change mode", err);
        // Revert UI if server fails
        currentMode = currentMode === "Manual" ? "Auto-Pilot" : "Manual";
        updateModeUI();
    }
}

function updateModeUI() {
    const label = document.getElementById('mode-label');
    const circle = document.getElementById('toggle-circle');
    const toggle = document.getElementById('mode-toggle');

    // Bulletproof explicit class management
    if (currentMode === "Auto-Pilot") {
        label.innerText = "Auto-Pilot Active";
        label.classList.add('text-blue-600');
        
        toggle.classList.remove('bg-slate-200');
        toggle.classList.add('bg-blue-600');
        
        circle.classList.add('translate-x-7');
    } else {
        label.innerText = "Manual Mode";
        label.classList.remove('text-blue-600');
        
        toggle.classList.remove('bg-blue-600');
        toggle.classList.add('bg-slate-200');
        
        circle.classList.remove('translate-x-7');
    }
}

// Utility animation for the new action cards
document.head.insertAdjacentHTML("beforeend", `<style>
@keyframes slideInRight {
    from { transform: translateX(20px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}
</style>`);

// Start polling
setInterval(updateDashboard, 1000);