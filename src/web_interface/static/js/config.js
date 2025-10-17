/**
 * Sistema de Configurações - JavaScript
 * Gerencia validação, interações dinâmicas e funcionalidades da interface de configurações
 */

class ConfigManager {
    constructor() {
        this.currentConfigType = null;
        this.originalFormData = {};
        this.init();
    }

    init() {
        console.log('🔧 ConfigManager iniciado');
        this.setupEventListeners();
        this.setupFormValidation();
        this.saveOriginalFormData();
        this.setupConditionalVisibility();
    }

    setupEventListeners() {
        // Toggle switches para mostrar/ocultar seções
        const proxyToggle = document.getElementById('proxy_enabled');
        const cacheToggle = document.getElementById('cache_enabled');
        const discordToggle = document.getElementById('discord_enabled');

        if (proxyToggle) {
            proxyToggle.addEventListener('change', () => {
                this.toggleSection('proxy-settings', proxyToggle.checked);
            });
        }

        if (cacheToggle) {
            cacheToggle.addEventListener('change', () => {
                this.toggleSection('cache-settings', cacheToggle.checked);
            });
        }

        if (discordToggle) {
            discordToggle.addEventListener('change', () => {
                this.toggleSection('discord-settings', discordToggle.checked);
            });
        }

        // Formulários
        const flexibleForm = document.getElementById('flexibleConfigForm');
        const automationForm = document.getElementById('automationConfigForm');

        if (flexibleForm) {
            flexibleForm.addEventListener('submit', (e) => this.handleFormSubmit(e, 'flexible'));
        }

        if (automationForm) {
            automationForm.addEventListener('submit', (e) => this.handleFormSubmit(e, 'automation'));
        }

        // Detectar mudanças nos formulários
        document.querySelectorAll('input, textarea, select').forEach(element => {
            element.addEventListener('change', () => this.detectFormChanges());
            element.addEventListener('input', () => this.detectFormChanges());
        });

        // Botão de teste do Discord webhook
        const testWebhookBtn = document.querySelector('[onclick="testDiscordWebhook()"]');
        if (testWebhookBtn) {
            testWebhookBtn.addEventListener('click', () => this.testDiscordWebhook());
        }
    }

    setupFormValidation() {
        // Validação em tempo real
        const inputs = document.querySelectorAll('input[type="number"], input[type="url"], input[type="text"]');
        
        inputs.forEach(input => {
            input.addEventListener('blur', () => this.validateField(input));
            input.addEventListener('input', () => this.clearFieldError(input));
        });
    }

    validateField(field) {
        const value = field.value.trim();
        const fieldName = field.name;
        let isValid = true;
        let errorMessage = '';

        // Validação baseada no tipo e nome do campo
        switch (fieldName) {
            case 'http_timeout':
            case 'retry_delay':
            case 'cache_duration':
                if (value && (isNaN(value) || parseInt(value) < 1)) {
                    isValid = false;
                    errorMessage = 'Deve ser um número maior que 0';
                }
                break;

            case 'max_retries':
                if (value && (isNaN(value) || parseInt(value) < 0)) {
                    isValid = false;
                    errorMessage = 'Deve ser um número maior ou igual a 0';
                }
                break;

            case 'timer_interval':
                if (value && (isNaN(value) || parseInt(value) < 1 || parseInt(value) > 1440)) {
                    isValid = false;
                    errorMessage = 'Deve ser entre 1 e 1440 minutos';
                }
                break;

            case 'quarantine_limit':
                if (value && (isNaN(value) || parseInt(value) < 1 || parseInt(value) > 50)) {
                    isValid = false;
                    errorMessage = 'Deve ser entre 1 e 50 erros';
                }
                break;

            case 'discord_webhook':
                if (value && !this.isValidUrl(value)) {
                    isValid = false;
                    errorMessage = 'URL inválida';
                }
                break;

            case 'http_proxy':
            case 'https_proxy':
                if (value && !this.isValidProxy(value)) {
                    isValid = false;
                    errorMessage = 'Formato de proxy inválido (ex: http://proxy:8080)';
                }
                break;
        }

        if (!isValid) {
            this.showFieldError(field, errorMessage);
        } else {
            this.clearFieldError(field);
        }

        return isValid;
    }

