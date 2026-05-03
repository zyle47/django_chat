(function () {
    const fab = document.getElementById('friends-fab');
    const panel = document.getElementById('friends-panel');
    const closeBtn = document.getElementById('friends-close');
    const pendingList = document.getElementById('friends-pending-list');
    const friendList = document.getElementById('friends-friend-list');
    const pendingCount = document.getElementById('friends-pending-count');
    const friendCount = document.getElementById('friends-friend-count');
    const fabBadge = document.getElementById('friends-fab-badge');
    const fabUnreadBadge = document.getElementById('friends-fab-unread-badge');

    const friendsView = document.getElementById('friends-view');
    const dmView = document.getElementById('dm-view');
    const dmBack = document.getElementById('dm-back');
    const dmCloseBtn = document.getElementById('dm-close');
    const dmLabel = document.getElementById('dm-peer-label');
    const dmLog = document.getElementById('dm-log');
    const dmInput = document.getElementById('dm-input');
    const dmSend = document.getElementById('dm-send');

    if (!fab || !panel) return;

    let dmSocket = null;
    let dmPeer = null;
    let peerLastReadAt = null;
    const myUsername = (() => {
        const el = document.getElementById('friends-current-username');
        try { return el ? JSON.parse(el.textContent) : null; } catch { return null; }
    })();

    function getCsrf() {
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    function setBadge(n) {
        if (n > 0) {
            fabBadge.hidden = false;
            fabBadge.textContent = String(n);
        } else {
            fabBadge.hidden = true;
        }
    }

    function setUnreadBadge(n) {
        if (n > 0) {
            fabUnreadBadge.hidden = false;
            fabUnreadBadge.textContent = String(n);
        } else {
            fabUnreadBadge.hidden = true;
        }
    }

    function escapeText(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function renderEmpty(list, text) {
        list.innerHTML = `<div class="friends-empty">${escapeText(text)}</div>`;
    }

    function renderPending(items) {
        pendingCount.textContent = String(items.length);
        setBadge(items.length);
        if (!items.length) {
            renderEmpty(pendingList, 'No pending requests.');
            return;
        }
        pendingList.innerHTML = '';
        for (const r of items) {
            const row = document.createElement('div');
            row.className = 'friend-row';
            row.dataset.fromUsername = r.from_username;
            row.innerHTML = `
                <div class="name">${escapeText(r.from_username)}</div>
                <div class="friend-actions">
                    <button type="button" class="friend-btn accept" data-action="accept">Accept</button>
                    <button type="button" class="friend-btn reject" data-action="reject">Reject</button>
                </div>`;
            pendingList.appendChild(row);
        }
    }

    function renderFriends(items) {
        friendCount.textContent = String(items.length);
        if (!items.length) {
            renderEmpty(friendList, 'No friends yet.');
            return;
        }
        friendList.innerHTML = '';
        for (const f of items) {
            const row = document.createElement('div');
            row.className = 'friend-row';
            row.dataset.username = f.username;
            const unread = f.unread_count || 0;
            const unreadHtml = (unread === 0)
                ? ''
                : `<span class="friend-unread">${escapeText(String(unread))}</span>`;
            row.innerHTML = `
                <div class="name"><span class="name-text">${escapeText(f.username)}</span>${unreadHtml}</div>
                <div class="friend-actions">
                    <button type="button" class="friend-btn" data-action="dm">DM</button>
                    <button type="button" class="friend-btn danger" data-action="remove" disabled title="Remove — coming in v2">Remove</button>
                    <button type="button" class="friend-btn danger" data-action="ban" disabled title="Ban — coming in v2">Ban</button>
                </div>`;
            friendList.appendChild(row);
        }
    }

    async function fetchJson(url, options) {
        const resp = await fetch(url, { credentials: 'same-origin', ...options });
        let data = null;
        try { data = await resp.json(); } catch { data = null; }
        return { ok: resp.ok, status: resp.status, data };
    }

    async function refresh() {
        try {
            const [pending, friends, unread] = await Promise.all([
                fetchJson('/api/friends/requests/'),
                fetchJson('/api/friends/'),
                fetchJson('/api/friends/unread-count/'),
            ]);
            renderPending(pending.data?.requests || []);
            renderFriends(friends.data?.friends || []);
            setUnreadBadge(unread.data?.count || 0);
        } catch {
            renderEmpty(pendingList, 'Failed to load.');
            renderEmpty(friendList, 'Failed to load.');
        }
    }

    async function respond(action, fromUsername) {
        const body = new URLSearchParams({ from_username: fromUsername });
        await fetchJson(`/api/friends/${action}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrf(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body,
        });
        refresh();
    }

    pendingList.addEventListener('click', e => {
        const btn = e.target.closest('.friend-btn');
        if (!btn) return;
        const row = btn.closest('.friend-row');
        const name = row?.dataset.fromUsername;
        if (!name) return;
        const action = btn.dataset.action;
        if (action === 'accept' || action === 'reject') respond(action, name);
    });

    friendList.addEventListener('click', e => {
        const btn = e.target.closest('.friend-btn');
        if (!btn || btn.disabled) return;
        if (btn.dataset.action !== 'dm') return;
        const row = btn.closest('.friend-row');
        const name = row?.dataset.username;
        if (name) openDM(name);
    });

    fab.addEventListener('click', () => {
        const opening = panel.hidden;
        panel.hidden = !opening;
        if (opening) refresh();
    });
    closeBtn.addEventListener('click', () => { panel.hidden = true; });
    dmBack.addEventListener('click', closeDM);
    dmCloseBtn.addEventListener('click', () => { closeDM(); panel.hidden = true; });
    dmSend.addEventListener('click', sendDM);
    dmInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendDM(); });

    dmLog.addEventListener('click', e => {
        const btn = e.target.closest('.dm-action');
        if (!btn) return;
        const msg = btn.closest('.dm-msg');
        if (!msg) return;
        if (btn.classList.contains('edit'))   enterDmEdit(msg);
        else if (btn.classList.contains('del'))    deleteDm(msg);
        else if (btn.classList.contains('save'))   saveDmEdit(msg);
        else if (btn.classList.contains('cancel')) exitDmEdit(msg);
    });
    dmLog.addEventListener('keydown', e => {
        if (!e.target.classList.contains('dm-edit-input')) return;
        const msg = e.target.closest('.dm-msg');
        if (!msg) return;
        if (e.key === 'Enter')  { e.preventDefault(); saveDmEdit(msg); }
        if (e.key === 'Escape') exitDmEdit(msg);
    });

    document.addEventListener('friends-update', refresh);

    function fmtTime(iso) {
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return '';
        return new Intl.DateTimeFormat(undefined, {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        }).format(d);
    }

    function isAtBottom() {
        return dmLog.scrollTop + dmLog.clientHeight >= dmLog.scrollHeight - 50;
    }

    function appendDmMessage(m) {
        const empty = dmLog.querySelector('.dm-empty');
        if (empty) empty.remove();
        const wasAtBottom = isAtBottom();
        const div = document.createElement('div');
        const isMine = m.from_username === myUsername;
        div.className = `dm-msg ${isMine ? 'mine' : 'theirs'}`;
        div.dataset.id = m.id;
        div.dataset.createdAt = m.created_at;
        const actionsHtml = isMine
            ? `<div class="dm-msg-actions">
                <button type="button" class="dm-action edit" title="Edit">&#9998;</button>
                <button type="button" class="dm-action del" title="Delete">&#10005;</button>
              </div>`
            : '';
        const editedHtml = m.edited_at ? `<span class="dm-edited">(edited)</span>` : '';
        div.innerHTML = `
            ${actionsHtml}
            <div class="dm-msg-text"></div>
            <div class="dm-edit-form">
                <input class="dm-edit-input" type="text" maxlength="2000" />
                <button type="button" class="dm-action save" title="Save">&#10003;</button>
                <button type="button" class="dm-action cancel" title="Cancel">&#10005;</button>
            </div>
            <span class="dm-msg-time">${fmtTime(m.created_at)} ${editedHtml}</span>`;
        div.querySelector('.dm-msg-text').textContent = m.message;
        if (isMine) div.querySelector('.dm-edit-input').value = m.message;
        dmLog.appendChild(div);
        if (wasAtBottom || isMine) dmLog.scrollTop = dmLog.scrollHeight;
        renderSeenIndicator();
    }

    function scrollToFirstUnread(myLastReadAt) {
        if (!myLastReadAt) {
            dmLog.scrollTop = dmLog.scrollHeight;
            return;
        }
        const cutoff = new Date(myLastReadAt).getTime();
        if (Number.isNaN(cutoff)) {
            dmLog.scrollTop = dmLog.scrollHeight;
            return;
        }
        const theirs = dmLog.querySelectorAll('.dm-msg.theirs');
        let firstUnread = null;
        for (const el of theirs) {
            const t = new Date(el.dataset.createdAt).getTime();
            if (!Number.isNaN(t) && t > cutoff) { firstUnread = el; break; }
        }
        if (firstUnread) {
            const divider = document.createElement('div');
            divider.className = 'dm-new-divider';
            divider.textContent = '/// new messages ///';
            firstUnread.before(divider);
            dmLog.scrollTop = firstUnread.offsetTop + firstUnread.offsetHeight - dmLog.clientHeight - 50;
        } else {
            dmLog.scrollTop = dmLog.scrollHeight;
        }
    }

    function renderSeenIndicator() {
        // Remove any existing tag.
        dmLog.querySelector('.dm-seen-tag')?.remove();
        if (!peerLastReadAt) return;
        const cutoff = new Date(peerLastReadAt).getTime();
        if (Number.isNaN(cutoff)) return;

        // Find the last "mine" message with created_at <= peer's last_read_at.
        const mineMsgs = dmLog.querySelectorAll('.dm-msg.mine');
        let target = null;
        for (const el of mineMsgs) {
            const t = new Date(el.dataset.createdAt).getTime();
            if (!Number.isNaN(t) && t <= cutoff) target = el;
        }
        if (!target) return;
        const tag = document.createElement('div');
        tag.className = 'dm-seen-tag';
        tag.textContent = 'seen';
        target.after(tag);
    }

    function applyDmEdit(id, newText, editedAt) {
        const el = dmLog.querySelector(`.dm-msg[data-id="${id}"]`);
        if (!el) return;
        el.querySelector('.dm-msg-text').textContent = newText;
        const inp = el.querySelector('.dm-edit-input');
        if (inp) inp.value = newText;
        const time = el.querySelector('.dm-msg-time');
        if (time && !time.querySelector('.dm-edited')) {
            const tag = document.createElement('span');
            tag.className = 'dm-edited';
            tag.textContent = '(edited)';
            time.appendChild(document.createTextNode(' '));
            time.appendChild(tag);
        }
        exitDmEdit(el);
    }

    function enterDmEdit(el) {
        el.classList.add('editing');
        el.querySelector('.dm-edit-input')?.focus();
    }

    function exitDmEdit(el) {
        el.classList.remove('editing');
    }

    function saveDmEdit(el) {
        const id = +el.dataset.id;
        const inp = el.querySelector('.dm-edit-input');
        const text = inp?.value.trim();
        if (!id || !text || !dmSocket || dmSocket.readyState !== WebSocket.OPEN) return;
        dmSocket.send(JSON.stringify({ type: 'message.edit', message_id: id, message: text }));
    }

    function deleteDm(el) {
        const id = +el.dataset.id;
        if (!id || !dmSocket || dmSocket.readyState !== WebSocket.OPEN) return;
        dmSocket.send(JSON.stringify({ type: 'message.delete', message_id: id }));
    }

    async function openDM(peerUsername) {
        dmPeer = peerUsername;
        peerLastReadAt = null;
        dmLabel.textContent = `// ${peerUsername}`;
        dmLog.innerHTML = '<div class="dm-empty">Loading&hellip;</div>';
        friendsView.hidden = true;
        dmView.hidden = false;
        dmInput.disabled = false;
        dmSend.disabled = false;
        dmInput.value = '';
        dmInput.focus();

        try {
            const resp = await fetch(`/api/friends/${encodeURIComponent(peerUsername)}/messages/`, {
                credentials: 'same-origin',
            });
            const data = await resp.json();
            if (!resp.ok) {
                dmLog.innerHTML = `<div class="dm-empty">${escapeText(data.error || 'Failed to load')}</div>`;
                return;
            }
            peerLastReadAt = data.peer_last_read_at || null;
            const myLastReadAt = data.my_last_read_at || null;
            dmLog.innerHTML = '';
            if (!data.messages.length) {
                dmLog.innerHTML = '<div class="dm-empty">No messages yet — say hi.</div>';
            } else {
                for (const m of data.messages) appendDmMessage(m);
                renderSeenIndicator();
                scrollToFirstUnread(myLastReadAt);
            }
        } catch {
            dmLog.innerHTML = '<div class="dm-empty">Failed to load.</div>';
            return;
        }

        connectDmSocket(peerUsername);
        // Server marked the conversation read; refresh the badge.
        document.dispatchEvent(new CustomEvent('friends-update'));
    }

    function connectDmSocket(peerUsername) {
        closeDmSocket();
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        dmSocket = new WebSocket(`${proto}://${location.host}/ws/dm/${encodeURIComponent(peerUsername)}/`);
        dmSocket.onmessage = e => {
            try {
                const data = JSON.parse(e.data);
                if (data.type === 'dm_message') appendDmMessage(data);
                else if (data.type === 'dm_deleted') {
                    dmLog.querySelector(`.dm-msg[data-id="${data.id}"]`)?.remove();
                    renderSeenIndicator();
                } else if (data.type === 'dm_edited') {
                    applyDmEdit(data.id, data.message, data.edited_at);
                } else if (data.type === 'dm_read') {
                    peerLastReadAt = data.last_read_at;
                    renderSeenIndicator();
                }
            } catch {}
        };
        dmSocket.onclose = (e) => {
            dmSocket = null;
            // If user navigated away, dmPeer is already null — silent close.
            if (!dmPeer) return;
            // 4410 = peer no longer a friend / was disabled / was deleted.
            // 4403 = friendship gone before connect could complete.
            if (e.code === 4410 || e.code === 4403) {
                showDmEnded('This person is no longer available.');
            }
        };
    }

    function closeDmSocket() {
        if (dmSocket) {
            dmSocket.close();
            dmSocket = null;
        }
    }

    function showDmEnded(text) {
        const div = document.createElement('div');
        div.className = 'dm-empty';
        div.textContent = text;
        dmLog.appendChild(div);
        dmInput.disabled = true;
        dmSend.disabled = true;
    }

    function sendDM() {
        const text = dmInput.value.trim();
        if (!text || !dmSocket || dmSocket.readyState !== WebSocket.OPEN) return;
        dmSocket.send(JSON.stringify({ type: 'message', message: text }));
        dmInput.value = '';
        dmInput.focus();
    }

    function closeDM() {
        // Reset dmPeer first so onclose treats it as user-initiated and stays silent.
        dmPeer = null;
        closeDmSocket();
        dmInput.disabled = false;
        dmSend.disabled = false;
        dmView.hidden = true;
        friendsView.hidden = false;
    }

    // Initial fetch just for the badge count
    refresh();
})();
