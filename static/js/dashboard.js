// Dashboard JavaScript functionality
class IntegrationDashboard {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.startStatusMonitoring();
        this.initializeTooltips();
    }

    setupEventListeners() {
        // Connection test buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-test-connection]')) {
                const service = e.target.getAttribute('data-test-connection');
                this.testConnection(service, e.target);
            }
        });

        // Sync confirmation
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-sync-confirm]')) {
                this.showSyncConfirmation();
            }
        });

        // Auto-refresh toggle
        const autoRefreshToggle = document.getElementById('autoRefreshToggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                this.toggleAutoRefresh(e.target.checked);
            });
        }
    }

    async testConnection(service, button) {
        const originalText = button.innerHTML;
        const originalDisabled = button.disabled;

        try {
            // Update button state
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Testing...';
            button.disabled = true;

            // Make API call
            const response = await fetch(`/test_connection/${service}`);
            const result = await response.json();

            // Update UI based on result
            this.updateConnectionStatus(service, result);
            this.showNotification(
                result.success ? 'success' : 'danger',
                `${service.toUpperCase()} Connection: ${result.message}`
            );

        } catch (error) {
            console.error('Connection test error:', error);
            this.showNotification('danger', `Error testing ${service} connection: ${error.message}`);
        } finally {
            // Restore button state
            button.innerHTML = originalText;
            button.disabled = originalDisabled;
        }
    }

    updateConnectionStatus(service, result) {
        const statusElement = document.getElementById(`${service}-status`);
        const statusText = document.getElementById(`${service}-status-text`);
        const statusIcon = document.getElementById(`${service}-status-icon`);
        
        if (statusElement) {
            statusElement.className = `connection-status ${result.success ? 'text-success' : 'text-danger'}`;
        }

        if (statusText) {
            statusText.textContent = result.success ? 'Connected' : 'Disconnected';
            statusText.className = `badge bg-${result.success ? 'success' : 'danger'}`;
        }

        if (statusIcon) {
            statusIcon.className = `fas fa-${result.success ? 'check-circle' : 'times-circle'} fa-2x`;
        }

        // Update response time if available
        const responseTimeElement = document.getElementById(`${service}-response-time`);
        if (responseTimeElement && result.response_time) {
            responseTimeElement.textContent = `${result.response_time.toFixed(2)}s`;
        }
    }

    async refreshStatus() {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();
            
            this.updateConnectionStatus('opdv', status.opdv);
            this.updateConnectionStatus('omie', status.omie);
            
            // Update last refresh time
            const lastRefreshElement = document.getElementById('lastRefresh');
            if (lastRefreshElement) {
                lastRefreshElement.textContent = new Date().toLocaleTimeString();
            }

        } catch (error) {
            console.error('Status refresh error:', error);
        }
    }

    startStatusMonitoring() {
        // Initial status check
        this.refreshStatus();
        
        // Set up periodic refresh (every 2 minutes)
        this.statusInterval = setInterval(() => {
            this.refreshStatus();
        }, 120000);
    }

    toggleAutoRefresh(enabled) {
        if (enabled && !this.statusInterval) {
            this.startStatusMonitoring();
        } else if (!enabled && this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }
    }

    showSyncConfirmation() {
        const modal = new bootstrap.Modal(document.getElementById('syncModal'));
        modal.show();
    }

    showNotification(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            <i class="fas fa-${this.getAlertIcon(type)} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Insert at the top of the main container
        const container = document.querySelector('main.container');
        const firstChild = container.firstElementChild;
        container.insertBefore(alertDiv, firstChild);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }

    getAlertIcon(type) {
        const icons = {
            'success': 'check-circle',
            'danger': 'exclamation-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    initializeTooltips() {
        // Initialize Bootstrap tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Data table enhancements
    initializeDataTables() {
        // Initialize DataTables with custom configuration
        $('.data-table').DataTable({
            responsive: true,
            pageLength: 25,
            lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
            language: {
                search: "Search records:",
                lengthMenu: "Show _MENU_ records per page",
                info: "Showing _START_ to _END_ of _TOTAL_ records",
                paginate: {
                    first: "First",
                    last: "Last",
                    next: "Next",
                    previous: "Previous"
                }
            },
            columnDefs: [
                { targets: 'no-sort', orderable: false },
                { targets: 'text-center', className: 'text-center' },
                { targets: 'text-end', className: 'text-end' }
            ]
        });
    }

    // Progress tracking for sync operations
    showSyncProgress() {
        const progressBar = document.createElement('div');
        progressBar.className = 'sync-progress active';
        progressBar.id = 'syncProgress';
        document.body.appendChild(progressBar);
    }

    hideSyncProgress() {
        const progressBar = document.getElementById('syncProgress');
        if (progressBar) {
            progressBar.remove();
        }
    }

    // Export functionality
    exportData(format, dataType) {
        const timestamp = new Date().toISOString().split('T')[0];
        const filename = `${dataType}_export_${timestamp}.${format}`;
        
        if (format === 'csv') {
            this.exportToCSV(dataType, filename);
        } else if (format === 'json') {
            this.exportToJSON(dataType, filename);
        }
    }

    exportToCSV(dataType, filename) {
        const table = document.querySelector(`#${dataType}Table`);
        if (!table) return;

        const rows = Array.from(table.querySelectorAll('tr'));
        const csv = rows.map(row => {
            const cells = Array.from(row.querySelectorAll('th, td'));
            return cells.map(cell => `"${cell.textContent.replace(/"/g, '""')}"`).join(',');
        }).join('\n');

        this.downloadFile(csv, filename, 'text/csv');
    }

    exportToJSON(dataType, filename) {
        // This would need to be implemented based on the actual data structure
        // For now, we'll just show a notification
        this.showNotification('info', 'JSON export feature coming soon!');
    }

    downloadFile(content, filename, contentType) {
        const blob = new Blob([content], { type: contentType });
        const url = window.URL.createObjectURL(blob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    }

    // Utility functions
    formatCurrency(amount) {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(amount);
    }

    formatDate(dateString) {
        return new Date(dateString).toLocaleDateString('pt-BR');
    }

    formatDateTime(dateString) {
        return new Date(dateString).toLocaleString('pt-BR');
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.integrationDashboard = new IntegrationDashboard();
    
    // Initialize any data tables present on the page
    if (typeof $.fn.DataTable !== 'undefined') {
        window.integrationDashboard.initializeDataTables();
    }
});

// Global utility functions
function testConnection(service) {
    if (window.integrationDashboard) {
        const button = event.target;
        window.integrationDashboard.testConnection(service, button);
    }
}

function refreshStatus() {
    if (window.integrationDashboard) {
        window.integrationDashboard.refreshStatus();
    }
}

function exportData(format, dataType) {
    if (window.integrationDashboard) {
        window.integrationDashboard.exportData(format, dataType);
    }
}

function startSync() {
    // Hide modal footer, show progress
    const modalFooter = document.querySelector('#syncModal .modal-footer');
    const progressSection = document.getElementById('syncProgressSection');
    const confirmBtn = document.getElementById('confirmSyncBtn');
    
    if (modalFooter) modalFooter.style.display = 'none';
    if (progressSection) progressSection.style.display = 'block';
    if (confirmBtn) confirmBtn.disabled = true;
    
    // Show log container and start progress animation
    const logContainer = document.getElementById('sync-log-container');
    if (logContainer) {
        logContainer.style.display = 'block';
    }
    
    // Clear previous logs
    const syncLog = document.getElementById('sync-log');
    if (syncLog) {
        syncLog.innerHTML = '';
    }
    
    // Add initial log message
    setTimeout(() => {
        addSyncLogMessage('🚀 Iniciando processo de sincronização...');
    }, 100);
    
    let progress = 0;
    updateSyncProgress(10, 'Iniciando sincronização...');
    
    const progressInterval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress > 90) progress = 90;
        updateSyncProgress(progress, 'Sincronizando dados...');
    }, 1000);

    // Get selected items - apenas itens explicitamente selecionados
    const selectedOrders = Array.from(document.querySelectorAll('.order-checkbox:checked')).map(cb => cb.getAttribute('data-order-id'));
    const selectedCustomers = Array.from(document.querySelectorAll('.customer-checkbox:checked')).map(cb => cb.getAttribute('data-customer-id'));
    
    console.log('Selected orders:', selectedOrders);
    console.log('Selected customers:', selectedCustomers);
    
    // Verificar se algo foi selecionado
    if (selectedOrders.length === 0 && selectedCustomers.length === 0) {
        clearInterval(progressInterval);
        updateSyncProgress(100, 'Erro: Nenhum item selecionado!');
        setTimeout(() => {
            addSyncLogMessage('⚠️ Nenhum item foi selecionado para sincronização');
        }, 200);
        setTimeout(() => {
            const modal = bootstrap.Modal.getInstance(document.getElementById('syncModal'));
            if (modal) modal.hide();
            showNotification('warning', 'Selecione pelo menos um pedido ou cliente para sincronizar');
        }, 1500);
        return;
    }
    
    // Log dos itens selecionados
    setTimeout(() => {
        if (selectedOrders.length > 0) {
            addSyncLogMessage(`📦 ${selectedOrders.length} pedido(s) selecionado(s): ${selectedOrders.join(', ')}`);
            addDashboardSyncLog(`📦 ${selectedOrders.length} pedido(s) selecionado(s): ${selectedOrders.join(', ')}`);
        }
        if (selectedCustomers.length > 0) {
            addSyncLogMessage(`👥 ${selectedCustomers.length} cliente(s) selecionado(s): ${selectedCustomers.join(', ')}`);
            addDashboardSyncLog(`👥 ${selectedCustomers.length} cliente(s) selecionado(s): ${selectedCustomers.join(', ')}`);
        }
    }, 300);
    
    // Make the sync request with selected items
    fetch('/api/sync', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            selected_orders: selectedOrders,
            selected_customers: selectedCustomers
        })
    })
    .then(response => {
        clearInterval(progressInterval);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Always try to parse JSON response
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Resposta do servidor não é JSON válido');
        }
        
        return response.json();
    })
    .then(data => {
        // Show sync logs section
        document.getElementById('syncLogsSection').style.display = 'block';
        
        if (data.success) {
            updateSyncProgress(100, 'Sincronização concluída com sucesso!');
            addSyncLogMessage('✅ Sincronização concluída com sucesso!');
            addDashboardSyncLog('✅ Sincronização concluída com sucesso!');
            
            // Show customer results
            if (data.customer_results && data.customer_results.length > 0) {
                addDashboardSyncLog('📋 Resultados dos Clientes:');
                data.customer_results.forEach(customerResult => {
                    if (customerResult.success) {
                        const message = customerResult.already_exists 
                            ? `✅ Cliente ${customerResult.name}: Cliente já foi cadastrado anteriormente (ID: ${customerResult.omie_id})`
                            : `✅ Cliente ${customerResult.name}: Criado no Omie (ID: ${customerResult.omie_id})`;
                        addDashboardSyncLog(message);
                    } else {
                        addDashboardSyncLog(`❌ Cliente ${customerResult.name}: ${customerResult.error}`);
                    }
                });
            }
            
            // Show order results
            if (data.order_results && data.order_results.length > 0) {
                addDashboardSyncLog('📦 Resultados dos Pedidos:');
                data.order_results.forEach(orderResult => {
                    if (orderResult.success) {
                        addDashboardSyncLog(`✅ Pedido ${orderResult.order_number}: Criado no Omie (ID: ${orderResult.omie_id})`);
                    } else {
                        addDashboardSyncLog(`❌ Pedido ${orderResult.order_number}: ${orderResult.error}`);
                    }
                });
            }
            
            // Show summary
            if (data.summary) {
                addDashboardSyncLog('📊 Resumo da Sincronização:');
                Object.entries(data.summary).forEach(([key, value]) => {
                    if (typeof value === 'number' && value > 0) {
                        addDashboardSyncLog(`   ${key}: ${value}`);
                    }
                });
            }
            
            // Add close button and success notification
            setTimeout(() => {
                addSyncLogMessage('✨ Clique em "Fechar" para continuar');
                showNotification('success', data.message);
                // No auto-reload - user will refresh manually
            }, 1000);
        } else {
            updateSyncProgress(100, 'Erro na sincronização');
            addSyncLogMessage('❌ Erro na sincronização: ' + data.message);
            addDashboardSyncLog('❌ Erro na sincronização: ' + data.message);
            addSyncLogMessage('🔄 Tente novamente ou verifique os logs');
            showNotification('danger', data.message);
        }
        
        // Add manual close button instead of auto-close
        setTimeout(() => {
            const progressSection = document.getElementById('syncProgressSection');
            if (progressSection) {
                const closeButton = document.createElement('div');
                closeButton.className = 'text-center mt-3';
                closeButton.innerHTML = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>';
                progressSection.appendChild(closeButton);
            }
        }, 1500);
    })
    .catch(error => {
        clearInterval(progressInterval);
        console.error('Sync error:', error);
        
        let errorMessage = 'Falha na sincronização: ';
        if (error.message.includes('500')) {
            errorMessage += 'Erro do servidor. Tente novamente com menos registros.';
        } else if (error.message.includes('408')) {
            errorMessage += 'Operação expirou. Tente com menos registros.';
        } else {
            errorMessage += error.message;
        }
        
        // Show sync logs section
        document.getElementById('syncLogsSection').style.display = 'block';
        
        updateSyncProgress(100, 'Erro na comunicação');
        addSyncLogMessage('❌ Erro na conexão: ' + error.message);
        addDashboardSyncLog('❌ Erro na comunicação com o servidor: ' + error.message);
        addSyncLogMessage('🔄 Verifique a conexão e tente novamente');
        
        // Add manual close button for errors too
        setTimeout(() => {
            const progressSection = document.getElementById('syncProgressSection');
            if (progressSection) {
                const closeButton = document.createElement('div');
                closeButton.className = 'text-center mt-3';
                closeButton.innerHTML = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>';
                progressSection.appendChild(closeButton);
            }
            showNotification('danger', errorMessage);
        }, 1500);
    });
}

