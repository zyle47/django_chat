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
