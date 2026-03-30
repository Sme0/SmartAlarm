document.addEventListener('DOMContentLoaded', () => {
    const navButtons = document.querySelectorAll('.nav-btn');
    const sections = document.querySelectorAll('.view-section');

    const activateTab = (targetId, syncHash = false) => {
        if (!targetId) return;
        const targetSection = document.getElementById(targetId);
        if (!targetSection) return;

        navButtons.forEach(b => b.classList.remove('active'));
        sections.forEach(s => s.classList.remove('active'));

        const matchingButton = Array.from(navButtons).find(
            btn => btn.getAttribute('data-target') === targetId
        );

        if (matchingButton) matchingButton.classList.add('active');
        targetSection.classList.add('active');

        if (syncHash && window.location.hash !== `#${targetId}`) {
            history.replaceState(null, '', `#${targetId}`);
        }
    };

    // Handle tab switching
    navButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const targetId = e.currentTarget.getAttribute('data-target');
            activateTab(targetId, true);
        });
    });

    // Initialize account tab on load: hash target first, otherwise first available tab.
    const hashTarget = (window.location.hash || '').replace('#', '');
    if (hashTarget) {
        activateTab(hashTarget, false);
    } else if (navButtons.length > 0) {
        activateTab(navButtons[0].getAttribute('data-target'), false);
    }

    // Handle device pairing simulation
    const pairBtn = document.getElementById('btn-pair');
    const deviceInput = document.getElementById('device-code');
    const pairStatus = document.getElementById('pair-status');

    if (pairBtn) {
        pairBtn.addEventListener('click', () => {
            if (deviceInput.value.trim() !== '') {
                deviceInput.value = '';
                pairStatus.classList.remove('hidden');
                
                // Hide message after 3 seconds
                setTimeout(() => {
                    pairStatus.classList.add('hidden');
                }, 3000);
            }
        });
    }
});