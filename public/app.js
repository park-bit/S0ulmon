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
        try {
            const response = await fetch('/api/stats');
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
        // Update stats
        document.getElementById('val-today').innerHTML = `${data.today_generation.toFixed(2)} <span class="unit">kWh</span>`;
        document.getElementById('val-live').innerHTML = `${data.live_power.toFixed(2)} <span class="unit">kW</span>`;
        
        // Month and total placeholder (we'll implement backend for these later if requested)
        document.getElementById('val-month').innerHTML = `${data.month_generation ? data.month_generation.toFixed(2) : '-'} <span class="unit">kWh</span>`;
        document.getElementById('val-total').innerHTML = `${data.total_generation ? data.total_generation.toFixed(2) : '-'} <span class="unit">kWh</span>`;

        // Render Chart
        renderChart(data.history);
    }

    function renderChart(historyData) {
        const ctx = document.getElementById('weeklyChart').getContext('2d');
        
        // Sort dates chronologically
        const dates = Object.keys(historyData).sort();
        
        const labels = dates.map(d => {
            const dt = new Date(d);
            return dt.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric' });
        });
        
        const values = dates.map(d => historyData[d].toFixed(2));

        if (chartInstance) {
            chartInstance.destroy();
        }

        Chart.defaults.color = '#94a3b8';
        Chart.defaults.font.family = "'Inter', sans-serif";

        chartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Total Yield (kWh)',
                    data: values,
                    backgroundColor: 'rgba(59, 130, 246, 0.8)',
                    borderColor: 'rgb(59, 130, 246)',
                    borderWidth: 1,
                    borderRadius: 6,
                    hoverBackgroundColor: 'rgba(59, 130, 246, 1)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleFont: { size: 14, family: "'Outfit', sans-serif" },
                        bodyFont: { size: 14, family: "'Inter', sans-serif" },
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: false
                    }
                },
                scales: {
                    y: {
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
        setButtonLoading(true);
        
        try {
            const response = await fetch('/api/send_email', { method: 'POST' });
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
