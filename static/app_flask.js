/**
 * Bus QA LLM Evaluator - Flask Web App JavaScript
 * Main application logic for the web interface
 */

// Global state management
const AppState = {
    config: {
        baseUrl: 'https://live-demo.agenticai.pro.vn',
        headers: {},
        brandMode: 'single',
        selectedBrand: 'son_hai',
        maxConcurrency: 30,
        temperature: 0.2,
        applyDiagnostics: true,
        showMetrics: true
    },
    conversationIds: [],
    evaluationResults: null,
    summaryData: null,
    streamingActive: false,
    bulkConversations: null,
    evaluationMode: 'batch' // 'single' or 'batch'
};

// Utility functions
const Utils = {
    formatTime(seconds) {
        if (seconds < 60) return `${seconds.toFixed(1)}s`;
        if (seconds < 3600) return `${Math.floor(seconds/60)}m ${Math.floor(seconds%60)}s`;
        return `${Math.floor(seconds/3600)}h ${Math.floor((seconds%3600)/60)}m`;
    },

    formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    },

    showToast(title, message, type = 'info') {
        const toast = document.getElementById('toast');
        const toastTitle = document.getElementById('toastTitle');
        const toastBody = document.getElementById('toastBody');
        
        toastTitle.textContent = title;
        toastBody.textContent = message;
        
        toast.className = `toast ${type === 'error' ? 'bg-danger text-white' : type === 'success' ? 'bg-success text-white' : 'bg-info text-white'}`;
        
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
    },

    showLoading(show = true) {
        const spinner = document.getElementById('loadingSpinner');
        spinner.style.display = show ? 'block' : 'none';
    },

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// API functions
const API = {
    async request(endpoint, options = {}) {
        const url = endpoint.startsWith('http') ? endpoint : `/api${endpoint}`;
        
        const config = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            Utils.showLoading(true);
            const response = await fetch(url, config);
            const data = await response.json();
            
            if (!data.success && response.status >= 400) {
                throw new Error(data.error || 'API request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API Error:', error);
            Utils.showToast('API Error', error.message, 'error');
            throw error;
        } finally {
            Utils.showLoading(false);
        }
    },

    async get(endpoint) {
        return this.request(endpoint);
    },

    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async upload(endpoint, formData) {
        const url = endpoint.startsWith('http') ? endpoint : `/api${endpoint}`;
        
        try {
            Utils.showLoading(true);
            const response = await fetch(url, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (!data.success && response.status >= 400) {
                throw new Error(data.error || 'API request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API Upload Error:', error);
            Utils.showToast('API Upload Error', error.message, 'error');
            throw error;
        } finally {
            Utils.showLoading(false);
        }
    }
};

// Configuration management
const Config = {
    async load() {
        try {
            console.log('Fetching config from API...');
            const data = await API.get('/config');
            console.log('Config data received:', data);
            
            if (data.success) {
                AppState.config = { ...AppState.config, ...data.config };
                console.log('Config merged with AppState:', AppState.config);
                
                console.log('Updating UI...');
                this.updateUI();
                
                console.log('Loading brand info...');
                this.loadBrandInfo();
                
                console.log('Loading flows info...');
                this.loadFlowsInfo();
            } else {
                console.error('Config API returned error:', data.error);
                throw new Error(data.error || 'Failed to load config');
            }
        } catch (error) {
            console.error('Config.load() error:', error);
            Utils.showToast('Config Error', 'Failed to load configuration: ' + error.message, 'error');
            throw error;
        }
    },

    updateUI() {
        const config = AppState.config;
        console.log('updateUI() called with config:', config);
        
        // Update form values
        const baseUrlEl = document.getElementById('baseUrl');
        if (baseUrlEl) {
            baseUrlEl.value = config.base_url || config.baseUrl || '';
            console.log('Set baseUrl to:', baseUrlEl.value);
        } else {
            console.error('baseUrl element not found!');
        }
        
        const maxConcurrencyEl = document.getElementById('maxConcurrency');
        if (maxConcurrencyEl) {
            maxConcurrencyEl.value = config.maxConcurrency;
            console.log('Set maxConcurrency to:', config.maxConcurrency);
        }
        
        const concurrencyValueEl = document.getElementById('concurrencyValue');
        if (concurrencyValueEl) concurrencyValueEl.textContent = config.maxConcurrency;
        
        const temperatureEl = document.getElementById('temperature');
        if (temperatureEl) temperatureEl.value = config.temperature;
        
        const temperatureValueEl = document.getElementById('temperatureValue');
        if (temperatureValueEl) temperatureValueEl.textContent = config.temperature;
        
        const apiRateLimitEl = document.getElementById('apiRateLimit');
        if (apiRateLimitEl) apiRateLimitEl.value = config.api_rate_limit || 200;
        
        const rateLimitValueEl = document.getElementById('rateLimitValue');
        if (rateLimitValueEl) rateLimitValueEl.textContent = config.api_rate_limit || 200;
        
        // Update checkboxes
        document.getElementById('progressiveBatching').checked = config.use_progressive_batching !== false;
        document.getElementById('highPerformanceApi').checked = config.use_high_performance_api !== false;
        document.getElementById('enableCaching').checked = config.enable_caching === true;
        document.getElementById('showMetrics').checked = config.show_performance_metrics !== false;
        document.getElementById('applyDiagnostics').checked = config.apply_diagnostics !== false;

        // Update brand selector
        const brandSelect = document.getElementById('selectedBrand');
        if (config.brand_options) {
            brandSelect.innerHTML = '';
            config.brand_options.forEach(brand => {
                const option = document.createElement('option');
                option.value = brand;
                option.textContent = brand.replace('_', ' ').toUpperCase();
                brandSelect.appendChild(option);
            });
        }

        // Update diagnostics info
        if (config.diagnostics_info) {
            const diagnosticsInfo = document.getElementById('diagnosticsInfo');
            diagnosticsInfo.innerHTML = `
                <small class="text-muted">
                    Operational Readiness: ${config.diagnostics_info.operational_readiness} rules<br>
                    Risk Compliance: ${config.diagnostics_info.risk_compliance} rules
                </small>
            `;
        }
    },

    async loadBrandInfo() {
        try {
            const brand = AppState.config.selectedBrand;
            const data = await API.get(`/brand/${brand}`);
            
            if (data.success) {
                const brandInfo = document.getElementById('brandPolicyInfo');
                const policy = data.brand_policy;
                
                brandInfo.innerHTML = `
                    <div class="mt-2">
                        <h6 class="text-primary">Brand Policy Flags:</h6>
                        <ul class="list-unstyled small">
                            <li><i class="fas ${policy.forbid_phone_collect ? 'fa-check text-success' : 'fa-times text-danger'}"></i> Cấm thu SĐT</li>
                            <li><i class="fas ${policy.require_fixed_greeting ? 'fa-check text-success' : 'fa-times text-danger'}"></i> Chào cố định</li>
                            <li><i class="fas ${policy.ban_full_summary ? 'fa-check text-success' : 'fa-times text-danger'}"></i> Cấm tóm tắt</li>
                            <li><i class="fas fa-info-circle text-info"></i> Max openers: ${policy.max_prompted_openers}</li>
                            <li><i class="fas ${policy.read_money_in_words ? 'fa-check text-success' : 'fa-times text-danger'}"></i> Đọc tiền bằng chữ</li>
                        </ul>
                    </div>
                `;
            }
        } catch (error) {
            console.warn('Failed to load brand info:', error);
        }
    },

    loadFlowsInfo() {
        const flowsInfo = document.getElementById('flowsInfo');
        if (AppState.config.flows && AppState.config.flows.length > 0) {
            flowsInfo.innerHTML = `
                <small class="text-muted">
                    <strong>Available flows:</strong> ${AppState.config.flows.join(', ')}
                </small>
            `;
        } else {
            flowsInfo.innerHTML = `
                <small class="text-muted">
                    <strong>Default flows:</strong> booking_inquiry, route_planning, customer_support, general_inquiry
                </small>
            `;
        }
    }
};

// Configuration Manager
const ConfigManager = {
    init() {
        this.setupEventListeners();
        this.loadInitialConfig();
    },

    setupEventListeners() {
        // Input method radio buttons
        const inputMethodRadios = document.querySelectorAll('input[name="inputMethod"]');
        inputMethodRadios.forEach(radio => {
            radio.addEventListener('change', this.handleInputMethodChange.bind(this));
        });

        // Base URL and headers
        const baseUrlInput = document.getElementById('baseUrl');
        const headersInput = document.getElementById('headers');
        
        if (baseUrlInput) {
            baseUrlInput.addEventListener('change', (e) => {
                AppState.config.baseUrl = e.target.value;
                console.log('Base URL updated:', e.target.value);
            });
        }

        if (headersInput) {
            headersInput.addEventListener('change', (e) => {
                try {
                    AppState.config.headers = e.target.value ? JSON.parse(e.target.value) : {};
                    console.log('Headers updated:', AppState.config.headers);
                } catch (error) {
                    console.warn('Invalid JSON in headers:', error);
                    AppState.config.headers = {};
                }
            });
        }

        // File upload
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', this.handleFileUpload.bind(this));
        }

        // Bulk list buttons
        const testTokenBtn = document.getElementById('testTokenBtn');
        const fetchConversationsBtn = document.getElementById('fetchConversationsBtn');
        
        if (testTokenBtn) {
            testTokenBtn.addEventListener('click', this.handleTestToken.bind(this));
        }
        
        if (fetchConversationsBtn) {
            fetchConversationsBtn.addEventListener('click', this.handleFetchConversations.bind(this));
        }

        // Benchmark button
        const benchmarkBtn = document.getElementById('benchmarkBtn');
        if (benchmarkBtn) {
            benchmarkBtn.addEventListener('click', this.handleBenchmark.bind(this));
        }

        // Conversation IDs textarea
        const conversationIdsTextarea = document.getElementById('conversationIds');
        if (conversationIdsTextarea) {
            conversationIdsTextarea.addEventListener('input', Utils.debounce(this.handleConversationIdsChange.bind(this), 500));
        }
    },

    loadInitialConfig() {
        // Load base URL
        const baseUrlInput = document.getElementById('baseUrl');
        if (baseUrlInput && !baseUrlInput.value) {
            baseUrlInput.value = AppState.config.baseUrl;
        }

        // Set initial input method
        const textAreaMethod = document.getElementById('textAreaMethod');
        if (textAreaMethod) {
            textAreaMethod.checked = true;
            this.handleInputMethodChange({ target: textAreaMethod });
        }
    },

    handleInputMethodChange(event) {
        const method = event.target.value;
        
        // Hide all input sections
        document.getElementById('textAreaInput').style.display = 'none';
        document.getElementById('fileUploadInput').style.display = 'none';
        document.getElementById('bulkListInput').style.display = 'none';
        
        // Show selected input section
        switch (method) {
            case 'textarea':
                document.getElementById('textAreaInput').style.display = 'block';
                break;
            case 'file':
                document.getElementById('fileUploadInput').style.display = 'block';
                break;
            case 'bulk':
                document.getElementById('bulkListInput').style.display = 'block';
                break;
        }
        
        console.log('Input method changed to:', method);
    },

    async handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        try {
            const formData = new FormData();
            formData.append('file', file);

            const data = await API.upload('/upload-ids', formData);
            
            if (data.success) {
                AppState.conversationIds = data.conversation_ids;
                this.updateConversationPreview();
                Utils.showToast('Upload Success', `Loaded ${data.total_count} conversation IDs`, 'success');
            }
        } catch (error) {
            Utils.showToast('Upload Error', error.message, 'error');
        }
    },

    async handleTestToken() {
        const bearerToken = document.getElementById('bearerToken').value;
        const listBaseUrl = document.getElementById('listBaseUrl').value;

        if (!bearerToken) {
            Utils.showToast('Input Error', 'Bearer token is required', 'error');
            return;
        }

        try {
            const data = await API.post('/test-bearer-token', {
                bearer_token: bearerToken,
                list_base_url: listBaseUrl
            });

            if (data.success) {
                if (data.valid) {
                    Utils.showToast('Token Valid', 'Bearer token is valid!', 'success');
                } else {
                    Utils.showToast('Token Invalid', data.message || 'Bearer token is invalid', 'error');
                }
            }
        } catch (error) {
            Utils.showToast('Test Error', error.message, 'error');
        }
    },

    async handleFetchConversations() {
        const bulkParams = {
            list_base_url: document.getElementById('listBaseUrl').value,
            bot_id: document.getElementById('botId').value,
            bearer_token: document.getElementById('bearerToken').value,
            page_size: parseInt(document.getElementById('pageSize').value),
            max_pages: parseInt(document.getElementById('maxPages').value),
            take: parseInt(document.getElementById('take').value),
            skip: parseInt(document.getElementById('skip').value),
            strategy: document.getElementById('strategy').value,
            min_turns: parseInt(document.getElementById('minTurns').value)
        };

        if (!bulkParams.bot_id || !bulkParams.bearer_token) {
            Utils.showToast('Input Error', 'Bot ID and Bearer Token are required', 'error');
            return;
        }

        try {
            const data = await API.post('/bulk-list', bulkParams);
            
            if (data.success) {
                AppState.conversationIds = data.conversation_ids;
                AppState.bulkConversations = data.conversations;
                this.updateConversationPreview();
                Utils.showToast('Fetch Success', `Fetched ${data.total_fetched} conversations`, 'success');
            }
        } catch (error) {
            Utils.showToast('Fetch Error', error.message, 'error');
        }
    },

    async handleBenchmark() {
        try {
            const data = await API.post('/benchmark', {
                test_conversations: 5,
                concurrency_levels: [10, 20, 30],
                iterations: 1
            });

            if (data.success) {
                this.displayBenchmarkResults(data.results, data.recommendation);
                Utils.showToast('Benchmark Complete', 'Performance benchmark completed!', 'success');
            }
        } catch (error) {
            Utils.showToast('Benchmark Error', error.message, 'error');
        }
    },

    handleConversationIdsChange(event) {
        const text = event.target.value.trim();
        if (text) {
            AppState.conversationIds = text.split('\n').filter(id => id.trim()).map(id => id.trim());
            this.updateConversationPreview();
        } else {
            AppState.conversationIds = [];
            this.hideConversationPreview();
        }
    },

    updateConversationPreview() {
        const preview = document.getElementById('conversationPreview');
        const countSpan = document.getElementById('conversationCount');
        const idsList = document.getElementById('idsList');

        if (AppState.conversationIds.length > 0) {
            preview.style.display = 'block';
            countSpan.textContent = AppState.conversationIds.length;
            
            // Show first 10 IDs
            const previewIds = AppState.conversationIds.slice(0, 10);
            const remainingCount = AppState.conversationIds.length - previewIds.length;
            
            let idsHtml = previewIds.map((id, i) => `<small class="d-block">${i + 1}. ${id}</small>`).join('');
            if (remainingCount > 0) {
                idsHtml += `<small class="d-block text-muted">... and ${remainingCount} more</small>`;
            }
            
            idsList.innerHTML = idsHtml;
        } else {
            this.hideConversationPreview();
        }
    },

    hideConversationPreview() {
        const preview = document.getElementById('conversationPreview');
        preview.style.display = 'none';
    },

    displayBenchmarkResults(results, recommendation) {
        // Display benchmark results in a modal or section
        console.log('Benchmark Results:', results);
        console.log('Recommendation:', recommendation);
        
        // Create a simple modal for benchmark results
        const modalHtml = `
            <div class="modal fade" id="benchmarkModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Benchmark Results</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p><strong>Recommendation:</strong> ${recommendation.message}</p>
                            <h6>Performance Results:</h6>
                            <table class="table table-sm">
                                <thead>
                                    <tr>
                                        <th>Concurrency</th>
                                        <th>Throughput</th>
                                        <th>Avg Time</th>
                                        <th>Success Rate</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${results.map(r => `
                                        <tr>
                                            <td>${r.concurrency}</td>
                                            <td>${r.throughput.toFixed(1)} conv/s</td>
                                            <td>${r.avg_time.toFixed(2)}s</td>
                                            <td>${(r.success_rate * 100).toFixed(1)}%</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existingModal = document.getElementById('benchmarkModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add new modal
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('benchmarkModal'));
        modal.show();
    }
};

