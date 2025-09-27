// Global variables
let currentFilename = null;
let currentFileType = null;
let pdfDoc = null;
let pageNum = 1;
let pageRendering = false;
let pageNumPending = null;
let scale = 1.2;
let canvas = null;
let ctx = null;
let currentPage = null;
let isDragging = false;
let startX, startY, scrollLeft, scrollTop;

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    const formEl = document.getElementById('invoiceForm');
    if (!formEl) {
        console.error('invoiceForm element not found');
        return;
    }

    canvas = document.getElementById('pdfCanvas');
    ctx = canvas.getContext('2d');

    // Set up PDF.js worker
    if (typeof pdfjsLib !== 'undefined') {
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    }

    formEl.addEventListener('submit', handleFileUpload);
    
    // Set up verify button
    document.getElementById('verifyBtn').addEventListener('click', handleVerification);
    
    // Set up retry button
    document.getElementById('retryBtn').addEventListener('click', handleRetryParsing);
    
    // Set up PDF navigation
    document.getElementById('prevPage').addEventListener('click', () => {
        if (pageNum <= 1) return;
        pageNum--;
        queueRenderPage(pageNum);
    });
    
    document.getElementById('nextPage').addEventListener('click', () => {
        if (pageNum >= pdfDoc.numPages) return;
        pageNum++;
        queueRenderPage(pageNum);
    });
    
    // Set up zoom controls
    document.getElementById('zoomIn').addEventListener('click', () => {
        scale = Math.min(scale * 1.2, 5.0);
        updateZoomLevel();
        queueRenderPage(pageNum);
    });
    
    document.getElementById('zoomOut').addEventListener('click', () => {
        scale = Math.max(scale / 1.2, 0.3);
        updateZoomLevel();
        queueRenderPage(pageNum);
    });
    
    document.getElementById('fitWidth').addEventListener('click', () => {
        if (currentPage) {
            const container = document.querySelector('.pdf-canvas-container');
            const containerWidth = container.clientWidth - 40; // Account for padding
            const pageWidth = currentPage.getViewport({scale: 1.0}).width;
            scale = containerWidth / pageWidth;
            updateZoomLevel();
            queueRenderPage(pageNum);
        }
    });
    
    document.getElementById('fitHeight').addEventListener('click', () => {
        if (currentPage) {
            const container = document.querySelector('.pdf-canvas-container');
            const containerHeight = container.clientHeight - 40; // Account for padding
            const pageHeight = currentPage.getViewport({scale: 1.0}).height;
            scale = containerHeight / pageHeight;
            updateZoomLevel();
            queueRenderPage(pageNum);
        }
    });
    
    document.getElementById('resetZoom').addEventListener('click', () => {
        scale = 1.2;
        updateZoomLevel();
        queueRenderPage(pageNum);
    });
    
    // Set up canvas dragging for panning when zoomed in
    canvas.addEventListener('mousedown', startDragging);
    canvas.addEventListener('mousemove', drag);
    canvas.addEventListener('mouseup', stopDragging);
    canvas.addEventListener('mouseleave', stopDragging);
    
    // Mouse wheel zoom
    const pdfContainer = document.getElementById('pdfContainer');
    pdfContainer.addEventListener('wheel', handleWheelZoom);
}

async function handleFileUpload(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('file');
    const file = fileInput.files[0];
    
    if (!file) {
        showError('Please select a file');
        return;
    }
    
    currentFilename = file.name;
    currentFileType = file.type;
    
    const formData = new FormData();
    formData.append('file', file);
    
    console.log('Uploading file:', file.name, 'Size:', file.size);
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        console.log('Response status:', response.status);
        console.log('Response data:', data);

        if (response.status === 200) {
            displayResults(data);
            loadFilePreview(file.name);
        } else if (response.status === 202 && data.results_url) {
            startPolling(data.results_url);
            loadFilePreview(file.name);
        } else {
            showError(data.error || 'Error processing file');
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    }
}

function startPolling(resultsUrl) {
    const maxAttempts = 10;
    const intervalMs = 3000;
    let attempts = 0;
    hideError();
    
    const poll = async () => {
        attempts++;
        console.log('Polling attempt', attempts);
        try {
            const resp = await fetch(resultsUrl, { cache: 'no-store' });
            if (resp.status === 200) {
                const data = await resp.json();
                displayResults(data);
                return;
            }
        } catch (e) {
            console.log('Polling error:', e);
        }
        if (attempts < maxAttempts) {
            setTimeout(poll, intervalMs);
        } else {
            showError('Processing timed out. Please retry later.');
        }
    };
    setTimeout(poll, intervalMs);
}