function updateSyncProgress(percentage, message) {
    const progressBar = document.querySelector('#syncProgressSection .progress-bar');
    const progressText = document.getElementById('syncProgressText');
    
    if (progressBar) {
        progressBar.style.width = `${percentage}%`;
        progressBar.setAttribute('aria-valuenow', percentage);
    }
    
    if (progressText) {
        progressText.textContent = message;
    }
}

function addSyncLogMessage(message) {
    const syncLog = document.getElementById('sync-log');
    if (syncLog) {
        const timestamp = new Date().toLocaleTimeString('pt-BR');
        const logEntry = document.createElement('div');
        logEntry.className = 'mb-1';
        logEntry.innerHTML = `<span class="text-primary">[${timestamp}]</span> ${message}`;
        syncLog.appendChild(logEntry);
        // Auto-scroll to bottom
        syncLog.scrollTop = syncLog.scrollHeight;
    }
}

function showNotification(type, message) {
    // Simple notification - could be enhanced with toast
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    const iconClass = type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle';
    
    const notification = document.createElement('div');
    notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        <i class="${iconClass} me-2"></i>${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 5000);
}

// Checkbox selection functions
function toggleAllOrders(selectAllCheckbox) {
    const orderCheckboxes = document.querySelectorAll('.order-checkbox');
    orderCheckboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
    updateSyncButton();
}