// Performance management
const PerformanceManager = {
    init() {
        // Range sliders
        this.setupRangeSlider('maxConcurrency', 'concurrencyValue', (value) => {
            AppState.config.maxConcurrency = parseInt(value);
        });

        this.setupRangeSlider('temperature', 'temperatureValue', (value) => {
            AppState.config.temperature = parseFloat(value);
        });

        this.setupRangeSlider('apiRateLimit', 'rateLimitValue', (value) => {
            AppState.config.apiRateLimit = parseInt(value);
        });

        // Benchmark button
        document.getElementById('benchmarkBtn').addEventListener('click', this.openBenchmarkModal.bind(this));
        document.getElementById('runBenchmarkBtn').addEventListener('click', this.runBenchmark.bind(this));
    },

    setupRangeSlider(inputId, displayId, callback) {
        const input = document.getElementById(inputId);
        const display = document.getElementById(displayId);
        
        input.addEventListener('input', (event) => {
            const value = event.target.value;
            display.textContent = value;
            if (callback) callback(value);
        });
    },

    openBenchmarkModal() {
        const modal = new bootstrap.Modal(document.getElementById('benchmarkModal'));
        modal.show();
    },

    async runBenchmark() {
        const conversations = parseInt(document.getElementById('benchmarkConversations').value);
        const iterations = parseInt(document.getElementById('benchmarkIterations').value);
        const concurrencyLevels = document.getElementById('benchmarkConcurrency').value
            .split(',').map(x => parseInt(x.trim())).filter(x => !isNaN(x));

        try {
            const data = await API.post('/benchmark', {
                test_conversations: conversations,
                iterations: iterations,
                concurrency_levels: concurrencyLevels
            });

            if (data.success) {
                this.displayBenchmarkResults(data.results, data.recommendation);
                Utils.showToast('Benchmark', 'Benchmark completed successfully', 'success');
            }
        } catch (error) {
            Utils.showToast('Benchmark Error', 'Benchmark failed', 'error');
        }
    },

    displayBenchmarkResults(results, recommendation) {
        const resultsDiv = document.getElementById('benchmarkResults');
        const recommendationDiv = document.getElementById('benchmarkRecommendation');
        
        // Show results
        resultsDiv.style.display = 'block';
        
        // Display recommendation
        recommendationDiv.innerHTML = `
            <strong>Recommendation:</strong> ${recommendation.message}<br>
            <strong>Optimal Concurrency:</strong> ${recommendation.optimal_concurrency}
        `;

        // Create chart
        const ctx = document.getElementById('benchmarkChartCanvas').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: results.map(r => `${r.concurrency}`),
                datasets: [{
                    label: 'Throughput (conv/s)',
                    data: results.map(r => r.throughput),
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Throughput (conversations/second)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Concurrency Level'
                        }
                    }
                }
            }
        });
    }
};

