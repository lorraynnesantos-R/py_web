/**
 * JavaScript para funcionalidades de mapeamento
 * Task 4.4: Gerenciamento de Obras - Interações AJAX e funcionalidades avançadas
 */

// Configurações globais
const MappingManager = {
    currentScan: null,
    selectedObras: new Set(),
    filters: {
        status: 'all',
        search: '',
        page: 1,
        per_page: 20
    },
    
    // URLs das APIs
    apiUrls: {
        scans: '/mapping/api/scans',
        scanObras: '/mapping/api/scan/{scan_name}/obras',
        manualUpload: '/mapping/obra/{scan_name}/{obra_id}/manual-upload',
        toggleQuarantine: '/mapping/obra/{scan_name}/{obra_id}/toggle-quarantine'
    }
};

/**
 * Inicialização do sistema de mapping
 */
function initMappingManager() {
    console.log('🔧 Inicializando MappingManager...');
    
    // Event listeners para filtros
    setupFilterListeners();
    
    // Event listeners para ações
    setupActionListeners();
    
    // Auto-refresh para páginas com dados dinâmicos
    setupAutoRefresh();
    
    // Keyboard shortcuts
    setupKeyboardShortcuts();
    
    console.log('✅ MappingManager inicializado');
}

/**
 * Configurar listeners para filtros
 */
function setupFilterListeners() {
    // Filtro de status
    const statusFilter = document.getElementById('status');
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            MappingManager.filters.status = this.value;
            MappingManager.filters.page = 1; // Reset página
            applyFilters();
        });
    }
    
    // Campo de busca com debounce
    const searchInput = document.getElementById('search');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                MappingManager.filters.search = this.value;
                MappingManager.filters.page = 1; // Reset página
                applyFilters();
            }, 500); // 500ms de debounce
        });
    }
    
    // Items por página
    const perPageSelect = document.getElementById('per_page');
    if (perPageSelect) {
        perPageSelect.addEventListener('change', function() {
            MappingManager.filters.per_page = parseInt(this.value);
            MappingManager.filters.page = 1; // Reset página
            applyFilters();
        });
    }
}

/**
 * Configurar listeners para ações
 */
function setupActionListeners() {
    // Checkboxes de seleção
    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('obra-checkbox')) {
            handleObraSelection(e.target);
        }
    });
    
    // Botões de ação em lote
    const bulkActions = document.querySelectorAll('[data-bulk-action]');
    bulkActions.forEach(btn => {
        btn.addEventListener('click', function() {
            const action = this.getAttribute('data-bulk-action');
            handleBulkAction(action);
        });
    });
}

/**
 * Configurar auto-refresh
 */
function setupAutoRefresh() {
    // Auto-refresh apenas em páginas específicas
    const autoRefreshPages = ['scan_detail', 'obra_detail'];
    const currentPage = document.body.getAttribute('data-page');
    
    if (autoRefreshPages.includes(currentPage)) {
        // Verificar se há processos em andamento
        const processingItems = document.querySelectorAll('.badge:contains("Processando")');
        
        if (processingItems.length > 0) {
            console.log('📡 Auto-refresh ativado (processos em andamento)');
            setTimeout(() => {
                refreshCurrentData();
            }, 30000); // 30 segundos
        }
    }
}

/**
 * Configurar atalhos de teclado
 */
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl+A - Selecionar todos
        if (e.ctrlKey && e.key === 'a' && document.querySelectorAll('.obra-checkbox').length > 0) {
            e.preventDefault();
            selectAllObras();
        }
        
        // Escape - Limpar seleção
        if (e.key === 'Escape') {
            clearSelection();
        }
        
        // F5 ou Ctrl+R - Refresh inteligente
        if (e.key === 'F5' || (e.ctrlKey && e.key === 'r')) {
            e.preventDefault();
            refreshCurrentData();
        }
    });
}

/**
 * Aplicar filtros via AJAX
 */
