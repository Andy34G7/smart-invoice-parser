document.addEventListener('DOMContentLoaded', () => {
const formEl = document.getElementById('invoiceForm');
if(!formEl){
    console.error('invoiceForm element not found');
    return;
}
formEl.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('file');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a file');
        return;
    }
    
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
            // Immediate results
            displayResults(data);
        } else if (response.status === 202 && data.results_url) {
            // Start polling
            startPolling(data.results_url);
        } else {
            document.getElementById('error').textContent = data.error || 'Error processing file';
            document.getElementById('error').style.display = 'block';
        }
    } catch (error) {
        document.getElementById('error').textContent = 'Network error: ' + error.message;
        document.getElementById('error').style.display = 'block';
    }
}); // submit handler end
}); // DOMContentLoaded end

async function fetchResults(resultsUrl) {
    try {
        const response = await fetch(resultsUrl);
        const data = await response.json();
        
        if (response.ok) {
            displayResults(data);
        } else {
            document.getElementById('error').textContent = data.error || 'Results not found';
            document.getElementById('error').style.display = 'block';
        }
    } catch (error) {
        document.getElementById('error').textContent = 'Error fetching results: ' + error.message;
        document.getElementById('error').style.display = 'block';
    }
}

function startPolling(resultsUrl) {
    const maxAttempts = 10;
    const intervalMs = 3000;
    let attempts = 0;
    document.getElementById('error').style.display = 'none';
    const poll = async () => {
        attempts++;
        console.log('Polling attempt', attempts);
        try {
            const resp = await fetch(resultsUrl, { cache: 'no-store' });
            if (resp.status === 200) {
                const data = await resp.json();
                displayResults(data);
                return; // stop polling
            }
        } catch (e) {
            console.log('Polling error:', e);
        }
        if (attempts < maxAttempts) {
            setTimeout(poll, intervalMs);
        } else {
            document.getElementById('error').textContent = 'Processing timed out. Please retry later.';
            document.getElementById('error').style.display = 'block';
        }
    };
    setTimeout(poll, intervalMs);
}

function displayResults(data) {
    const resultsContent = document.getElementById('resultsContent');
    resultsContent.innerHTML = '';
    
    const table = document.createElement('table');
    table.border = '1';
    
    for (const [key, value] of Object.entries(data)) {
        const row = table.insertRow();
        const cell1 = row.insertCell(0);
        const cell2 = row.insertCell(1);
        cell1.innerHTML = '<strong>' + key.replace(/_/g, ' ').toUpperCase() + '</strong>';
        cell2.innerHTML = value || 'N/A';
    }
    
    resultsContent.appendChild(table);
    document.getElementById('results').style.display = 'block';
}