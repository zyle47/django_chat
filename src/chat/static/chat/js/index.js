const roomNameInput     = document.getElementById('room-name-input');
const roomPassInput     = document.getElementById('room-password-input');
const roomList          = document.getElementById('room-list');
const roomSearch        = document.getElementById('room-search');
const roomCountEl       = document.getElementById('room-count');
const fingerprintEl     = document.getElementById('room-fingerprint');
const selectedFpEl      = document.getElementById('selected-fingerprint');
const passwordFieldWrap = document.getElementById('password-field-wrap');
const submitWrap        = document.getElementById('submit-wrap');
const selectHint        = document.getElementById('room-select-hint');
const entryPanel        = document.getElementById('room-entry-panel');
const adminRoomNameEl   = document.getElementById('admin-room-name');

let selectedRoomHash = null;
let requiredPwLength = 0;
const pwLengths = JSON.parse(document.getElementById('pw-lengths-data').textContent);

async function sha256hex(str) {
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function hueFromName(name) {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffff;
    return h % 360;
}
function colorForName(name) {
    const h = hueFromName(name);
    return `hsl(${h}, 100%, 60%)`;
}

function colorizeOrbs() {
    document.querySelectorAll('.room-orb[data-name]').forEach(orb => {
        const c = colorForName(orb.dataset.name);
        orb.style.background = c;
        orb.style.color = '#000';
    });
}

function updateCount() {
    const all     = [...roomList.querySelectorAll('.room-card')];
    const visible = all.filter(c => c.style.display !== 'none');
    const t = all.length, v = visible.length;
    roomCountEl.textContent = (t === v) ? `${t} room${t !== 1 ? 's' : ''}` : `${v} / ${t}`;
}

async function obfuscateCards() {
    for (const card of document.querySelectorAll('.room-card')) {
        const name = card.dataset.roomName;
        if (!name) continue;
        const hash = await sha256hex(name);
        const nameEl = card.querySelector('.room-card-name');
        if (nameEl) nameEl.textContent = hash.slice(0, 16);
        const orb = card.querySelector('.room-orb');
        if (orb) orb.textContent = hash[0].toUpperCase();
    }
}

function filterRooms() {
    const q = roomSearch.value.toLowerCase().trim();
    let visible = 0;
    roomList.querySelectorAll('.room-card').forEach(card => {
        const displayText = (card.querySelector('.room-card-name')?.textContent || '').toLowerCase();
        const match = !q || displayText.includes(q);
        card.style.display = match ? '' : 'none';
        if (match) visible++;
    });
    updateCount();
    let noMatch = roomList.querySelector('.no-match-msg');
    if (visible === 0 && roomList.querySelectorAll('.room-card').length > 0) {
        if (!noMatch) {
            noMatch = document.createElement('div');
            noMatch.className = 'empty-state no-match-msg';
            noMatch.innerHTML = '<div class="big">&#128269;</div><p>No rooms match your search.</p>';
            roomList.appendChild(noMatch);
        }
    } else {
        noMatch && noMatch.remove();
    }
}

async function addRoomToList(roomName) {
    if (!roomName || roomList.querySelector(`[data-room-name="${CSS.escape(roomName)}"]`)) return;
    const emptyEl = roomList.querySelector('#empty-state');
    if (emptyEl) emptyEl.remove();
    const c = colorForName(roomName);
    const hash = await sha256hex(roomName);
    const btn = document.createElement('button');
    btn.className = 'room-card room-pill-btn';
    btn.dataset.roomName = roomName;
    btn.type = 'button';
    btn.innerHTML = `<div class="room-orb" style="background:${c};color:#000">${hash[0].toUpperCase()}</div><div class="room-card-name">${hash.slice(0, 16)}</div>`;
    roomList.appendChild(btn);
    updateCount();
    filterRooms();
}

function showRoomFields() {
    passwordFieldWrap.style.display = '';
    submitWrap.style.display = 'none';
    passwordFieldWrap.classList.remove('field-revealed');
    void passwordFieldWrap.offsetWidth;
    passwordFieldWrap.classList.add('field-revealed');
    roomPassInput.focus();
}

function hideRoomFields() {
    passwordFieldWrap.style.display = 'none';
    submitWrap.style.display = 'none';
    if (roomPassInput) roomPassInput.value = '';
}

if (roomPassInput) {
    roomPassInput.addEventListener('input', () => {
        const matches = requiredPwLength > 0
            ? roomPassInput.value.length === requiredPwLength
            : roomPassInput.value.length > 0;
        submitWrap.style.display = matches ? '' : 'none';
    });
}

function showEntryPanel() {
    selectHint.style.display = 'none';
    entryPanel.style.display = '';
    entryPanel.classList.remove('field-revealed');
    void entryPanel.offsetWidth;
    entryPanel.classList.add('field-revealed');
}

const createRoomBtn = document.getElementById('create-room-btn');
if (createRoomBtn) {
    createRoomBtn.addEventListener('click', () => {
        selectedRoomHash = null;
        requiredPwLength = 0;
        selectedFpEl.textContent = '// new room';
        if (fingerprintEl) { fingerprintEl.textContent = ''; fingerprintEl.classList.remove('has-value'); }
        passwordFieldWrap.style.display = '';
        submitWrap.style.display = 'none';
        roomNameInput.value = '';
        showEntryPanel();
        roomNameInput.focus();
    });
}

roomList.addEventListener('click', async e => {
    const btn = e.target.closest('.room-pill-btn');
    if (!btn) return;
    const name = btn.dataset.roomName;
    selectedRoomHash = await sha256hex(name);
    requiredPwLength = pwLengths[selectedRoomHash] || 0;
    showEntryPanel();
    if (IS_SUPERUSER) {
        adminRoomNameEl.textContent = name;
        roomNameInput.value = name;
    } else {
        selectedFpEl.textContent = '// ' + selectedRoomHash;
        roomNameInput.value = '';
        if (fingerprintEl) { fingerprintEl.textContent = ''; fingerprintEl.classList.remove('has-value'); }
        hideRoomFields();
        roomNameInput.focus();
    }
});

if (!IS_SUPERUSER) {
    roomNameInput.addEventListener('input', async () => {
        const val = roomNameInput.value.trim();
        if (!val) {
            fingerprintEl.textContent = '';
            fingerprintEl.classList.remove('has-value');
            if (selectedRoomHash) hideRoomFields();
            return;
        }
        const hash = await sha256hex(val);
        fingerprintEl.textContent = '// ' + hash;
        fingerprintEl.classList.add('has-value');
        if (!selectedRoomHash) return; // create mode — password field already visible
        if (hash === selectedRoomHash) showRoomFields(); else hideRoomFields();
    });
}

document.querySelectorAll('.flash-notification').forEach(el => {
    setTimeout(() => {
        el.style.transition = 'opacity 0.8s ease';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 800);
    }, 6000);
});