async function applyFilters() {
    if (!MappingManager.currentScan) return;
    
    showLoadingState('Aplicando filtros...');
    
    try {
        const url = buildApiUrl('scanObras', { scan_name: MappingManager.currentScan });
        const params = new URLSearchParams(MappingManager.filters);
        
        const response = await fetch(`${url}?${params}`);
        const data = await response.json();
        
        if (data.success) {
            updateObrasTable(data.data.obras);
            updatePagination(data.data.pagination);
            updateFiltersInfo(data.data.filters);
        } else {
            showToast('Erro ao aplicar filtros: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Erro ao aplicar filtros:', error);
        showToast('Erro ao aplicar filtros', 'error');
    } finally {
        hideLoadingState();
    }
}

/**
 * Atualizar tabela de obras
 */
function updateObrasTable(obras) {
    const tbody = document.querySelector('#obrasTable tbody');
    if (!tbody) return;
    
    if (obras.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-4">
                    <i class="fas fa-search fa-2x text-muted mb-2"></i>
                    <p class="text-muted">Nenhuma obra encontrada com os filtros atuais</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = obras.map(obra => `
        <tr id="obra-${obra.id}" class="obra-row">
            <td>
                <input type="checkbox" class="obra-checkbox" value="${obra.id}">
            </td>
            <td>
                <div class="d-flex align-items-center">
                    <div>
                        <div class="fw-bold">${escapeHtml(obra.titulo)}</div>
                        <small class="text-muted">${escapeHtml(obra.url_relativa)}</small>
                    </div>
                </div>
            </td>
            <td>
                ${renderStatusBadge(obra.status)}
            </td>
            <td>
                <small>${obra.ultimo_upload ? formatDateTimeShort(obra.ultimo_upload) : 'Nunca'}</small>
            </td>
            <td>
                ${renderErrorBadge(obra.erros_consecutivos)}
            </td>
            <td>
                <small>${obra.capitulos_disponivel || 0}/${obra.total_capitulos || 0}</small>
            </td>
            <td>
                ${renderActionButtons(obra)}
            </td>
        </tr>
    `).join('');
    
    // Re-anexar event listeners
    setupActionListeners();
}

/**
 * Renderizar badge de status
 */
function renderStatusBadge(status) {
    const badges = {
        'ativo': '<span class="badge bg-success"><i class="fas fa-check"></i> Ativo</span>',
        'quarentena': '<span class="badge bg-warning"><i class="fas fa-pause"></i> Quarentena</span>',
        'processando': '<span class="badge bg-primary"><i class="fas fa-spinner fa-spin"></i> Processando</span>'
    };
    
    return badges[status] || `<span class="badge bg-secondary">${escapeHtml(status)}</span>`;
}

/**
 * Renderizar badge de erros
 */
function renderErrorBadge(erros) {
    if (erros > 0) {
        const badgeClass = erros >= 10 ? 'bg-danger' : 'bg-warning';
        return `<span class="badge ${badgeClass}">${erros}</span>`;
    }
    return '<span class="badge bg-success">0</span>';
}

/**
 * Renderizar botões de ação
 */
function renderActionButtons(obra) {
    return `
        <div class="btn-group btn-group-sm">
            <a href="/mapping/obra/${MappingManager.currentScan}/${obra.id}" 
               class="btn btn-outline-primary" title="Ver detalhes">
                <i class="fas fa-eye"></i>
            </a>
            <button type="button" class="btn btn-outline-success" 
                    onclick="quickManualUpload('${obra.id}', '${escapeHtml(obra.titulo)}')" 
                    title="Upload manual">
                <i class="fas fa-upload"></i>
            </button>
            <button type="button" class="btn btn-outline-warning" 
                    onclick="quickToggleQuarantine('${obra.id}', '${escapeHtml(obra.titulo)}', '${obra.status}')" 
                    title="Alternar quarentena">
                <i class="fas fa-pause"></i>
            </button>
            <a href="/mapping/obra/${MappingManager.currentScan}/${obra.id}/edit" 
               class="btn btn-outline-secondary" title="Editar">
                <i class="fas fa-edit"></i>
            </a>
        </div>
    `;
}

/**
 * Seleção de obras
 */
function handleObraSelection(checkbox) {
    const obraId = checkbox.value;
    
    if (checkbox.checked) {
        MappingManager.selectedObras.add(obraId);
    } else {
        MappingManager.selectedObras.delete(obraId);
    }
    
    updateBulkActionsVisibility();
    updateSelectAllCheckbox();
}

function selectAllObras() {
    const checkboxes = document.querySelectorAll('.obra-checkbox');
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = true;
    }
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = true;
        MappingManager.selectedObras.add(checkbox.value);
    });
    
    updateBulkActionsVisibility();
}

