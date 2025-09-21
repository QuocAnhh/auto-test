/**
 * Prompt Suggestions Component
 * Displays LLM-based prompt analysis and improvement suggestions
 */

class PromptSuggestions {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.data = null;
        this.isLoading = false;
    }

    /**
     * Initialize the component
     */
    init() {
        this.render();
    }

    /**
     * Set data and refresh display
     */
    setData(data) {
        this.data = data;
        this.render();
    }

    /**
     * Render the component
     */
    render() {
        if (!this.data) {
            this.renderEmptyState();
            return;
        }

        this.container.innerHTML = `
            <div class="prompt-suggestions-container">
                ${this.renderHeader()}
                ${this.renderAnalysis()}
                ${this.renderSpecificFixes()}
                ${this.renderSummary()}
            </div>
        `;
    }

    /**
     * Render empty state
     */
    renderEmptyState() {
        this.container.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-lightbulb display-4"></i>
                <h4 class="mt-3">No Prompt Analysis Yet</h4>
                <p>Run an evaluation to get prompt improvement suggestions.</p>
            </div>
        `;
    }

    /**
     * Render header section
     */
    renderHeader() {
        const brandId = this.data.brand_id || 'Unknown Brand';
        const timestamp = this.data.timestamp ? new Date(this.data.timestamp).toLocaleString() : 'Unknown';
        
        return `
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="mb-0">
                        <i class="bi bi-stethoscope"></i> Prompt Analysis Results
                    </h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <strong>Brand:</strong> ${brandId}
                        </div>
                        <div class="col-md-6">
                            <strong>Analyzed:</strong> ${timestamp}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render analysis overview
     */
    renderAnalysis() {
        const analysis = this.data.analysis || {};
        const patterns = analysis.overall_patterns || [];
        const issues = analysis.critical_issues || [];
        const trends = analysis.trends || [];

        return `
            <div class="card mb-4">
                <div class="card-header">
                    <h6 class="mb-0">
                        <i class="bi bi-graph-up"></i> Analysis Overview
                    </h6>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-4">
                            <h6>Overall Patterns</h6>
                            ${patterns.length > 0 ? 
                                patterns.map(pattern => `<div class="alert alert-info alert-sm">${pattern}</div>`).join('') :
                                '<div class="text-muted">No patterns identified</div>'
                            }
                        </div>
                        <div class="col-md-4">
                            <h6>Critical Issues</h6>
                            ${issues.length > 0 ? 
                                issues.map(issue => `<div class="alert alert-danger alert-sm">${issue}</div>`).join('') :
                                '<div class="text-muted">No critical issues</div>'
                            }
                        </div>
                        <div class="col-md-4">
                            <h6>Trends</h6>
                            ${trends.length > 0 ? 
                                trends.map(trend => `<div class="alert alert-warning alert-sm">${trend}</div>`).join('') :
                                '<div class="text-muted">No trends identified</div>'
                            }
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render specific fixes
     */
    renderSpecificFixes() {
        const fixes = this.data.analysis?.specific_fixes || [];
        
        if (fixes.length === 0) {
            return `
                <div class="card mb-4">
                    <div class="card-header">
                        <h6 class="mb-0">
                            <i class="bi bi-tools"></i> Specific Fixes
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="text-muted">No specific fixes identified</div>
                    </div>
                </div>
            `;
        }

        return `
            <div class="card mb-4">
                <div class="card-header">
                    <h6 class="mb-0">
                        <i class="bi bi-tools"></i> Specific Fixes (${fixes.length})
                    </h6>
                </div>
                <div class="card-body">
                    ${fixes.map((fix, index) => this.renderFixCard(fix, index)).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Render individual fix card
     */
    renderFixCard(fix, index) {
        const priorityClass = this.getPriorityClass(fix.priority);
        const priorityIcon = this.getPriorityIcon(fix.priority);
        
        return `
            <div class="card mb-3">
                <div class="card-header ${priorityClass}">
                    <div class="d-flex justify-content-between align-items-center">
                        <h6 class="mb-0">
                            ${priorityIcon} ${fix.criterion} (${fix.avg_score}/100 → ${fix.target_score}/100)
                        </h6>
                        <span class="badge ${priorityClass}">${fix.priority.toUpperCase()}</span>
                    </div>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h6>Problem Pattern</h6>
                            <p class="text-muted">${fix.problem_pattern}</p>
                            
                            <h6>Prompt Section</h6>
                            <p class="text-info">${fix.prompt_section} (Lines ${fix.line_range[0]}-${fix.line_range[1]})</p>
                            
                            <h6>Expected Improvement</h6>
                            <p class="text-success">${fix.expected_improvement}</p>
                        </div>
                        <div class="col-md-6">
                            <h6>Current Code</h6>
                            <pre class="bg-light p-2 rounded"><code>${fix.current_code}</code></pre>
                            
                            <h6>Suggested Code</h6>
                            <pre class="bg-success bg-opacity-10 p-2 rounded"><code>${fix.suggested_code}</code></pre>
                        </div>
                    </div>
                    
                    <div class="mt-3">
                        <h6>Reasoning</h6>
                        <p class="text-muted">${fix.reasoning}</p>
                    </div>
                    
                    <div class="mt-3">
                        <button class="btn btn-outline-primary btn-sm" onclick="promptSuggestions.showDiff(${index})">
                            <i class="bi bi-arrow-left-right"></i> Show Diff
                        </button>
                        <button class="btn btn-outline-success btn-sm" onclick="promptSuggestions.applyFix(${index})">
                            <i class="bi bi-check-circle"></i> Apply Fix
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render summary section
     */
    renderSummary() {
        const summary = this.data.analysis?.summary || 'No summary available';
        
        return `
            <div class="card">
                <div class="card-header">
                    <h6 class="mb-0">
                        <i class="bi bi-file-text"></i> Summary
                    </h6>
                </div>
                <div class="card-body">
                    <p class="mb-0">${summary}</p>
                </div>
            </div>
        `;
    }

    /**
     * Get priority CSS class
     */
    getPriorityClass(priority) {
        switch (priority.toLowerCase()) {
            case 'high': return 'bg-danger text-white';
            case 'medium': return 'bg-warning text-dark';
            case 'low': return 'bg-info text-white';
            default: return 'bg-secondary text-white';
        }
    }

    /**
     * Get priority icon
     */
    getPriorityIcon(priority) {
        switch (priority.toLowerCase()) {
            case 'high': return '<i class="bi bi-exclamation-triangle-fill"></i>';
            case 'medium': return '<i class="bi bi-exclamation-circle-fill"></i>';
            case 'low': return '<i class="bi bi-info-circle-fill"></i>';
            default: return '<i class="bi bi-question-circle-fill"></i>';
        }
    }

    /**
     * Show diff view for a specific fix
     */
    showDiff(fixIndex) {
        const fix = this.data.analysis?.specific_fixes?.[fixIndex];
        if (!fix) return;

        // Create modal for diff view
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Diff View - ${fix.criterion}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6>Current Code</h6>
                                <pre class="bg-light p-3 rounded"><code>${fix.current_code}</code></pre>
                            </div>
                            <div class="col-md-6">
                                <h6>Suggested Code</h6>
                                <pre class="bg-success bg-opacity-10 p-3 rounded"><code>${fix.suggested_code}</code></pre>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" onclick="promptSuggestions.applyFix(${fixIndex})">Apply Fix</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        // Clean up modal after it's hidden
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }

    /**
     * Apply a specific fix
     */
    applyFix(fixIndex) {
        const fix = this.data.analysis?.specific_fixes?.[fixIndex];
        if (!fix) return;

        // Emit event for fix application
        window.dispatchEvent(new CustomEvent('applyPromptFix', {
            detail: {
                fix: fix,
                fixIndex: fixIndex
            }
        }));

        // Show success message
        this.showAlert(`Fix for ${fix.criterion} has been applied!`, 'success');
    }

    /**
     * Show alert message
     */
    showAlert(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        this.container.insertBefore(alertDiv, this.container.firstChild);

        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }

    /**
     * Load prompt suggestions for a brand
     */
    async loadSuggestions(brandId, evaluationSummary) {
        this.isLoading = true;
        this.renderLoadingState();

        try {
            const response = await fetch('/analyze/prompt-suggestions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    brand_id: brandId,
                    evaluation_summary: evaluationSummary
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            this.setData(data);
        } catch (error) {
            console.error('Error loading prompt suggestions:', error);
            this.showAlert(`Error loading suggestions: ${error.message}`, 'danger');
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * Render loading state
     */
    renderLoadingState() {
        this.container.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-3">Analyzing prompt and generating suggestions...</p>
            </div>
        `;
    }
}

// Export for global use
window.PromptSuggestions = PromptSuggestions;