    showFieldError(field, message) {
        this.clearFieldError(field);
        
        field.classList.add('is-invalid');
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'invalid-feedback';
        errorDiv.textContent = message;
        
        field.parentNode.appendChild(errorDiv);
    }

    clearFieldError(field) {
        field.classList.remove('is-invalid');
        
        const errorDiv = field.parentNode.querySelector('.invalid-feedback');
        if (errorDiv) {
            errorDiv.remove();
        }
    }

    isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch (_) {
            return false;
        }
    }

    isValidProxy(proxy) {
        // Aceita formatos: http://host:port, https://host:port, host:port
        const proxyRegex = /^(https?:\/\/)?[a-zA-Z0-9.-]+:\d+$/;
        return proxyRegex.test(proxy);
    }

    toggleSection(sectionId, show) {
        const section = document.getElementById(sectionId);
        if (section) {
            section.style.display = show ? 'block' : 'none';
            
            // Animação suave
            if (show) {
                section.style.opacity = '0';
                section.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    section.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                    section.style.opacity = '1';
                    section.style.transform = 'translateY(0)';
                }, 10);
            }
        }
    }

    setupConditionalVisibility() {
        // Configurar visibilidade inicial baseada nos toggles
        const proxyEnabled = document.getElementById('proxy_enabled')?.checked || false;
        const cacheEnabled = document.getElementById('cache_enabled')?.checked || false;
        const discordEnabled = document.getElementById('discord_enabled')?.checked || false;

        this.toggleSection('proxy-settings', proxyEnabled);
        this.toggleSection('cache-settings', cacheEnabled);
        this.toggleSection('discord-settings', discordEnabled);
    }

    saveOriginalFormData() {
        const forms = ['flexibleConfigForm', 'automationConfigForm'];
        
        forms.forEach(formId => {
            const form = document.getElementById(formId);
            if (form) {
                this.originalFormData[formId] = new FormData(form);
            }
        });
    }

    detectFormChanges() {
        // Detecta se houve mudanças nos formulários
        const hasChanges = this.hasUnsavedChanges();
        
        if (hasChanges) {
            this.showUnsavedChangesWarning();
        } else {
            this.hideUnsavedChangesWarning();
        }
    }

    hasUnsavedChanges() {
        const forms = ['flexibleConfigForm', 'automationConfigForm'];
        
        for (const formId of forms) {
            const form = document.getElementById(formId);
            if (form && this.originalFormData[formId]) {
                const currentData = new FormData(form);
                const originalData = this.originalFormData[formId];
                
                // Comparar dados
                for (const [key, value] of currentData.entries()) {
                    if (originalData.get(key) !== value) {
                        return true;
                    }
                }
            }
        }
        
        return false;
    }

    showUnsavedChangesWarning() {
        let warning = document.getElementById('unsaved-warning');
        if (!warning) {
            warning = document.createElement('div');
            warning.id = 'unsaved-warning';
            warning.className = 'alert alert-warning position-fixed';
            warning.style.cssText = `
                top: 20px;
                right: 20px;
                z-index: 9999;
                min-width: 300px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            `;
            warning.innerHTML = `
                <i class="bi bi-exclamation-triangle me-2"></i>
                <strong>Alterações não salvas!</strong>
                <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
            `;
            document.body.appendChild(warning);
        }
    }

    hideUnsavedChangesWarning() {
        const warning = document.getElementById('unsaved-warning');
        if (warning) {
            warning.remove();
        }
    }

    async handleFormSubmit(event, configType) {
        event.preventDefault();
        
        const form = event.target;
        const submitBtn = form.querySelector('button[type="submit"]');
        
        // Validar todos os campos antes de enviar
        const inputs = form.querySelectorAll('input[type="number"], input[type="url"], input[type="text"]');
        let isValid = true;
        
        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });
        
        if (!isValid) {
            this.showNotification('Por favor, corrija os erros antes de salvar.', 'error');
            return;
        }
        
        // Mostrar loading
        this.setButtonLoading(submitBtn, true);
        
        try {
            // Criar backup automático
            const backupResult = await this.createBackup(configType);
            if (!backupResult.success) {
                throw new Error(`Erro ao criar backup: ${backupResult.error}`);
            }
            
            // Enviar formulário
            const formData = new FormData(form);
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                this.showNotification('✅ Configurações salvas com sucesso!', 'success');
                this.saveOriginalFormData(); // Atualizar dados originais
                this.hideUnsavedChangesWarning();
                
                // Recarregar página após salvar para atualizar dados
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                throw new Error('Erro ao salvar configurações');
            }
            
        } catch (error) {
            console.error('Erro ao salvar configurações:', error);
            this.showNotification(`❌ ${error.message}`, 'error');
        } finally {
            this.setButtonLoading(submitBtn, false);
        }
    }

    async createBackup(configType) {
        try {
            const response = await fetch('/config/api/backup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ config_type: configType })
            });
            
            return await response.json();
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async testDiscordWebhook() {
        const webhookUrl = document.getElementById('discord_webhook').value.trim();
        
        if (!webhookUrl) {
            this.showNotification('Por favor, insira a URL do webhook primeiro.', 'warning');
            return;
        }
        
        if (!this.isValidUrl(webhookUrl)) {
            this.showNotification('URL do webhook inválida.', 'error');
            return;
        }
        
        const testBtn = document.querySelector('[onclick="testDiscordWebhook()"]');
        this.setButtonLoading(testBtn, true);
        
        try {
            const response = await fetch('/config/api/test-discord', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ webhook_url: webhookUrl })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('✅ Webhook testado com sucesso!', 'success');
            } else {
                this.showNotification(`❌ Erro no teste: ${result.error}`, 'error');
            }
            
        } catch (error) {
            this.showNotification(`❌ Erro ao testar webhook: ${error.message}`, 'error');
        } finally {
            this.setButtonLoading(testBtn, false);
        }
    }

    setButtonLoading(button, loading) {
        if (!button) return;
        
        if (loading) {
            button.disabled = true;
            button.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Carregando...`;
        } else {
            button.disabled = false;
            // Restaurar texto original baseado no contexto
            if (button.closest('#flexibleConfigForm')) {
                button.innerHTML = '<i class="bi bi-check-circle me-2"></i>Salvar Configurações';
            } else if (button.closest('#automationConfigForm')) {
                button.innerHTML = '<i class="bi bi-check-circle me-2"></i>Salvar Configurações';
            } else if (button.textContent.includes('Testar')) {
                button.innerHTML = '<i class="bi bi-send me-2"></i>Testar Webhook';
            }
        }
    }

    showNotification(message, type = 'info') {
        // Remove notificação existente
        const existing = document.getElementById('notification');
        if (existing) existing.remove();
        
        const notification = document.createElement('div');
        notification.id = 'notification';
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} position-fixed`;
        notification.style.cssText = `
            top: 20px;
            right: 20px;
            z-index: 10000;
            min-width: 350px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border: none;
            border-radius: 8px;
        `;
        
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remover após 5 segundos
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
}

// Funções globais para compatibilidade com template
function restoreDefaults(configType) {
    const config = window.configManager;
    config.currentConfigType = configType;
    
    const modal = new bootstrap.Modal(document.getElementById('confirmRestoreModal'));
    modal.show();
    
    // Configurar evento do botão de confirmação
    document.getElementById('confirmRestoreBtn').onclick = async () => {
        modal.hide();
        await config.performRestore(configType);
    };
}

function testDiscordWebhook() {
    window.configManager.testDiscordWebhook();
}

// Extensão da classe para funcionalidades adicionais
ConfigManager.prototype.performRestore = async function(configType) {
    try {
        const response = await fetch('/config/restore-defaults', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `config_type=${configType}`
        });
        
        if (response.ok) {
            this.showNotification(`✅ Configurações padrão restauradas para: ${configType}`, 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            throw new Error('Erro ao restaurar configurações');
        }
        
    } catch (error) {
        this.showNotification(`❌ Erro ao restaurar configurações: ${error.message}`, 'error');
    }
};

// Inicializar quando o DOM estiver carregado
document.addEventListener('DOMContentLoaded', () => {
    window.configManager = new ConfigManager();
});

// Prevenir saída da página com mudanças não salvas
window.addEventListener('beforeunload', (event) => {
    if (window.configManager && window.configManager.hasUnsavedChanges()) {
        event.preventDefault();
        event.returnValue = 'Você tem alterações não salvas. Deseja realmente sair?';
        return event.returnValue;
    }
});