/**
 * Curation Interface JavaScript
 * Handles timer, AJAX requests for tagging and verification
 */

// Timer state
let timerInterval = null;
let startTime = null;
let elapsedSeconds = 0;
let chunksCurated = 0;

/**
 * Initialize curation functionality
 */
function initializeCuration() {
    // Timer controls
    const startBtn = document.getElementById('start-timer');
    const stopBtn = document.getElementById('stop-timer');

    if (startBtn) {
        startBtn.addEventListener('click', startTimer);
    }

    if (stopBtn) {
        stopBtn.addEventListener('click', stopTimer);
    }

    // Tag buttons
    const tagButtons = document.querySelectorAll('.btn-tag');
    tagButtons.forEach(btn => {
        btn.addEventListener('click', handleTagLifecycle);
    });

    // Verify buttons
    const verifyButtons = document.querySelectorAll('.btn-verify');
    verifyButtons.forEach(btn => {
        btn.addEventListener('click', handleVerifyChunk);
    });
}

/**
 * Start curation session timer
 */
function startTimer() {
    const startBtn = document.getElementById('start-timer');
    const stopBtn = document.getElementById('stop-timer');

    startTime = Date.now();
    timerInterval = setInterval(updateTimer, 1000);

    startBtn.disabled = true;
    stopBtn.disabled = false;

    console.log('Session started');
}

/**
 * Stop curation session timer and log time
 */
function stopTimer() {
    const startBtn = document.getElementById('start-timer');
    const stopBtn = document.getElementById('stop-timer');

    clearInterval(timerInterval);

    const durationSeconds = Math.floor((Date.now() - startTime) / 1000);

    // Log time to backend
    fetch('/api/curate/time', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            duration_seconds: durationSeconds,
            chunks_curated: chunksCurated
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`Session logged: ${durationSeconds}s, ${chunksCurated} chunks`);
            alert(`Session complete! Time: ${formatTime(durationSeconds)}, Chunks: ${chunksCurated}`);
        } else {
            console.error('Failed to log session:', data.error);
        }
    })
    .catch(error => {
        console.error('Error logging session:', error);
    });

    startBtn.disabled = false;
    stopBtn.disabled = true;
    elapsedSeconds = 0;
    chunksCurated = 0;
    updateTimer();

    console.log('Session stopped');
}

/**
 * Update timer display
 */
function updateTimer() {
    const timerDisplay = document.getElementById('timer');

    if (startTime) {
        elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
    }

    timerDisplay.textContent = formatTime(elapsedSeconds);
}

/**
 * Format seconds to MM:SS
 */
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

/**
 * Handle lifecycle tagging
 */
function handleTagLifecycle(event) {
    const btn = event.target;
    const chunkId = btn.getAttribute('data-chunk-id');
    const select = document.querySelector(`.lifecycle-select[data-chunk-id="${chunkId}"]`);
    const lifecycle = select.value;

    // Send tag request
    fetch('/api/curate/tag', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            chunk_id: chunkId,
            lifecycle: lifecycle
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`Tagged chunk ${chunkId} as ${lifecycle}`);
            btn.textContent = '✓ Tagged';
            btn.disabled = true;
            btn.classList.remove('btn-tag');
            btn.classList.add('btn-secondary');
        } else {
            console.error('Failed to tag chunk:', data.error);
            alert('Failed to tag chunk. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error tagging chunk:', error);
        alert('Error tagging chunk. Please try again.');
    });
}

/**
 * Handle chunk verification
 */
function handleVerifyChunk(event) {
    const btn = event.target;
    const chunkId = btn.getAttribute('data-chunk-id');

    // Send verify request
    fetch('/api/curate/verify', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            chunk_id: chunkId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`Verified chunk ${chunkId}`);

            // Update UI
            const card = document.querySelector(`.chunk-card[data-chunk-id="${chunkId}"]`);
            const statusSpan = card.querySelector('.chunk-status');
            statusSpan.textContent = '✅ Verified';

            // Disable buttons
            btn.textContent = '✓ Verified';
            btn.disabled = true;

            // Update stats
            chunksCurated++;
            document.getElementById('chunks-curated').textContent = chunksCurated;

            const remaining = document.querySelectorAll('.chunk-card').length - chunksCurated;
            document.getElementById('chunks-remaining').textContent = remaining;

            // Fade out card after delay
            setTimeout(() => {
                card.style.opacity = '0.5';
            }, 500);
        } else {
            console.error('Failed to verify chunk:', data.error);
            alert('Failed to verify chunk. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error verifying chunk:', error);
        alert('Error verifying chunk. Please try again.');
    });
}