function displayResults(data) {
    const resultsContent = document.getElementById('resultsContent');
    resultsContent.innerHTML = '';
    
    // Create editable table
    const table = document.createElement('table');
    table.className = 'results-table';
    
    // Define the fields that should be editable
    const editableFields = ['vendor_name', 'invoice_number', 'invoice_date', 'total_amount', 'vendor_gstin', 'customer_gstin'];
    
    for (const [key, value] of Object.entries(data)) {
        if (key === 'id' || key === 'extracted_at' || key === 'file_path') continue;
        
        const row = table.insertRow();
        const cell1 = row.insertCell(0);
        const cell2 = row.insertCell(1);
        
        cell1.innerHTML = '<strong>' + formatFieldName(key) + '</strong>';
        
        if (editableFields.includes(key)) {
            const input = document.createElement('input');
            input.type = getInputType(key);
            input.value = value || '';
            input.dataset.field = key;
            input.className = 'editable-field';
            cell2.appendChild(input);
        } else {
            let displayValue = value || 'N/A';
            
            // Special formatting for processing tier
            if (key === 'processing_tier' && value) {
                displayValue = `${value} ${getTierIcon(value)}`;
            }
            
            cell2.innerHTML = displayValue;
        }
    }
    
    resultsContent.appendChild(table);
    
    // Show main content and update button states
    document.getElementById('mainContent').classList.add('active');
    document.getElementById('results').style.display = 'block';
    
    // Update retry button based on current tier
    const currentTier = data.processing_tier;
    updateRetryButtonText(currentTier);
    
    // Check if already verified
    const verifyBtn = document.getElementById('verifyBtn');
    if (data.verified) {
        verifyBtn.textContent = 'Verified ✓';
        verifyBtn.classList.add('verified');
        verifyBtn.disabled = true;
    } else {
        verifyBtn.textContent = 'Verified';
        verifyBtn.classList.remove('verified');
        verifyBtn.disabled = false;
    }
    
    hideError();
}

