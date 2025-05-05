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
                if (data.success) {
                    window.location.href = '/graphs';
                } else {
                    showToast(data.message || "An error occurred during upload.");
                }
            })
            .catch(error => {
                console.error('Upload error:', error);
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
});
