document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login.html';
        return;
    }

    loadSettings();

    document.getElementById('btn-save').addEventListener('click', saveSettings);
    document.getElementById('btn-logout').addEventListener('click', () => {
        localStorage.removeItem('token');
        window.location.href = '/login.html';
    });
});

async function loadSettings() {
    try {
        const response = await fetch('/api/settings', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (response.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/login.html';
            return;
        }
        
        const result = await response.json();
        if (result.status === 'success') {
            const data = result.data;
            document.getElementById('receive-emails').checked = data.receive_emails;
            
            if (data.providers.renac) {
                document.getElementById('renac-username').value = data.providers.renac.username || '';
                document.getElementById('renac-password').value = data.providers.renac.password || '';
                document.getElementById('renac-station').value = data.providers.renac.station_id || '';
            }
            
            if (data.providers.shinemonitor) {
                document.getElementById('shine-username').value = data.providers.shinemonitor.username || '';
                document.getElementById('shine-password').value = data.providers.shinemonitor.password || '';
                document.getElementById('shine-company').value = data.providers.shinemonitor.company_key || '';
                document.getElementById('shine-plant').value = data.providers.shinemonitor.plant_id || '';
            }
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
        showToast('Failed to load settings', 'error');
    }
}

async function saveSettings() {
    const btn = document.getElementById('btn-save');
    const btnText = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.loader');
    
    btnText.classList.add('hidden');
    loader.classList.remove('hidden');
    
    const payload = {
        receive_emails: document.getElementById('receive-emails').checked,
        providers: {
            renac: {
                username: document.getElementById('renac-username').value,
                password: document.getElementById('renac-password').value,
                station_id: document.getElementById('renac-station').value
            },
            shinemonitor: {
                username: document.getElementById('shine-username').value,
                password: document.getElementById('shine-password').value,
                company_key: document.getElementById('shine-company').value,
                plant_id: document.getElementById('shine-plant').value
            }
        }
    };
    
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify(payload)
        });
        
        if (response.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/login.html';
            return;
        }
        
        const result = await response.json();
        if (result.status === 'success') {
            showToast('Settings saved successfully!');
        } else {
            showToast(result.message || 'Failed to save settings', 'error');
        }
    } catch (error) {
        console.error('Failed to save settings:', error);
        showToast('Network error while saving settings', 'error');
    } finally {
        btnText.classList.remove('hidden');
        loader.classList.add('hidden');
    }
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.remove('hidden');
    void toast.offsetWidth;
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 4000);
}
