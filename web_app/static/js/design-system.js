/**
 * JavaScript para Sistema de Design MediocreToons Auto Uploader v2
 * Inclui animações, interações e efeitos visuais
 */

document.addEventListener('DOMContentLoaded', function() {
    
    // ====================================
    // ANIMAÇÕES E EFEITOS VISUAIS
    // ====================================
    
    // Adicionar animação fade-in aos elementos com a classe
    const fadeElements = document.querySelectorAll('.fade-in');
    fadeElements.forEach((element, index) => {
        element.style.animationDelay = `${index * 0.1}s`;
    });
    
    // Adicionar animação slide-up aos elementos com a classe
    const slideElements = document.querySelectorAll('.slide-up');
    slideElements.forEach((element, index) => {
        element.style.animationDelay = `${index * 0.2}s`;
    });
    
    // ====================================
    // INTERAÇÕES DE BOTÕES
    // ====================================
    
    // Efeito de ripple nos botões
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.cssText = `
                width: ${size}px;
                height: ${size}px;
                left: ${x}px;
                top: ${y}px;
                position: absolute;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.5);
                transform: scale(0);
                animation: ripple 0.6s ease-out;
                pointer-events: none;
            `;
            
            // Adicionar keyframes do ripple se não existir
            if (!document.querySelector('#ripple-styles')) {
                const style = document.createElement('style');
                style.id = 'ripple-styles';
                style.textContent = `
                    @keyframes ripple {
                        to {
                            transform: scale(2);
                            opacity: 0;
                        }
                    }
                    .btn {
                        position: relative;
                        overflow: hidden;
                    }
                `;
                document.head.appendChild(style);
            }
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
    
    // ====================================
    // INDICADORES DE STATUS ANIMADOS
    // ====================================
    
    // Pulsação para indicadores online
    const onlineIndicators = document.querySelectorAll('.status-online, .status-indicator.online');
    onlineIndicators.forEach(indicator => {
        indicator.style.animation = 'pulse 2s infinite';
    });
    
    // ====================================
    // CARDS INTERATIVOS
    // ====================================
    
    // Hover effects para dashboard cards
    const dashboardCards = document.querySelectorAll('.dashboard-card, .card');
    dashboardCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-4px)';
            this.style.boxShadow = 'var(--shadow-lg)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = 'var(--shadow)';
        });
    });
    
    // ====================================
    // CONFIRMAÇÕES INTERATIVAS
    // ====================================
    
    // Melhorar confirmações com modal-style
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const message = this.getAttribute('data-confirm');
            
            // Criar modal de confirmação personalizado
            const modal = createConfirmModal(message, () => {
                // Se confirmado, executar ação original
                if (this.tagName === 'BUTTON' && this.form) {
                    this.form.submit();
                } else if (this.href) {
                    window.location.href = this.href;
                }
            });
            
            document.body.appendChild(modal);
            setTimeout(() => modal.classList.add('show'), 10);
        });
    });
    
    function createConfirmModal(message, onConfirm) {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h5><i class="fas fa-question-circle text-warning"></i> Confirmação</h5>
                </div>
                <div class="modal-body">
                    <p>${message}</p>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary cancel-btn">Cancelar</button>
                    <button class="btn btn-primary confirm-btn">Confirmar</button>
                </div>
            </div>
        `;
        
        // Adicionar estilos do modal
        if (!document.querySelector('#modal-styles')) {
            const style = document.createElement('style');
            style.id = 'modal-styles';
            style.textContent = `
                .modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: var(--z-modal);
                    opacity: 0;
                    visibility: hidden;
                    transition: all var(--transition-normal);
                }
                .modal-overlay.show {
                    opacity: 1;
                    visibility: visible;
                }
                .modal-content {
                    background: var(--color-white);
                    border-radius: var(--border-radius-lg);
                    box-shadow: var(--shadow-xl);
                    min-width: 300px;
                    max-width: 500px;
                    margin: var(--space-4);
                    transform: scale(0.9) translateY(20px);
                    transition: all var(--transition-normal);
                }
                .modal-overlay.show .modal-content {
                    transform: scale(1) translateY(0);
                }
                .modal-header {
                    padding: var(--space-4);
                    border-bottom: 1px solid var(--color-gray-200);
                }
                .modal-body {
                    padding: var(--space-4);
                }
                .modal-footer {
                    padding: var(--space-4);
                    border-top: 1px solid var(--color-gray-200);
                    display: flex;
                    justify-content: flex-end;
                    gap: var(--space-2);
                }
            `;
            document.head.appendChild(style);
        }
        
        // Event listeners
        modal.querySelector('.cancel-btn').addEventListener('click', () => {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 250);
        });
        
        modal.querySelector('.confirm-btn').addEventListener('click', () => {
            modal.classList.remove('show');
            setTimeout(() => {
                modal.remove();
                onConfirm();
            }, 250);
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('show');
                setTimeout(() => modal.remove(), 250);
            }
        });
        
        return modal;
    }
    
    // ====================================
    // PROGRESS BARS ANIMADAS
    // ====================================
    
    // Animar progress bars quando visíveis
    const progressBars = document.querySelectorAll('.progress-bar');
    const progressObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const progressBar = entry.target;
                const width = progressBar.style.width || progressBar.getAttribute('data-width') || '0%';
                progressBar.style.width = '0%';
                setTimeout(() => {
                    progressBar.style.width = width;
                }, 100);
            }
        });
    });
    
    progressBars.forEach(bar => progressObserver.observe(bar));
    
    // ====================================
    // TOOLTIPS CUSTOMIZADOS
    // ====================================
    
    // Adicionar tooltips aos elementos com title
    const tooltipElements = document.querySelectorAll('[title]');
    tooltipElements.forEach(element => {
        const title = element.getAttribute('title');
        element.removeAttribute('title');
        
        const tooltip = document.createElement('div');
        tooltip.className = 'custom-tooltip';
        tooltip.textContent = title;
        
        element.addEventListener('mouseenter', (e) => {
            document.body.appendChild(tooltip);
            const rect = element.getBoundingClientRect();
            tooltip.style.cssText = `
                position: fixed;
                top: ${rect.top - tooltip.offsetHeight - 8}px;
                left: ${rect.left + rect.width / 2 - tooltip.offsetWidth / 2}px;
                background: var(--color-gray-800);
                color: var(--color-white);
                padding: var(--space-1) var(--space-2);
                border-radius: var(--border-radius);
                font-size: var(--font-size-xs);
                z-index: var(--z-tooltip);
                pointer-events: none;
                opacity: 0;
                transition: opacity var(--transition-fast);
            `;
            setTimeout(() => tooltip.style.opacity = '1', 10);
        });
        
        element.addEventListener('mouseleave', () => {
            if (tooltip.parentNode) {
                tooltip.style.opacity = '0';
                setTimeout(() => tooltip.remove(), 150);
            }
        });
    });
    
    // ====================================
    // NOTIFICAÇÕES TOAST
    // ====================================
    
    window.showToast = function(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-${getToastIcon(type)}"></i>
                <span>${message}</span>
            </div>
            <button class="toast-close"><i class="fas fa-times"></i></button>
        `;
        
        // Adicionar estilos do toast se necessário
        if (!document.querySelector('#toast-styles')) {
            const style = document.createElement('style');
            style.id = 'toast-styles';
            style.textContent = `
                .toast {
                    position: fixed;
                    top: var(--space-4);
                    right: var(--space-4);
                    background: var(--color-white);
                    border-radius: var(--border-radius);
                    box-shadow: var(--shadow-lg);
                    padding: var(--space-3) var(--space-4);
                    z-index: var(--z-tooltip);
                    transform: translateX(100%);
                    transition: transform var(--transition-normal);
                    display: flex;
                    align-items: center;
                    gap: var(--space-2);
                    min-width: 300px;
                }
                .toast.show { transform: translateX(0); }
                .toast-info { border-left: 4px solid var(--color-info); }
                .toast-success { border-left: 4px solid var(--color-success); }
                .toast-warning { border-left: 4px solid var(--color-warning); }
                .toast-danger { border-left: 4px solid var(--color-danger); }
                .toast-content { flex: 1; display: flex; align-items: center; gap: var(--space-2); }
                .toast-close { 
                    background: none; 
                    border: none; 
                    cursor: pointer; 
                    opacity: 0.7;
                    transition: opacity var(--transition-fast);
                }
                .toast-close:hover { opacity: 1; }
            `;
            document.head.appendChild(style);
        }
        
        // Event listeners
        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 250);
        });
        
        document.body.appendChild(toast);
        setTimeout(() => toast.classList.add('show'), 10);
        
        if (duration > 0) {
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 250);
            }, duration);
        }
    };
    
    function getToastIcon(type) {
        switch (type) {
            case 'success': return 'check-circle';
            case 'warning': return 'exclamation-triangle';
            case 'danger': return 'exclamation-circle';
            default: return 'info-circle';
        }
    }
    
    // ====================================
    // AUTO-REFRESH COM INDICADOR VISUAL
    // ====================================
    
    // Melhorar auto-refresh de estatísticas
    let refreshInterval;
    
    window.startAutoRefresh = function(url, interval = 30000) {
        if (refreshInterval) clearInterval(refreshInterval);
        
        refreshInterval = setInterval(() => {
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateStats(data.data);
                        showToast('Estatísticas atualizadas', 'success', 2000);
                    }
                })
                .catch(error => {
                    console.error('Erro ao atualizar stats:', error);
                    showToast('Erro ao atualizar estatísticas', 'danger', 3000);
                });
        }, interval);
    };
    
    function updateStats(data) {
        const statsElements = document.querySelectorAll('[data-stat]');
        statsElements.forEach(el => {
            const statName = el.getAttribute('data-stat');
            if (data[statName] !== undefined) {
                // Animação de contagem
                const currentValue = parseInt(el.textContent) || 0;
                const newValue = parseInt(data[statName]) || 0;
                animateCounter(el, currentValue, newValue);
            }
        });
    }
    
    function animateCounter(element, start, end, duration = 1000) {
        const startTime = performance.now();
        const update = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const current = Math.round(start + (end - start) * progress);
            element.textContent = current;
            
            if (progress < 1) {
                requestAnimationFrame(update);
            }
        };
        requestAnimationFrame(update);
    }
    
    // Iniciar auto-refresh se não estiver em página de formulário
    if (!document.querySelector('form')) {
        startAutoRefresh('/api/quarantine/stats');
    }
    
    console.log('🎨 Sistema de Design MediocreToons v2 carregado com sucesso!');
});