function clearSelection() {
    const checkboxes = document.querySelectorAll('.obra-checkbox');
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = false;
    }
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    
    MappingManager.selectedObras.clear();
    updateBulkActionsVisibility();
}

function updateSelectAllCheckbox() {
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const totalCheckboxes = document.querySelectorAll('.obra-checkbox').length;
    const selectedCount = MappingManager.selectedObras.size;
    
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = selectedCount > 0 && selectedCount === totalCheckboxes;
        selectAllCheckbox.indeterminate = selectedCount > 0 && selectedCount < totalCheckboxes;
    }
}

function updateBulkActionsVisibility() {
    const bulkActions = document.getElementById('bulkActions');
    const selectedCount = document.getElementById('selectedCount');
    
    if (bulkActions && selectedCount) {
        if (MappingManager.selectedObras.size > 0) {
            bulkActions.style.display = 'block';
            selectedCount.textContent = MappingManager.selectedObras.size;
        } else {
            bulkActions.style.display = 'none';
        }
    }
}

/**
 * Ações rápidas
 */
async function quickManualUpload(obraId, obraTitle) {
    if (!confirm(`Adicionar "${obraTitle}" à fila de upload manual?`)) return;
    
    try {
        const url = buildApiUrl('manualUpload', { 
            scan_name: MappingManager.currentScan, 
            obra_id: obraId 
        });
        
        const response = await fetch(url, { method: 'POST' });
        
        if (response.ok) {
            showToast(`"${obraTitle}" adicionada à fila de upload`, 'success');
            refreshObraRow(obraId);
        } else {
            showToast('Erro ao adicionar à fila', 'error');
        }
    } catch (error) {
        console.error('Erro no upload manual:', error);
        showToast('Erro ao adicionar à fila', 'error');
    }
}

async function quickToggleQuarantine(obraId, obraTitle, currentStatus) {
    const action = currentStatus === 'ativo' ? 'colocar em quarentena' : 'reativar';
    
    if (!confirm(`Deseja ${action} "${obraTitle}"?`)) return;
    
    try {
        const url = buildApiUrl('toggleQuarantine', { 
            scan_name: MappingManager.currentScan, 
            obra_id: obraId 
        });
        
        const response = await fetch(url, { method: 'POST' });
        
        if (response.ok) {
            const newStatus = currentStatus === 'ativo' ? 'quarentena' : 'ativo';
            showToast(`"${obraTitle}" ${action}`, newStatus === 'ativo' ? 'success' : 'warning');
            refreshObraRow(obraId);
        } else {
            showToast('Erro ao alterar status', 'error');
        }
    } catch (error) {
        console.error('Erro ao alterar quarentena:', error);
        showToast('Erro ao alterar status', 'error');
    }
}

/**
 * Ações em lote
 */
