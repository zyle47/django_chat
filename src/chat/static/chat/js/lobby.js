const roomNameInput     = document.getElementById('room-name-input');
const roomPassInput     = document.getElementById('room-password-input');
const roomList          = document.getElementById('room-list');
const favoritesList     = document.getElementById('favorites-list');
const favoritesCount    = document.getElementById('favorites-count');
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

const FAV_STAR_HTML = '<span class="room-star" data-fav-toggle aria-label="Toggle favourite" title="Favourite">&#9734;</span>';
const NOTE_PLACEHOLDER = '+ add note';

function getCsrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
}

function cardsByHash(hash) {
    return document.querySelectorAll(`.room-card[data-room-hash="${CSS.escape(hash)}"]`);
}


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
    btn.innerHTML = `<div class="room-orb" style="background:${room_color};color:#000">${room_icon}</div><div class="room-card-body"><div class="room-card-name">${room_display}</div></div>${FAV_STAR_HTML}`;
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

function clearSelectedCards() {
    document.querySelectorAll('.room-card.is-selected').forEach(c => c.classList.remove('is-selected'));
}

function deselectRoom() {
    selectedRoomHash = null;
    clearSelectedCards();
    selectHint.style.display = '';
    entryPanel.style.display = 'none';
    entryPanel.classList.remove('field-revealed');
    if (roomPassInput) roomPassInput.value = '';
    if (roomNameInput) roomNameInput.value = '';
    if (fingerprintEl) { fingerprintEl.textContent = ''; fingerprintEl.classList.remove('has-value'); }
    if (selectedFpEl) selectedFpEl.textContent = '';
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
        submitWrap.style.display = roomPassInput.value.length > 0 ? '' : 'none';
    });

    roomPassInput.closest('form')?.addEventListener('submit', e => {
        if (roomPassInput.value.length === 0) e.preventDefault();
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
        clearSelectedCards();
        selectedRoomHash = null;
        roomNameInput.value = '';
        showEntryPanel();
        if (IS_SUPERUSER) {
            adminRoomNameEl.style.display = 'none';
            const adminCreateWrap = document.getElementById('admin-create-wrap');
            const adminCreateInput = document.getElementById('admin-create-input');
            const adminPasswordWrap = document.getElementById('admin-password-wrap');
            const adminPasswordInput = document.getElementById('admin-password-input');
            adminCreateWrap.style.display = '';
            adminCreateInput.value = '';
            adminPasswordWrap.style.display = '';
            adminPasswordInput.value = '';
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

function selectRoomCard(btn) {
    if (btn.dataset.roomHash === selectedRoomHash) {
        deselectRoom();
        return;
    }
    clearSelectedCards();
    cardsByHash(btn.dataset.roomHash).forEach(c => c.classList.add('is-selected'));
    selectedRoomHash = btn.dataset.roomHash;
    showEntryPanel();
    if (IS_SUPERUSER) {
        const name = btn.dataset.roomName;
        const adminPasswordWrap = document.getElementById('admin-password-wrap');
        const adminPasswordInput = document.getElementById('admin-password-input');
        adminRoomNameEl.textContent = name;
        adminRoomNameEl.style.display = 'block';
        document.getElementById('admin-create-wrap').style.display = 'none';
        adminPasswordWrap.style.display = 'none';
        adminPasswordInput.value = '';
        if (adminLifetimeWrap) adminLifetimeWrap.style.display = 'none';
        roomNameInput.value = name;
    } else {
        selectedFpEl.textContent = '// ' + selectedRoomHash;
        roomNameInput.value = '';
        if (fingerprintEl) { fingerprintEl.textContent = ''; fingerprintEl.classList.remove('has-value'); }
        hideRoomFields();
        roomNameInput.focus();
    }
}

function handleListClick(e) {
    const noteEdit = e.target.closest('[data-note-edit]');
    if (noteEdit) {
        e.stopPropagation();
        const card = noteEdit.closest('.room-card');
        if (card) openNoteEditor(card);
        return;
    }
    const star = e.target.closest('.room-star');
    if (star) {
        e.stopPropagation();
        const card = star.closest('.room-card');
        if (card) toggleFavorite(card);
        return;
    }
    const btn = e.target.closest('.room-pill-btn');
    if (!btn) return;
    selectRoomCard(btn);
}

roomList.addEventListener('click', handleListClick);
if (favoritesList) favoritesList.addEventListener('click', handleListClick);

async function toggleFavorite(card) {
    const hash = card.dataset.roomHash;
    if (!hash) return;
    try {
        const resp = await fetch(`/api/rooms/${encodeURIComponent(hash)}/favorite/`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': getCsrf() },
        });
        if (!resp.ok) return;
        const data = await resp.json();
        setFavoriteState(hash, !!data.favorited);
    } catch {}
}

function setFavoriteState(hash, favorited) {
    cardsByHash(hash).forEach(card => {
        card.classList.toggle('is-favorite', favorited);
        const star = card.querySelector('.room-star');
        if (star) {
            star.classList.toggle('is-active', favorited);
            star.innerHTML = favorited ? '&#9733;' : '&#9734;';
        }
    });
    if (!favoritesList) return;
    const existing = favoritesList.querySelector(`.room-card[data-room-hash="${CSS.escape(hash)}"]`);
    if (favorited && !existing) {
        const source = roomList.querySelector(`.room-card[data-room-hash="${CSS.escape(hash)}"]`);
        if (source) {
            const clone = source.cloneNode(true);
            clone.classList.toggle('is-selected', hash === selectedRoomHash);
            const body = clone.querySelector('.room-card-body');
            if (body && !clone.querySelector('.room-note')) {
                body.appendChild(buildNoteSpan(''));
            }
            const emptyEl = favoritesList.querySelector('#favorites-empty');
            if (emptyEl) emptyEl.remove();
            favoritesList.prepend(clone);
        }
    } else if (!favorited && existing) {
        existing.remove();
    }
    updateFavoritesCount();
}

function updateFavoritesCount() {
    if (!favoritesList) return;
    const n = favoritesList.querySelectorAll('.room-card').length;
    if (favoritesCount) favoritesCount.textContent = String(n);
    let emptyEl = favoritesList.querySelector('#favorites-empty');
    if (n === 0 && !emptyEl) {
        emptyEl = document.createElement('div');
        emptyEl.className = 'empty-state';
        emptyEl.id = 'favorites-empty';
        emptyEl.innerHTML = '<div class="big">&#9734;</div><p>No favourites yet.<br>Tap a star to pin a room.</p>';
        favoritesList.appendChild(emptyEl);
    } else if (n > 0 && emptyEl) {
        emptyEl.remove();
    }
}

/* ---- Per-favourite private notes (shown only in the favourites column) ---- */

function buildNoteSpan(note) {
    const span = document.createElement('span');
    span.className = 'room-note' + (note ? '' : ' is-empty');
    span.setAttribute('data-note-edit', '');
    span.dataset.note = note || '';
    span.title = 'Edit your private note';
    span.textContent = note || NOTE_PLACEHOLDER;
    return span;
}

function setNoteSpan(span, note) {
    span.dataset.note = note || '';
    span.textContent = note || NOTE_PLACEHOLDER;
    span.classList.toggle('is-empty', !note);
}

let noteModal = null;
let noteEditHash = null;

function ensureNoteModal() {
    if (noteModal) return noteModal;
    const backdrop = document.createElement('div');
    backdrop.className = 'note-modal-backdrop';
    backdrop.innerHTML =
        '<div class="note-modal">' +
        '<div class="note-modal-title">// Room Note</div>' +
        '<input class="note-modal-input" type="text" maxlength="200" placeholder="Private note for this room…" autocomplete="off" />' +
        '<div class="note-modal-hint">Only you can see this — it never shows in the room browser.</div>' +
        '<div class="note-modal-actions">' +
        '<button type="button" class="btn btn-secondary note-modal-cancel">Cancel</button>' +
        '<button type="button" class="btn btn-primary note-modal-save">Save</button>' +
        '</div></div>';
    document.body.appendChild(backdrop);

    const input = backdrop.querySelector('.note-modal-input');
    backdrop.querySelector('.note-modal-cancel').addEventListener('click', closeNoteModal);
    backdrop.querySelector('.note-modal-save').addEventListener('click', saveNote);
    backdrop.addEventListener('click', e => { if (e.target === backdrop) closeNoteModal(); });
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); saveNote(); }
        else if (e.key === 'Escape') { e.preventDefault(); closeNoteModal(); }
    });

    noteModal = backdrop;
    return backdrop;
}

