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
const userLifetimeWrap  = document.getElementById('user-lifetime-wrap');
const adminLifetimeWrap = document.getElementById('admin-lifetime-wrap');

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
    if (userLifetimeWrap) userLifetimeWrap.style.display = 'none';
}

document.querySelectorAll('.lifetime-chips').forEach(group => {
    const target = document.getElementById(group.dataset.target);
    group.addEventListener('click', e => {
        const chip = e.target.closest('.chip');
        if (!chip) return;
        group.querySelectorAll('.chip').forEach(c => c.classList.remove('is-selected'));
        chip.classList.add('is-selected');
        if (target) target.value = chip.dataset.seconds;
    });
});

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
        roomNameInput.value = '';
        showEntryPanel();
        if (IS_SUPERUSER) {
            adminRoomNameEl.style.display = 'none';
            const adminCreateWrap = document.getElementById('admin-create-wrap');
            const adminCreateInput = document.getElementById('admin-create-input');
            adminCreateWrap.style.display = '';
            adminCreateInput.value = '';
            adminCreateInput.focus();
            if (adminLifetimeWrap) adminLifetimeWrap.style.display = '';
        } else {
            if (selectedFpEl) selectedFpEl.textContent = '// new room';
            if (fingerprintEl) { fingerprintEl.textContent = ''; fingerprintEl.classList.remove('has-value'); }
            passwordFieldWrap.style.display = '';
            submitWrap.style.display = 'none';
            if (userLifetimeWrap) userLifetimeWrap.style.display = '';
            roomNameInput.focus();
        }
    });
}

const adminCreateInput = document.getElementById('admin-create-input');
if (adminCreateInput) {
    adminCreateInput.addEventListener('input', () => {
        roomNameInput.value = adminCreateInput.value.trim();
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
        adminRoomNameEl.style.display = 'block';
        document.getElementById('admin-create-wrap').style.display = 'none';
        if (adminLifetimeWrap) adminLifetimeWrap.style.display = 'none';
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
        else if (p.type === 'room_activity' || p.type === 'room_recompute') {
            recomputeRoomUnread(p.room_name);
        }
        else if (p.type === 'friends_changed') document.dispatchEvent(new CustomEvent('friends-update'));
    } catch {}
};

async function recomputeRoomUnread(name) {
    const card = roomList.querySelector(`.room-card[data-room-name="${CSS.escape(name)}"]`);
    if (!card) return;
    try {
        const resp = await fetch(`/api/rooms/${encodeURIComponent(name)}/unread/`, { credentials: 'same-origin' });
        if (!resp.ok) return;
        const data = await resp.json();
        card.classList.toggle('has-msgs', !!data.unread);
    } catch {}
}