// Evaluation management
const EvaluationManager = {
    init() {
        document.getElementById('evaluateBtn').addEventListener('click', this.startEvaluation.bind(this));
        document.getElementById('clearResultsBtn').addEventListener('click', this.clearResults.bind(this));
        
        // Export buttons
        document.getElementById('exportPdfBtn').addEventListener('click', () => this.exportResults('pdf'));
        document.getElementById('exportExcelBtn').addEventListener('click', () => this.exportResults('excel'));
        document.getElementById('exportJsonBtn').addEventListener('click', () => this.exportResults('json'));
    },

    async startEvaluation() {
        if (AppState.conversationIds.length === 0) {
            Utils.showToast('Error', 'No conversation IDs provided', 'error');
            return;
        }

        // Show progress section
        document.getElementById('progressSection').style.display = 'block';
        document.getElementById('streamingSection').style.display = 'block';
        
        // Reset progress
        this.updateProgress(0, 0, AppState.conversationIds.length);
        
        AppState.streamingActive = true;

        // Collect all configuration
        const evaluationConfig = {
            conversation_ids: AppState.conversationIds,
            brand_mode: AppState.config.brandMode,
            selected_brand: AppState.config.selectedBrand,
            bot_map_path: document.getElementById('botMapPath').value,
            base_url: document.getElementById('baseUrl').value,
            headers: document.getElementById('headers').value,
            apply_diagnostics: document.getElementById('applyDiagnostics').checked,
            performance_config: {
                max_concurrency: AppState.config.maxConcurrency,
                temperature: AppState.config.temperature,
                use_progressive_batching: document.getElementById('progressiveBatching').checked,
                use_high_performance_api: document.getElementById('highPerformanceApi').checked,
                enable_caching: document.getElementById('enableCaching').checked,
                show_performance_metrics: document.getElementById('showMetrics').checked,
                api_rate_limit: AppState.config.apiRateLimit,
                max_chars: parseInt(document.getElementById('maxChars').value)
            }
        };

        try {
            const data = await API.post('/evaluate', evaluationConfig);
            
            if (data.success) {
                AppState.evaluationResults = data.results;
                AppState.summaryData = data.summary;
                
                this.displayResults();
                Utils.showToast('Evaluation Complete', `Processed ${data.total_processed} conversations successfully`, 'success');
            }
        } catch (error) {
            Utils.showToast('Evaluation Failed', error.message, 'error');
        } finally {
            AppState.streamingActive = false;
            document.getElementById('progressSection').style.display = 'none';
        }
    },

    updateProgress(progress, current, total) {
        document.getElementById('progressBar').style.width = `${progress * 100}%`;
        document.getElementById('progressText').textContent = 
            `Processing: ${current}/${total} (${(progress * 100).toFixed(1)}%)`;
        document.getElementById('progressPercent').textContent = `${(progress * 100).toFixed(1)}%`;
    },

    displayResults() {
        const resultsSection = document.getElementById('resultsSection');
        resultsSection.style.display = 'block';

        // Display summary cards
        this.displaySummaryCards();
        
        // Display results table
        this.displayResultsTable();
        
        // Display charts
        this.displayCharts();

        // Update last batch info
        const lastBatchInfo = document.getElementById('lastBatchInfo');
        lastBatchInfo.textContent = `Last batch: ${AppState.evaluationResults.length} results`;
        lastBatchInfo.style.display = 'inline';
    },

    displaySummaryCards() {
        const summaryCards = document.getElementById('summaryCards');
        const summary = AppState.summaryData;
        
        summaryCards.innerHTML = `
            <div class="col-md-3">
                <div class="card text-center bg-primary text-white">
                    <div class="card-body">
                        <h4>${summary.count}</h4>
                        <p class="mb-0">Total Conversations</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center bg-success text-white">
                    <div class="card-body">
                        <h4>${summary.successful_count}</h4>
                        <p class="mb-0">Successful</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center bg-info text-white">
                    <div class="card-body">
                        <h4>${summary.avg_total_score.toFixed(1)}</h4>
                        <p class="mb-0">Average Score</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center bg-warning text-dark">
                    <div class="card-body">
                        <h4>${(summary.policy_violation_rate * 100).toFixed(1)}%</h4>
                        <p class="mb-0">Policy Violations</p>
                    </div>
                </div>
            </div>
        `;
    },

    displayResultsTable() {
        const tableBody = document.getElementById('resultsTableBody');
        tableBody.innerHTML = '';

        AppState.evaluationResults.forEach(result => {
            if (!result.error) {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${result.conversation_id.slice(-15)}</td>
                    <td>${result.brand || 'N/A'}</td>
                    <td>${result.result.flow || 'N/A'}</td>
                    <td><span class="badge ${this.getScoreBadgeClass(result.result.total_score)}">${result.result.total_score.toFixed(1)}</span></td>
                    <td><span class="badge bg-secondary">${result.result.label}</span></td>
                    <td>${(result.result.confidence * 100).toFixed(1)}%</td>
                    <td>${result.metrics.processing_time ? result.metrics.processing_time.toFixed(2) + 's' : 'N/A'}</td>
                    <td><span class="status-indicator success"></span>Success</td>
                `;
                tableBody.appendChild(row);
            }
        });
    },

    getScoreBadgeClass(score) {
        if (score >= 80) return 'badge-score-excellent';
        if (score >= 70) return 'badge-score-good';
        if (score >= 60) return 'badge-score-average';
        return 'badge-score-poor';
    },

    displayCharts() {
        // Score distribution chart
        const scoreCtx = document.getElementById('scoreChart').getContext('2d');
        const scores = AppState.evaluationResults
            .filter(r => !r.error)
            .map(r => r.result.total_score);

        new Chart(scoreCtx, {
            type: 'histogram',
            data: {
                datasets: [{
                    label: 'Score Distribution',
                    data: scores,
                    backgroundColor: 'rgba(13, 110, 253, 0.7)',
                    borderColor: '#0d6efd',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                }
            }
        });

        // Flow distribution chart
        const flowCtx = document.getElementById('flowChart').getContext('2d');
        const flowDistribution = {};
        
        AppState.evaluationResults.forEach(result => {
            if (!result.error) {
                const flow = result.result.flow || 'unknown';
                flowDistribution[flow] = (flowDistribution[flow] || 0) + 1;
            }
        });

        new Chart(flowCtx, {
            type: 'pie',
            data: {
                labels: Object.keys(flowDistribution),
                datasets: [{
                    data: Object.values(flowDistribution),
                    backgroundColor: [
                        '#0d6efd', '#198754', '#ffc107', 
                        '#dc3545', '#0dcaf0', '#6f42c1'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    },

    async exportResults(format) {
        if (!AppState.evaluationResults || !AppState.summaryData) {
            Utils.showToast('Export Error', 'No results to export', 'error');
            return;
        }

        try {
            const response = await fetch(`/api/export/${format}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    results: AppState.evaluationResults,
                    summary: AppState.summaryData
                })
            });

            if (format === 'json') {
                const data = await response.json();
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                this.downloadBlob(blob, `evaluation_results_${new Date().toISOString().slice(0, 19)}.json`);
            } else {
                const blob = await response.blob();
                const filename = response.headers.get('Content-Disposition')
                    ?.match(/filename="(.+)"/)?.[1] || `evaluation_results.${format}`;
                this.downloadBlob(blob, filename);
            }

            Utils.showToast('Export Success', `Results exported as ${format.toUpperCase()}`, 'success');
        } catch (error) {
            Utils.showToast('Export Error', `Failed to export ${format}`, 'error');
        }
    },

    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    async clearResults() {
        try {
            await API.post('/clear-results', {});
            
            AppState.evaluationResults = null;
            AppState.summaryData = null;
            
            document.getElementById('resultsSection').style.display = 'none';
            document.getElementById('progressSection').style.display = 'none';
            document.getElementById('streamingSection').style.display = 'none';
            document.getElementById('lastBatchInfo').style.display = 'none';
            
            Utils.showToast('Clear Results', 'Results cleared successfully', 'success');
        } catch (error) {
            Utils.showToast('Clear Error', 'Failed to clear results', 'error');
        }
    }
};

