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
            window.location.href = '/login';
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
                window.location.href = '/login';
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

        if (combined.co2_saved !== undefined && combined.co2_saved !== null) {
            document.getElementById('val-co2').innerHTML = `${combined.co2_saved.toFixed(1)} <span class="unit">kg</span>`;
        } else {
            document.getElementById('val-co2').innerHTML = `- <span class="unit">kg</span>`;
        }
        
        document.getElementById('val-status').textContent = combined.inverters_online || 'Online';

        // Render Chart
        renderChart(data);

        // Lazy load heatmap after main chart renders
        setTimeout(loadHeatmap, 150);
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

    async function loadHeatmap() {
        const token = localStorage.getItem('token');
        if (!token) return;

        const loadingEl = document.getElementById('heatmap-loading');
        const gridEl = document.getElementById('heatmap-grid');
        if (!gridEl) return;

        try {
            const res = await fetch('/api/heatmap', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error('Failed to fetch heatmap data');
            const json = await res.json();
            const payload = json.data || {};
            const daysData = payload.days || {};
            const maxKwh = payload.max_kwh || 1.0;

            const dateKeys = Object.keys(daysData).sort();
            if (dateKeys.length === 0) {
                loadingEl.innerHTML = '<span style="color: var(--text-secondary); font-size: 0.85rem;">No historical data available.</span>';
                return;
            }

            gridEl.innerHTML = '';
            
            // Build weekly columns
            let currentCol = document.createElement('div');
            currentCol.className = 'heatmap-col';
            
            // Find start day of week for first date
            const firstDate = new Date(dateKeys[0]);
            const startDayOfWeek = firstDate.getDay(); // 0 is Sunday
            
            for (let i = 0; i < startDayOfWeek; i++) {
                const emptyCell = document.createElement('div');
                emptyCell.className = 'heatmap-cell';
                emptyCell.style.opacity = '0';
                emptyCell.style.pointerEvents = 'none';
                currentCol.appendChild(emptyCell);
            }

            dateKeys.forEach(dateStr => {
                const item = daysData[dateStr] || { total: 0, renac: 0, shinemonitor: 0 };
                const total = item.total || 0;
                
                let lvl = 'lvl-0';
                if (total > 0) {
                    const ratio = total / maxKwh;
                    if (ratio <= 0.25) lvl = 'lvl-1';
                    else if (ratio <= 0.50) lvl = 'lvl-2';
                    else if (ratio <= 0.75) lvl = 'lvl-3';
                    else lvl = 'lvl-4';
                }

                const cell = document.createElement('div');
                cell.className = `heatmap-cell ${lvl}`;
                cell.dataset.date = dateStr;
                cell.dataset.total = total.toFixed(2);
                cell.dataset.renac = (item.renac || 0).toFixed(2);
                cell.dataset.shine = (item.shinemonitor || 0).toFixed(2);

                cell.addEventListener('mouseenter', showHeatmapTooltip);
                cell.addEventListener('mouseleave', hideHeatmapTooltip);

                currentCol.appendChild(cell);

                const d = new Date(dateStr);
                if (d.getDay() === 6) {
                    gridEl.appendChild(currentCol);
                    currentCol = document.createElement('div');
                    currentCol.className = 'heatmap-col';
                }
            });

            if (currentCol.children.length > 0) {
                gridEl.appendChild(currentCol);
            }

            loadingEl.classList.add('hidden');
            gridEl.classList.remove('hidden');

        } catch (err) {
            console.error('Heatmap error:', err);
            if (loadingEl) {
                loadingEl.innerHTML = '<span style="color: var(--text-secondary); font-size: 0.85rem;">Heatmap unavailable.</span>';
            }
        }
    }

    let tooltipEl = null;
    function showHeatmapTooltip(e) {
        if (!tooltipEl) {
            tooltipEl = document.createElement('div');
            tooltipEl.className = 'heatmap-tooltip';
            document.body.appendChild(tooltipEl);
        }

        const dateStr = this.dataset.date;
        const total = this.dataset.total;
        const renac = this.dataset.renac;
        const shine = this.dataset.shine;

        const dt = new Date(dateStr);
        const formattedDate = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

        tooltipEl.innerHTML = `<strong>${formattedDate}</strong>: ${total} kWh<br><span style="color: #94a3b8; font-size: 0.75rem;">RENAC: ${renac} kWh | ShineMonitor: ${shine} kWh</span>`;
        tooltipEl.style.display = 'block';

        const rect = this.getBoundingClientRect();
        tooltipEl.style.left = `${rect.left + window.scrollX - (tooltipEl.offsetWidth / 2) + (rect.width / 2)}px`;
        tooltipEl.style.top = `${rect.top + window.scrollY - tooltipEl.offsetHeight - 8}px`;
    }

    function hideHeatmapTooltip() {
        if (tooltipEl) {
            tooltipEl.style.display = 'none';
        }
    }
});
