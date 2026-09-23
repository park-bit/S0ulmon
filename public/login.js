document.addEventListener('DOMContentLoaded', () => {
    // If already logged in, redirect to dashboard
    if (localStorage.getItem('token')) {
        window.location.href = '/index.html';
    }
});

function switchView(viewId) {
    const views = ['view-login', 'view-forgot', 'view-reset'];
    views.forEach(v => {
        const el = document.getElementById(v);
        if (v === viewId) {
            el.classList.remove('hidden');
        } else {
            el.classList.add('hidden');
        }
    });
}

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

async function requestOTP() {
    const email = document.getElementById('forgot-email').value;
    const errorDiv = document.getElementById('forgot-error');
    
    if (!email) {
        errorDiv.textContent = 'Please enter your email';
        errorDiv.style.display = 'block';
        return;
    }
    
    errorDiv.style.display = 'none';
    const btn = document.getElementById('btn-forgot');
    const btnText = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.loader');
    
    btnText.classList.add('hidden');
    loader.classList.remove('hidden');
    
    try {
        const response = await fetch('/api/forgot_password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        
        const result = await response.json();
        
        if (!response.ok || result.status === 'error') {
            throw new Error(result.message || 'Failed to send OTP');
        }
        
        showToast('OTP sent to your email.');
        // Store email globally for the next step
        window.resetEmail = email;
        switchView('view-reset');
        
    } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.style.display = 'block';
    } finally {
        btnText.classList.remove('hidden');
        loader.classList.add('hidden');
    }
}

async function resetPassword() {
    const otp = document.getElementById('reset-otp').value;
    const password = document.getElementById('reset-password').value;
    const email = window.resetEmail || document.getElementById('forgot-email').value;
    const errorDiv = document.getElementById('reset-error');
    
    if (!otp || !password || !email) {
        errorDiv.textContent = 'Please enter OTP and new password';
        errorDiv.style.display = 'block';
        return;
    }
    
    errorDiv.style.display = 'none';
    const btn = document.getElementById('btn-reset');
    const btnText = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.loader');
    
    btnText.classList.add('hidden');
    loader.classList.remove('hidden');
    
    try {
        const response = await fetch('/api/reset_password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, otp, new_password: password })
        });
        
        const result = await response.json();
        
        if (!response.ok || result.status === 'error') {
            throw new Error(result.message || 'Password reset failed');
        }
        
        showToast('Password reset successful. Please log in.');
        document.getElementById('password').value = '';
        switchView('view-login');
        
    } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.style.display = 'block';
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
