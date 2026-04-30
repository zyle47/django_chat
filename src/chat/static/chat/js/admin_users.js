let pendingForm = null;

function confirmDelete(btn) {
    pendingForm = btn.closest('form');
    document.getElementById('modal-username').textContent = btn.dataset.username;
    document.getElementById('delete-modal').classList.add('open');
}

function closeModal() {
    document.getElementById('delete-modal').classList.remove('open');
    pendingForm = null;
}

document.getElementById('modal-confirm').addEventListener('click', () => {
    if (pendingForm) pendingForm.submit();
});

document.getElementById('delete-modal').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
});

const tabs   = document.querySelectorAll('.tab');
const rows   = document.querySelectorAll('tbody tr[data-status]');
const counts = { pending: 0, registered: 0 };

rows.forEach(r => { counts[r.dataset.status] = (counts[r.dataset.status] || 0) + 1; });
document.getElementById('count-pending').textContent    = counts.pending    || 0;
document.getElementById('count-registered').textContent = counts.registered || 0;

function switchTab(target) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === target));
    rows.forEach(r => { r.hidden = r.dataset.status !== target; });
    document.getElementById('empty-pending').hidden    = target !== 'pending'    || counts.pending    > 0;
    document.getElementById('empty-registered').hidden = target !== 'registered' || counts.registered > 0;
}

tabs.forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));

// Default tab: registered
switchTab('registered');

document.querySelectorAll('.flash-notification').forEach(el => {
    setTimeout(() => {
        el.style.transition = 'opacity 0.8s ease';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 800);
    }, 6000);
});