// =================================================================================
// AppState: Manages the application's state
// =================================================================================
/*
const AppState = {
    config: {
        baseUrl: 'https://live-demo.agenticai.pro.vn',
        headers: {},
        brandMode: 'single',
        selectedBrand: 'son_hai',
        maxConcurrency: 30,
        temperature: 0.2,
        applyDiagnostics: true,
        showMetrics: true
    },
    conversationIds: [],
    evaluationResults: null,
    summaryData: null,
    streamingActive: false,
    bulkConversations: null,
    evaluationMode: 'batch' // 'single' or 'batch'

    isBatchMode: () => AppState.get('evaluationMode') === 'batch',
};
*/

// =================================================================================
// Utils: General utility functions
// =================================================================================
/*
const Utils = {
    formatTime(seconds) {
        if (seconds < 60) return `${seconds.toFixed(1)}s`;
        if (seconds < 3600) return `${Math.floor(seconds/60)}m ${Math.floor(seconds%60)}s`;
        return `${Math.floor(seconds/3600)}h ${Math.floor((seconds%3600)/60)}m`;
    },
};
*/

// =================================================================================
// =================================================================================
// =================================================================================
// Main Application Logic
// =================================================================================
// =================================================================================
// =================================================================================

// =================================================================================
// DOM Manager: Handles all interactions with the DOM
// =================================================================================
/*
const DOMManager = {
    updateConversationPreview(ids) {
        const preview = document.getElementById('conversationPreview');
        const countSpan = document.getElementById('conversationCount');
        const idsList = document.getElementById('idsList');

        if (ids.length > 0) {
            preview.style.display = 'block';
            countSpan.textContent = ids.length;
            
            // Show first 10 IDs
            const previewIds = ids.slice(0, 10);
            const remainingCount = ids.length - previewIds.length;
            
            let idsHtml = previewIds.map((id, i) => `<small class="d-block">${i + 1}. ${id}</small>`).join('');
            if (remainingCount > 0) {
                idsHtml += `<small class="d-block text-muted">... and ${remainingCount} more</small>`;
            }
            
            idsList.innerHTML = idsHtml;
        } else {
            this.hideConversationPreview();
        }
    }
};
*/

