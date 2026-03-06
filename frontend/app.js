document.addEventListener('DOMContentLoaded', () => {
    const navButtons = document.querySelectorAll('.nav-btn');
    const sections = document.querySelectorAll('.view-section');

    // Handle tab switching
    navButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Remove active states
            navButtons.forEach(b => b.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));

            // Set new active states
            e.target.classList.add('active');
            const targetId = e.target.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
        });
    });

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