/**
 * Export Component
 * Handles data export functionality (PDF, Excel, CSV)
 */

class ExportManager {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.data = null;
        this.exportFormats = ['csv', 'excel', 'pdf'];
    }

    /**
     * Initialize export manager
     */
    init() {
        this.render();
    }

    /**
     * Set data for export
     */
    setData(data) {
        this.data = data;
        this.render();
    }

    /**
     * Render export options
     */
    render() {
        if (!this.data || this.data.length === 0) {
            this.renderEmptyState();
            return;
        }

        this.container.innerHTML = `
            <div class="row">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-download"></i> Export Options</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-4 mb-3">
                                    <div class="card h-100">
                                        <div class="card-body text-center">
                                            <i class="bi bi-file-earmark-spreadsheet display-4 text-success"></i>
                                            <h5 class="mt-3">Excel Export</h5>
                                            <p class="text-muted">Export to Excel with formatting and charts</p>
                                            <button class="btn btn-success" onclick="exportManager.exportExcel()">
                                                <i class="bi bi-download"></i> Export Excel
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-4 mb-3">
                                    <div class="card h-100">
                                        <div class="card-body text-center">
                                            <i class="bi bi-file-earmark-pdf display-4 text-danger"></i>
                                            <h5 class="mt-3">PDF Report</h5>
                                            <p class="text-muted">Generate comprehensive PDF report</p>
                                            <button class="btn btn-danger" onclick="exportManager.exportPDF()">
                                                <i class="bi bi-download"></i> Export PDF
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-4 mb-3">
                                    <div class="card h-100">
                                        <div class="card-body text-center">
                                            <i class="bi bi-file-earmark-text display-4 text-primary"></i>
                                            <h5 class="mt-3">CSV Export</h5>
                                            <p class="text-muted">Simple CSV format for data analysis</p>
                                            <button class="btn btn-primary" onclick="exportManager.exportCSV()">
                                                <i class="bi bi-download"></i> Export CSV
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-gear"></i> Export Settings</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label class="form-label">Include Charts</label>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="includeCharts" checked>
                                    <label class="form-check-label" for="includeCharts">
                                        Include analytics charts
                                    </label>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Include Raw Data</label>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="includeRawData" checked>
                                    <label class="form-check-label" for="includeRawData">
                                        Include detailed conversation data
                                    </label>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Include Performance Metrics</label>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="includePerformance" checked>
                                    <label class="form-check-label" for="includePerformance">
                                        Include performance analysis
                                    </label>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Report Title</label>
                                <input type="text" class="form-control" id="reportTitle" 
                                       value="BusQA LLM Evaluation Report">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-info-circle"></i> Export Preview</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-3">
                                    <div class="text-center">
                                        <div class="h4 text-primary">${this.data.length}</div>
                                        <div class="text-muted">Total Conversations</div>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="text-center">
                                        <div class="h4 text-success">${this.calculateSuccessRate()}%</div>
                                        <div class="text-muted">Success Rate</div>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="text-center">
                                        <div class="h4 text-info">${this.calculateAverageScore().toFixed(1)}</div>
                                        <div class="text-muted">Average Score</div>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="text-center">
                                        <div class="h4 text-warning">${this.calculateProcessingTime().toFixed(1)}s</div>
                                        <div class="text-muted">Avg Processing Time</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            ${this.renderExportHistory()}
        `;
    }

    /**
     * Render empty state
     */
    renderEmptyState() {
        this.container.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-download display-4"></i>
                <h4 class="mt-3">No Data to Export</h4>
                <p>Run an evaluation to see export options.</p>
            </div>
        `;
    }

    /**
     * Render export history
     */
    renderExportHistory() {
        const history = this.getExportHistory();
        if (history.length === 0) return '';

        return `
            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-clock-history"></i> Recent Exports</h5>
                        </div>
                        <div class="card-body">
                            <div class="table-responsive">
                                <table class="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Format</th>
                                            <th>Size</th>
                                            <th>Status</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${history.map(item => `
                                            <tr>
                                                <td>${new Date(item.date).toLocaleString()}</td>
                                                <td><span class="badge bg-${item.format === 'pdf' ? 'danger' : item.format === 'excel' ? 'success' : 'primary'}">${item.format.toUpperCase()}</span></td>
                                                <td>${item.size}</td>
                                                <td><span class="badge bg-success">Completed</span></td>
                                                <td>
                                                    <button class="btn btn-sm btn-outline-primary" onclick="exportManager.downloadExport('${item.id}')">
                                                        <i class="bi bi-download"></i>
                                                    </button>
                                                </td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Export to Excel
     */
    async exportExcel() {
        try {
            this.showExportProgress('Preparing Excel export...');
            
            const workbook = await this.createExcelWorkbook();
            const buffer = await workbook.xlsx.writeBuffer();
            
            this.downloadFile(buffer, 'evaluation_results.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
            this.addToExportHistory('excel', this.getFileSize(buffer));
            this.hideExportProgress();
            
        } catch (error) {
            console.error('Excel export error:', error);
            this.showExportError('Failed to export Excel file');
        }
    }

    /**
     * Export to PDF
     */
    async exportPDF() {
        try {
            this.showExportProgress('Generating PDF report...');
            
            const pdfDoc = await this.createPDFDocument();
            const pdfBytes = await pdfDoc.save();
            
            this.downloadFile(pdfBytes, 'evaluation_report.pdf', 'application/pdf');
            this.addToExportHistory('pdf', this.getFileSize(pdfBytes));
            this.hideExportProgress();
            
        } catch (error) {
            console.error('PDF export error:', error);
            this.showExportError('Failed to export PDF file');
        }
    }

    /**
     * Export to CSV
     */
    exportCSV() {
        try {
            this.showExportProgress('Preparing CSV export...');
            
            const csvContent = this.createCSVContent();
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            
            this.downloadBlob(blob, 'evaluation_results.csv');
            this.addToExportHistory('csv', this.getFileSize(blob));
            this.hideExportProgress();
            
        } catch (error) {
            console.error('CSV export error:', error);
            this.showExportError('Failed to export CSV file');
        }
    }

    /**
     * Create Excel workbook
     */
    async createExcelWorkbook() {
        // This would use a library like ExcelJS
        // For now, we'll create a simple CSV-like structure
        const XLSX = await import('https://cdn.sheetjs.com/xlsx-0.20.1/package/xlsx.mjs');
        
        const worksheet = XLSX.utils.json_to_sheet(this.data);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, 'Evaluation Results');
        
        return workbook;
    }

    /**
     * Create PDF document
     */
    async createPDFDocument() {
        // This would use a library like jsPDF
        const { jsPDF } = await import('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js');
        
        const doc = new jsPDF();
        
        // Add title
        doc.setFontSize(20);
        doc.text('BusQA LLM Evaluation Report', 20, 30);
        
        // Add summary
        doc.setFontSize(12);
        doc.text(`Total Conversations: ${this.data.length}`, 20, 50);
        doc.text(`Success Rate: ${this.calculateSuccessRate()}%`, 20, 60);
        doc.text(`Average Score: ${this.calculateAverageScore().toFixed(1)}`, 20, 70);
        
        // Add data table
        const tableData = this.data.map(item => [
            item.conversation_id,
            item.total_score,
            item.label,
            item.confidence,
            item.detected_flow
        ]);
        
        doc.autoTable({
            head: [['ID', 'Score', 'Label', 'Confidence', 'Flow']],
            body: tableData,
            startY: 80
        });
        
        return doc;
    }

    /**
     * Create CSV content
     */
    createCSVContent() {
        const headers = ['ID', 'Score', 'Label', 'Confidence', 'Flow', 'Processing Time'];
        const rows = this.data.map(item => [
            item.conversation_id,
            item.total_score,
            item.label,
            item.confidence,
            item.detected_flow,
            item.processing_time || 0
        ]);
        
        return [headers, ...rows].map(row => 
            row.map(cell => `"${cell}"`).join(',')
        ).join('\n');
    }

    /**
     * Download file
     */
    downloadFile(buffer, filename, mimeType) {
        const blob = new Blob([buffer], { type: mimeType });
        this.downloadBlob(blob, filename);
    }

    /**
     * Download blob
     */
    downloadBlob(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    /**
     * Show export progress
     */
    showExportProgress(message) {
        // Create progress modal if it doesn't exist
        let modal = document.getElementById('exportProgressModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'exportProgressModal';
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-body text-center">
                            <div class="spinner-border text-primary mb-3"></div>
                            <p id="exportProgressText">${message}</p>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        
        document.getElementById('exportProgressText').textContent = message;
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    /**
     * Hide export progress
     */
    hideExportProgress() {
        const modal = document.getElementById('exportProgressModal');
        if (modal) {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        }
    }

    /**
     * Show export error
     */
    showExportError(message) {
        this.hideExportProgress();
        alert(`Export Error: ${message}`);
    }

    /**
     * Calculate success rate
     */
    calculateSuccessRate() {
        if (this.data.length === 0) return 0;
        const successful = this.data.filter(item => item.total_score >= 60).length;
        return Math.round((successful / this.data.length) * 100);
    }

    /**
     * Calculate average score
     */
    calculateAverageScore() {
        if (this.data.length === 0) return 0;
        const total = this.data.reduce((sum, item) => sum + item.total_score, 0);
        return total / this.data.length;
    }

    /**
     * Calculate average processing time
     */
    calculateProcessingTime() {
        if (this.data.length === 0) return 0;
        const total = this.data.reduce((sum, item) => sum + (item.processing_time || 0), 0);
        return total / this.data.length;
    }

    /**
     * Get file size
     */
    getFileSize(buffer) {
        const bytes = buffer.byteLength || buffer.size;
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    /**
     * Add to export history
     */
    addToExportHistory(format, size) {
        const history = this.getExportHistory();
        history.unshift({
            id: Date.now().toString(),
            date: new Date().toISOString(),
            format: format,
            size: size
        });
        
        // Keep only last 10 exports
        if (history.length > 10) {
            history.splice(10);
        }
        
        localStorage.setItem('exportHistory', JSON.stringify(history));
    }

    /**
     * Get export history
     */
    getExportHistory() {
        try {
            return JSON.parse(localStorage.getItem('exportHistory') || '[]');
        } catch {
            return [];
        }
    }

    /**
     * Download export from history
     */
    downloadExport(id) {
        // This would re-download the file from history
        console.log('Downloading export:', id);
    }
}

// Export for global use
window.ExportManager = ExportManager;
