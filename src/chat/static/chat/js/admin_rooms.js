const tabs   = document.querySelectorAll('.tab');
const rows   = document.querySelectorAll('tbody tr[data-status]');
const counts = { active: 0, deleted: 0 };

rows.forEach(r => { counts[r.dataset.status] = (counts[r.dataset.status] || 0) + 1; });
document.getElementById('count-active').textContent  = counts.active  || 0;
document.getElementById('count-deleted').textContent = counts.deleted || 0;

function switchTab(target) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === target));
    rows.forEach(r => { r.hidden = r.dataset.status !== target; });
    document.getElementById('empty-active').hidden  = target !== 'active'  || counts.active  > 0;
    document.getElementById('empty-deleted').hidden = target !== 'deleted' || counts.deleted > 0;
}

tabs.forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));

// Default tab: deleted
switchTab('deleted');

let pendingForm = null;
function confirmDelete(btn) {
    pendingForm = btn.closest('form');
    document.getElementById('modal-roomname').textContent = btn.dataset.roomname;
    document.getElementById('delete-modal').classList.add('open');
}
function closeModal() {
    document.getElementById('delete-modal').classList.remove('open');
    pendingForm = null;
}
document.getElementById('modal-confirm').addEventListener('click', () => { if (pendingForm) pendingForm.submit(); });
document.getElementById('delete-modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });

document.querySelectorAll('.flash-notification').forEach(el => {
    setTimeout(() => {
        el.style.transition = 'opacity 0.8s ease';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 800);
    }, 6000);
});
