const API_BASE = "http://127.0.0.1:8000/api";
let currentMode = "Manual";
let isAlarming = false;
let audioCtx = null;

function playCodeBlueBeep() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') audioCtx.resume();
    try {
        const osc = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(850, audioCtx.currentTime);
        gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.5);
        osc.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.5);
    } catch(e) {}
}

async function updateDashboard() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();
        currentMode = data.mode;
        updateModeUI();
        renderWards(data.wards, data.nurses);
        renderTriageTable(data.wards);
        renderPendingQueue(data.pending);
        renderAuditLog(data.audit_log);
        checkCodeBlue(data.wards);
    } catch (err) { console.error("Backend offline", err); }
}

function checkCodeBlue(wards) {
    const allBeds = [...wards.Ward_A.beds, ...wards.Ward_B.beds];
    const hasCritical = allBeds.some(bed => bed.risk_score >= 90);
    const overlay = document.getElementById('alarm-overlay');
    if (hasCritical) {
        if (!isAlarming) overlay.classList.add('code-blue-active');
        isAlarming = true;
        playCodeBlueBeep();
    } else {
        overlay.classList.remove('code-blue-active');
        isAlarming = false;
    }
}

function renderWards(wards, nurses) {
    ['Ward_A', 'Ward_B'].forEach(wardId => {
        const container = document.getElementById(wardId === 'Ward_A' ? 'ward-a-grid' : 'ward-b-grid');
        container.innerHTML = wards[wardId].beds.map(bed => {
            const isCritical = bed.risk_score > 75;
            const isUnmonitored = !bed.assigned_nurse_id && (bed.risk_score > 40);
            return `
                <div class="room-card p-4 rounded-xl border-2 bg-slate-50 ${isCritical ? 'pulse-red border-red-500 bg-red-50 shadow-md' : isUnmonitored ? 'border-amber-400 border-dashed bg-amber-50' : 'border-slate-100 bg-white'}">
                    <div class="flex justify-between items-start mb-1">
                        <span class="font-bold text-slate-700">${bed.id}</span>
                        <span class="text-xs font-bold ${isCritical ? 'text-red-600' : 'text-slate-400'}">${bed.risk_score}% RISK</span>
                    </div>
                    <div class="flex justify-between items-center text-[10px] text-slate-400 mono-text mb-2 border-b border-slate-100 pb-1">
                        <span>MAP: ${bed.vitals.map.toFixed(1)}</span>
                        <span>HR: ${bed.vitals.hr.toFixed(1)}</span>
                    </div>
                    <div class="text-[10px] text-slate-500 uppercase tracking-wider">Assigned Staff</div>
                    <div class="font-semibold text-sm text-slate-800">${bed.assigned_nurse_id ? nurses[bed.assigned_nurse_id].name : '<span class="text-amber-600 animate-pulse">UNASSIGNED</span>'}</div>
                </div>`;
        }).join('');
    });
}

function renderTriageTable(wards) {
    const tableBody = document.getElementById('triage-body');
    const allBeds = [...wards.Ward_A.beds, ...wards.Ward_B.beds].sort((a,b) => b.risk_score - a.risk_score);
    tableBody.innerHTML = allBeds.map(bed => `
        <tr class="border-b border-slate-50 hover:bg-slate-50 transition-colors">
            <td class="py-3 px-2 font-bold">${bed.id}</td>
            <td class="py-3 px-2"><div class="w-24 bg-slate-200 rounded-full h-2 overflow-hidden"><div class="${bed.risk_score > 75 ? 'bg-red-500' : 'bg-blue-600'} h-2 transition-all duration-500" style="width: ${bed.risk_score}%"></div></div></td>
            <td class="py-3 px-2 ${bed.deltas.map < -2 ? 'text-red-500 font-bold' : 'text-slate-500'} mono-text text-xs">${bed.deltas.map.toFixed(2)} Δ MAP</td>
            <td class="py-3 px-2 text-slate-600 text-xs font-semibold">${bed.assigned_nurse_id || '---'}</td>
        </tr>`).join('');
}

