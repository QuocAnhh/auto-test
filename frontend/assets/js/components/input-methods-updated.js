/**
 * Input Methods Component - Updated for Bulk Evaluation
 * Handles different input methods: text area, file upload, bulk list
 */

class InputMethods {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentMethod = 'text';
        this.conversations = [];
        this.kbJson = null;
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

                    <div class="mb-3">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="useKbJsonSwitch">
                            <label class="form-check-label" for="useKbJsonSwitch">Use KB JSON (optional)</label>
                        </div>
                    </div>
                    <div id="kbJsonContainer" class="mb-3 d-none">
                        <label for="kbJsonText" class="form-label">KB JSON</label>
                        <textarea class="form-control" id="kbJsonText" rows="10" placeholder="Paste KB JSON here (optional)"></textarea>
                        <div class="form-text">If provided, backend will evaluate using this KB instead of brand prompt.</div>
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

        // KB JSON toggle and input
        const kbSwitch = document.getElementById('useKbJsonSwitch');
        const kbContainer = document.getElementById('kbJsonContainer');
        const kbText = document.getElementById('kbJsonText');
        if (kbSwitch && kbContainer) {
            kbSwitch.addEventListener('change', (e) => {
                if (e.target.checked) {
                    kbContainer.classList.remove('d-none');
                } else {
                    kbContainer.classList.add('d-none');
                    this.kbJson = null;
                }
            });
        }
        if (kbText) {
            kbText.addEventListener('input', () => {
                const val = kbText.value.trim();
                if (!val) { this.kbJson = null; return; }
                try {
                    this.kbJson = JSON.parse(val);
                } catch (e) {
                    this.kbJson = null;
                }
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

        // Persist KB JSON text across tab switches
        const kbText = document.getElementById('kbJsonText');
        if (kbText && this.kbJson) {
            try { kbText.value = JSON.stringify(this.kbJson, null, 2); } catch (_) {}
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
     * Get optional KB JSON if provided
     */
    getKbJson() {
        return this.kbJson;
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
     * Fetch bulk conversations with retry logic
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

        // Show progress indicator (minimal delay)
        this.showFetchProgress('Connecting...', 0);

        try {
            // Try direct fetch first for speed, fallback to retry if needed
            let response;
            try {
                this.showFetchProgress('Fetching...', 50);
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000);
                
                response = await fetch('/fetch-conversations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        bot_id: botId,
                        bearer_token: bearerToken,
                        limit: limit,
                        strategy: strategy
                    }),
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
            } catch (error) {
                // If direct fetch fails, use retry logic
                console.log('Direct fetch failed, using retry logic:', error.message);
                response = await this.fetchWithRetry('/fetch-conversations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        bot_id: botId,
                        bearer_token: bearerToken,
                        limit: limit,
                        strategy: strategy
                    })
                });
            }

            if (response.ok) {
                this.showFetchProgress('Processing results...', 90);
                
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
                
                this.showFetchProgress('Complete!', 100);
                setTimeout(() => {
                    this.hideFetchProgress();
                    this.showAlert(`✅ Fetched ${this.conversations.length} conversations`, 'success');
                }, 500);
                
                // Display conversation IDs in results table immediately
                // Add small delay to ensure main app is ready
                setTimeout(() => {
                    this.displayConversationIds();
                }, 100);
            } else {
                this.hideFetchProgress();
                this.showAlert('❌ Failed to fetch conversations', 'error');
            }
        } catch (error) {
            this.hideFetchProgress();
            this.showAlert(`Fetch error: ${error.message}`, 'error');
        }
    }

    /**
     * Display conversation IDs in results table
     */
    displayConversationIds() {
        if (!this.conversations || this.conversations.length === 0) return;
        
        // Create placeholder results for conversation IDs
        const placeholderResults = this.conversations.map(conv => ({
            conversation_id: conv.conversation_id || conv.id || `conv-${Math.random().toString(36).substr(2, 9)}`,
            result: {
                detected_flow: 'Pending',
                total_score: 0,
                label: 'Pending',
                confidence: 0,
                criteria: {}
            },
            metrics: {
                policy_violations: 0
            },
            status: 'pending',
            timestamp: Date.now()
        }));
        
        // Notify main app to update results table
        console.log('📋 Displaying', placeholderResults.length, 'conversation IDs');
        if (window.busQAApp && window.busQAApp.resultsTable) {
            window.busQAApp.resultsTable.setData(placeholderResults);
            console.log('✅ Results table updated with conversation IDs');
        } else {
            console.warn('⚠️ Main app or results table not available');
        }
    }

    /**
     * Fetch with retry logic (optimized for speed)
     */
    async fetchWithRetry(url, options, maxRetries = 2) {
        let lastError;
        
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                this.showFetchProgress(`Attempt ${attempt}/${maxRetries}...`, (attempt - 1) / maxRetries * 100);
                
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 seconds timeout (faster)
                
                const response = await fetch(url, {
                    ...options,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (response.ok) {
                    this.hideFetchProgress();
                    return response;
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            } catch (error) {
                lastError = error;
                console.warn(`Fetch attempt ${attempt} failed:`, error.message);
                
                if (attempt < maxRetries) {
                    const delay = attempt * 500; // Faster backoff: 500ms, 1s
                    this.showFetchProgress(`Retrying in ${delay/1000}s... (${attempt}/${maxRetries})`, attempt / maxRetries * 100);
                    await new Promise(resolve => setTimeout(resolve, delay));
                }
            }
        }
        
        this.hideFetchProgress();
        throw lastError;
    }

    /**
     * Show fetch progress
     */
    showFetchProgress(message, progress) {
        // Create or update progress indicator
        let progressDiv = document.getElementById('fetchProgress');
        if (!progressDiv) {
            progressDiv = document.createElement('div');
            progressDiv.id = 'fetchProgress';
            progressDiv.className = 'alert alert-info d-flex align-items-center';
            progressDiv.innerHTML = `
                <div class="spinner-border spinner-border-sm me-2" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="flex-grow-1">
                    <div class="fw-bold">Fetching Conversations</div>
                    <div class="progress mt-1" style="height: 6px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" style="width: 0%"></div>
                    </div>
                </div>
            `;
            this.container.appendChild(progressDiv);
        }
        
        // Update message and progress
        const messageDiv = progressDiv.querySelector('.fw-bold');
        const progressBar = progressDiv.querySelector('.progress-bar');
        
        if (messageDiv) messageDiv.textContent = message;
        if (progressBar) progressBar.style.width = `${progress}%`;
    }

    /**
     * Hide fetch progress
     */
    hideFetchProgress() {
        const progressDiv = document.getElementById('fetchProgress');
        if (progressDiv) {
            progressDiv.remove();
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
