document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const resetBtn = document.getElementById('resetBtn');
    const toggleDarkModeBtn = document.getElementById('toggleDarkModeBtn');
    const fileNameDisplay = document.getElementById('fileNameDisplay');
    const toast = document.getElementById('toast');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const mainContainer = document.getElementById('mainContainer');
    const homeBtn = document.getElementById('homeBtn');

    let selectedFile = null;

    // Show Toast Notification
    function showToast(message) {
        toast.textContent = message;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3000);
    }

    // Apply Dark Mode from Local Storage
    function applyDarkModeFromStorage() {
        if (localStorage.getItem("darkMode") === "true") {
            document.body.classList.add("dark-mode");
            mainContainer.classList.add("dark-mode");
            if (dropZone) dropZone.classList.add("dark-mode");
        }
    }

    applyDarkModeFromStorage();

    // File Drag-and-Drop Logic
    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                selectedFile = files[0];
                fileInput.files = files;
                analyzeBtn.disabled = false;
                fileNameDisplay.textContent = `Selected File: ${selectedFile.name}`;
            }
        });

        dropZone.addEventListener('click', () => {
            fileInput.click();
        });
    }

    // File Input Logic
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const files = e.target.files;
            if (files.length > 0) {
                selectedFile = files[0];
                analyzeBtn.disabled = false;
                fileNameDisplay.textContent = `Selected File: ${selectedFile.name}`;
            }
        });
    }

    // Analyze Button Logic
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', () => {
            if (!selectedFile) return;

            const formData = new FormData();
            formData.append('file', selectedFile);
            mainContainer.classList.add('blur');
            loadingOverlay.classList.remove('hidden');

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                mainContainer.classList.remove('blur');
                loadingOverlay.classList.add('hidden');
                if (data.success && data.files && data.files.length > 0) {
                    const filename = data.files[0];
                    window.location.href = `/graphs?file=${encodeURIComponent(filename)}`;
                } else {
                    alert(data.message || "An error occurred during upload.");
                }
            })
            .catch(error => {
                mainContainer.classList.remove('blur');
                loadingOverlay.classList.add('hidden');
                showToast("An unexpected error occurred during upload.");
            });
        });
    }

    // Reset Button Logic
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            fetch('/reset', { method: 'GET' })
                .then(() => {
                    window.location.reload();
                })
                .catch((error) => {
                    console.error('Error resetting app:', error);
                    showToast('Reset failed.');
                });
        });
    }

    // Toggle Dark Mode Button Logic
    if (toggleDarkModeBtn) {
        console.log('Toggle Dark Mode button found and event listener attached.');
        toggleDarkModeBtn.addEventListener('click', (event) => {
            event.stopPropagation(); // Prevent interference
            console.log('Toggle Dark Mode button clicked.');
            const darkIsActive = document.body.classList.contains('dark-mode');
            const newDarkModeState = !darkIsActive;

            document.body.classList.toggle('dark-mode');
            if (mainContainer) mainContainer.classList.toggle('dark-mode');
            if (dropZone) dropZone.classList.toggle('dark-mode');

            const graphsContainer = document.querySelector('.graphs-container');
            if (graphsContainer) graphsContainer.classList.toggle('dark-mode');

            localStorage.setItem("darkMode", newDarkModeState);
        });
    } else {
        console.error('Toggle Dark Mode button not found.');
    }

    // Back to Home Button Logic
    if (homeBtn) {
        console.log('Back to Home button found and event listener attached.');
        homeBtn.addEventListener('click', (event) => {
            event.stopPropagation(); // Prevent interference
            console.log('Back to Home button clicked.');
            window.location.href = '/';
        });
    } else {
        console.error('Back to Home button not found.');
    }

    // Carousel Logic
    const images = document.querySelectorAll('.carousel-img');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    let currentIndex = 0;

    function showImage(index) {
        images.forEach((img, i) => {
            img.style.display = i === index ? 'block' : 'none';
        });
    }

    if (images.length > 0) {
        showImage(currentIndex);
    }

    if (prevBtn && nextBtn) {
        prevBtn.addEventListener('click', (event) => {
            event.stopPropagation(); // Prevent interference
            currentIndex = (currentIndex - 1 + images.length) % images.length;
            showImage(currentIndex);
        });

        nextBtn.addEventListener('click', (event) => {
            event.stopPropagation(); // Prevent interference
            currentIndex = (currentIndex + 1) % images.length;
            showImage(currentIndex);
        });
    }

    // Initialize the Bootstrap carousel manually
    const carouselElement = document.getElementById('graphCarousel');
    if (carouselElement) {
        const carousel = new bootstrap.Carousel(carouselElement, {
            interval: false, // Disable automatic cycling
            ride: false      // Ensure it doesn't start automatically
        });

        // Explicitly stop the carousel from cycling
        carousel.pause();

        console.log('Carousel initialized with manual controls.');
    }

    // Trigger Analysis on Enter Key
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            if (selectedFile && !analyzeBtn.disabled) {
                analyzeBtn.click(); // Simulate a click on the Analyze button
            }
        }
    });

    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.onsubmit = function(e) {
            e.preventDefault();
            showLoading();
            const files = document.getElementById('fileInput').files;
            const formData = new FormData();
            for (let file of files) formData.append('file', file);
            fetch('/upload', { method: 'POST', body: formData })
                .then(res => res.json())
                .then(data => {
                    hideLoading();
                    if (data.success) {
                        data.files.forEach(filename => renderFileComponent(filename));
                    }
                })
                .catch(() => hideLoading());
        };
    }

    function renderFileComponent(filename) {
        showLoading();
        fetch(`/api/graph-data?file=${encodeURIComponent(filename)}`)
            .then(res => res.json())
            .then(data => {
                const container = document.createElement('div');
                container.className = 'file-output';
                container.style = "border:1px solid #ccc; margin:30px 0; padding:20px; border-radius:8px;";
                container.innerHTML = `<h3>${filename}</h3>`;
                if (!data.success) {
                    container.innerHTML += `<p style="color:red;">${data.message}</p>`;
                } else {
                    container.innerHTML += `
                        <h4>JSON Output</h4>
                        <div>
                            ${renderGraphDataOutput(data.data, filename)}
                            <a href="/export-processed-data?file=${encodeURIComponent(filename)}" class="analyze-btn" download>⬇️ Export Processed Data (CSV)</a>
                        </div>
                    `;
                }
                document.getElementById('allGraphOutputs').appendChild(container);
                hideLoading();
            })
            .catch(() => {
                hideLoading();
            });
    }

    function showLoading() {
        document.getElementById('loadingOverlay').classList.remove('hidden');
    }

    function hideLoading() {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }

    const initialFile = getQueryParam('file');
    if (initialFile) {
        renderFileComponent(initialFile);
    } else {
        hideLoading();
    }
});