// =================================================================================
// API Client: Handles all API requests
// =================================================================================
/*
const APIClient = {
    async request(endpoint, options = {}) {
        const url = endpoint.startsWith('http') ? endpoint : `/api${endpoint}`;
        
        const config = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            Utils.showLoading(true);
            const response = await fetch(url, config);
            const data = await response.json();
            
            if (!data.success && response.status >= 400) {
                throw new Error(data.error || 'API request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API Error:', error);
            Utils.showToast('API Error', error.message, 'error');
            throw error;
        } finally {
            Utils.showLoading(false);
        }
    },

    async get(endpoint) {
        return this.request(endpoint);
    },

    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async upload(endpoint, formData) {
        const url = endpoint.startsWith('http') ? endpoint : `/api${endpoint}`;
        
        try {
            Utils.showLoading(true);
            const response = await fetch(url, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (!data.success && response.status >= 400) {
                throw new Error(data.error || 'API request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API Upload Error:', error);
            Utils.showToast('API Upload Error', error.message, 'error');
            throw error;
        } finally {
            Utils.showLoading(false);
        }
    }
};
*/

// =================================================================================
// Event Handlers: Manages user interactions
// =================================================================================
/*
const EventHandlers = {
    init() {
        this.setupEventListeners();
    },

    setupEventListeners() {
        // Input method radio buttons
        const inputMethodRadios = document.querySelectorAll('input[name="inputMethod"]');
        inputMethodRadios.forEach(radio => {
            radio.addEventListener('change', this.handleInputMethodChange.bind(this));
        });

        // Base URL and headers
        const baseUrlInput = document.getElementById('baseUrl');
        const headersInput = document.getElementById('headers');
        
        if (baseUrlInput) {
            baseUrlInput.addEventListener('change', (e) => {
                AppState.config.baseUrl = e.target.value;
                console.log('Base URL updated:', e.target.value);
            });
        }

        if (headersInput) {
            headersInput.addEventListener('change', (e) => {
                try {
                    AppState.config.headers = e.target.value ? JSON.parse(e.target.value) : {};
                    console.log('Headers updated:', AppState.config.headers);
                } catch (error) {
                    console.warn('Invalid JSON in headers:', error);
                    AppState.config.headers = {};
                }
            });
        }

        // File upload
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', this.handleFileUpload.bind(this));
        }

        // Bulk list buttons
        const testTokenBtn = document.getElementById('testTokenBtn');
        const fetchConversationsBtn = document.getElementById('fetchConversationsBtn');
        
        if (testTokenBtn) {
            testTokenBtn.addEventListener('click', this.handleTestToken.bind(this));
        }
        
        if (fetchConversationsBtn) {
            fetchConversationsBtn.addEventListener('click', this.handleFetchConversations.bind(this));
        }

        // Benchmark button
        const benchmarkBtn = document.getElementById('benchmarkBtn');
        if (benchmarkBtn) {
            benchmarkBtn.addEventListener('click', this.handleBenchmark.bind(this));
        }

        // Conversation IDs textarea
        const conversationIdsTextarea = document.getElementById('conversationIds');
        if (conversationIdsTextarea) {
            conversationIdsTextarea.addEventListener('input', Utils.debounce(this.handleConversationIdsChange.bind(this), 500));
        }
    },

    handleInputMethodChange(event) {
        const method = event.target.value;
        
        // Hide all input sections
        document.getElementById('textAreaInput').style.display = 'none';
        document.getElementById('fileUploadInput').style.display = 'none';
        document.getElementById('bulkListInput').style.display = 'none';
        
        // Show selected input section
        switch (method) {
            case 'textarea':
                document.getElementById('textAreaInput').style.display = 'block';
                break;
            case 'file':
                document.getElementById('fileUploadInput').style.display = 'block';
                break;
            case 'bulk':
                document.getElementById('bulkListInput').style.display = 'block';
                break;
        }
        
        console.log('Input method changed to:', method);
    },

    async handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        try {
            const formData = new FormData();
            formData.append('file', file);

            const data = await API.upload('/upload-ids', formData);
            
            if (data.success) {
                AppState.conversationIds = data.conversation_ids;
                this.updateConversationPreview();
                Utils.showToast('Upload Success', `Loaded ${data.total_count} conversation IDs`, 'success');
            }
        } catch (error) {
            Utils.showToast('Upload Error', error.message, 'error');
        }
    },

    async handleTestToken() {
        const bearerToken = document.getElementById('bearerToken').value;
        const listBaseUrl = document.getElementById('listBaseUrl').value;

        if (!bearerToken) {
            Utils.showToast('Input Error', 'Bearer token is required', 'error');
            return;
        }

        try {
            const data = await API.post('/test-bearer-token', {
                bearer_token: bearerToken,
                list_base_url: listBaseUrl
            });

            if (data.success) {
                if (data.valid) {
                    Utils.showToast('Token Valid', 'Bearer token is valid!', 'success');
                } else {
                    Utils.showToast('Token Invalid', data.message || 'Bearer token is invalid', 'error');
                }
            }
        } catch (error) {
            Utils.showToast('Test Error', error.message, 'error');
        }
    },

    async handleFetchConversations() {
        const bulkParams = {
            list_base_url: document.getElementById('listBaseUrl').value,
            bot_id: document.getElementById('botId').value,
            bearer_token: document.getElementById('bearerToken').value,
            page_size: parseInt(document.getElementById('pageSize').value),
            max_pages: parseInt(document.getElementById('maxPages').value),
            take: parseInt(document.getElementById('take').value),
            skip: parseInt(document.getElementById('skip').value),
            strategy: document.getElementById('strategy').value,
            min_turns: parseInt(document.getElementById('minTurns').value)
        };

        if (!bulkParams.bot_id || !bulkParams.bearer_token) {
            Utils.showToast('Input Error', 'Bot ID and Bearer Token are required', 'error');
            return;
        }

        try {
            const data = await API.post('/bulk-list', bulkParams);
            
            if (data.success) {
                AppState.conversationIds = data.conversation_ids;
                AppState.bulkConversations = data.conversations;
                this.updateConversationPreview();
                Utils.showToast('Fetch Success', `Fetched ${data.total_fetched} conversations`, 'success');
            }
        } catch (error) {
            Utils.showToast('Fetch Error', error.message, 'error');
        }
    },

    async handleBenchmark() {
        try {
            const data = await API.post('/benchmark', {
                test_conversations: 5,
                concurrency_levels: [10, 20, 30],
                iterations: 1
            });

            if (data.success) {
                this.displayBenchmarkResults(data.results, data.recommendation);
                Utils.showToast('Benchmark Complete', 'Performance benchmark completed!', 'success');
            }
        } catch (error) {
            Utils.showToast('Benchmark Error', error.message, 'error');
        }
    },

    handleConversationIdsChange(event) {
        const text = event.target.value.trim();
        if (text) {
            AppState.conversationIds = text.split('\n').filter(id => id.trim()).map(id => id.trim());
            this.updateConversationPreview();
        } else {
            AppState.conversationIds = [];
            this.hideConversationPreview();
        }
    },

    updateConversationPreview() {
        const preview = document.getElementById('conversationPreview');
        const countSpan = document.getElementById('conversationCount');
        const idsList = document.getElementById('idsList');

        if (AppState.conversationIds.length > 0) {
            preview.style.display = 'block';
            countSpan.textContent = AppState.conversationIds.length;
            
            // Show first 10 IDs
            const previewIds = AppState.conversationIds.slice(0, 10);
            const remainingCount = AppState.conversationIds.length - previewIds.length;
            
            let idsHtml = previewIds.map((id, i) => `<small class="d-block">${i + 1}. ${id}</small>`).join('');
            if (remainingCount > 0) {
                idsHtml += `<small class="d-block text-muted">... and ${remainingCount} more</small>`;
            }
            
            idsList.innerHTML = idsHtml;
        } else {
            this.hideConversationPreview();
        }
    },

    hideConversationPreview() {
        const preview = document.getElementById('conversationPreview');
        preview.style.display = 'none';
    },

    displayBenchmarkResults(results, recommendation) {
        // Display benchmark results in a modal or section
        console.log('Benchmark Results:', results);
        console.log('Recommendation:', recommendation);
        
        // Create a simple modal for benchmark results
        const modalHtml = `
            <div class="modal fade" id="benchmarkModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Benchmark Results</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p><strong>Recommendation:</strong> ${recommendation.message}</p>
                            <h6>Performance Results:</h6>
                            <table class="table table-sm">
                                <thead>
                                    <tr>
                                        <th>Concurrency</th>
                                        <th>Throughput</th>
                                        <th>Avg Time</th>
                                        <th>Success Rate</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${results.map(r => `
                                        <tr>
                                            <td>${r.concurrency}</td>
                                            <td>${r.throughput.toFixed(1)} conv/s</td>
                                            <td>${r.avg_time.toFixed(2)}s</td>
                                            <td>${(r.success_rate * 100).toFixed(1)}%</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existingModal = document.getElementById('benchmarkModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add new modal
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('benchmarkModal'));
        modal.show();
    }
};

// =================================================================================
// Chart Manager: Manages all charts
// =================================================================================
/*
const ChartManager = {
    init() {
        // Initialize all charts
        this.setupScoreDistributionChart();
        this.setupFlowDistributionChart();
    },

    setupScoreDistributionChart() {
        const ctx = document.getElementById('scoreChart').getContext('2d');
        const scores = AppState.evaluationResults
            .filter(r => !r.error)
            .map(r => r.result.total_score);

        new Chart(ctx, {
            type: 'histogram',
            data: {
                datasets: [{
                    label: 'Score Distribution',
                    data: scores,
                    backgroundColor: 'rgba(13, 110, 253, 0.7)',
                    borderColor: '#0d6efd',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                }
            }
        });
    },

    setupFlowDistributionChart() {
        const ctx = document.getElementById('flowChart').getContext('2d');
        const flowDistribution = {};
        
        AppState.evaluationResults.forEach(result => {
            if (!result.error) {
                const flow = result.result.flow || 'unknown';
                flowDistribution[flow] = (flowDistribution[flow] || 0) + 1;
            }
        });

        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: Object.keys(flowDistribution),
                datasets: [{
                    data: Object.values(flowDistribution),
                    backgroundColor: [
                        '#0d6efd', '#198754', '#ffc107', 
                        '#dc3545', '#0dcaf0', '#6f42c1'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }
};
*/

