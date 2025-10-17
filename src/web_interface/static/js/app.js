/* JavaScript Principal - MediocreToons Auto Uploader v2 */

/**
 * Classe principal da aplicação
 */
class MediocreApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupTooltips();
        this.setupAutoRefresh();
        this.setupNotifications();
        
        console.log('MediocreToons Auto Uploader v2 - Interface Web Carregada');
    }

    /**
     * Configurar event listeners globais
     */
    setupEventListeners() {
        // Confirmar ações destrutivas
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-confirm]')) {
                e.preventDefault();
                const message = e.target.getAttribute('data-confirm');
                if (confirm(message)) {
                    // Se é um link, navegar
                    if (e.target.tagName === 'A') {
                        window.location.href = e.target.href;
                    }
                    // Se é um form, submeter
                    else if (e.target.type === 'submit') {
                        e.target.closest('form').submit();
                    }
                }
            }
        });

        // Auto-submit em selects com data-auto-submit
        document.addEventListener('change', (e) => {
            if (e.target.matches('select[data-auto-submit]')) {
                e.target.closest('form').submit();
            }
        });

        // Copiar para clipboard
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-clipboard]')) {
                e.preventDefault();
                const text = e.target.getAttribute('data-clipboard');
                this.copyToClipboard(text);
                this.showToast('Copiado para a área de transferência!', 'success');
            }
        });
    }

    /**
     * Configurar tooltips do Bootstrap
     */
    setupTooltips() {
        if (typeof bootstrap !== 'undefined') {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    }

    /**
     * Configurar auto-refresh para elementos específicos
     */
    setupAutoRefresh() {
        const autoRefreshElements = document.querySelectorAll('[data-auto-refresh]');
        
        autoRefreshElements.forEach(element => {
            const interval = parseInt(element.getAttribute('data-auto-refresh')) * 1000;
            const url = element.getAttribute('data-refresh-url');
            
            if (url && interval > 0) {
                setInterval(() => {
                    this.refreshElement(element, url);
                }, interval);
            }
        });
    }

    /**
     * Configurar sistema de notificações
     */
    setupNotifications() {
        // Verificar se o navegador suporta notificações
        if ('Notification' in window) {
            // Solicitar permissão se necessário
            if (Notification.permission === 'default') {
                Notification.requestPermission();
            }
        }
    }

    /**
     * Fazer requisição AJAX
     */
    async makeRequest(url, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        };

        const finalOptions = { ...defaultOptions, ...options };

        try {
            const response = await fetch(url, finalOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
            
        } catch (error) {
            console.error('Erro na requisição:', error);
            this.showToast('Erro na comunicação com o servidor', 'error');
            throw error;
        }
    }

    /**
     * Atualizar elemento específico via AJAX
     */
    async refreshElement(element, url) {
        try {
            const data = await this.makeRequest(url);
            
            if (typeof data === 'object' && data.success) {
                // Atualizar conteúdo do elemento
                if (data.html) {
                    element.innerHTML = data.html;
                }
                
                // Reativar tooltips
                this.setupTooltips();
                
            } else if (typeof data === 'string') {
                element.innerHTML = data;
            }
            
        } catch (error) {
            console.error('Erro ao atualizar elemento:', error);
        }
    }

    /**
     * Mostrar toast notification
     */
    showToast(message, type = 'info', duration = 5000) {
        const toastContainer = this.getOrCreateToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${this.getBootstrapColorClass(type)} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi bi-${this.getIconForType(type)} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        if (typeof bootstrap !== 'undefined') {
            const bsToast = new bootstrap.Toast(toast, {
                delay: duration
            });
            bsToast.show();
            
            // Remover elemento após esconder
            toast.addEventListener('hidden.bs.toast', () => {
                toast.remove();
            });
        } else {
            // Fallback sem Bootstrap
            setTimeout(() => {
                toast.remove();
            }, duration);
        }
    }

    /**
     * Obter ou criar container de toasts
     */
    getOrCreateToastContainer() {
        let container = document.getElementById('toast-container');
        
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1060';
            document.body.appendChild(container);
        }
        
        return container;
    }

    /**
     * Converter tipo para classe Bootstrap
     */
    getBootstrapColorClass(type) {
        const map = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'info'
        };
        return map[type] || 'info';
    }

    /**
     * Obter ícone para tipo
     */
    getIconForType(type) {
        const map = {
            'success': 'check-circle',
            'error': 'exclamation-triangle',
            'warning': 'exclamation-circle',
            'info': 'info-circle'
        };
        return map[type] || 'info-circle';
    }

    /**
     * Copiar texto para clipboard
     */
    async copyToClipboard(text) {
        try {
            if (navigator.clipboard) {
                await navigator.clipboard.writeText(text);
            } else {
                // Fallback para navegadores mais antigos
                const textArea = document.createElement('textarea');
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
            }
        } catch (error) {
            console.error('Erro ao copiar para clipboard:', error);
            throw error;
        }
    }

    /**
     * Formatar bytes em tamanho legível
     */
    formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';

        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    /**
     * Formatar data/hora
     */
    formatDateTime(dateString, locale = 'pt-BR') {
        const date = new Date(dateString);
        return date.toLocaleString(locale);
    }

    /**
     * Mostrar notificação do navegador
     */
    showBrowserNotification(title, message, icon = null) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(title, {
                body: message,
                icon: icon || '/static/favicon.ico'
            });
        }
    }

    /**
     * Debounce function
     */
    debounce(func, wait, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func(...args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func(...args);
        };
    }

    /**
     * Throttle function
     */
    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
}

/**
 * Utilitários específicos para componentes
 */
class ComponentUtils {
    /**
     * Configurar DataTable se disponível
     */
    static initDataTable(selector, options = {}) {
        if (typeof $.fn.DataTable !== 'undefined') {
            const defaultOptions = {
                language: {
                    url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/pt-BR.json'
                },
                responsive: true,
                pageLength: 25,
                order: [[0, 'desc']]
            };
            
            return $(selector).DataTable({ ...defaultOptions, ...options });
        }
    }

    /**
     * Configurar Chart.js se disponível
     */
    static initChart(canvas, config) {
        if (typeof Chart !== 'undefined') {
            return new Chart(canvas, config);
        }
    }

    /**
     * Configurar modais de confirmação
     */
    static setupConfirmModals() {
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-bs-toggle="modal"][data-confirm]')) {
                e.preventDefault();
                
                const target = e.target.getAttribute('data-bs-target');
                const modal = document.querySelector(target);
                
                if (modal) {
                    const confirmBtn = modal.querySelector('.btn-confirm');
                    const message = e.target.getAttribute('data-confirm');
                    
                    modal.querySelector('.modal-body p').textContent = message;
                    
                    if (confirmBtn) {
                        confirmBtn.onclick = () => {
                            if (e.target.tagName === 'A') {
                                window.location.href = e.target.href;
                            } else if (e.target.closest('form')) {
                                e.target.closest('form').submit();
                            }
                        };
                    }
                }
            }
        });
    }
}

// Inicializar aplicação quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.mediocreApp = new MediocreApp();
    ComponentUtils.setupConfirmModals();
});

// Expor utilitários globalmente
window.ComponentUtils = ComponentUtils;