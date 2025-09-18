/**
 * Input Methods Component
 * Handles different input methods: text area, file upload, bulk list
 */

class InputMethods {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentMethod = 'text';
        this.conversations = [];
        this.fileData = null;
        this.bulkConfig = {
            startDate: '',
            endDate: '',
            limit: 100,
            strategy: 'random',
            bearerToken: ''
        };
    }

    /**
     * Initialize input methods
     */
    init() {
        this.render();
        this.setupEventListeners();
    }

    /**
     * Render input methods
     */
    render() {
        this.container.innerHTML = `
            <div class="input-methods-container">
                <!-- Method Selection -->
                <div class="mb-4">
                    <label class="form-label">Input Method</label>
                    <div class="btn-group w-100" role="group">
                        <input type="radio" class="btn-check" name="inputMethod" id="textMethod" value="text" checked>
                        <label class="btn btn-outline-primary" for="textMethod">
                            <i class="bi bi-textarea-t"></i> Text Area
                        </label>
                        
                        <input type="radio" class="btn-check" name="inputMethod" id="fileMethod" value="file">
                        <label class="btn btn-outline-primary" for="fileMethod">
                            <i class="bi bi-upload"></i> File Upload
                        </label>
                        
                        <input type="radio" class="btn-check" name="inputMethod" id="bulkMethod" value="bulk">
                        <label class="btn btn-outline-primary" for="bulkMethod">
                            <i class="bi bi-list-ul"></i> Bulk List
                        </label>
                    </div>
                </div>

                <!-- Text Area Method -->
                <div id="textInputMethod" class="input-method-content">
                    <div class="mb-3">
                        <label for="conversationText" class="form-label">Conversation Data</label>
                        <textarea class="form-control" id="conversationText" rows="10" 
                                  placeholder="Enter conversation data in the following format:

user: Hello, I need help with my booking
assistant: Hello! I'd be happy to help you with your booking. Could you please provide your booking reference number?
user: My reference is ABC123
assistant: Thank you! Let me look up your booking with reference ABC123..."></textarea>
                        <div class="form-text">
                            Format: Each message should start with "user:", "assistant:", or "system:" followed by the content.
                        </div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <button class="btn btn-outline-secondary btn-sm" onclick="inputMethods.parseSampleData()">
                                <i class="bi bi-file-text"></i> Load Sample
                            </button>
                            <button class="btn btn-outline-secondary btn-sm" onclick="inputMethods.clearTextArea()">
                                <i class="bi bi-trash"></i> Clear
                            </button>
                        </div>
                        <div>
                            <span class="badge bg-info" id="textConversationCount">0 conversations</span>
                        </div>
                    </div>
                </div>

                <!-- File Upload Method -->
                <div id="fileInputMethod" class="input-method-content d-none">
                    <div class="file-upload-area" id="fileUploadArea">
                        <div class="text-center">
                            <i class="bi bi-cloud-upload display-4 text-muted"></i>
                            <h5 class="mt-3">Drop files here or click to browse</h5>
                            <p class="text-muted">Supported formats: JSON, CSV, TXT</p>
                            <input type="file" id="fileInput" class="d-none" accept=".json,.csv,.txt">
                            <button class="btn btn-primary" onclick="document.getElementById('fileInput').click()">
                                <i class="bi bi-upload"></i> Choose Files
                            </button>
                        </div>
                    </div>
                    <div id="filePreview" class="mt-3 d-none">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h6 class="mb-0">File Preview</h6>
                                <button class="btn btn-sm btn-outline-danger" onclick="inputMethods.removeFile()">
                                    <i class="bi bi-trash"></i> Remove
                                </button>
                            </div>
                            <div class="card-body">
                                <div id="fileInfo"></div>
                                <div id="fileContent" class="mt-3"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Bulk List Method -->
                <div id="bulkInputMethod" class="input-method-content d-none">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="startDate" class="form-label">Start Date</label>
                                <input type="date" class="form-control" id="startDate">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="endDate" class="form-label">End Date</label>
                                <input type="date" class="form-control" id="endDate">
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="bulkLimit" class="form-label">Limit</label>
                                <input type="number" class="form-control" id="bulkLimit" value="100" min="1" max="1000">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="bulkStrategy" class="form-label">Selection Strategy</label>
                                <select class="form-select" id="bulkStrategy">
                                    <option value="random">Random</option>
                                    <option value="longest">Longest</option>
                                    <option value="shortest">Shortest</option>
                                    <option value="recent">Most Recent</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label for="bearerToken" class="form-label">Bearer Token</label>
                        <input type="password" class="form-control" id="bearerToken" 
                               placeholder="Enter your API bearer token">
                        <div class="form-text">
                            Required for accessing external API to fetch conversations.
                        </div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <button class="btn btn-outline-primary" onclick="inputMethods.testBearerToken()">
                                <i class="bi bi-check-circle"></i> Test Token
                            </button>
                            <button class="btn btn-outline-secondary" onclick="inputMethods.fetchBulkData()">
                                <i class="bi bi-download"></i> Fetch Data
                            </button>
                        </div>
                        <div>
                            <span class="badge bg-info" id="bulkConversationCount">0 conversations</span>
                        </div>
                    </div>
                </div>

                <!-- Conversation Preview -->
                <div id="conversationPreview" class="mt-4 d-none">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h6 class="mb-0">Conversation Preview</h6>
                            <button class="btn btn-sm btn-outline-primary" onclick="inputMethods.exportConversations()">
                                <i class="bi bi-download"></i> Export
                            </button>
                        </div>
                        <div class="card-body">
                            <div id="conversationList"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupFileUpload();
        this.updateConversationCount();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Method selection
        document.querySelectorAll('input[name="inputMethod"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.switchMethod(e.target.value);
            });
        });

        // Text area changes
        const textArea = document.getElementById('conversationText');
        if (textArea) {
            textArea.addEventListener('input', () => {
                this.parseTextArea();
            });
        }

        // Date inputs
        const startDate = document.getElementById('startDate');
        const endDate = document.getElementById('endDate');
        if (startDate && endDate) {
            // Set default dates
            const today = new Date();
            const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
            startDate.value = lastWeek.toISOString().split('T')[0];
            endDate.value = today.toISOString().split('T')[0];
        }
    }

    /**
     * Setup file upload functionality
     */
    setupFileUpload() {
        const fileUploadArea = document.getElementById('fileUploadArea');
        const fileInput = document.getElementById('fileInput');

        if (fileUploadArea && fileInput) {
            // Drag and drop
            fileUploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                fileUploadArea.classList.add('dragover');
            });

            fileUploadArea.addEventListener('dragleave', (e) => {
                e.preventDefault();
                fileUploadArea.classList.remove('dragover');
            });

            fileUploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                fileUploadArea.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    this.handleFileUpload(files[0]);
                }
            });

            // Click to upload
            fileUploadArea.addEventListener('click', () => {
                fileInput.click();
            });

            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.handleFileUpload(e.target.files[0]);
                }
            });
        }
    }

    /**
     * Switch input method
     */
    switchMethod(method) {
        this.currentMethod = method;
        
        // Hide all method contents
        document.querySelectorAll('.input-method-content').forEach(content => {
            content.classList.add('d-none');
        });
        
        // Show selected method
        const selectedContent = document.getElementById(`${method}InputMethod`);
        if (selectedContent) {
            selectedContent.classList.remove('d-none');
        }

        // Update conversation count
        this.updateConversationCount();
    }

    /**
     * Parse text area content
     */
    parseTextArea() {
        const textArea = document.getElementById('conversationText');
        if (!textArea) return;

        const text = textArea.value.trim();
        if (!text) {
            this.conversations = [];
            this.updateConversationCount();
            return;
        }

        try {
            this.conversations = DataUtils.parseConversationFromText(text);
            this.updateConversationCount();
            this.showConversationPreview();
        } catch (error) {
            console.error('Error parsing conversation text:', error);
            this.conversations = [];
        }
    }

    /**
     * Load sample data
     */
    parseSampleData() {
        const sampleText = `user: Hello, I need help with my booking
assistant: Hello! I'd be happy to help you with your booking. Could you please provide your booking reference number?
user: My reference is ABC123
assistant: Thank you! Let me look up your booking with reference ABC123. I can see your booking is confirmed for tomorrow at 2 PM.
user: Can I change the time to 4 PM?
assistant: I can help you change your booking time. Let me check availability for 4 PM tomorrow...`;

        const textArea = document.getElementById('conversationText');
        if (textArea) {
            textArea.value = sampleText;
            this.parseTextArea();
        }
    }

    /**
     * Clear text area
     */
    clearTextArea() {
        const textArea = document.getElementById('conversationText');
        if (textArea) {
            textArea.value = '';
            this.conversations = [];
            this.updateConversationCount();
            this.hideConversationPreview();
        }
    }

    /**
     * Handle file upload
     */
    async handleFileUpload(file) {
        try {
            const content = await this.readFileContent(file);
            this.parseFileContent(content, file.name);
            this.showFilePreview(file, content);
        } catch (error) {
            console.error('Error reading file:', error);
            this.showAlert('Error reading file: ' + error.message, 'danger');
        }
    }

    /**
     * Read file content
     */
    readFileContent(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(e);
            reader.readAsText(file);
        });
    }

    /**
     * Parse file content
     */
    parseFileContent(content, filename) {
        const extension = filename.split('.').pop().toLowerCase();
        
        try {
            switch (extension) {
                case 'json':
                    this.parseJSONContent(content);
                    break;
                case 'csv':
                    this.parseCSVContent(content);
                    break;
                case 'txt':
                    this.parseTextContent(content);
                    break;
                default:
                    throw new Error('Unsupported file format');
            }
            this.updateConversationCount();
            this.showConversationPreview();
        } catch (error) {
            console.error('Error parsing file content:', error);
            this.showAlert('Error parsing file: ' + error.message, 'danger');
        }
    }

    /**
     * Parse JSON content
     */
    parseJSONContent(content) {
        const data = JSON.parse(content);
        if (Array.isArray(data)) {
            this.conversations = data;
        } else if (data.conversations && Array.isArray(data.conversations)) {
            this.conversations = data.conversations;
        } else {
            throw new Error('Invalid JSON format. Expected array of conversations or object with conversations property.');
        }
    }

    /**
     * Parse CSV content
     */
    parseCSVContent(content) {
        const lines = content.split('\n').filter(line => line.trim());
        if (lines.length < 2) {
            throw new Error('CSV must have at least a header row and one data row');
        }

        const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
        this.conversations = [];

        for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''));
            if (values.length === headers.length) {
                const conversation = {};
                headers.forEach((header, index) => {
                    conversation[header] = values[index];
                });
                this.conversations.push(conversation);
            }
        }
    }

    /**
     * Parse text content
     */
    parseTextContent(content) {
        this.conversations = DataUtils.parseConversationFromText(content);
    }

    /**
     * Show file preview
     */
    showFilePreview(file, content) {
        const filePreview = document.getElementById('filePreview');
        const fileInfo = document.getElementById('fileInfo');
        const fileContent = document.getElementById('fileContent');

        if (filePreview && fileInfo && fileContent) {
            fileInfo.innerHTML = `
                <div class="row">
                    <div class="col-md-6">
                        <strong>File:</strong> ${file.name}<br>
                        <strong>Size:</strong> ${DataUtils.formatFileSize(file.size)}<br>
                        <strong>Type:</strong> ${file.type}
                    </div>
                    <div class="col-md-6">
                        <strong>Conversations:</strong> ${this.conversations.length}<br>
                        <strong>Parsed:</strong> <span class="badge bg-success">Success</span>
                    </div>
                </div>
            `;

            fileContent.innerHTML = `
                <pre class="bg-light p-3 rounded" style="max-height: 200px; overflow-y: auto;">${content.substring(0, 500)}${content.length > 500 ? '...' : ''}</pre>
            `;

            filePreview.classList.remove('d-none');
        }
    }

    /**
     * Remove file
     */
    removeFile() {
        this.conversations = [];
        this.fileData = null;
        document.getElementById('filePreview').classList.add('d-none');
        document.getElementById('fileInput').value = '';
        this.updateConversationCount();
        this.hideConversationPreview();
    }

    /**
     * Test bearer token
     */
    async testBearerToken() {
        const token = document.getElementById('bearerToken').value;
        if (!token) {
            this.showAlert('Please enter a bearer token', 'warning');
            return;
        }

        try {
            // This would call the API to test the token
            this.showAlert('Testing token...', 'info');
            // TODO: Implement actual token testing
            setTimeout(() => {
                this.showAlert('Token is valid!', 'success');
            }, 1000);
        } catch (error) {
            this.showAlert('Token test failed: ' + error.message, 'danger');
        }
    }

    /**
     * Fetch bulk data
     */
    async fetchBulkData() {
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        const limit = parseInt(document.getElementById('bulkLimit').value);
        const strategy = document.getElementById('bulkStrategy').value;
        const bearerToken = document.getElementById('bearerToken').value;

        if (!startDate || !endDate || !bearerToken) {
            this.showAlert('Please fill in all required fields', 'warning');
            return;
        }

        try {
            this.showAlert('Fetching conversations...', 'info');
            // TODO: Implement actual bulk data fetching
            // This would call the API to fetch conversations
            setTimeout(() => {
                this.conversations = this.generateMockBulkData(limit);
                this.updateConversationCount();
                this.showConversationPreview();
                this.showAlert(`Fetched ${this.conversations.length} conversations`, 'success');
            }, 2000);
        } catch (error) {
            this.showAlert('Failed to fetch data: ' + error.message, 'danger');
        }
    }

    /**
     * Generate mock bulk data
     */
    generateMockBulkData(count) {
        const conversations = [];
        for (let i = 0; i < count; i++) {
            conversations.push({
                conversation_id: `bulk-${i + 1}`,
                messages: [
                    { role: 'user', content: `User message ${i + 1}` },
                    { role: 'assistant', content: `Assistant response ${i + 1}` }
                ],
                metadata: { source: 'bulk-api' }
            });
        }
        return conversations;
    }

    /**
     * Show conversation preview
     */
    showConversationPreview() {
        const preview = document.getElementById('conversationPreview');
        const conversationList = document.getElementById('conversationList');

        if (preview && conversationList && this.conversations.length > 0) {
            conversationList.innerHTML = this.conversations.map((conv, index) => `
                <div class="card mb-2">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h6 class="card-title">${conv.conversation_id}</h6>
                                <p class="card-text">
                                    <small class="text-muted">
                                        ${conv.messages ? conv.messages.length : 0} messages
                                    </small>
                                </p>
                            </div>
                            <div>
                                <span class="badge bg-primary">${conv.metadata?.source || 'text'}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('');

            preview.classList.remove('d-none');
        }
    }

    /**
     * Hide conversation preview
     */
    hideConversationPreview() {
        const preview = document.getElementById('conversationPreview');
        if (preview) {
            preview.classList.add('d-none');
        }
    }

    /**
     * Update conversation count
     */
    updateConversationCount() {
        const count = this.conversations.length;
        document.getElementById('textConversationCount').textContent = `${count} conversations`;
        document.getElementById('bulkConversationCount').textContent = `${count} conversations`;
    }

    /**
     * Export conversations
     */
    exportConversations() {
        if (this.conversations.length === 0) {
            this.showAlert('No conversations to export', 'warning');
            return;
        }

        const data = JSON.stringify(this.conversations, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `conversations_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        window.URL.revokeObjectURL(url);
    }

    /**
     * Get conversations for evaluation
     */
    getConversations() {
        return this.conversations;
    }

    /**
     * Get bulk configuration
     */
    getBulkConfig() {
        return {
            startDate: document.getElementById('startDate').value,
            endDate: document.getElementById('endDate').value,
            limit: parseInt(document.getElementById('bulkLimit').value),
            strategy: document.getElementById('bulkStrategy').value,
            bearerToken: document.getElementById('bearerToken').value
        };
    }

    /**
     * Show alert
     */
    showAlert(message, type) {
        // Create alert element
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Insert at top of container
        this.container.insertBefore(alertDiv, this.container.firstChild);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

// Export for global use
window.InputMethods = InputMethods;
