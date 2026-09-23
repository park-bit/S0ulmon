document.addEventListener('DOMContentLoaded', () => {
    const btnEmail = document.getElementById('btn-email');
    const btnText = btnEmail.querySelector('.btn-text');
    const btnLoader = btnEmail.querySelector('.loader');
    
    const loadingOverlay = document.getElementById('loading-overlay');
    const dashboard = document.getElementById('dashboard');
    const toast = document.getElementById('toast');
    
    let chartInstance = null;

    // Fetch stats on load
    fetchStats();

    // Event Listeners
    btnEmail.addEventListener('click', sendEmailReport);

    async function fetchStats() {
        const token = localStorage.getItem('token');
        if (!token) {
            window.location.href = '/login.html';
            return;
        }
        
        try {
            const response = await fetch('/api/stats', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.status === 401) {
                localStorage.removeItem('token');
                window.location.href = '/login.html';
                return;
            }
            
            if (!response.ok) throw new Error('Failed to fetch data');
            const data = await response.json();
            
            updateUI(data);
            
            // Hide loading, show dashboard
            loadingOverlay.classList.remove('active');
            loadingOverlay.classList.add('hidden');
            dashboard.classList.remove('hidden');
            
        } catch (error) {
            console.error('Error:', error);
            showToast('Failed to load solar data. Please refresh.', 'error');
            loadingOverlay.querySelector('p').textContent = 'Error connecting to inverters.';
        }
    }

    function updateUI(data) {
        const combined = data.combined || {};
        // Update stats
        document.getElementById('val-today').innerHTML = `${(combined.today_generation || 0).toFixed(2)} <span class="unit">kWh</span>`;
        document.getElementById('val-live').innerHTML = `${(combined.live_power || 0).toFixed(2)} <span class="unit">kW</span>`;
        
        document.getElementById('val-month').innerHTML = `${combined.month_generation ? combined.month_generation.toFixed(2) : '-'} <span class="unit">kWh</span>`;
        document.getElementById('val-total').innerHTML = `${combined.total_generation ? combined.total_generation.toFixed(2) : '-'} <span class="unit">kWh</span>`;

        // Render Chart
        renderChart(data);
    }

    function renderChart(data) {
        const ctx = document.getElementById('weeklyChart').getContext('2d');
        
        const renacHistory = (data.renac && data.renac.history) || {};
        const shineHistory = (data.shinemonitor && data.shinemonitor.history) || {};
        
        // Get all unique dates
        const allDates = new Set([...Object.keys(renacHistory), ...Object.keys(shineHistory)]);
        const dates = Array.from(allDates).sort();
        
        const labels = dates.map(d => {
            const dt = new Date(d);
            return dt.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric' });
        });
        
        const renacValues = dates.map(d => (renacHistory[d] || 0).toFixed(2));
        const shineValues = dates.map(d => (shineHistory[d] || 0).toFixed(2));

        if (chartInstance) {
            chartInstance.destroy();
        }

        Chart.defaults.color = '#94a3b8';
        Chart.defaults.font.family = "'Inter', sans-serif";

        chartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'RENAC (kWh)',
                        data: renacValues,
                        backgroundColor: 'rgba(59, 130, 246, 0.8)',
                        borderColor: 'rgb(59, 130, 246)',
                        borderWidth: 1,
                        borderRadius: 4,
                        hoverBackgroundColor: 'rgba(59, 130, 246, 1)'
                    },
                    {
                        label: 'ShineMonitor (kWh)',
                        data: shineValues,
                        backgroundColor: 'rgba(16, 185, 129, 0.8)',
                        borderColor: 'rgb(16, 185, 129)',
                        borderWidth: 1,
                        borderRadius: 4,
                        hoverBackgroundColor: 'rgba(16, 185, 129, 1)'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: { color: '#e2e8f0' }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleFont: { size: 14, family: "'Outfit', sans-serif" },
                        bodyFont: { size: 14, family: "'Inter', sans-serif" },
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: true
                    }
                },
                scales: {
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)',
                            drawBorder: false
                        },
                        title: {
                            display: true,
                            text: 'Energy (kWh)',
                            font: { size: 12, family: "'Inter', sans-serif" }
                        }
                    },
                    x: {
                        stacked: true,
                        grid: {
                            display: false,
                            drawBorder: false
                        }
                    }
                }
            }
        });
    }

    async function sendEmailReport() {
        const token = localStorage.getItem('token');
        if (!token) return;
        
        setButtonLoading(true);
        
        try {
            const response = await fetch('/api/send_email', { 
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (!response.ok) throw new Error('Failed to send email');
            
            const result = await response.json();
            
            if (result.status === 'success') {
                showToast('Email report sent successfully!');
            } else {
                throw new Error(result.message || 'Unknown error');
            }
        } catch (error) {
            console.error('Error:', error);
            showToast('Failed to send email report.', 'error');
        } finally {
            setButtonLoading(false);
        }
    }

    function setButtonLoading(isLoading) {
        if (isLoading) {
            btnEmail.disabled = true;
            btnText.classList.add('hidden');
            btnLoader.classList.remove('hidden');
        } else {
            btnEmail.disabled = false;
            btnText.classList.remove('hidden');
            btnLoader.classList.add('hidden');
        }
    }

    function showToast(message, type = 'success') {
        toast.textContent = message;
        toast.className = `toast ${type}`;
        
        // Remove hidden class but trigger reflow so animation runs
        toast.classList.remove('hidden');
        void toast.offsetWidth;
        
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 4000);
    }
});
