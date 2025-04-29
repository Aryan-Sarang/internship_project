document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const resetBtn = document.getElementById('resetBtn');
    const toggleDarkModeBtn = document.getElementById('toggleDarkModeBtn');
    const fileNameDisplay = document.getElementById('fileNameDisplay');
    const toast = document.getElementById('toast');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const mainContainer = document.getElementById('mainContainer');

    let selectedFile = null;

    function showToast(message) {
        toast.textContent = message;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3000);
    }

    function applyDarkModeFromStorage() {
        if (localStorage.getItem("darkMode") === "true") {
            document.body.classList.add("dark-mode");
            mainContainer.classList.add("dark-mode");
            dropZone.classList.add("dark-mode");
        }
    }

    applyDarkModeFromStorage();

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
                    window.location.href = '/graphs'; // Redirect after successful upload
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

    if (toggleDarkModeBtn) {
        toggleDarkModeBtn.addEventListener('click', () => {
            const darkIsActive = document.body.classList.contains('dark-mode');
            const newDarkModeState = !darkIsActive;
        
            document.body.classList.toggle('dark-mode');
            if (mainContainer) mainContainer.classList.toggle('dark-mode');
        
            const dropZone = document.getElementById('dropZone');
            if (dropZone) dropZone.classList.toggle('dark-mode');
        
            const graphsContainer = document.querySelector('.graphs-container');
            if (graphsContainer) graphsContainer.classList.toggle('dark-mode');
        
            localStorage.setItem("darkMode", newDarkModeState);
        });
        
    }
});

const homeBtn = document.getElementById('homeBtn');
if (homeBtn) {
    homeBtn.addEventListener('click', () => {
        window.location.href = '/reset'; // triggers reset route
    });
}

document.getElementById("uploadForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.target);

    const response = await fetch("/upload", {
        method: "POST",
        body: formData,
    });

    if (response.ok) {
        window.location.href = "/graphs";  // Redirect to the graphs page
    } else {
        const result = await response.json();
        alert(result.message || "An error occurred while uploading the file.");
    }
});