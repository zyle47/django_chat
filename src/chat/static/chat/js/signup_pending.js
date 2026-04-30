let s = 5;
const el = document.getElementById('redirect-seconds');
const t = setInterval(() => {
    s -= 1;
    if (s <= 0) { clearInterval(t); location.href = '/'; return; }
    el.textContent = String(s);
}, 1000);