function renderPendingQueue(pending) {
    const queue = document.getElementById('pending-actions');
    document.getElementById('queue-count').innerText = pending.length;
    if (pending.length === 0) { queue.innerHTML = '<p class="text-slate-400 text-center py-10 italic text-sm">Waiting for signals...</p>'; return; }
    queue.innerHTML = pending.map(action => `
        <div class="bg-white border-l-4 ${action.reason.includes('CRITICAL') ? 'border-red-500' : 'border-blue-500'} shadow-sm p-3 rounded-r-lg border border-slate-200 animate-[slideInRight_0.3s_ease-out]">
            <div class="text-[10px] font-bold uppercase mb-1 ${action.reason.includes('CRITICAL') ? 'text-red-600' : 'text-blue-600'}">Proposed Dispatch</div>
            <div class="text-sm font-bold text-slate-800">${action.nurse_name} → ${action.target_bed}</div>
            <div class="text-[11px] text-slate-500 mb-3 leading-tight">${action.reason}</div>
            <button onclick="approveAction('${action.id}')" class="w-full ${action.reason.includes('CRITICAL') ? 'bg-red-600' : 'bg-blue-600'} text-white py-1.5 rounded text-xs font-bold transition-colors">APPROVE SWAP</button>
        </div>`).join('');
}

function renderAuditLog(log) {
    const logBody = document.getElementById('audit-body');
    if (!log || log.length === 0) { logBody.innerHTML = '<tr><td class="p-4 text-center text-slate-500 italic">Secure Ledger Initialized...</td></tr>'; return; }
    logBody.innerHTML = log.map((entry, i) => `
        <tr class="border-b border-slate-700 ${i === 0 ? 'bg-slate-800' : ''}">
            <td class="py-2 px-4 text-blue-400 w-24 font-bold">[${entry.time}]</td>
            <td class="py-2 px-4 text-emerald-400 w-48 font-bold">${entry.mode.toUpperCase()} ACTIVE</td>
            <td class="py-2 px-4 text-slate-100 font-bold">${entry.action}</td>
            <td class="py-2 px-4 text-slate-400 text-[10px] truncate w-1/3 italic">System Integrity: ${entry.reason}</td>
        </tr>`).join('');
}

async function approveAction(id) { if (audioCtx) audioCtx.resume(); await fetch(`${API_BASE}/allocate/approve/${id}`, {method:'POST'}); updateDashboard(); }

async function toggleSystemMode() {
    if (audioCtx) audioCtx.resume();
    currentMode = currentMode === "Manual" ? "Auto-Pilot" : "Manual";
    updateModeUI();
    await fetch(`${API_BASE}/settings/mode?mode=${currentMode}`, {method:'POST'});
}

async function setScenario(name) {
    if (audioCtx) audioCtx.resume();
    await fetch(`${API_BASE}/scenarios/trigger/${name}`, {method:'POST'});
    updateDashboard();
}

function updateModeUI() {
    const toggle = document.getElementById('mode-toggle');
    const circle = document.getElementById('toggle-circle');
    const label = document.getElementById('mode-label');
    if (currentMode === "Auto-Pilot") {
        label.innerText = "Auto-Pilot Active"; label.classList.add('text-blue-600');
        toggle.classList.replace('bg-slate-200', 'bg-blue-600'); circle.classList.add('translate-x-7');
    } else {
        label.innerText = "Manual Mode"; label.classList.remove('text-blue-600');
        toggle.classList.replace('bg-blue-600', 'bg-slate-200'); circle.classList.remove('translate-x-7');
    }
}

document.head.insertAdjacentHTML("beforeend", `<style>@keyframes slideInRight { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }</style>`);
setInterval(updateDashboard, 1000);