roomSearch.addEventListener('input', filterRooms);
colorizeOrbs();
obfuscateCards();
updateCount();

const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
const lobbySocket = new WebSocket(`${protocol}://${location.host}/ws/lobby/`);
lobbySocket.onmessage = e => {
    try {
        const p = JSON.parse(e.data);
        if (p.type === 'room_created') addRoomToList(p.room_name);
    } catch {}
};

// ── Network Pulse ─────────────────────────────────────────
const pulse = JSON.parse(document.getElementById('pulse-data').textContent);

function countUp(el, target, duration) {
    if (!el || target === 0) { if (el) el.textContent = '0'; return; }
    const start = performance.now();
    (function tick(now) {
        const t = Math.min((now - start) / duration, 1);
        const ease = 1 - Math.pow(1 - t, 3);
        el.textContent = Math.round(ease * target).toLocaleString();
        if (t < 1) requestAnimationFrame(tick);
    })(start);
}

countUp(document.getElementById('stat-msgs-24h'),   pulse.messages_24h,   700);
countUp(document.getElementById('stat-msgs-total'), pulse.messages_total, 900);
countUp(document.getElementById('stat-images'),     pulse.live_images,    600);
countUp(document.getElementById('stat-rooms'),      pulse.rooms,          500);

// ── Activity chart ────────────────────────────────────────
const canvas = document.getElementById('activity-chart');
const ctx    = canvas.getContext('2d');
const hourly = pulse.hourly;
const peak   = Math.max(...hourly, 1);
const peakIdx = hourly.indexOf(Math.max(...hourly));