function renderGraphDataOutput(data, filename) {
    // Top 5 tokens by order count
    const topOrderTokens = Object.entries(data.token_counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

    // Top 5 tokens by quantity
    const topQtyTokens = Object.entries(data.quantity_per_token)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

    // Entries per hour table
    const entriesPerHourRows = Object.entries(data.entries_per_hour)
        .map(([hour, count]) =>
            `<tr><td>${hour}</td><td>${count}</td></tr>`
        ).join('');

    // Quantity per hour table
    const qtyPerHourRows = Object.entries(data.quantity_per_hour)
        .map(([hour, qty]) =>
            `<tr><td>${hour}</td><td>${qty}</td></tr>`
        ).join('');

    return `
        <div style="margin-bottom:30px;">
            <h4>Top 5 Tokens by Number of Orders</h4>
            <table style="border-collapse:collapse;margin-bottom:20px;">
                <thead>
                    <tr><th>Token</th><th>Order Count</th></tr>
                </thead>
                <tbody>
                    ${topOrderTokens.map(([token, count]) =>
                        `<tr><td>${token}</td><td>${count}</td></tr>`
                    ).join('')}
                </tbody>
            </table>

            <h4>Top 5 Tokens by Total Quantity</h4>
            <table style="border-collapse:collapse;margin-bottom:20px;">
                <thead>
                    <tr><th>Token</th><th>Total Quantity</th></tr>
                </thead>
                <tbody>
                    ${topQtyTokens.map(([token, qty]) =>
                        `<tr><td>${token}</td><td>${qty}</td></tr>`
                    ).join('')}
                </tbody>
            </table>

            <h4>Entries Per Hour</h4>
            <table style="border-collapse:collapse;margin-bottom:20px;">
                <thead>
                    <tr><th>Hour</th><th>Entries</th></tr>
                </thead>
                <tbody>
                    ${entriesPerHourRows}
                </tbody>
            </table>

            <h4>Quantity Per Hour</h4>
            <table style="border-collapse:collapse;">
                <thead>
                    <tr><th>Hour</th><th>Total Quantity</th></tr>
                </thead>
                <tbody>
                    ${qtyPerHourRows}
                </tbody>
            </table>
        </div>
    `;
}