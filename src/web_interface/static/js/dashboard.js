/**
 * Dashboard Principal - MediocreToons Auto Uploader
 * Sistema completo de controle e monitoramento
 */

class DashboardManager {
    constructor() {
        this.updateInterval = null;
        this.charts = {};
        this.timerUpdateInterval = null;
        this.startTime = Date.now();
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.initCharts();
        this.startAutoUpdate();
        this.updateTimer();
        this.updateUptime();
        
        console.log('🚀 Dashboard MediocreToons inicializado');
    }

    setupEventListeners() {
        // Timer Controls
        document.getElementById('btn-start-timer')?.addEventListener('click', () => this.controlTimer('start'));
        document.getElementById('btn-pause-timer')?.addEventListener('click', () => this.controlTimer('pause'));
        document.getElementById('btn-stop-timer')?.addEventListener('click', () => this.controlTimer('stop'));
        document.getElementById('btn-reset-timer')?.addEventListener('click', () => this.controlTimer('reset'));
        
        // Timer Interval Change
        document.getElementById('timer-interval')?.addEventListener('change', (e) => this.updateTimerInterval(e.target.value));
        
        // Refresh Logs
        document.getElementById('refresh-logs')?.addEventListener('click', () => this.refreshLogs());
        
        // Auto-refresh toggle (if exists)
        document.getElementById('auto-refresh-toggle')?.addEventListener('change', (e) => {
            if (e.target.checked) {
                this.startAutoUpdate();
            } else {
                this.stopAutoUpdate();
            }
        });
    }

