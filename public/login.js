document.addEventListener('DOMContentLoaded', () => {
    // If already logged in, redirect to dashboard
    if (localStorage.getItem('token')) {
        window.location.href = '/index.html';
    }
});

async function handleAuth(action) {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('error-message');
    
    if (!email || !password) {
        errorDiv.textContent = 'Please enter both email and password';
        errorDiv.style.display = 'block';
        return;
    }
    
    errorDiv.style.display = 'none';
    const btn = document.getElementById(`btn-${action}`);
    const btnText = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.loader');
    
    if (loader) {
        btnText.classList.add('hidden');
        loader.classList.remove('hidden');
    }
    
    const endpoint = action === 'login' ? '/api/login' : '/api/register';
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });
        
        const result = await response.json();
        
        if (!response.ok || result.status === 'error') {
            throw new Error(result.message || 'Authentication failed');
        }
        
        if (action === 'register') {
            showToast('Registration successful! Please log in.');
            // Switch to login
            document.getElementById('password').value = '';
        } else if (action === 'login') {
            localStorage.setItem('token', result.data.token);
            window.location.href = '/index.html';
        }
        
    } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.style.display = 'block';
    } finally {
        if (loader) {
            btnText.classList.remove('hidden');
            loader.classList.add('hidden');
        }
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
