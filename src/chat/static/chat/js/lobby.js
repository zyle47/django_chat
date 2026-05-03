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


function updateCount() {
    const all     = [...roomList.querySelectorAll('.room-card')];
    const visible = all.filter(c => c.style.display !== 'none');
    const t = all.length, v = visible.length;
    roomCountEl.textContent = (t === v) ? `${t} room${t !== 1 ? 's' : ''}` : `${v} / ${t}`;
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

function addRoomToList({ room_hash, room_display, room_icon, room_color }) {
    if (!room_hash || roomList.querySelector(`[data-room-hash="${room_hash}"]`)) return;
    const emptyEl = roomList.querySelector('#empty-state');
    if (emptyEl) emptyEl.remove();
    const btn = document.createElement('button');
    btn.className = 'room-card room-pill-btn';
    btn.dataset.roomHash = room_hash;
    btn.type = 'button';
    btn.innerHTML = `<div class="room-orb" style="background:${room_color};color:#000">${room_icon}</div><div class="room-card-name">${room_display}</div>`;
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
        roomNameInput.value = '';
        showEntryPanel();
        if (IS_SUPERUSER) {
            adminRoomNameEl.style.display = 'none';
            const adminCreateWrap = document.getElementById('admin-create-wrap');
            const adminCreateInput = document.getElementById('admin-create-input');
            adminCreateWrap.style.display = '';
            adminCreateInput.value = '';
            adminCreateInput.focus();
        } else {
            if (selectedFpEl) selectedFpEl.textContent = '// new room';
            if (fingerprintEl) { fingerprintEl.textContent = ''; fingerprintEl.classList.remove('has-value'); }
            passwordFieldWrap.style.display = '';
            submitWrap.style.display = 'none';
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

roomList.addEventListener('click', e => {
    const btn = e.target.closest('.room-pill-btn');
    if (!btn) return;
    selectedRoomHash = btn.dataset.roomHash;
    requiredPwLength = pwLengths[selectedRoomHash] || 0;
    showEntryPanel();
    if (IS_SUPERUSER) {
        const name = btn.dataset.roomName;
        adminRoomNameEl.textContent = name;
        adminRoomNameEl.style.display = 'block';
        document.getElementById('admin-create-wrap').style.display = 'none';
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
updateCount();

const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
const lobbySocket = new WebSocket(`${protocol}://${location.host}/ws/lobby/`);
lobbySocket.onmessage = e => {
    try {
        const p = JSON.parse(e.data);
        if (p.type === 'room_created') addRoomToList(p);
    } catch {}
};