function toggleAllCustomers(selectAllCheckbox) {
    const customerCheckboxes = document.querySelectorAll('.customer-checkbox:not(:disabled)');
    customerCheckboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
    updateSyncButton();
}

window.updateSyncButton = function() {
    const selectedOrders = document.querySelectorAll('.order-checkbox:checked').length;
    const selectedCustomers = document.querySelectorAll('.customer-checkbox:checked').length;
    
    // Update modal summary
    const selectedOrdersCount = document.getElementById('selectedOrdersCount');
    const selectedCustomersCount = document.getElementById('selectedCustomersCount');
    const syncLimitAlert = document.getElementById('syncLimitAlert');
    
    if (selectedOrdersCount) selectedOrdersCount.textContent = selectedOrders;
    if (selectedCustomersCount) selectedCustomersCount.textContent = selectedCustomers;
    
    // Show/hide limit alert
    const totalSelected = selectedOrders + selectedCustomers;
    if (syncLimitAlert) {
        if (totalSelected > 10) {
            syncLimitAlert.style.display = 'block';
            syncLimitAlert.className = 'alert alert-danger';
            syncLimitAlert.innerHTML = '<i class="fas fa-exclamation-circle me-2"></i><strong>Limite excedido:</strong> Selecione no máximo 10 itens por sincronização.';
        } else if (totalSelected > 5) {
            syncLimitAlert.style.display = 'block';
            syncLimitAlert.className = 'alert alert-warning';
            syncLimitAlert.innerHTML = '<i class="fas fa-warning me-2"></i><strong>Atenção:</strong> Sincronizando ' + totalSelected + ' itens. Considere usar lotes menores para melhor performance.';
        } else {
            syncLimitAlert.style.display = 'none';
        }
    }
    
    // Enable/disable sync button
    const syncButton = document.querySelector('[data-bs-target="#syncModal"]');
    const confirmSyncBtn = document.getElementById('confirmSyncBtn');
    
    const hasSelection = selectedOrders > 0 || selectedCustomers > 0;
    
    if (syncButton) {
        syncButton.disabled = !hasSelection;
        const totalSelected = selectedOrders + selectedCustomers;
        if (!hasSelection) {
            syncButton.title = 'Selecione pelo menos um item para sincronizar';
        } else if (totalSelected > 10) {
            syncButton.disabled = true;
            syncButton.title = 'Máximo 10 itens por sincronização (API limit)';
        } else {
            syncButton.title = '';
        }
    }
    
    if (confirmSyncBtn) {
        const totalSelected = selectedOrders + selectedCustomers;
        confirmSyncBtn.disabled = !hasSelection || totalSelected > 10;
        
        if (totalSelected > 10) {
            confirmSyncBtn.title = 'Máximo 10 itens por sincronização';
        } else {
            confirmSyncBtn.title = '';
        }
    }
}