function formatFieldName(key) {
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function getInputType(key) {
    if (key === 'total_amount') return 'number';
    if (key === 'invoice_date') return 'date';
    return 'text';
}

async function handleVerification() {
    if (!currentFilename) {
        showError('No file uploaded');
        return;
    }
    
    // Collect data from editable fields
    const editableFields = document.querySelectorAll('.editable-field');
    const verifiedData = {};
    
    editableFields.forEach(field => {
        verifiedData[field.dataset.field] = field.value;
    });
    
    try {
        const response = await fetch(`/verify/${currentFilename}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(verifiedData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess('Data verified and updated successfully!');
            const verifyBtn = document.getElementById('verifyBtn');
            verifyBtn.textContent = 'Verified ✓';
            verifyBtn.classList.add('verified');
            verifyBtn.disabled = true;
        } else {
            showError(result.error || 'Failed to verify data');
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    }
}

async function handleRetryParsing() {
    if (!currentFilename) {
        showError('No file uploaded to retry');
        return;
    }
    
    const retryBtn = document.getElementById('retryBtn');
    const originalText = retryBtn.textContent;
    
    // Disable button and show loading state
    retryBtn.disabled = true;
    retryBtn.textContent = 'Retrying...';
    
    try {
        // Re-trigger the parsing by calling the reparse endpoint
        const response = await fetch(`/reparse/${currentFilename}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (response.status === 200) {
            // Immediate results
            displayResults(data);
            const tier = data.processing_tier || 'unknown';
            showSuccess(`File reparsed successfully using ${tier} tier!`);
        } else if (response.status === 202 && data.results_url) {
            // Start polling for results
            startPolling(data.results_url);
            showSuccess('Reparsing started, please wait...');
        } else {
            showError(data.error || 'Failed to reparse file');
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    } finally {
        // Re-enable button with updated text (will be set by displayResults if successful)
        if (retryBtn.textContent === 'Retrying...') {
            retryBtn.textContent = originalText;
            retryBtn.disabled = false;
        }
    }
}

async function loadFilePreview(filename) {
    const fileExtension = filename.split('.').pop().toLowerCase();
    
    if (fileExtension === 'pdf') {
        await loadPDFPreview(filename);
    } else if (['jpg', 'jpeg', 'png'].includes(fileExtension)) {
        loadImagePreview(filename);
    }
}

async function loadPDFPreview(filename) {
    try {
        const pdfContainer = document.getElementById('pdfContainer');
        const imagePreview = document.getElementById('imagePreview');
        
        pdfContainer.style.display = 'block';
        imagePreview.style.display = 'none';
        
        const loadingTask = pdfjsLib.getDocument(`/pdf/${filename}`);
        pdfDoc = await loadingTask.promise;
        
        document.getElementById('pageInfo').textContent = `Page 1 of ${pdfDoc.numPages}`;
        
        // Enable/disable navigation buttons
        document.getElementById('prevPage').disabled = true;
        document.getElementById('nextPage').disabled = pdfDoc.numPages <= 1;
        
        // Update zoom level display
        updateZoomLevel();
        
        // Render first page
        renderPage(1);
        
    } catch (error) {
        console.error('Error loading PDF:', error);
        showError('Failed to load PDF preview');
    }
}

function loadImagePreview(filename) {
    const pdfContainer = document.getElementById('pdfContainer');
    const imagePreview = document.getElementById('imagePreview');
    
    pdfContainer.style.display = 'none';
    imagePreview.style.display = 'block';
    
    imagePreview.innerHTML = `<img src="/uploads/${filename}" alt="Invoice Preview" />`;
}

function renderPage(num) {
    pageRendering = true;
    
    pdfDoc.getPage(num).then(function(page) {
        currentPage = page;
        const viewport = page.getViewport({scale: scale});
        canvas.height = viewport.height;
        canvas.width = viewport.width;
        
        const renderContext = {
            canvasContext: ctx,
            viewport: viewport
        };
        
        const renderTask = page.render(renderContext);
        
        renderTask.promise.then(function() {
            pageRendering = false;
            if (pageNumPending !== null) {
                renderPage(pageNumPending);
                pageNumPending = null;
            }
        });
    });
    
    document.getElementById('pageInfo').textContent = `Page ${num} of ${pdfDoc.numPages}`;
    document.getElementById('prevPage').disabled = (num <= 1);
    document.getElementById('nextPage').disabled = (num >= pdfDoc.numPages);
}

function queueRenderPage(num) {
    if (pageRendering) {
        pageNumPending = num;
    } else {
        renderPage(num);
    }
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

function hideError() {
    document.getElementById('error').style.display = 'none';
}

function showSuccess(message) {
    // Remove any existing status messages
    const existingStatus = document.querySelector('.status-message');
    if (existingStatus) {
        existingStatus.remove();
    }
    
    const statusDiv = document.createElement('div');
    statusDiv.className = 'status-message success';
    statusDiv.textContent = message;
    
    const verifySection = document.getElementById('verifySection');
    verifySection.insertBefore(statusDiv, verifySection.firstChild);
    
    // Remove success message after 3 seconds
    setTimeout(() => {
        if (statusDiv.parentNode) {
            statusDiv.remove();
        }
    }, 3000);
}

function updateZoomLevel() {
    const zoomPercentage = Math.round(scale * 100);
    document.getElementById('zoomLevel').textContent = `${zoomPercentage}%`;
}

function handleWheelZoom(e) {
    if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        scale = Math.max(0.3, Math.min(5.0, scale * delta));
        
        updateZoomLevel();
        queueRenderPage(pageNum);
    }
}

function startDragging(e) {
    if (scale <= 1.2) return; // Only allow dragging when zoomed in
    
    isDragging = true;
    const container = document.querySelector('.pdf-canvas-container');
    startX = e.pageX - container.offsetLeft;
    startY = e.pageY - container.offsetTop;
    scrollLeft = container.scrollLeft;
    scrollTop = container.scrollTop;
    canvas.style.cursor = 'grabbing';
}

function drag(e) {
    if (!isDragging) return;
    
    e.preventDefault();
    const container = document.querySelector('.pdf-canvas-container');
    const x = e.pageX - container.offsetLeft;
    const y = e.pageY - container.offsetTop;
    const walkX = (x - startX) * 2;
    const walkY = (y - startY) * 2;
    container.scrollLeft = scrollLeft - walkX;
    container.scrollTop = scrollTop - walkY;
}

function stopDragging() {
    isDragging = false;
    canvas.style.cursor = 'grab';
}

function getNextTierName(currentTier) {
    const tierHierarchy = {
        'RegexOnly': 'Regex+DocTR',
        'Regex': 'Regex+DocTR', 
        'Regex+DocTR': 'Text_QA',
        'Text_QA': 'LLM',
        'LLM': null
    };
    return tierHierarchy[currentTier] || 'Regex+DocTR';
}

function updateRetryButtonText(currentTier) {
    const retryBtn = document.getElementById('retryBtn');
    const nextTier = getNextTierName(currentTier);
    
    if (nextTier) {
        // Only show specific tier name for regex-based tiers
        if (currentTier === 'RegexOnly' || currentTier === 'Regex') {
            retryBtn.textContent = `Retry with ${nextTier}`;
        } else {
            retryBtn.textContent = 'Retry Parsing';
        }
        retryBtn.disabled = false;
    } else {
        retryBtn.textContent = 'Max Tier Reached';
        retryBtn.disabled = true;
    }
}