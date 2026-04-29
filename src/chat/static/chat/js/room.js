function setViewportHeight() {
    document.documentElement.style.setProperty('--vh', `${window.innerHeight * 0.01}px`);
}
setViewportHeight();
window.addEventListener('resize', setViewportHeight);

const roomName       = JSON.parse(document.getElementById('room-name-data').textContent);
const currentUsername = JSON.parse(document.getElementById('current-username-data').textContent) || 'Anonymous';
const protocol       = location.protocol === 'https:' ? 'wss' : 'ws';
const chatSocket     = new WebSocket(`${protocol}://${location.host}/ws/chat/${roomName}/`);

const chatLog    = document.getElementById('chat-log');
const msgInput   = document.getElementById('chat-message-input');
const submitBtn  = document.getElementById('chat-message-submit');
const imgBtn     = document.getElementById('img-btn');
const imgInput   = document.getElementById('img-input');
const previewBar = document.getElementById('img-preview-bar');
const imgPreview = document.getElementById('img-preview');
const imgPreviewInfo = document.getElementById('img-preview-info');
const imgCancel  = document.getElementById('img-cancel');

let emptyState   = document.getElementById('empty-state');
let pendingFile  = null;

function updateSubmitLabel() {
    const label = submitBtn.querySelector('.btn-label');
    if (!label) return;
    if (pendingFile) {
        submitBtn.classList.add('uploading');
        label.textContent = 'Upload ↑';
        submitBtn.title = 'Upload image';
    } else {
        submitBtn.classList.remove('uploading');
        label.textContent = 'Send';
        submitBtn.title = 'Send message';
    }
}

const USER_FONTS = [
    '"Impact", fantasy',
    '"Arial Black", sans-serif',
    '"Trebuchet MS", sans-serif',
    '"Georgia", serif',
    '"Verdana", sans-serif',
    '"Courier New", monospace',
];

function fontFromUsername(name) {
    const key = roomName + '::' + name;
    let h = 0;
    for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) & 0xffff;
    return USER_FONTS[h % USER_FONTS.length];
}

function applyNameFont(el) {
    el.style.fontFamily = fontFromUsername(el.textContent.trim());
}

document.querySelectorAll('.msg-meta strong').forEach(applyNameFont);

function fmt(value) {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? '' :
        new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(d);
}

document.querySelectorAll('.msg-time[data-ts]').forEach(el => {
    const f = fmt(el.dataset.ts);
    if (f) el.textContent = f;
});

function getCsrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
}

imgBtn.addEventListener('click', () => imgInput.click());

imgInput.addEventListener('change', () => {
    const file = imgInput.files[0];
    if (!file) return;
    pendingFile = file;
    imgPreview.src = URL.createObjectURL(file);
    imgPreviewInfo.textContent = `${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
    previewBar.classList.add('visible');
    updateSubmitLabel();
});

imgCancel.addEventListener('click', clearPreview);

function clearPreview() {
    pendingFile = null;
    imgInput.value = '';
    imgPreview.src = '';
    previewBar.classList.remove('visible');
    updateSubmitLabel();
}

async function doUpload() {
    if (!pendingFile) return;
    const form = new FormData();
    form.append('image', pendingFile);
    submitBtn.disabled = true;
    submitBtn.classList.add('uploading');
    const label = submitBtn.querySelector('.btn-label');
    if (label) label.textContent = 'Uploading…';
    try {
        const resp = await fetch(`/chat/${roomName}/image/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrf() },
            body: form,
        });
        const data = await resp.json();
        if (!resp.ok) {
            appendNotice(data.error || 'Upload failed.');
        } else {
            clearPreview();
        }
    } catch {
        appendNotice('Upload failed — network error.');
    }
    submitBtn.disabled = false;
    updateSubmitLabel();
}

function sendMessage() {
    const msg = msgInput.value.trim();
    if (!msg) return;
    chatSocket.send(JSON.stringify({ type: 'message', message: msg }));
    msgInput.value = '';
    msgInput.focus();
}

