document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    loadSettings();

    document.getElementById('btn-save').addEventListener('click', saveSettings);
    document.getElementById('btn-logout').addEventListener('click', () => {
        localStorage.removeItem('token');
        window.location.href = '/login';
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
            window.location.href = '/login';
            return;
        }
        
        const result = await response.json();
        if (result.status === 'success') {
            const data = result.data || {};
            const emailToggle = document.getElementById('receive-emails') || document.getElementById('receive_emails');
            if (emailToggle) {
                emailToggle.checked = !!data.receive_emails;
            }
            
            const providers = data.providers || {};
            if (providers.renac) {
                const ru = document.getElementById('renac-username');
                const rp = document.getElementById('renac-password');
                const rs = document.getElementById('renac-station');
                if (ru) ru.value = providers.renac.username || '';
                if (rp) rp.value = providers.renac.password || '';
                if (rs) rs.value = providers.renac.station_id || '';
            }
            
            if (providers.shinemonitor) {
                const su = document.getElementById('shine-username');
                const sp = document.getElementById('shine-password');
                const sc = document.getElementById('shine-company');
                const spl = document.getElementById('shine-plant');
                if (su) su.value = providers.shinemonitor.username || '';
                if (sp) sp.value = providers.shinemonitor.password || '';
                if (sc) sc.value = providers.shinemonitor.company_key || '';
                if (spl) spl.value = providers.shinemonitor.plant_id || '';
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
    
    const emailCheckbox = document.getElementById('receive-emails') || document.getElementById('receive_emails');
    const payload = {
        receive_emails: emailCheckbox ? emailCheckbox.checked : false,
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
            window.location.href = '/login';
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

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/login';
}