function openNoteEditor(card) {
    const hash = card.dataset.roomHash;
    if (!hash) return;
    noteEditHash = hash;
    const modal = ensureNoteModal();
    const noteEl = card.querySelector('.room-note');
    const input = modal.querySelector('.note-modal-input');
    input.value = noteEl ? (noteEl.dataset.note || '') : '';
    modal.classList.add('open');
    input.focus();
    input.select();
}

function closeNoteModal() {
    if (noteModal) noteModal.classList.remove('open');
    noteEditHash = null;
}

async function saveNote() {
    const hash = noteEditHash;
    if (!hash || !noteModal) { closeNoteModal(); return; }
    const note = noteModal.querySelector('.note-modal-input').value.trim();
    try {
        const resp = await fetch(`/api/rooms/${encodeURIComponent(hash)}/favorite/note/`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': getCsrf(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'note=' + encodeURIComponent(note),
        });
        if (resp.ok) {
            const data = await resp.json();
            applyNote(hash, data.note || '');
        }
    } catch {}
    closeNoteModal();
}

function applyNote(hash, note) {
    if (!favoritesList) return;
    const card = favoritesList.querySelector(`.room-card[data-room-hash="${CSS.escape(hash)}"]`);
    if (!card) return;
    const noteEl = card.querySelector('.room-note');
    if (noteEl) setNoteSpan(noteEl, note);
}

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
        else if (p.type === 'room_activity' || p.type === 'room_recompute') {
            recomputeRoomUnread(p.room_hash);
        }
        else if (p.type === 'friends_changed') document.dispatchEvent(new CustomEvent('friends-update'));
    } catch {}
};

async function recomputeRoomUnread(hash) {
    const cards = cardsByHash(hash);
    if (!cards.length) return;
    try {
        const resp = await fetch(`/api/rooms/${encodeURIComponent(hash)}/unread/`, { credentials: 'same-origin' });
        if (!resp.ok) return;
        const data = await resp.json();
        cards.forEach(card => card.classList.toggle('has-msgs', !!data.unread));
    } catch {}
}
