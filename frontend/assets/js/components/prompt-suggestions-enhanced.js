/**
 * Enhanced Prompt Suggestions Component
 * Handles display and interaction with prompt improvement suggestions
 * with advanced diff visualization and comparison features
 */
class PromptSuggestionsEnhanced {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.apiClient = new APIClient();
        this.suggestionsData = null;
        this.diffStates = {}; // Track which diffs are shown
    }

    init() {
        this.render();
        this.setupEventListeners();
        this.addCustomStyles();
    }

    /**
     * Add custom CSS for enhanced diff visualization
     */
    addCustomStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .diff-container {
                border: 1px solid #dee2e6;
                border-radius: 0.375rem;
                overflow: hidden;
            }
            
            .diff-line {
                padding: 0.25rem 0.5rem;
                font-family: 'Courier New', monospace;
                font-size: 0.875rem;
                line-height: 1.4;
                border-left: 3px solid transparent;
            }
            
            .diff-line.added {
                background-color: #d1edff;
                border-left-color: #0d6efd;
                color: #0c5460;
            }
            
            .diff-line.removed {
                background-color: #f8d7da;
                border-left-color: #dc3545;
                color: #721c24;
            }
            
            .diff-line.unchanged {
                background-color: #f8f9fa;
                color: #495057;
            }
            
            .diff-line-number {
                display: inline-block;
                width: 3rem;
                text-align: right;
                margin-right: 1rem;
                color: #6c757d;
                font-size: 0.75rem;
            }
            
            .code-container {
                position: relative;
            }
            
            .code-container::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 2px;
                background: linear-gradient(90deg, #dc3545, #0d6efd);
                border-radius: 0.375rem 0.375rem 0 0;
            }
            
            .suggested-code::before {
                background: linear-gradient(90deg, #198754, #0d6efd);
            }
            
            .fix-card {
                transition: all 0.3s ease;
                border-left: 4px solid transparent;
            }
            
            .fix-card.high-priority {
                border-left-color: #dc3545;
                box-shadow: 0 0 0 0.2rem rgba(220, 53, 69, 0.25);
            }
            
            .fix-card.medium-priority {
                border-left-color: #ffc107;
                box-shadow: 0 0 0 0.2rem rgba(255, 193, 7, 0.25);
            }
            
            .fix-card.low-priority {
                border-left-color: #198754;
                box-shadow: 0 0 0 0.2rem rgba(25, 135, 84, 0.25);
            }
            
            .code-line {
                display: flex;
                align-items: center;
                padding: 0.25rem 0;
                font-family: 'Courier New', monospace;
                font-size: 0.875rem;
                line-height: 1.4;
            }
            
            .line-number {
                display: inline-block;
                width: 3rem;
                text-align: right;
                margin-right: 1rem;
                color: #6c757d;
                font-size: 0.75rem;
                background-color: #f8f9fa;
                padding: 0.25rem 0.5rem;
                border-radius: 0.25rem;
            }
            
            .line-content {
                flex: 1;
                padding: 0.25rem 0.5rem;
                border-radius: 0.25rem;
            }
            
            .highlight-removed .line-content {
                background-color: #f8d7da;
                color: #721c24;
                border-left: 3px solid #dc3545;
            }
            
            .highlight-added .line-content {
                background-color: #d1edff;
                color: #0c5460;
                border-left: 3px solid #0d6efd;
            }
            
            .change-item {
                margin-bottom: 0.5rem;
                padding: 0.5rem;
                border-radius: 0.375rem;
                border-left: 4px solid;
            }
            
            .change-item.removed {
                background-color: #f8d7da;
                border-left-color: #dc3545;
            }
            
            .change-item.added {
                background-color: #d1edff;
                border-left-color: #0d6efd;
            }
            
            .change-type {
                font-weight: bold;
                margin-right: 0.5rem;
            }
            
            .change-line {
                color: #6c757d;
                font-size: 0.875rem;
                margin-right: 0.5rem;
            }
            
            .change-content {
                margin: 0.25rem 0 0 0;
                font-size: 0.875rem;
                background-color: rgba(255, 255, 255, 0.7);
                padding: 0.25rem 0.5rem;
                border-radius: 0.25rem;
            }
            
            .comparison-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 1rem;
            }
            
            @media (max-width: 768px) {
                .comparison-grid {
                    grid-template-columns: 1fr;
                }
            }
            
            .highlight-changes {
                animation: pulse 2s infinite;
            }
            
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.7; }
                100% { opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }

    render() {
        if (!this.suggestionsData) {
            this.container.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="bi bi-lightbulb display-4"></i>
                    <h4 class="mt-3">No Suggestions Yet</h4>
                    <p>Run an evaluation and click "Analyze Prompt" to get improvement suggestions.</p>
                </div>
            `;
            return;
        }

        this.container.innerHTML = `
            <div class="prompt-suggestions-enhanced">
                ${this.renderAnalysisOverview()}
                ${this.renderSpecificFixes()}
                ${this.renderSummary()}
            </div>
        `;
    }

    /**
     * Render analysis overview with enhanced metrics
     */
    renderAnalysisOverview() {
        const analysis = this.suggestionsData.analysis?.analysis || {};
        const fixes = this.suggestionsData.analysis?.specific_fixes || [];
        
        const highPriorityFixes = fixes.filter(f => f.priority === 'high').length;
        const mediumPriorityFixes = fixes.filter(f => f.priority === 'medium').length;
        const lowPriorityFixes = fixes.filter(f => f.priority === 'low').length;
        
        return `
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="mb-0">
                        <i class="bi bi-graph-up"></i> Analysis Overview
                    </h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-3">
                            <div class="text-center">
                                <div class="display-6 text-danger">${highPriorityFixes}</div>
                                <div class="text-muted">High Priority</div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="text-center">
                                <div class="display-6 text-warning">${mediumPriorityFixes}</div>
                                <div class="text-muted">Medium Priority</div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="text-center">
                                <div class="display-6 text-success">${lowPriorityFixes}</div>
                                <div class="text-muted">Low Priority</div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="text-center">
                                <div class="display-6 text-info">${fixes.length}</div>
                                <div class="text-muted">Total Fixes</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render specific fixes with enhanced diff visualization
     */
    renderSpecificFixes() {
        const fixes = this.suggestionsData.analysis?.specific_fixes || [];
        
        if (!fixes.length) {
            return '<div class="alert alert-info">No specific fixes available.</div>';
        }
        
        return `
            <div class="card mb-4">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">
                        <i class="bi bi-tools"></i> Specific Fixes (${fixes.length})
                    </h5>
                    <div class="btn-group btn-group-sm" role="group">
                        <button type="button" class="btn btn-outline-secondary" onclick="promptSuggestions.toggleAllDiffs()">
                            <i class="bi bi-arrow-left-right"></i> Toggle All Diffs
                        </button>
                        <button type="button" class="btn btn-outline-info" onclick="promptSuggestions.exportAllSuggestions()">
                            <i class="bi bi-download"></i> Export All
                        </button>
                    </div>
                </div>
                <div class="card-body">
                    ${fixes.map((fix, index) => this.renderFixCard(fix, index)).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Render individual fix card with enhanced visualization
     */
    renderFixCard(fix, index) {
        const priorityClass = this.getPriorityClass(fix.priority);
        const priorityIcon = this.getPriorityIcon(fix.priority);
        
        return `
            <div class="card mb-3 fix-card ${fix.priority}-priority">
                <div class="card-header ${priorityClass}">
                    <div class="d-flex justify-content-between align-items-center">
                        <h6 class="mb-0">
                            ${priorityIcon} ${fix.criterion} (${fix.avg_score}/100 → ${fix.target_score}/100)
                        </h6>
                        <div class="d-flex gap-2">
                            <span class="badge ${priorityClass}">${fix.priority.toUpperCase()}</span>
                            <span class="badge bg-info">${fix.expected_improvement}</span>
                        </div>
                    </div>
                </div>
                <div class="card-body">
                    <div class="alert alert-warning">
                        <strong><i class="bi bi-exclamation-triangle"></i> Problem:</strong> ${fix.problem_pattern}
                    </div>
                    
                    <!-- Enhanced Code Comparison with Line Numbers -->
                    <div class="comparison-grid">
                        <div class="current-code">
                            <h6><i class="bi bi-x-circle text-danger"></i> Current Code 
                                <small class="text-muted">(Dòng ${fix.line_range ? fix.line_range[0] : 'N/A'}-${fix.line_range ? fix.line_range[1] : 'N/A'})</small>
                            </h6>
                            <div class="code-container">
                                <pre class="bg-danger bg-opacity-10 p-3 rounded"><code>${this.renderCodeWithLineNumbers(fix.current_code, fix.line_range, 'current')}</code></pre>
                            </div>
                        </div>
                        <div class="suggested-code">
                            <h6><i class="bi bi-check-circle text-success"></i> Suggested Code 
                                <small class="text-muted">(Cải thiện)</small>
                            </h6>
                            <div class="code-container suggested-code">
                                <pre class="bg-success bg-opacity-10 p-3 rounded"><code>${this.renderCodeWithLineNumbers(fix.suggested_code, fix.line_range, 'suggested')}</code></pre>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Inline Diff View -->
                    <div class="mt-3">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6><i class="bi bi-arrow-left-right"></i> Diff View</h6>
                            <button class="btn btn-outline-secondary btn-sm" onclick="promptSuggestions.toggleDiff(${index})">
                                <i class="bi bi-eye"></i> Toggle Diff
                            </button>
                        </div>
                        <div id="diff-${index}" class="diff-container" style="display: none;">
                            <div class="diff-view">
                                ${this.generateDiff(fix.current_code, fix.suggested_code)}
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-3">
                        <h6><i class="bi bi-lightbulb"></i> Reasoning</h6>
                        <p class="text-muted bg-light p-3 rounded">${fix.reasoning}</p>
                    </div>
                    
                    ${fix.context_before ? `
                    <div class="mt-3">
                        <h6><i class="bi bi-arrow-up"></i> Context Trước</h6>
                        <pre class="bg-light p-2 rounded small">${this.escapeHtml(fix.context_before)}</pre>
                    </div>
                    ` : ''}
                    
                    ${fix.context_after ? `
                    <div class="mt-3">
                        <h6><i class="bi bi-arrow-down"></i> Context Sau</h6>
                        <pre class="bg-light p-2 rounded small">${this.escapeHtml(fix.context_after)}</pre>
                    </div>
                    ` : ''}
                    
                    ${fix.highlight_changes && fix.highlight_changes.length > 0 ? `
                    <div class="mt-3">
                        <h6><i class="bi bi-highlighter"></i> Chi tiết thay đổi</h6>
                        <div class="highlight-changes">
                            ${fix.highlight_changes.map(change => `
                                <div class="change-item ${change.type}">
                                    <span class="change-type">${change.type === 'removed' ? '❌ Xóa' : '✅ Thêm'}</span>
                                    <span class="change-line">Dòng ${change.line}</span>
                                    <pre class="change-content">${this.escapeHtml(change.text)}</pre>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    ` : ''}
                    
                    <div class="mt-3 d-flex gap-2 flex-wrap">
                        <button class="btn btn-outline-primary btn-sm" onclick="promptSuggestions.showDiffModal(${index})">
                            <i class="bi bi-arrow-left-right"></i> Full Diff
                        </button>
                        <button class="btn btn-outline-success btn-sm" onclick="promptSuggestions.applyFix(${index})">
                            <i class="bi bi-check-circle"></i> Apply Fix
                        </button>
                        <button class="btn btn-outline-info btn-sm" onclick="promptSuggestions.copyToClipboard(${index})">
                            <i class="bi bi-clipboard"></i> Copy
                        </button>
                        <button class="btn btn-outline-warning btn-sm" onclick="promptSuggestions.exportFix(${index})">
                            <i class="bi bi-download"></i> Export
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render code with line numbers and highlighting
     */
    renderCodeWithLineNumbers(code, lineRange, type) {
        const lines = code.split('\n');
        const startLine = lineRange ? lineRange[0] : 1;
        
        return lines.map((line, index) => {
            const lineNumber = startLine + index;
            const isHighlighted = type === 'current' ? 'highlight-removed' : 'highlight-added';
            
            return `<div class="code-line ${isHighlighted}">
                <span class="line-number">${lineNumber}</span>
                <span class="line-content">${this.escapeHtml(line)}</span>
            </div>`;
        }).join('');
    }

    /**
     * Generate diff visualization between current and suggested code
     */
    generateDiff(currentCode, suggestedCode) {
        const currentLines = currentCode.split('\n');
        const suggestedLines = suggestedCode.split('\n');
        
        let diffHtml = '';
        let currentIndex = 0;
        let suggestedIndex = 0;
        let lineNumber = 1;
        
        while (currentIndex < currentLines.length || suggestedIndex < suggestedLines.length) {
            const currentLine = currentLines[currentIndex] || '';
            const suggestedLine = suggestedLines[suggestedIndex] || '';
            
            if (currentLine === suggestedLine) {
                // Unchanged line
                diffHtml += `
                    <div class="diff-line unchanged">
                        <span class="diff-line-number">${lineNumber}</span>
                        ${this.escapeHtml(currentLine)}
                    </div>
                `;
                currentIndex++;
                suggestedIndex++;
            } else if (currentIndex >= currentLines.length) {
                // Added line
                diffHtml += `
                    <div class="diff-line added">
                        <span class="diff-line-number">+</span>
                        ${this.escapeHtml(suggestedLine)}
                    </div>
                `;
                suggestedIndex++;
            } else if (suggestedIndex >= suggestedLines.length) {
                // Removed line
                diffHtml += `
                    <div class="diff-line removed">
                        <span class="diff-line-number">-</span>
                        ${this.escapeHtml(currentLine)}
                    </div>
                `;
                currentIndex++;
            } else {
                // Modified line - show both
                diffHtml += `
                    <div class="diff-line removed">
                        <span class="diff-line-number">-</span>
                        ${this.escapeHtml(currentLine)}
                    </div>
                    <div class="diff-line added">
                        <span class="diff-line-number">+</span>
                        ${this.escapeHtml(suggestedLine)}
                    </div>
                `;
                currentIndex++;
                suggestedIndex++;
            }
            lineNumber++;
        }
        
        return diffHtml;
    }

    /**
     * Toggle diff visibility for a specific fix
     */
    toggleDiff(index) {
        const diffElement = document.getElementById(`diff-${index}`);
        if (diffElement) {
            const isVisible = diffElement.style.display !== 'none';
            diffElement.style.display = isVisible ? 'none' : 'block';
            this.diffStates[index] = !isVisible;
        }
    }

    /**
     * Toggle all diffs visibility
     */
    toggleAllDiffs() {
        const fixes = this.suggestionsData.analysis?.specific_fixes || [];
        const allVisible = Object.values(this.diffStates).every(state => state);
        
        fixes.forEach((_, index) => {
            const diffElement = document.getElementById(`diff-${index}`);
            if (diffElement) {
                diffElement.style.display = allVisible ? 'none' : 'block';
                this.diffStates[index] = !allVisible;
            }
        });
    }

    /**
     * Copy suggested code to clipboard
     */
    async copyToClipboard(index) {
        const fix = this.suggestionsData.analysis?.specific_fixes?.[index];
        if (fix) {
            try {
                await navigator.clipboard.writeText(fix.suggested_code);
                this.showToast('Copied to clipboard!', 'success');
            } catch (err) {
                this.showToast('Failed to copy to clipboard', 'error');
            }
        }
    }

    /**
     * Export individual fix
     */
    exportFix(index) {
        const fix = this.suggestionsData.analysis?.specific_fixes?.[index];
        if (fix) {
            const exportData = {
                criterion: fix.criterion,
                current_code: fix.current_code,
                suggested_code: fix.suggested_code,
                reasoning: fix.reasoning,
                priority: fix.priority,
                expected_improvement: fix.expected_improvement
            };
            
            this.downloadJSON(exportData, `fix-${fix.criterion}-${Date.now()}.json`);
        }
    }

    /**
     * Export all suggestions
     */
    exportAllSuggestions() {
        if (this.suggestionsData) {
            this.downloadJSON(this.suggestionsData, `prompt-suggestions-${Date.now()}.json`);
        }
    }

    /**
     * Show diff in modal
     */
    showDiffModal(index) {
        const fix = this.suggestionsData.analysis?.specific_fixes?.[index];
        if (fix) {
            const modalHtml = `
                <div class="modal fade" id="diffModal" tabindex="-1">
                    <div class="modal-dialog modal-xl">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Diff: ${fix.criterion}</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="diff-view">
                                    ${this.generateDiff(fix.current_code, fix.suggested_code)}
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                                <button type="button" class="btn btn-primary" onclick="promptSuggestions.copyToClipboard(${index})">Copy Suggested</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Remove existing modal
            const existingModal = document.getElementById('diffModal');
            if (existingModal) {
                existingModal.remove();
            }
            
            // Add new modal
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('diffModal'));
            modal.show();
        }
    }

    /**
     * Apply fix (placeholder - would integrate with prompt editor)
     */
    applyFix(index) {
        const fix = this.suggestionsData.analysis?.specific_fixes?.[index];
        if (fix) {
            this.showToast(`Fix for ${fix.criterion} applied!`, 'success');
            // Here you would integrate with actual prompt editor
        }
    }

    /**
     * Utility functions
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    downloadJSON(data, filename) {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    showToast(message, type = 'info') {
        // Simple toast implementation
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'error' ? 'danger' : type} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="bi bi-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
                ${message}
            </div>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    getPriorityClass(priority) {
        switch (priority.toLowerCase()) {
            case 'high': return 'bg-danger text-white';
            case 'medium': return 'bg-warning text-dark';
            case 'low': return 'bg-success text-white';
            default: return 'bg-secondary text-white';
        }
    }

    getPriorityIcon(priority) {
        switch (priority.toLowerCase()) {
            case 'high': return '<i class="bi bi-exclamation-triangle-fill"></i>';
            case 'medium': return '<i class="bi bi-exclamation-circle-fill"></i>';
            case 'low': return '<i class="bi bi-info-circle-fill"></i>';
            default: return '<i class="bi bi-question-circle-fill"></i>';
        }
    }

    /**
     * Load suggestions from API
     */
    async loadSuggestions(brandId, evaluationSummary) {
        try {
            this.container.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-2">Analyzing prompt suggestions...</p>
                </div>
            `;

            const response = await this.apiClient.request('/analyze/prompt-suggestions', {
                method: 'POST',
                body: JSON.stringify({
                    brand_id: brandId,
                    evaluation_summary: evaluationSummary
                })
            });

            this.suggestionsData = response;
            this.render();
        } catch (error) {
            console.error('Error loading suggestions:', error);
            this.container.innerHTML = `
                <div class="alert alert-danger">
                    <h5>Error Loading Suggestions</h5>
                    <p>${error.message}</p>
                </div>
            `;
        }
    }

    /**
     * Flexible loader: supports brandId or currentPrompt
     */
    async loadSuggestionsFlexible({ brandId = null, currentPrompt = null, evaluationSummary }) {
        try {
            this.container.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-2">Analyzing prompt suggestions...</p>
                </div>
            `;

            const body = {
                evaluation_summary: evaluationSummary
            };

            if (brandId) body.brand_id = brandId;
            if (!brandId && currentPrompt) body.current_prompt = currentPrompt;

            const response = await this.apiClient.request('/analyze/prompt-suggestions', {
                method: 'POST',
                body: JSON.stringify(body)
            });

            this.suggestionsData = response;
            this.render();
        } catch (error) {
            console.error('Error loading suggestions (flexible):', error);
            this.container.innerHTML = `
                <div class="alert alert-danger">
                    <h5>Error Loading Suggestions</h5>
                    <p>${error.message}</p>
                </div>
            `;
        }
    }

    setupEventListeners() {
        // Add any additional event listeners here
    }

    renderSummary() {
        const summary = this.suggestionsData?.analysis?.summary || 'No summary available';
        
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
}

// Make it globally available
window.PromptSuggestionsEnhanced = PromptSuggestionsEnhanced;
