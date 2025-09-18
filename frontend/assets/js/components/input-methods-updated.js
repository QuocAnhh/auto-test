/**
 * Input Methods Component - Updated for Bulk Evaluation
 * Handles different input methods: text area, file upload, bulk list
 */

class InputMethods {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentMethod = 'text';
        this.conversations = [];
        this.fileData = null;
        this.bulkConfig = {
            botId: '',
            limit: 10,
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
                            <i class="bi bi-list-ul"></i> Bulk Evaluation
                        </label>
                    </div>
                </div>

                <!-- Text Area Method -->
                <div id="textInputMethod" class="input-method-content">
                    <div class="mb-3">
                        <label for="conversationText" class="form-label">Conversation Data</label>
                        <textarea class="form-control" id="conversationText" rows="10"
                                  placeholder="Paste your conversation data here..."></textarea>
                        <div class="form-text">
                            Enter conversation data in JSON format or plain text.
                        </div>
                    </div>
                </div>

                <!-- File Upload Method -->
                <div id="fileInputMethod" class="input-method-content d-none">
                    <div class="mb-3">
                        <label for="conversationFile" class="form-label">Upload File</label>
                        <input type="file" class="form-control" id="conversationFile" accept=".json,.txt,.csv">
                        <div class="form-text">
                            Supported formats: JSON, TXT, CSV
                        </div>
                    </div>
                    <div id="filePreview" class="mt-3 d-none">
                        <h6>File Preview:</h6>
                        <pre class="bg-light p-3 rounded" id="fileContent"></pre>
                    </div>
                </div>

                <!-- Bulk Evaluation Method -->
                <div id="bulkInputMethod" class="input-method-content d-none">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="botId" class="form-label">Bot ID *</label>
                                <input type="text" class="form-control" id="botId" placeholder="Enter bot ID (e.g., 5706)" required>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="bulkLimit" class="form-label">Limit</label>
                                <input type="number" class="form-control" id="bulkLimit" value="10" min="1" max="100">
                            </div>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="bulkStrategy" class="form-label">Selection Strategy</label>
                                <select class="form-select" id="bulkStrategy">
                                    <option value="random">Random</option>
                                    <option value="newest">Newest</option>
                                    <option value="oldest">Oldest</option>
                                    <option value="head">Head</option>
                                    <option value="tail">Tail</option>
                                </select>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="bearerToken" class="form-label">Bearer Token *</label>
                                <div class="input-group">
                                    <input type="password" class="form-control" id="bearerToken" 
                                           placeholder="Loading from environment..." required>
                                    <button class="btn btn-outline-secondary" type="button" id="loadTokenBtn">
                                        <i class="fas fa-sync-alt"></i> Load from Env
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="d-grid gap-2">
                        <button type="button" class="btn btn-outline-primary" id="fetchBulkData">
                            <i class="bi bi-download"></i> Fetch Conversations
                        </button>
                        <button type="button" class="btn btn-outline-secondary" id="testBulkToken">
                            <i class="bi bi-check-circle"></i> Test Token
                        </button>
                    </div>
                    <div class="alert alert-info mt-3">
                        <i class="bi bi-info-circle"></i>
                        <strong>Bulk Evaluation:</strong> First fetch conversations, then evaluate them separately.
                    </div>
                    <div id="bulkDataStatus" class="mt-3 d-none">
                        <div class="alert alert-success">
                            <i class="bi bi-check-circle"></i>
                            <span id="bulkDataCount">0</span> conversations ready for evaluation
                        </div>
                    </div>
                </div>
            </div>
        `;
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

        // File upload
        const fileInput = document.getElementById('conversationFile');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                this.handleFileUpload(e.target.files[0]);
            });
        }

        // Text area
        const textArea = document.getElementById('conversationText');
        if (textArea) {
            textArea.addEventListener('input', () => {
                this.parseTextData();
            });
        }

        // Bulk evaluation buttons
        const fetchBtn = document.getElementById('fetchBulkData');
        if (fetchBtn) {
            fetchBtn.addEventListener('click', () => {
                this.fetchBulkConversations();
            });
        }

        const loadTokenBtn = document.getElementById('loadTokenBtn');
        if (loadTokenBtn) {
            loadTokenBtn.addEventListener('click', () => {
                this.loadBearerTokenFromEnv();
            });
        }

        const testBtn = document.getElementById('testBulkToken');
        if (testBtn) {
            testBtn.addEventListener('click', () => {
                this.testBearerToken();
            });
        }
    }

    /**
     * Switch input method
     */
    switchMethod(method) {
        this.currentMethod = method;
        
        // Hide all content
        document.querySelectorAll('.input-method-content').forEach(content => {
            content.classList.add('d-none');
        });

        // Show selected content
        const selectedContent = document.getElementById(`${method}InputMethod`);
        if (selectedContent) {
            selectedContent.classList.remove('d-none');
        }
    }

    /**
     * Get current method
     */
    getCurrentMethod() {
        return this.currentMethod;
    }

    /**
     * Get conversations
     */
    getConversations() {
        return this.conversations;
    }

    /**
     * Parse text data
     */
    parseTextData() {
        const text = document.getElementById('conversationText').value;
        if (!text.trim()) {
            this.conversations = [];
            return;
        }

        try {
            // Try to parse as JSON
            const data = JSON.parse(text);
            if (Array.isArray(data)) {
                this.conversations = data;
            } else {
                this.conversations = [data];
            }
        } catch (e) {
            // If not JSON, treat as plain text
            this.conversations = [{
                conversation_id: 'text-input-1',
                messages: [
                    { role: 'user', content: text }
                ]
            }];
        }
    }

    /**
     * Handle file upload
     */
    handleFileUpload(file) {
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            const content = e.target.result;
            this.parseFileContent(content, file.type);
        };
        reader.readAsText(file);
    }

    /**
     * Parse file content
     */
    parseFileContent(content, fileType) {
        try {
            let data;
            if (fileType === 'application/json') {
                data = JSON.parse(content);
            } else if (fileType === 'text/csv') {
                data = this.parseCSV(content);
            } else {
                data = [{ conversation_id: 'file-input-1', messages: [{ role: 'user', content: content }] }];
            }

            if (Array.isArray(data)) {
                this.conversations = data;
            } else {
                this.conversations = [data];
            }

            // Show preview
            const preview = document.getElementById('filePreview');
            const fileContent = document.getElementById('fileContent');
            if (preview && fileContent) {
                fileContent.textContent = JSON.stringify(data, null, 2);
                preview.classList.remove('d-none');
            }
        } catch (error) {
            console.error('Error parsing file:', error);
            this.conversations = [];
        }
    }

    /**
     * Parse CSV content
     */
    parseCSV(content) {
        const lines = content.split('\n');
        const conversations = [];
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line) {
                conversations.push({
                    conversation_id: `csv-${i + 1}`,
                    messages: [{ role: 'user', content: line }]
                });
            }
        }
        
        return conversations;
    }

    /**
     * Load bearer token from environment
     */
    async loadBearerTokenFromEnv() {
        try {
            const response = await fetch('/config/bearer-token');
            if (response.ok) {
                const result = await response.json();
                const bearerTokenInput = document.getElementById('bearerToken');
                if (bearerTokenInput) {
                    bearerTokenInput.value = result.bearer_token;
                    bearerTokenInput.placeholder = 'Bearer token loaded from environment';
                    this.showAlert('✅ Bearer token loaded from environment', 'success');
                }
            } else {
                this.showAlert('❌ Failed to load bearer token from environment', 'error');
            }
        } catch (error) {
            this.showAlert(`Load token error: ${error.message}`, 'error');
        }
    }

    /**
     * Test bearer token
     */
    async testBearerToken() {
        const botId = document.getElementById('botId').value;
        const bearerToken = document.getElementById('bearerToken').value;
        const listBaseUrl = 'https://live-demo.agenticai.pro.vn';

        if (!botId || !bearerToken) {
            this.showAlert('Bot ID and Bearer Token are required', 'warning');
            return;
        }

        try {
            this.showAlert('Testing token...', 'info');
            
            const response = await fetch('/test-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    base_url: listBaseUrl,
                    bearer_token: bearerToken
                })
            });

            if (response.ok) {
                this.showAlert('✅ Token is valid!', 'success');
            } else {
                this.showAlert('❌ Token test failed', 'error');
            }
        } catch (error) {
            this.showAlert(`Token test error: ${error.message}`, 'error');
        }
    }

    /**
     * Fetch bulk conversations
     */
    async fetchBulkConversations() {
        const botId = document.getElementById('botId').value;
        const bearerToken = document.getElementById('bearerToken').value;
        const limit = parseInt(document.getElementById('bulkLimit').value) || 10;
        const strategy = document.getElementById('bulkStrategy').value || 'random';

        if (!botId || !bearerToken) {
            this.showAlert('Bot ID and Bearer Token are required', 'warning');
            return;
        }

        try {
            this.showAlert('Fetching conversations...', 'info');
            
            const response = await fetch('/fetch-conversations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    bot_id: botId,
                    bearer_token: bearerToken,
                    limit: limit,
                    strategy: strategy
                })
            });

            if (response.ok) {
                const result = await response.json();
                this.conversations = result.conversations || [];
                
                console.log('Fetched conversations:', this.conversations);
                console.log('Fetched conversations length:', this.conversations.length);
                
                // Show success status
                const statusDiv = document.getElementById('bulkDataStatus');
                const countSpan = document.getElementById('bulkDataCount');
                if (statusDiv && countSpan) {
                    countSpan.textContent = this.conversations.length;
                    statusDiv.classList.remove('d-none');
                }
                
                this.showAlert(`✅ Fetched ${this.conversations.length} conversations`, 'success');
            } else {
                this.showAlert('❌ Failed to fetch conversations', 'error');
            }
        } catch (error) {
            this.showAlert(`Fetch error: ${error.message}`, 'error');
        }
    }

    /**
     * Show alert message
     */
    showAlert(message, type) {
        // Simple alert for now - can be enhanced later
        console.log(`${type.toUpperCase()}: ${message}`);
    }
}

// Export for use in other modules
window.InputMethods = InputMethods;
