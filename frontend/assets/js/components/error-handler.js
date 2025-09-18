/**
 * Error Handler Component
 * Comprehensive error management and user feedback
 */

class ErrorHandler {
    constructor() {
        this.errorLog = [];
        this.maxLogSize = 100;
        this.setupGlobalErrorHandling();
    }

    /**
     * Setup global error handling
     */
    setupGlobalErrorHandling() {
        // Global JavaScript errors
        window.addEventListener('error', (event) => {
            this.handleError({
                type: 'javascript',
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                error: event.error
            });
        });

        // Unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError({
                type: 'promise',
                message: event.reason?.message || 'Unhandled promise rejection',
                error: event.reason
            });
        });

        // Network errors
        window.addEventListener('online', () => {
            this.showAlert('Connection restored', 'success');
        });

        window.addEventListener('offline', () => {
            this.handleError({
                type: 'network',
                message: 'Network connection lost',
                severity: 'warning'
            });
        });
    }

    /**
     * Handle error
     */
    handleError(error) {
        const errorEntry = {
            id: Date.now().toString(),
            timestamp: new Date().toISOString(),
            type: error.type || 'unknown',
            message: error.message || 'Unknown error',
            severity: error.severity || 'error',
            details: error.details || null,
            stack: error.stack || null,
            userAgent: navigator.userAgent,
            url: window.location.href
        };

        // Add to error log
        this.errorLog.unshift(errorEntry);
        if (this.errorLog.length > this.maxLogSize) {
            this.errorLog.pop();
        }

        // Log to console
        console.error('Error handled:', errorEntry);

        // Show user notification
        this.showErrorNotification(errorEntry);

        // Send to monitoring service (if configured)
        this.sendToMonitoring(errorEntry);

        return errorEntry;
    }

    /**
     * Show error notification
     */
    showErrorNotification(error) {
        const alertType = this.getAlertType(error.severity);
        const icon = this.getErrorIcon(error.type);
        
        const alertHTML = `
            <div class="alert ${alertType} alert-dismissible fade show" role="alert">
                <div class="d-flex align-items-center">
                    <i class="bi ${icon} me-2"></i>
                    <div class="flex-grow-1">
                        <strong>${this.getErrorTitle(error.type)}</strong>
                        <div class="small">${error.message}</div>
                    </div>
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
                ${error.severity === 'error' ? `
                    <div class="mt-2">
                        <button class="btn btn-sm btn-outline-secondary" onclick="errorHandler.showErrorDetails('${error.id}')">
                            <i class="bi bi-info-circle"></i> Details
                        </button>
                        <button class="btn btn-sm btn-outline-primary" onclick="errorHandler.retryLastAction()">
                            <i class="bi bi-arrow-clockwise"></i> Retry
                        </button>
                    </div>
                ` : ''}
            </div>
        `;

        // Insert at top of main content
        const mainContent = document.querySelector('.col-md-9');
        if (mainContent) {
            mainContent.insertBefore(this.createAlertElement(alertHTML), mainContent.firstChild);
        }
    }

    /**
     * Create alert element
     */
    createAlertElement(html) {
        const div = document.createElement('div');
        div.innerHTML = html;
        return div.firstElementChild;
    }

    /**
     * Get alert type based on severity
     */
    getAlertType(severity) {
        switch (severity) {
            case 'error': return 'alert-danger';
            case 'warning': return 'alert-warning';
            case 'info': return 'alert-info';
            default: return 'alert-secondary';
        }
    }

    /**
     * Get error icon based on type
     */
    getErrorIcon(type) {
        switch (type) {
            case 'network': return 'bi-wifi-off';
            case 'api': return 'bi-cloud-slash';
            case 'javascript': return 'bi-bug';
            case 'promise': return 'bi-exclamation-triangle';
            case 'validation': return 'bi-exclamation-circle';
            default: return 'bi-exclamation-octagon';
        }
    }

    /**
     * Get error title based on type
     */
    getErrorTitle(type) {
        switch (type) {
            case 'network': return 'Network Error';
            case 'api': return 'API Error';
            case 'javascript': return 'JavaScript Error';
            case 'promise': return 'Promise Rejection';
            case 'validation': return 'Validation Error';
            default: return 'Error';
        }
    }

    /**
     * Show error details
     */
    showErrorDetails(errorId) {
        const error = this.errorLog.find(e => e.id === errorId);
        if (!error) return;

        const modal = this.createErrorDetailsModal(error);
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    /**
     * Create error details modal
     */
    createErrorDetailsModal(error) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi ${this.getErrorIcon(error.type)}"></i>
                            Error Details
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6>Basic Information</h6>
                                <table class="table table-sm">
                                    <tr><td><strong>Type:</strong></td><td>${error.type}</td></tr>
                                    <tr><td><strong>Severity:</strong></td><td><span class="badge ${this.getAlertType(error.severity)}">${error.severity}</span></td></tr>
                                    <tr><td><strong>Time:</strong></td><td>${new Date(error.timestamp).toLocaleString()}</td></tr>
                                    <tr><td><strong>URL:</strong></td><td><code>${error.url}</code></td></tr>
                                </table>
                            </div>
                            <div class="col-md-6">
                                <h6>Message</h6>
                                <div class="bg-light p-3 rounded">
                                    <code>${error.message}</code>
                                </div>
                            </div>
                        </div>
                        ${error.stack ? `
                            <div class="mt-3">
                                <h6>Stack Trace</h6>
                                <pre class="bg-dark text-light p-3 rounded" style="max-height: 200px; overflow-y: auto;">${error.stack}</pre>
                            </div>
                        ` : ''}
                        ${error.details ? `
                            <div class="mt-3">
                                <h6>Additional Details</h6>
                                <pre class="bg-light p-3 rounded">${JSON.stringify(error.details, null, 2)}</pre>
                            </div>
                        ` : ''}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" onclick="errorHandler.copyErrorDetails('${error.id}')">
                            <i class="bi bi-clipboard"></i> Copy Details
                        </button>
                        <button type="button" class="btn btn-danger" onclick="errorHandler.reportError('${error.id}')">
                            <i class="bi bi-bug"></i> Report Bug
                        </button>
                    </div>
                </div>
            </div>
        `;
        return modal;
    }

    /**
     * Copy error details to clipboard
     */
    copyErrorDetails(errorId) {
        const error = this.errorLog.find(e => e.id === errorId);
        if (!error) return;

        const details = {
            type: error.type,
            message: error.message,
            severity: error.severity,
            timestamp: error.timestamp,
            url: error.url,
            stack: error.stack,
            details: error.details
        };

        navigator.clipboard.writeText(JSON.stringify(details, null, 2))
            .then(() => {
                this.showAlert('Error details copied to clipboard', 'success');
            })
            .catch(err => {
                console.error('Failed to copy to clipboard:', err);
            });
    }

    /**
     * Report error
     */
    reportError(errorId) {
        const error = this.errorLog.find(e => e.id === errorId);
        if (!error) return;

        // This would typically send to a bug reporting service
        console.log('Reporting error:', error);
        this.showAlert('Error reported successfully', 'success');
    }

    /**
     * Retry last action
     */
    retryLastAction() {
        // This would retry the last failed action
        console.log('Retrying last action...');
        this.showAlert('Retrying last action...', 'info');
    }

    /**
     * Send to monitoring service
     */
    sendToMonitoring(error) {
        // This would send to monitoring services like Sentry, LogRocket, etc.
        if (error.severity === 'error') {
            console.log('Sending error to monitoring service:', error);
        }
    }

    /**
     * Show alert
     */
    showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        const mainContent = document.querySelector('.col-md-9');
        if (mainContent) {
            mainContent.insertBefore(alertDiv, mainContent.firstChild);
        }

        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }

    /**
     * Get error log
     */
    getErrorLog() {
        return this.errorLog;
    }

    /**
     * Clear error log
     */
    clearErrorLog() {
        this.errorLog = [];
    }

    /**
     * Get error statistics
     */
    getErrorStatistics() {
        const stats = {
            total: this.errorLog.length,
            byType: {},
            bySeverity: {},
            recent: this.errorLog.filter(e => 
                Date.now() - new Date(e.timestamp).getTime() < 24 * 60 * 60 * 1000
            ).length
        };

        this.errorLog.forEach(error => {
            stats.byType[error.type] = (stats.byType[error.type] || 0) + 1;
            stats.bySeverity[error.severity] = (stats.bySeverity[error.severity] || 0) + 1;
        });

        return stats;
    }
}

// Export for global use
window.ErrorHandler = ErrorHandler;