submitBtn.addEventListener('click', () => pendingFile ? doUpload() : sendMessage());
msgInput.addEventListener('keyup', e => { if (e.key === 'Enter' && !pendingFile) sendMessage(); });

function appendNotice(text) {
    const d = document.createElement('div');
    d.className = 'msg-notice';
    d.textContent = text;
    chatLog.appendChild(d);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function appendMessage(data) {
    if (emptyState) { emptyState.remove(); emptyState = null; }
    const isMine = data.username === currentUsername;
    const art = document.createElement('article');
    art.className = `msg${isMine ? ' own-msg' : ''}`;
    art.dataset.msgId = data.message_id;
    if (data.color) art.style.setProperty('--bubble-bg', data.color);
    const timerHtml = data.expires_at
        ? `<span class="msg-timer" data-expires="${data.expires_at}">--:--:--</span>`
        : '';
    art.innerHTML = `
        <div class="msg-meta">
            <strong></strong>
            <time class="msg-time">${data.timestamp ? fmt(data.timestamp) : ''}</time>
            ${timerHtml}
            ${isMine ? `<div class="msg-actions">
                <button class="action-btn edit-btn" title="Edit">&#9998;</button>
                <button class="action-btn del-btn" title="Delete">&#10005;</button>
            </div>` : ''}
        </div>
        <p class="msg-body"></p>
        ${isMine ? `<div class="edit-form">
            <input class="edit-input" type="text" maxlength="1000" />
            <button class="edit-save" title="Save">&#10003;</button>
            <button class="edit-cancel-btn" title="Cancel">&#10005;</button>
        </div>` : ''}`;
    const strong = art.querySelector('strong');
    strong.textContent = data.username;
    applyNameFont(strong);
    art.querySelector('.msg-body').textContent = data.message;
    if (isMine) art.querySelector('.edit-input').value = data.message;
    chatLog.appendChild(art);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function appendImage(data) {
    if (emptyState) { emptyState.remove(); emptyState = null; }
    const isMine = data.username === currentUsername;
    const art = document.createElement('article');
    art.className = `msg msg-image${isMine ? ' own-msg' : ''}`;
    art.dataset.imgId = data.image_id;
    art.style.setProperty('--bubble-bg', data.color);
    art.innerHTML = `
        <div class="msg-meta">
            <strong></strong>
            <span class="img-timer" data-expires="${data.expires_at}">60:00</span>
            ${isMine ? `<div class="msg-actions">
                <button class="action-btn del-btn img-del-btn" title="Delete">&#10005;</button>
            </div>` : ''}
        </div>
        <img class="chat-img" src="${data.image_url}" loading="lazy" alt="Image" />`;
    const strong = art.querySelector('strong');
    strong.textContent = data.username;
    applyNameFont(strong);
    chatLog.appendChild(art);
    chatLog.scrollTop = chatLog.scrollHeight;
}

chatSocket.onmessage = e => {
    const data = JSON.parse(e.data);
    switch (data.type) {
        case 'message_deleted': handleMsgDeleted(data); break;
        case 'message_edited': handleMsgEdited(data); break;
        case 'chat_image': appendImage(data); break;
        case 'image_deleted': handleImgDeleted(data); break;
        default: appendMessage(data); break;
    }
};

chatSocket.onclose = () => appendNotice('Connection closed — refresh to reconnect.');

function handleMsgDeleted(data) {
    document.querySelector(`[data-msg-id="${data.message_id}"]`)?.remove();
}

function handleMsgEdited(data) {
    const art = document.querySelector(`[data-msg-id="${data.message_id}"]`);
    if (!art) return;
    const body = art.querySelector('.msg-body');
    if (body) body.textContent = data.message;
    const inp = art.querySelector('.edit-input');
    if (inp) inp.value = data.message;
    let tag = art.querySelector('.edited-tag');
    if (!tag) {
        tag = document.createElement('span');
        tag.className = 'edited-tag';
        art.querySelector('.msg-time')?.after(tag);
    }
    tag.textContent = '(edited)';
    exitEdit(art);
}

function handleImgDeleted(data) {
    document.querySelector(`[data-img-id="${data.image_id}"]`)?.remove();
}

document.getElementById('chat-log').addEventListener('click', e => {
    const art = e.target.closest('.msg');
    if (!art) return;

    if (e.target.closest('.del-btn')) {
        const msgId = art.dataset.msgId ? +art.dataset.msgId : null;
        const imgId = art.dataset.imgId ? +art.dataset.imgId : null;
        if (msgId) chatSocket.send(JSON.stringify({ type: 'message.delete', message_id: msgId }));
        if (imgId) deleteImg(imgId);
        return;
    }
    if (e.target.closest('.edit-btn')) { enterEdit(art); return; }
    if (e.target.closest('.edit-save')) { saveEdit(art); return; }
    if (e.target.closest('.edit-cancel-btn')) { exitEdit(art); return; }
});

document.getElementById('chat-log').addEventListener('keydown', e => {
    if (!e.target.classList.contains('edit-input')) return;
    const art = e.target.closest('.msg');
    if (!art) return;
    if (e.key === 'Enter') { e.preventDefault(); saveEdit(art); }
    if (e.key === 'Escape') exitEdit(art);
});

function enterEdit(art) {
    art.querySelector('.msg-body').style.display = 'none';
    art.querySelector('.edit-form').classList.add('active');
    art.querySelector('.edit-input').focus();
}

function exitEdit(art) {
    art.querySelector('.msg-body').style.display = '';
    art.querySelector('.edit-form')?.classList.remove('active');
}

function saveEdit(art) {
    const inp = art.querySelector('.edit-input');
    const newText = inp?.value.trim();
    const msgId = +art.dataset.msgId;
    if (!newText || !msgId) { exitEdit(art); return; }
    chatSocket.send(JSON.stringify({ type: 'message.edit', message_id: msgId, message: newText }));
}

async function deleteImg(imgId) {
    await fetch(`/chat/image/${imgId}/delete/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrf() },
    });
}

function fmtCountdown(diff) {
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    const s = Math.floor((diff % 60000) / 1000);
    if (h > 0) return `${h}:${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
    return `${m}:${s.toString().padStart(2,'0')}`;
}

function updateTimers() {
    const now = Date.now();
    document.querySelectorAll('.img-timer[data-expires]').forEach(el => {
        const diff = Math.max(0, new Date(el.dataset.expires) - now);
        if (diff === 0) { el.closest('.msg')?.remove(); return; }
        el.textContent = fmtCountdown(diff);
    });
    document.querySelectorAll('.msg-timer[data-expires]').forEach(el => {
        const diff = Math.max(0, new Date(el.dataset.expires) - now);
        if (diff === 0) { el.closest('.msg')?.remove(); return; }
        el.textContent = fmtCountdown(diff);
    });
}
setInterval(updateTimers, 1000);
updateTimers();

const lightbox     = document.getElementById('lightbox');
const lightboxImg  = document.getElementById('lightbox-img');
const lightboxClose = document.getElementById('lightbox-close');

function openLightbox(src) {
    lightboxImg.src = src;
    lightbox.classList.add('open');
}
function closeLightbox() {
    lightbox.classList.remove('open');
    lightboxImg.src = '';
}

lightbox.addEventListener('click', e => { if (e.target === lightbox) closeLightbox(); });
lightboxClose.addEventListener('click', closeLightbox);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });

document.getElementById('chat-log').addEventListener('click', e => {
    const img = e.target.closest('.chat-img');
    if (img && img.src) openLightbox(img.src);
});
document.getElementById('chat-log').addEventListener('contextmenu', e => {
    if (e.target.closest('.chat-img')) e.preventDefault();
});
document.getElementById('chat-log').addEventListener('dragstart', e => {
    if (e.target.closest('.chat-img')) e.preventDefault();
});

chatLog.scrollTop = chatLog.scrollHeight;
msgInput.focus();