// =================================================================================
// Input Manager: Manages conversation ID inputs
// =================================================================================
/*
const InputManager = {
    init() {
        // Setup event listeners for conversation ID inputs
        const conversationIdsTextarea = document.getElementById('conversationIds');
        if (conversationIdsTextarea) {
            conversationIdsTextarea.addEventListener('input', Utils.debounce(this.handleConversationIdsChange.bind(this), 500));
        }
    },

    handleConversationIdsChange(event) {
        const text = event.target.value.trim();
        if (text) {
            AppState.conversationIds = text.split('\n').filter(id => id.trim()).map(id => id.trim());
            DOMManager.updateConversationPreview(AppState.conversationIds);
        } else {
            AppState.conversationIds = [];
            DOMManager.hideConversationPreview();
        }
    }
};
*/

// =================================================================================
// Main App Initialization
// =================================================================================
/*
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚌 Initializing Bus QA LLM Evaluator Web App...');
    
    try {
        // Check if elements exist before initialization
        const baseUrlElement = document.getElementById('baseUrl');
        console.log('baseUrl element:', baseUrlElement);
        
        const headersElement = document.getElementById('headers');
        console.log('headers element:', headersElement);
    
        // Initialize all managers
        console.log('Loading Config...');
        await Config.load();
        console.log('Config loaded');
        
        console.log('Initializing InputManager...');
        InputManager.init();
        console.log('InputManager initialized');
        
        console.log('Initializing BrandManager...');
        BrandManager.init();
        console.log('BrandManager initialized');
        
        console.log('Initializing PerformanceManager...');
        PerformanceManager.init();
        console.log('PerformanceManager initialized');
        
        console.log('Initializing EvaluationManager...');
        EvaluationManager.init();
        console.log('EvaluationManager initialized');
        
        // Initialize configuration manager
        ConfigManager.init();
        
        // Load initial configuration (if exists)
        if (typeof loadConfiguration === 'function') {
            loadConfiguration();
        }
        
        // Initialize UI (if exists)
        if (typeof initializeUI === 'function') {
            initializeUI();
        }
        
        // Setup event listeners (if exists)
        if (typeof setupEventListeners === 'function') {
            setupEventListeners();
        }
        
        console.log('✅ Application initialized successfully');
        Utils.showToast('Ready', 'Bus QA LLM Evaluator is ready to use!', 'success');
        
    } catch (error) {
        console.error('❌ Failed to initialize application:', error);
        console.error('Error details:', error.stack);
        Utils.showToast('Initialization Error', 'Failed to initialize application: ' + error.message, 'error');
    }
});
*/

