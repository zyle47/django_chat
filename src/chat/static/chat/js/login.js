document.querySelectorAll('.flash-notification').forEach(el => {
    setTimeout(() => {
        el.style.transition = 'opacity 0.8s ease';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 800);
    }, 6000);
});