// Make functions available globally
window.toggleAllOrders = function(selectAllCheckbox) {
    const orderCheckboxes = document.querySelectorAll('.order-checkbox');
    orderCheckboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
    updateSyncButton();
}

window.toggleAllCustomers = function(selectAllCheckbox) {
    const customerCheckboxes = document.querySelectorAll('.customer-checkbox');
    customerCheckboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
    updateSyncButton();
}

// Dashboard sync log functions
function addDashboardSyncLog(message) {
    const container = document.getElementById('syncLogsContainer');
    if (!container) return;
    
    // Clear initial message
    if (container.querySelector('.text-muted')) {
        container.innerHTML = '';
    }
    
    const timestamp = new Date().toLocaleTimeString('pt-BR');
    const logEntry = document.createElement('div');
    logEntry.className = 'mb-1';
    logEntry.innerHTML = `<span class="text-secondary">[${timestamp}]</span> ${message}`;
    
    container.appendChild(logEntry);
    container.scrollTop = container.scrollHeight;
}

function clearSyncLogs() {
    const container = document.getElementById('syncLogsContainer');
    if (container) {
        container.innerHTML = '<div class="text-muted">Aguardando operações de sincronização...</div>';
    }
    // Hide the logs section
    const logsSection = document.getElementById('syncLogsSection');
    if (logsSection) {
        logsSection.style.display = 'none';
    }
}

// Handle page visibility changes for auto-refresh
document.addEventListener('visibilitychange', function() {
    if (window.integrationDashboard) {
        if (document.hidden) {
            // Pause auto-refresh when tab is not visible
            window.integrationDashboard.toggleAutoRefresh(false);
        } else {
            // Resume auto-refresh when tab becomes visible
            const autoRefreshToggle = document.getElementById('autoRefreshToggle');
            if (autoRefreshToggle && autoRefreshToggle.checked) {
                window.integrationDashboard.toggleAutoRefresh(true);
            }
        }
    }
});