// Single Conversation Evaluation Functions
function setupEvaluationModeToggle() {
    const singleModeRadio = document.getElementById('singleEvalMode');
    const batchModeRadio = document.getElementById('batchEvalMode');
    const singleInput = document.getElementById('singleConversationInput');
    const batchInput = document.getElementById('batchConversationInput');
    const evaluateSingleBtn = document.getElementById('evaluateSingleBtn');
    
    if (!singleModeRadio || !batchModeRadio || !singleInput || !batchInput) {
        console.warn('Evaluation mode toggle elements not found');
        return;
    }
    
    function toggleEvaluationMode() {
        if (singleModeRadio.checked) {
            AppState.evaluationMode = 'single';
            singleInput.style.display = 'block';
            batchInput.style.display = 'none';
            updateEvaluateButtonText('single');
        } else {
            AppState.evaluationMode = 'batch';
            singleInput.style.display = 'none';
            batchInput.style.display = 'block';
            updateEvaluateButtonText('batch');
        }
    }
    
    singleModeRadio.addEventListener('change', toggleEvaluationMode);
    batchModeRadio.addEventListener('change', toggleEvaluationMode);
    
    // Setup single conversation evaluation button
    if (evaluateSingleBtn) {
        evaluateSingleBtn.addEventListener('click', handleSingleEvaluation);
    }
    
    // Initialize display
    toggleEvaluationMode();
}