function drawChart(progress) {
    const dpr  = window.devicePixelRatio || 1;
    const cssW = canvas.offsetWidth;
    const cssH = canvas.offsetHeight;
    if (!cssW || !cssH) return;
    canvas.width  = cssW * dpr;
    canvas.height = cssH * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const W = cssW, H = cssH;
    const PL = 30, PR = 6, PT = 10, PB = 28;
    const cW = W - PL - PR;
    const cH = H - PT - PB;
    const barW = cW / 24;
    const gap  = Math.max(1.5, barW * 0.18);

    ctx.clearRect(0, 0, W, H);

    // Horizontal grid lines
    ctx.strokeStyle = 'rgba(0,245,255,0.07)';
    ctx.lineWidth = 1;
    for (let i = 1; i <= 4; i++) {
        const y = PT + cH - (i / 4) * cH;
        ctx.beginPath(); ctx.moveTo(PL, y); ctx.lineTo(PL + cW, y); ctx.stroke();
    }
    // Baseline
    ctx.strokeStyle = 'rgba(0,245,255,0.18)';
    ctx.beginPath(); ctx.moveTo(PL, PT + cH); ctx.lineTo(PL + cW, PT + cH); ctx.stroke();

    // Bars
    hourly.forEach((val, i) => {
        const animated = val * progress;
        const bh = Math.max(2, (animated / peak) * cH);
        const x  = PL + i * barW + gap / 2;
        const y  = PT + cH - bh;
        const bw = barW - gap;
        const isPeak    = i === peakIdx && val > 0;
        const isCurrent = i === 23;

        const grad = ctx.createLinearGradient(x, y, x, y + bh);
        if (isPeak) {
            grad.addColorStop(0, '#ff00de');
            grad.addColorStop(1, 'rgba(255,0,222,0.15)');
            ctx.shadowBlur  = 22;
            ctx.shadowColor = '#ff00de';
        } else if (isCurrent) {
            grad.addColorStop(0, '#00f5ff');
            grad.addColorStop(1, 'rgba(0,245,255,0.1)');
            ctx.shadowBlur  = 14;
            ctx.shadowColor = '#00f5ff';
        } else {
            grad.addColorStop(0, 'rgba(0,245,255,0.65)');
            grad.addColorStop(1, 'rgba(0,245,255,0.07)');
            ctx.shadowBlur  = 6;
            ctx.shadowColor = '#00f5ff';
        }
        ctx.fillStyle = grad;
        ctx.fillRect(x, y, bw, bh);
        ctx.shadowBlur = 0;
    });

    // X-axis hour labels
    ctx.fillStyle  = 'rgba(61,107,122,0.85)';
    ctx.font       = `10px "Courier New", monospace`;
    ctx.textAlign  = 'center';
    const now = new Date();
    [0, 6, 12, 18, 23].forEach(i => {
        const d = new Date(now - (23 - i) * 3_600_000);
        const lbl = d.getHours().toString().padStart(2, '0') + ':00';
        ctx.fillText(lbl, PL + i * barW + barW / 2, H - 6);
    });

    // Y-axis max
    if (peak > 1) {
        ctx.textAlign  = 'right';
        ctx.fillStyle  = 'rgba(61,107,122,0.6)';
        ctx.fillText(peak, PL - 4, PT + 10);
    }
}

// Sweep animation
const animDur = 900;
const animT0  = performance.now();
(function frame(now) {
    const t    = Math.min((now - animT0) / animDur, 1);
    const ease = 1 - Math.pow(1 - t, 3);
    drawChart(ease);
    if (t < 1) requestAnimationFrame(frame);
})(animT0);

window.addEventListener('resize', () => drawChart(1));
