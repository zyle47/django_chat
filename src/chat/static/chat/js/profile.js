(function () {
    'use strict';

    // ── CSRF ──────────────────────────────────────────────────────────────────
    function getCsrf() {
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    // ── Modal helpers ─────────────────────────────────────────────────────────
    function openModal(el) { el.classList.add('open'); }
    function closeModal(el) { el.classList.remove('open'); }

    // ── Elements ──────────────────────────────────────────────────────────────
    const editModal      = document.getElementById('edit-profile-modal');
    const upgradeModal   = document.getElementById('upgrade-modal');
    const openEditBtn    = document.getElementById('open-edit-profile');
    const openUpgradeBtn = document.getElementById('open-upgrade');
    const closeEditBtn   = document.getElementById('close-edit-profile');
    const closeUpgradeBtn= document.getElementById('close-upgrade');

    if (!editModal || !upgradeModal) return;

    const fileInput      = document.getElementById('avatar-file-input');
    const currentImg     = document.getElementById('avatar-current-img');
    const placeholder    = document.getElementById('avatar-placeholder');
    const saveBtn        = document.getElementById('save-avatar-btn');
    const removeBtn      = document.getElementById('remove-avatar-btn');
    const errorDiv       = document.getElementById('edit-profile-error');
    const upgradeBody    = document.getElementById('upgrade-modal-body');

    // ── Edit Profile modal ────────────────────────────────────────────────────
    openEditBtn.addEventListener('click', function () {
        // Reset state
        fileInput.value = '';
        errorDiv.style.display = 'none';
        errorDiv.textContent = '';

        // Show current avatar if any badge img exists
        const badgeImg = document.querySelector('.user-badge .user-badge-av');
        if (badgeImg) {
            currentImg.src = badgeImg.src;
            currentImg.style.display = 'block';
            placeholder.style.display = 'none';
        } else {
            currentImg.style.display = 'none';
            placeholder.style.display = 'block';
        }

        openModal(editModal);
    });

    closeEditBtn.addEventListener('click', function () { closeModal(editModal); });

    // Close on backdrop click
    editModal.addEventListener('click', function (e) {
        if (e.target === editModal) closeModal(editModal);
    });

    // Live preview on file pick
    fileInput.addEventListener('change', function () {
        const file = fileInput.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function (ev) {
            currentImg.src = ev.target.result;
            currentImg.style.display = 'block';
            placeholder.style.display = 'none';
        };
        reader.readAsDataURL(file);
    });

    function showError(msg) {
        errorDiv.textContent = msg;
        errorDiv.style.display = 'block';
    }

    saveBtn.addEventListener('click', function () {
        errorDiv.style.display = 'none';
        const file = fileInput.files[0];
        if (!file) {
            showError('Please select an image file.');
            return;
        }
        const fd = new FormData();
        fd.append('avatar', file);
        fetch('/profile/edit/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrf() },
            body: fd,
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok) {
                    location.reload();
                } else {
                    showError(data.error || 'Unknown error.');
                }
            })
            .catch(function () { showError('Network error. Please try again.'); });
    });

    removeBtn.addEventListener('click', function () {
        errorDiv.style.display = 'none';
        const fd = new FormData();
        fd.append('action', 'remove');
        fetch('/profile/edit/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrf() },
            body: fd,
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok) {
                    location.reload();
                } else {
                    showError(data.error || 'Unknown error.');
                }
            })
            .catch(function () { showError('Network error. Please try again.'); });
    });

    // ── Upgrade modal ─────────────────────────────────────────────────────────
    openUpgradeBtn.addEventListener('click', function () {
        upgradeBody.innerHTML = '<div class="upgrade-loading">Loading&hellip;</div>';
        openModal(upgradeModal);

        fetch('/upgrade/', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(function (r) { return r.json(); })
            .then(function (data) { renderUpgrade(data); })
            .catch(function () {
                upgradeBody.innerHTML = '<div class="upgrade-loading">Failed to load. Please try again.</div>';
            });
    });

    closeUpgradeBtn.addEventListener('click', function () { closeModal(upgradeModal); });
    upgradeModal.addEventListener('click', function (e) {
        if (e.target === upgradeModal) closeModal(upgradeModal);
    });

    function escapeHtml(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function renderUpgrade(data) {
        const current = data.current_level || 'bronze';
        const tiers = data.tiers || {};
        const addresses = data.addresses || {};

        let html = '<div class="upgrade-tier-grid">';
        Object.keys(tiers).forEach(function (key) {
            const tier = tiers[key];
            const label = tier.label || key;
            const btc = tier.btc || '';
            const eth = tier.eth || '';
            const btcAddr = addresses.btc || '';
            const ethAddr = addresses.eth || '';
            const isCurrent = (key === current);

            html += '<div class="upgrade-tier-card">';
            html += '<div class="upgrade-tier-label tier-pill tier-' + escapeHtml(key) + '">' + escapeHtml(label) + '</div>';
            if (isCurrent) {
                html += '<div class="upgrade-current-badge">Current tier</div>';
            } else {
                if (btc && btcAddr) {
                    html += '<div class="upgrade-addr-row">';
                    html += '<span><strong>BTC:</strong> ' + escapeHtml(btc) + ' BTC</span>';
                    html += '<button class="upgrade-copy-btn" data-copy="' + escapeHtml(btcAddr) + '" title="Copy address">Copy</button>';
                    html += '</div>';
                    html += '<div style="font-size:0.65rem;color:var(--muted);word-break:break-all;">' + escapeHtml(btcAddr) + '</div>';
                }
                if (eth && ethAddr) {
                    html += '<div class="upgrade-addr-row">';
                    html += '<span><strong>ETH:</strong> ' + escapeHtml(eth) + ' ETH</span>';
                    html += '<button class="upgrade-copy-btn" data-copy="' + escapeHtml(ethAddr) + '" title="Copy address">Copy</button>';
                    html += '</div>';
                    html += '<div style="font-size:0.65rem;color:var(--muted);word-break:break-all;">' + escapeHtml(ethAddr) + '</div>';
                }
                html += '<button class="btn btn-secondary upgrade-send-btn" data-level="' + escapeHtml(key) + '">';
                html += 'I\'ve sent payment';
                html += '</button>';
            }
            html += '</div>';
        });
        html += '</div>';

        upgradeBody.innerHTML = html;

        // Wire copy buttons
        upgradeBody.querySelectorAll('.upgrade-copy-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const text = btn.getAttribute('data-copy');
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(text).then(function () {
                        btn.textContent = 'Copied!';
                        setTimeout(function () { btn.textContent = 'Copy'; }, 1500);
                    });
                }
            });
        });

        // Wire "I've sent payment" buttons
        upgradeBody.querySelectorAll('.upgrade-send-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const level = btn.getAttribute('data-level');
                const fd = new FormData();
                fd.append('requested_level', level);
                btn.disabled = true;
                btn.textContent = 'Sending…';
                fetch('/upgrade/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCsrf() },
                    body: fd,
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (data.ok) {
                            btn.closest('.upgrade-tier-card').innerHTML +=
                                '<div class="upgrade-success-note">Payment request submitted. Pending admin approval.</div>';
                            btn.remove();
                        } else {
                            btn.disabled = false;
                            btn.textContent = "I've sent payment";
                            alert(data.error || 'Error submitting request.');
                        }
                    })
                    .catch(function () {
                        btn.disabled = false;
                        btn.textContent = "I've sent payment";
                        alert('Network error. Please try again.');
                    });
            });
        });
    }
})();