function updateEvaluateButtonText(mode) {
    const evaluateBtn = document.getElementById('evaluateBtn');
    if (evaluateBtn) {
        const brandMode = AppState.config.brandMode;
        if (mode === 'batch') {
            evaluateBtn.innerHTML = `<i class="fas fa-rocket"></i> Chấm điểm batch (${brandMode})`;
        }
    }
}

async function handleSingleEvaluation() {
    const conversationIdInput = document.getElementById('singleConversationId');
    const conversationId = conversationIdInput.value.trim();
    
    if (!conversationId) {
        Utils.showToast('Input Error', 'Please enter a conversation ID', 'error');
        return;
    }
    
    try {
        Utils.showLoading(true);
        
        const requestData = {
            conversation_id: conversationId,
            brand_name: AppState.config.selectedBrand,
            base_url: AppState.config.baseUrl,
            apply_diagnostics: AppState.config.applyDiagnostics
        };
        
        console.log('Sending single evaluation request:', requestData);
        
        const data = await API.post('/evaluate-single', requestData);
        
        if (data.success) {
            displaySingleResult(data.result);
            Utils.showToast('Evaluation Success', 'Single conversation evaluated successfully!', 'success');
        } else {
            throw new Error(data.error || 'Evaluation failed');
        }
        
    } catch (error) {
        console.error('Single evaluation error:', error);
        Utils.showToast('Evaluation Error', error.message, 'error');
    } finally {
        Utils.showLoading(false);
    }
}

function displaySingleResult(result) {
    // Clear previous results
    ResultsManager.clearResults();
    
    // Show results section
    const resultsSection = document.getElementById('resultsSection');
    if (resultsSection) {
        resultsSection.style.display = 'block';
    }
    
    // Create single result display
    const resultsTableBody = document.getElementById('resultsTableBody');
    if (resultsTableBody) {
        resultsTableBody.innerHTML = '';
        const row = createResultRow(result);
        resultsTableBody.appendChild(row);
    }
    
    // Update last batch info
    const lastBatchInfo = document.getElementById('lastBatchInfo');
    if (lastBatchInfo && result.result) {
        const evalResult = result.result;
        lastBatchInfo.innerHTML = `Single: ${evalResult.detected_flow} | ${evalResult.total_score.toFixed(1)} pts | ${evalResult.label}`;
        lastBatchInfo.style.display = 'inline';
    }
    
    // Store result in global state
    AppState.evaluationResults = [result];
    AppState.summaryData = {
        count: 1,
        successful_count: result.error ? 0 : 1,
        avg_total_score: result.error ? 0 : result.result.total_score,
        processing_time: result.metrics?.processing_time || 0
    };
    
    console.log('Single result displayed:', result);
}

function createResultRow(result) {
    const row = document.createElement('tr');
    
    if (result.error) {
        row.innerHTML = `
            <td>${result.conversation_id}</td>
            <td>-</td>
            <td>ERROR</td>
            <td>-</td>
            <td>ERROR</td>
            <td>-</td>
            <td>-</td>
            <td><span class="badge bg-danger">Error</span></td>
        `;
        row.classList.add('table-danger');
    } else {
        const evalResult = result.result;
        const metrics = result.metrics || {};
        
        row.innerHTML = `
            <td>${result.conversation_id}</td>
            <td>${result.brand_id || '-'}</td>
            <td>${evalResult.detected_flow}</td>
            <td><span class="fw-bold">${evalResult.total_score.toFixed(1)}</span></td>
            <td><span class="badge bg-${getLabelColor(evalResult.label)}">${evalResult.label}</span></td>
            <td>${(evalResult.confidence * 100).toFixed(1)}%</td>
            <td>${metrics.processing_time?.toFixed(2) || '-'}s</td>
            <td><span class="badge bg-success">Success</span></td>
        `;
        
        // Add row color based on score
        if (evalResult.total_score >= 80) {
            row.classList.add('table-success');
        } else if (evalResult.total_score >= 60) {
            row.classList.add('table-warning');
        } else {
            row.classList.add('table-danger');
        }
    }
    
    return row;
}

function getLabelColor(label) {
    switch (label.toLowerCase()) {
        case 'excellent': return 'success';
        case 'good': return 'primary';
        case 'satisfactory': return 'info';
        case 'needs improvement': return 'warning';
        case 'poor': return 'danger';
        default: return 'secondary';
    }
}