    async controlTimer(action) {
        this.showLoading(true);
        
        try {
            const response = await fetch('/api/dashboard/timer/control', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ action: action })
            });

            const data = await response.json();

            if (data.success) {
                this.showAlert(`Timer ${action} executado com sucesso!`, 'success');
                await this.updateDashboardData();
                this.updateTimerStatus(action);
            } else {
                throw new Error(data.error || 'Erro desconhecido');
            }
        } catch (error) {
            console.error('Erro ao controlar timer:', error);
            this.showAlert(`Erro ao executar ${action}: ${error.message}`, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async updateTimerInterval(interval) {
        try {
            const response = await fetch('/api/dashboard/timer/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ interval: parseInt(interval) })
            });

            const data = await response.json();

            if (data.success) {
                this.showAlert(`Intervalo atualizado para ${interval} minutos`, 'success');
                await this.updateDashboardData();
            } else {
                throw new Error(data.error || 'Erro ao atualizar intervalo');
            }
        } catch (error) {
            console.error('Erro ao atualizar intervalo:', error);
            this.showAlert(`Erro ao atualizar intervalo: ${error.message}`, 'error');
        }
    }

    updateTimerStatus(action) {
        const badge = document.getElementById('timer-status-badge');
        const timerDisplay = document.getElementById('timer-display');
        
        if (badge) {
            switch (action) {
                case 'start':
                    badge.innerHTML = '<i class="fas fa-play me-1"></i> Ativo';
                    badge.style.background = '#28a745';
                    break;
                case 'pause':
                    badge.innerHTML = '<i class="fas fa-pause me-1"></i> Pausado';
                    badge.style.background = '#ffc107';
                    break;
                case 'stop':
                    badge.innerHTML = '<i class="fas fa-stop me-1"></i> Parado';
                    badge.style.background = '#dc3545';
                    break;
                case 'reset':
                    badge.innerHTML = '<i class="fas fa-redo me-1"></i> Reset';
                    badge.style.background = '#17a2b8';
                    if (timerDisplay) timerDisplay.textContent = '30:00';
                    break;
            }
        }
    }

    async updateDashboardData() {
        try {
            const response = await fetch('/api/dashboard/stats');
            const data = await response.json();

            if (data.success) {
                this.updateMetrics(data.data);
                this.updateLastUpdate();
            }
        } catch (error) {
            console.error('Erro ao atualizar dados do dashboard:', error);
        }
    }

    updateMetrics(data) {
        // Update main metrics
        const elements = {
            'total-obras': data.global?.total_obras || 0,
            'obras-ativas': data.global?.obras_ativas || 0,
            'obras-quarentena': data.global?.obras_quarentena || 0,
            'queue-pending': data.queue?.pending_count || 0,
            'queue-processing': data.queue?.processing_count || 0
        };

        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
                // Add animation effect
                element.style.transform = 'scale(1.1)';
                setTimeout(() => {
                    element.style.transform = 'scale(1)';
                }, 200);
            }
        });

        // Update timer display
        if (data.scheduler?.time_remaining) {
            const timerDisplay = document.getElementById('timer-display');
            if (timerDisplay) {
                timerDisplay.textContent = data.scheduler.time_remaining;
            }
            this.updateProgressRing(data.scheduler.time_remaining);
        }
    }

    updateProgressRing(timeRemaining) {
        const circle = document.getElementById('progress-circle');
        if (!circle) return;

        // Parse time remaining (format: "MM:SS")
        const [minutes, seconds] = timeRemaining.split(':').map(Number);
        const totalSeconds = minutes * 60 + seconds;
        const maxSeconds = 30 * 60; // 30 minutes default
        
        const progress = totalSeconds / maxSeconds;
        const circumference = 2 * Math.PI * 52; // r = 52
        const offset = circumference * (1 - progress);
        
        circle.style.strokeDashoffset = offset;
    }

    updateLastUpdate() {
        const element = document.getElementById('last-update');
        if (element) {
            element.textContent = new Date().toLocaleTimeString('pt-BR');
        }
    }

    updateUptime() {
        const element = document.getElementById('system-uptime');
        if (element) {
            const uptime = Date.now() - this.startTime;
            const hours = Math.floor(uptime / (1000 * 60 * 60));
            const minutes = Math.floor((uptime % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((uptime % (1000 * 60)) / 1000);
            
            element.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
        
        // Update every second
        setTimeout(() => this.updateUptime(), 1000);
    }

    initCharts() {
        this.initActivityChart();
        this.initSuccessChart();
    }

    initActivityChart() {
        const ctx = document.getElementById('activityChart');
        if (!ctx) return;

        const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 300);
        gradient.addColorStop(0, 'rgba(255, 107, 53, 0.3)');
        gradient.addColorStop(1, 'rgba(255, 107, 53, 0.05)');

        this.charts.activity = new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'],
                datasets: [{
                    label: 'Uploads Realizados',
                    data: [12, 19, 8, 15, 22, 18, 25],
                    borderColor: '#ff6b35',
                    backgroundColor: gradient,
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#ff6b35',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                },
                elements: {
                    point: {
                        hoverBackgroundColor: '#ff6b35'
                    }
                }
            }
        });
    }

    initSuccessChart() {
        const ctx = document.getElementById('successChart');
        if (!ctx) return;

        this.charts.success = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Sucesso', 'Erro', 'Quarentena'],
                datasets: [{
                    data: [85, 10, 5],
                    backgroundColor: [
                        '#28a745',
                        '#dc3545',
                        '#ffc107'
                    ],
                    borderWidth: 0,
                    cutout: '70%'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    }
                }
            }
        });
    }

    async refreshLogs() {
        try {
            const response = await fetch('/api/dashboard/logs?limit=10');
            const data = await response.json();

            if (data.success) {
                this.updateLogsContainer(data.logs);
                this.showAlert('Logs atualizados!', 'success');
            }
        } catch (error) {
            console.error('Erro ao atualizar logs:', error);
            this.showAlert('Erro ao atualizar logs', 'error');
        }
    }

    updateLogsContainer(logs) {
        const container = document.getElementById('logs-container');
        if (!container) return;

        if (logs.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-file-alt fa-2x mb-3"></i>
                    <p>Nenhum log recente encontrado</p>
                </div>
            `;
            return;
        }

        container.innerHTML = logs.map(log => `
            <div class="log-entry">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <strong>${log.level || 'INFO'}</strong>
                        <span class="text-muted ms-2">${log.message || 'Log message'}</span>
                    </div>
                    <small class="text-muted">
                        ${log.timestamp ? new Date(log.timestamp).toLocaleTimeString('pt-BR') : 'timestamp'}
                    </small>
                </div>
            </div>
        `).join('');
    }

    startAutoUpdate() {
        this.stopAutoUpdate(); // Clear existing interval
        
        this.updateInterval = setInterval(() => {
            this.updateDashboardData();
        }, 15000); // Update every 15 seconds
        
        console.log('✅ Auto-update ativado (15s)');
    }

    stopAutoUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
            console.log('⏸️  Auto-update pausado');
        }
    }

    updateTimer() {
        this.timerUpdateInterval = setInterval(() => {
            this.updateDashboardData();
        }, 5000); // Update timer every 5 seconds
    }

    showLoading(show) {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            if (show) {
                overlay.classList.remove('d-none');
            } else {
                overlay.classList.add('d-none');
            }
        }
    }

    showAlert(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        
        const icon = type === 'error' ? 'exclamation-triangle' : type === 'success' ? 'check-circle' : 'info-circle';
        
        alertDiv.innerHTML = `
            <i class="fas fa-${icon} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(alertDiv);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }

    // Keyboard shortcuts
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 'r':
                        e.preventDefault();
                        this.refreshLogs();
                        break;
                    case ' ':
                        e.preventDefault();
                        this.controlTimer('pause');
                        break;
                }
            }
        });
    }

    // Cleanup on page unload
    destroy() {
        this.stopAutoUpdate();
        if (this.timerUpdateInterval) {
            clearInterval(this.timerUpdateInterval);
        }
        Object.values(this.charts).forEach(chart => chart.destroy());
    }
}

// Initialize Dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboardManager = new DashboardManager();
    
    // Setup keyboard shortcuts
    window.dashboardManager.setupKeyboardShortcuts();
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        window.dashboardManager.destroy();
    });
});

// Add smooth scroll behavior for internal links
document.addEventListener('click', (e) => {
    if (e.target.matches('a[href^="#"]')) {
        e.preventDefault();
        const target = document.querySelector(e.target.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    }
});

// Add ripple effect to buttons
document.addEventListener('click', (e) => {
    if (e.target.matches('.btn-timer')) {
        const btn = e.target;
        const ripple = document.createElement('span');
        ripple.className = 'ripple';
        ripple.style.cssText = `
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.5);
            pointer-events: none;
            transform: scale(0);
            animation: ripple 0.6s linear;
        `;
        
        const rect = btn.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        ripple.style.width = ripple.style.height = size + 'px';
        ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
        ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
        
        btn.style.position = 'relative';
        btn.style.overflow = 'hidden';
        btn.appendChild(ripple);
        
        setTimeout(() => ripple.remove(), 600);
    }
});

// Add ripple animation CSS
const rippleCSS = `
    @keyframes ripple {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;

const style = document.createElement('style');
style.textContent = rippleCSS;
document.head.appendChild(style);

console.log('🎨 Dashboard MediocreToons carregado com sucesso!');