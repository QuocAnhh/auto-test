/**
 * Results Table Component
 * Handles display and interaction with evaluation results
 */

class ResultsTable {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.data = [];
        this.filteredData = [];
        this.sortColumn = null;
        this.sortDirection = 'asc';
        this.currentPage = 1;
        this.itemsPerPage = 10;
        this.selectedRows = new Set();
    }

    /**
     * Initialize the results table
     */
    init() {
        this.render();
        this.setupEventListeners();
    }

    /**
     * Set data and refresh table
     */
    setData(data) {
        console.log('📊 ResultsTable.setData called with:', data ? data.length : 0, 'items');
        this.data = data;
        this.filteredData = [...data];
        this.currentPage = 1;
        this.selectedRows.clear();
        this.render();
        console.log('✅ ResultsTable rendered');
    }

    /**
     * Render the table
     */
    render() {
        if (!this.data || this.data.length === 0) {
            this.renderEmptyState();
            return;
        }

        const paginatedData = this.getPaginatedData();
        
        this.container.innerHTML = `
            <div class="table-controls mb-3">
                <div class="row align-items-center">
                    <div class="col-md-6">
                        <div class="input-group">
                            <span class="input-group-text">
                                <i class="bi bi-search"></i>
                            </span>
                            <input type="text" class="form-control" id="searchInput" placeholder="Search results...">
                        </div>
                    </div>
                    <div class="col-md-6 text-end">
                        <div class="btn-group" role="group">
                            <button class="btn btn-outline-primary btn-sm" id="selectAllBtn">
                                <i class="bi bi-check-square"></i> Select All
                            </button>
                            <button class="btn btn-outline-secondary btn-sm" id="clearSelectionBtn">
                                <i class="bi bi-square"></i> Clear
                            </button>
                            <button class="btn btn-outline-danger btn-sm" id="exportSelectedBtn" disabled>
                                <i class="bi bi-download"></i> Export Selected
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="table-responsive">
                <table class="table table-hover">
                    <thead class="table-dark">
                        <tr>
                            <th>
                                <input type="checkbox" class="form-check-input" id="selectAllCheckbox">
                            </th>
                            <th class="sortable" data-column="conversation_id">
                                ID <i class="bi bi-arrow-down-up"></i>
                            </th>
                            <th class="sortable" data-column="total_score">
                                Score <i class="bi bi-arrow-down-up"></i>
                            </th>
                            <th class="sortable" data-column="label">
                                Label <i class="bi bi-arrow-down-up"></i>
                            </th>
                            <th class="sortable" data-column="confidence">
                                Confidence <i class="bi bi-arrow-down-up"></i>
                            </th>
                            <th class="sortable" data-column="detected_flow">
                                Flow <i class="bi bi-arrow-down-up"></i>
                            </th>
                            <th class="sortable" data-column="processing_time">
                                Time <i class="bi bi-arrow-down-up"></i>
                            </th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${paginatedData.map(row => this.renderRow(row)).join('')}
                    </tbody>
                </table>
            </div>

            ${this.renderPagination()}
        `;

        this.updateSelectionUI();
    }

    /**
     * Render empty state
     */
    renderEmptyState() {
        this.container.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-inbox display-4"></i>
                <h4 class="mt-3">No Results Yet</h4>
                <p>Start an evaluation to see results here.</p>
            </div>
        `;
    }

    /**
     * Render table row
     */
    renderRow(row) {
        const isSelected = this.selectedRows.has(row.conversation_id);
        const scoreColor = this.getScoreColor(row.total_score);
        const confidenceColor = this.getConfidenceColor(row.confidence);
        
        return `
            <tr class="${isSelected ? 'table-primary' : ''}" data-id="${row.conversation_id}">
                <td>
                    <input type="checkbox" class="form-check-input row-checkbox" 
                           data-id="${row.conversation_id}" ${isSelected ? 'checked' : ''}>
                </td>
                <td>
                    <code>${row.conversation_id}</code>
                </td>
                <td>
                    <span class="badge ${scoreColor} fs-6">${this.getScore(row)}</span>
                </td>
                <td>
                    <span class="badge ${this.getLabelColor(this.getLabel(row))}">${this.getLabel(row)}</span>
                </td>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="progress me-2" style="width: 60px; height: 8px;">
                            <div class="progress-bar ${confidenceColor}" 
                                 style="width: ${this.getConfidence(row) * 100}%"></div>
                        </div>
                        <small>${(this.getConfidence(row) * 100).toFixed(1)}%</small>
                    </div>
                </td>
                <td>
                    <span class="badge bg-info">${row.detected_flow}</span>
                </td>
                <td>
                    <small class="text-muted">${this.formatDuration(row.processing_time)}</small>
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary btn-sm" 
                                onclick="resultsTable.viewDetails('${row.conversation_id}')"
                                title="View Details">
                            <i class="bi bi-eye"></i>
                        </button>
                        <button class="btn btn-outline-secondary btn-sm" 
                                onclick="resultsTable.exportRow('${row.conversation_id}')"
                                title="Export">
                            <i class="bi bi-download"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }

    /**
     * Render pagination
     */
    renderPagination() {
        const totalPages = Math.ceil(this.filteredData.length / this.itemsPerPage);
        if (totalPages <= 1) return '';

        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(totalPages, this.currentPage + 2);

        let paginationHTML = `
            <nav aria-label="Results pagination">
                <ul class="pagination justify-content-center">
                    <li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
                        <button class="page-link" onclick="resultsTable.goToPage(${this.currentPage - 1})">
                            <i class="bi bi-chevron-left"></i>
                        </button>
                    </li>
        `;

        for (let i = startPage; i <= endPage; i++) {
            paginationHTML += `
                <li class="page-item ${i === this.currentPage ? 'active' : ''}">
                    <button class="page-link" onclick="resultsTable.goToPage(${i})">${i}</button>
                </li>
            `;
        }

        paginationHTML += `
                    <li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}">
                        <button class="page-link" onclick="resultsTable.goToPage(${this.currentPage + 1})">
                            <i class="bi bi-chevron-right"></i>
                        </button>
                    </li>
                </ul>
            </nav>
        `;

        return paginationHTML;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterData(e.target.value);
            });
        }

        // Select all checkbox
        const selectAllCheckbox = document.getElementById('selectAllCheckbox');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                this.toggleSelectAll(e.target.checked);
            });
        }

        // Row checkboxes
        document.querySelectorAll('.row-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                this.toggleRowSelection(e.target.dataset.id, e.target.checked);
            });
        });

        // Sortable columns
        document.querySelectorAll('.sortable').forEach(header => {
            header.addEventListener('click', (e) => {
                this.sortData(e.target.dataset.column);
            });
        });

        // Action buttons
        document.getElementById('selectAllBtn')?.addEventListener('click', () => {
            this.selectAll();
        });

        document.getElementById('clearSelectionBtn')?.addEventListener('click', () => {
            this.clearSelection();
        });

        document.getElementById('exportSelectedBtn')?.addEventListener('click', () => {
            this.exportSelected();
        });
    }

    /**
     * Filter data based on search term
     */
    filterData(searchTerm) {
        if (!searchTerm.trim()) {
            this.filteredData = [...this.data];
        } else {
            const term = searchTerm.toLowerCase();
            this.filteredData = this.data.filter(row => 
                row.conversation_id.toLowerCase().includes(term) ||
                row.label.toLowerCase().includes(term) ||
                row.detected_flow.toLowerCase().includes(term)
            );
        }
        this.currentPage = 1;
        this.render();
    }

    /**
     * Sort data by column
     */
    sortData(column) {
        if (this.sortColumn === column) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = column;
            this.sortDirection = 'asc';
        }

        this.filteredData.sort((a, b) => {
            let aVal = a[column];
            let bVal = b[column];

            if (typeof aVal === 'string') {
                aVal = aVal.toLowerCase();
                bVal = bVal.toLowerCase();
            }

            if (this.sortDirection === 'asc') {
                return aVal > bVal ? 1 : -1;
            } else {
                return aVal < bVal ? 1 : -1;
            }
        });

        this.render();
    }

    /**
     * Get paginated data
     */
    getPaginatedData() {
        const start = (this.currentPage - 1) * this.itemsPerPage;
        const end = start + this.itemsPerPage;
        return this.filteredData.slice(start, end);
    }

    /**
     * Go to specific page
     */
    goToPage(page) {
        const totalPages = Math.ceil(this.filteredData.length / this.itemsPerPage);
        if (page >= 1 && page <= totalPages) {
            this.currentPage = page;
            this.render();
        }
    }

    /**
     * Toggle select all
     */
    toggleSelectAll(checked) {
        if (checked) {
            this.selectAll();
        } else {
            this.clearSelection();
        }
    }

    /**
     * Select all visible rows
     */
    selectAll() {
        const paginatedData = this.getPaginatedData();
        paginatedData.forEach(row => {
            this.selectedRows.add(row.conversation_id);
        });
        this.updateSelectionUI();
        this.render();
    }

    /**
     * Clear all selections
     */
    clearSelection() {
        this.selectedRows.clear();
        this.updateSelectionUI();
        this.render();
    }

    /**
     * Toggle row selection
     */
    toggleRowSelection(id, selected) {
        if (selected) {
            this.selectedRows.add(id);
        } else {
            this.selectedRows.delete(id);
        }
        this.updateSelectionUI();
    }

    /**
     * Update selection UI
     */
    updateSelectionUI() {
        const exportBtn = document.getElementById('exportSelectedBtn');
        if (exportBtn) {
            exportBtn.disabled = this.selectedRows.size === 0;
        }

        const selectAllCheckbox = document.getElementById('selectAllCheckbox');
        if (selectAllCheckbox) {
            const paginatedData = this.getPaginatedData();
            const allSelected = paginatedData.every(row => 
                this.selectedRows.has(row.conversation_id)
            );
            selectAllCheckbox.checked = allSelected && paginatedData.length > 0;
        }
    }

    /**
     * View details for specific row
     */
    viewDetails(conversationId) {
        const row = this.data.find(r => r.conversation_id === conversationId);
        if (row) {
            // Emit event for details view
            window.dispatchEvent(new CustomEvent('viewDetails', { 
                detail: { conversationId, data: row } 
            }));
        }
    }

    /**
     * Export specific row
     */
    exportRow(conversationId) {
        const row = this.data.find(r => r.conversation_id === conversationId);
        if (row) {
            this.exportData([row]);
        }
    }

    /**
     * Export selected rows
     */
    exportSelected() {
        const selectedData = this.data.filter(row => 
            this.selectedRows.has(row.conversation_id)
        );
        this.exportData(selectedData);
    }

    /**
     * Export data to CSV
     */
    exportData(data) {
        if (data.length === 0) return;

        const headers = ['ID', 'Score', 'Label', 'Confidence', 'Flow', 'Time'];
        const csvContent = [
            headers.join(','),
            ...data.map(row => [
                row.conversation_id,
                row.total_score,
                row.label,
                row.confidence,
                row.detected_flow,
                row.processing_time
            ].join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `evaluation_results_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
    }

    /**
     * Get score color class
     */
    getScoreColor(score) {
        if (score >= 80) return 'bg-success';
        if (score >= 60) return 'bg-warning';
        return 'bg-danger';
    }

    /**
     * Get confidence color class
     */
    getConfidenceColor(confidence) {
        if (confidence >= 0.8) return 'bg-success';
        if (confidence >= 0.6) return 'bg-warning';
        return 'bg-danger';
    }

    /**
     * Get label color class
     */
    getLabelColor(label) {
        switch (label.toLowerCase()) {
            case 'excellent': return 'bg-success';
            case 'good': return 'bg-primary';
            case 'fair': return 'bg-warning';
            case 'poor': return 'bg-danger';
            default: return 'bg-secondary';
        }
    }

    /**
     * Get score from different data structures
     */
    getScore(row) {
        // Handle bulk evaluation format
        if (row.result && row.result.total_score !== undefined) {
            return row.result.total_score.toFixed(1);
        }
        // Handle direct format
        if (row.total_score !== undefined) {
            return row.total_score.toFixed(1);
        }
        // Default fallback
        return '0.0';
    }

    /**
     * Get label from different data structures
     */
    getLabel(row) {
        // Handle bulk evaluation format
        if (row.result && row.result.label !== undefined) {
            return row.result.label;
        }
        // Handle direct format
        if (row.label !== undefined) {
            return row.label;
        }
        // Default fallback
        return 'unknown';
    }

    /**
     * Get confidence from different data structures
     */
    getConfidence(row) {
        // Handle bulk evaluation format
        if (row.result && row.result.confidence !== undefined) {
            return row.result.confidence;
        }
        // Handle direct format
        if (row.confidence !== undefined) {
            return row.confidence;
        }
        // Default fallback
        return 0.5;
    }

    /**
     * Format duration
     */
    formatDuration(seconds) {
        if (seconds < 60) {
            return `${seconds.toFixed(1)}s`;
        } else {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = Math.floor(seconds % 60);
            return `${minutes}m ${remainingSeconds}s`;
        }
    }
}

// Export for global use
window.ResultsTable = ResultsTable;