async function handleBulkAction(action) {
    const selectedObras = Array.from(MappingManager.selectedObras);
    
    if (selectedObras.length === 0) {
        showToast('Nenhuma obra selecionada', 'warning');
        return;
    }
    
    let confirmMessage = '';
    
    switch (action) {
        case 'upload':
            confirmMessage = `Adicionar ${selectedObras.length} obras à fila de upload manual?`;
            break;
        case 'quarantine':
            confirmMessage = `Alternar status de quarentena de ${selectedObras.length} obras?`;
            break;
        default:
            return;
    }
    
    if (!confirm(confirmMessage)) return;
    
    showLoadingState(`Processando ${selectedObras.length} obras...`);
    
    let successCount = 0;
    let errorCount = 0;
    
    for (const obraId of selectedObras) {
        try {
            let url;
            
            switch (action) {
                case 'upload':
                    url = buildApiUrl('manualUpload', { 
                        scan_name: MappingManager.currentScan, 
                        obra_id: obraId 
                    });
                    break;
                case 'quarantine':
                    url = buildApiUrl('toggleQuarantine', { 
                        scan_name: MappingManager.currentScan, 
                        obra_id: obraId 
                    });
                    break;
            }
            
            const response = await fetch(url, { method: 'POST' });
            
            if (response.ok) {
                successCount++;
            } else {
                errorCount++;
            }
        } catch (error) {
            console.error(`Erro ao processar obra ${obraId}:`, error);
            errorCount++;
        }
    }
    
    hideLoadingState();
    
    // Mostrar resultado
    if (successCount > 0) {
        showToast(`${successCount} obras processadas com sucesso`, 'success');
    }
    
    if (errorCount > 0) {
        showToast(`${errorCount} obras com erro`, 'error');
    }
    
    // Limpar seleção e atualizar dados
    clearSelection();
    refreshCurrentData();
}

/**
 * Refresh de dados
 */
async function refreshCurrentData() {
    const currentPage = document.body.getAttribute('data-page');
    
    switch (currentPage) {
        case 'scan_detail':
            await applyFilters();
            break;
        case 'obra_detail':
            location.reload(); // Por enquanto, reload completo
            break;
        default:
            location.reload();
    }
}

async function refreshObraRow(obraId) {
    // Atualizar apenas uma linha específica
    try {
        const url = buildApiUrl('scanObras', { scan_name: MappingManager.currentScan });
        const params = new URLSearchParams({ obra_id: obraId });
        
        const response = await fetch(`${url}?${params}`);
        const data = await response.json();
        
        if (data.success && data.data.obras.length > 0) {
            const obra = data.data.obras[0];
            const row = document.getElementById(`obra-${obraId}`);
            
            if (row) {
                // Atualizar células específicas
                row.cells[2].innerHTML = renderStatusBadge(obra.status);
                row.cells[3].innerHTML = `<small>${obra.ultimo_upload ? formatDateTimeShort(obra.ultimo_upload) : 'Nunca'}</small>`;
                row.cells[4].innerHTML = renderErrorBadge(obra.erros_consecutivos);
            }
        }
    } catch (error) {
        console.error('Erro ao atualizar linha:', error);
    }
}

/**
 * Utilitários
 */
function buildApiUrl(endpoint, params = {}) {
    let url = MappingManager.apiUrls[endpoint];
    
    for (const [key, value] of Object.entries(params)) {
        url = url.replace(`{${key}}`, encodeURIComponent(value));
    }
    
    return url;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDateTimeShort(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('pt-BR') + ' ' + date.toLocaleTimeString('pt-BR', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

function showLoadingState(message = 'Carregando...') {
    // Implementar overlay de loading
    const loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'loadingOverlay';
    loadingOverlay.className = 'position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center';
    loadingOverlay.style.backgroundColor = 'rgba(0,0,0,0.5)';
    loadingOverlay.style.zIndex = '9999';
    loadingOverlay.innerHTML = `
        <div class="bg-white p-4 rounded shadow">
            <div class="d-flex align-items-center">
                <div class="spinner-border text-primary me-3" role="status">
                    <span class="visually-hidden">Carregando...</span>
                </div>
                <span>${message}</span>
            </div>
        </div>
    `;
    
    document.body.appendChild(loadingOverlay);
}

function hideLoadingState() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.remove();
    }
}

// Inicializar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Detectar scan atual se estivermos em página de scan
    const scanNameElement = document.querySelector('[data-scan-name]');
    if (scanNameElement) {
        MappingManager.currentScan = scanNameElement.getAttribute('data-scan-name');
    }
    
    // Inicializar sistema
    initMappingManager();
});

// Exportar para uso global
window.MappingManager = MappingManager;
window.quickManualUpload = quickManualUpload;
window.quickToggleQuarantine = quickToggleQuarantine;
window.selectAllObras = selectAllObras;
window.clearSelection = clearSelection;
window.refreshCurrentData = refreshCurrentData;