// Global state management
const AppState = {
    conversationIds: [],
    evaluationResults: null,
    summaryData: null,
    isEvaluating: false,
    streamingResults: [],
    performanceMetrics: {},
    benchmarkResults: null,
    config: {
        baseUrl: 'http://103.141.140.243:14496',
        headers: {},
        brandMode: 'single',
        selectedBrand: 'son_hai',
        maxConcurrency: 30,
        temperature: 0.2,
        useProgressiveBatching: true,
        useHighPerformanceApi: true,
        enableCaching: false,
        showPerformanceMetrics: true,
        applyDiagnostics: true
    }
};

// DOM elements
const elements = {
    // Input method controls
    inputMethodRadios: document.querySelectorAll('input[name="inputMethod"]'),
    textAreaInput: document.getElementById('textAreaInput'),
    fileUploadInput: document.getElementById('fileUploadInput'),
    bulkListInput: document.getElementById('bulkListInput'),
    conversationIds: document.getElementById('conversationIds'),
    fileInput: document.getElementById('fileInput'),
    
    // Brand configuration
    brandModeRadios: document.querySelectorAll('input[name="brandMode"]'),
    singleBrandConfig: document.getElementById('singleBrandConfig'),
    multiBrandConfig: document.getElementById('multiBrandConfig'),
    selectedBrand: document.getElementById('selectedBrand'),
    
    // Performance controls
    maxConcurrency: document.getElementById('maxConcurrency'),
    concurrencyValue: document.getElementById('concurrencyValue'),
    temperature: document.getElementById('temperature'),
    temperatureValue: document.getElementById('temperatureValue'),
    apiRateLimit: document.getElementById('apiRateLimit'),
    rateLimitValue: document.getElementById('rateLimitValue'),
    memoryCleanupInterval: document.getElementById('memoryCleanupInterval'),
    cleanupValue: document.getElementById('cleanupValue'),
    
    // Checkboxes
    useProgressiveBatching: document.getElementById('useProgressiveBatching'),
    useHighPerformanceApi: document.getElementById('useHighPerformanceApi'),
    enableCaching: document.getElementById('enableCaching'),
    showPerformanceMetrics: document.getElementById('showPerformanceMetrics'),
    applyDiagnostics: document.getElementById('applyDiagnostics'),
    redisCacheConfig: document.getElementById('redisCacheConfig'),
    
    // Main controls
    evaluateBtn: document.getElementById('evaluateBtn'),
    conversationPreview: document.getElementById('conversationPreview'),
    lastBatchResults: document.getElementById('lastBatchResults'),
    
    // Progress and results
    progressSection: document.getElementById('progressSection'),
    progressBar: document.getElementById('progressFill'),
    progressStatus: document.getElementById('progressStatus'),
    speedMetric: document.getElementById('speedMetric'),
    elapsedMetric: document.getElementById('elapsedMetric'),
    progressMetric: document.getElementById('progressMetric'),
    successRateMetric: document.getElementById('successRateMetric'),
    streamingResults: document.getElementById('streamingResults'),
    
    // Performance metrics
    performanceMetrics: document.getElementById('performanceMetrics'),
    cpuMetric: document.getElementById('cpuMetric'),
    memoryMetric: document.getElementById('memoryMetric'),
    throughputMetric: document.getElementById('throughputMetric'),
    cacheMetric: document.getElementById('cacheMetric'),
    
    // Results section
    resultsSection: document.getElementById('resultsSection'),
    tabButtons: document.querySelectorAll('.tab-button'),
    tabContents: document.querySelectorAll('.tab-content'),
    
    // Modal elements
    benchmarkModal: document.getElementById('benchmarkModal'),
    benchmarkBtn: document.getElementById('benchmarkBtn'),
    closeBenchmark: document.getElementById('closeBenchmark'),
    closeBenchmarkBtn: document.getElementById('closeBenchmarkBtn'),
    startBenchmarkBtn: document.getElementById('startBenchmarkBtn'),
    
    // Loading
    loadingOverlay: document.getElementById('loadingOverlay'),
    loadingText: document.getElementById('loadingText')
};

// Utility functions
const utils = {
    formatTime: (seconds) => {
        if (seconds < 60) return `${seconds.toFixed(1)}s`;
        if (seconds < 3600) return `${Math.floor(seconds/60)}m ${Math.floor(seconds%60)}s`;
        return `${Math.floor(seconds/3600)}h ${Math.floor((seconds%3600)/60)}m`;
    },
    
    formatBytes: (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    debounce: (func, wait) => {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    showLoading: (text = 'Processing...') => {
        elements.loadingText.textContent = text;
        elements.loadingOverlay.style.display = 'flex';
    },
    
    hideLoading: () => {
        elements.loadingOverlay.style.display = 'none';
    },
    
    showNotification: (message, type = 'info') => {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <span>${message}</span>
            <button class="close-notification">&times;</button>
        `;
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
        
        // Manual close
        notification.querySelector('.close-notification').onclick = () => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        };
    }
};

// API functions
const api = {
    async callAPI(endpoint, method = 'GET', data = null) {
        const config = {
            method,
            headers: {
                'Content-Type': 'application/json',
                ...AppState.config.headers
            }
        };
        
        if (data) {
            config.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(endpoint, config);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    },
    
    async evaluateConversations(conversationIds, config) {
        utils.showLoading('Starting batch evaluation...');
        
        try {
            const response = await this.callAPI('/api/evaluate-batch', 'POST', {
                conversation_ids: conversationIds,
                ...config
            });
            
            return response;
        } catch (error) {
            utils.showNotification(`Evaluation failed: ${error.message}`, 'error');
            throw error;
        } finally {
            utils.hideLoading();
        }
    },
    
    async fetchConversations(config) {
        utils.showLoading('Fetching conversations...');
        
        try {
            const response = await this.callAPI('/api/fetch-conversations', 'POST', config);
            return response;
        } catch (error) {
            utils.showNotification(`Failed to fetch conversations: ${error.message}`, 'error');
            throw error;
        } finally {
            utils.hideLoading();
        }
    },
    
    async testBearerToken(token, baseUrl) {
        utils.showLoading('Testing bearer token...');
        
        try {
            const response = await this.callAPI('/api/test-token', 'POST', {
                token,
                base_url: baseUrl
            });
            return response;
        } catch (error) {
            utils.showNotification(`Token test failed: ${error.message}`, 'error');
            throw error;
        } finally {
            utils.hideLoading();
        }
    },
    
    async runBenchmark(config) {
        utils.showLoading('Running performance benchmark...');
        
        try {
            const response = await this.callAPI('/api/benchmark', 'POST', config);
            return response;
        } catch (error) {
            utils.showNotification(`Benchmark failed: ${error.message}`, 'error');
            throw error;
        } finally {
            utils.hideLoading();
        }
    },
    
    async upload(endpoint, formData) {
        const url = endpoint.startsWith('http') ? endpoint : `/api${endpoint}`;
        
        try {
            utils.showLoading(true);
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
            utils.showNotification('API Upload Error', error.message, 'error');
            throw error;
        } finally {
            utils.hideLoading(false);
        }
    }
};

// Configuration management
const Config = {
    async load() {
        // Load configuration from server or default settings
        const defaultConfig = {
            baseUrl: 'http://103.141.140.243:14496',
            headers: {},
            brandMode: 'single',
            selectedBrand: 'son_hai',
            maxConcurrency: 30,
            temperature: 0.2,
            useProgressiveBatching: true,
            useHighPerformanceApi: true,
            enableCaching: false,
            showPerformanceMetrics: true,
            applyDiagnostics: true,
            flows: ['booking_inquiry', 'route_planning', 'customer_support', 'general_inquiry']
        };
        
        // Merge with server config if available
        try {
            const response = await api.callAPI('/api/config');
            Object.assign(defaultConfig, response);
        } catch (error) {
            console.warn('Failed to load config from server, using defaults:', error);
        }
        
        // Apply config
        Object.assign(AppState.config, defaultConfig);
        this.updateUI();
    },
    
    updateUI() {
        // Update UI elements based on config
        document.getElementById('baseUrl').value = AppState.config.baseUrl;
        document.getElementById('headers').value = JSON.stringify(AppState.config.headers, null, 2);
        document.getElementById('maxConcurrency').value = AppState.config.maxConcurrency;
        document.getElementById('temperature').value = AppState.config.temperature;
        document.getElementById('apiRateLimit').value = AppState.config.apiRateLimit;
        document.getElementById('memoryCleanupInterval').value = AppState.config.memoryCleanupInterval;
        
        // Update brand mode
        const brandModeRadios = document.querySelectorAll('input[name="brandMode"]');
        brandModeRadios.forEach(radio => {
            if (radio.value === AppState.config.brandMode) {
                radio.checked = true;
            } else {
                radio.checked = false;
            }
        });
        
        // Update flows info
        this.loadFlowsInfo();
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
        // Initialize configuration modal and events
        this.setupModal();
        this.setupEvents();
    },
    
    setupModal() {
        // Modal for configuration settings
        const modalHtml = `
            <div class="modal fade" id="configModal" tabindex="-1" aria-labelledby="configModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="configModalLabel">Configuration Settings</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="configForm">
                                <div class="mb-3">
                                    <label for="baseUrl" class="form-label">Base URL</label>
                                    <input type="text" class="form-control" id="baseUrl" required>
                                </div>
                                <div class="mb-3">
                                    <label for="headers" class="form-label">Headers (JSON)</label>
                                    <textarea class="form-control" id="headers" rows="4"></textarea>
                                </div>
                                <div class="mb-3">
                                    <label for="maxConcurrency" class="form-label">Max Concurrency</label>
                                    <input type="number" class="form-control" id="maxConcurrency" min="1" max="100" required>
                                </div>
                                <div class="mb-3">
                                    <label for="temperature" class="form-label">Temperature</label>
                                    <input type="number" class="form-control" id="temperature" step="0.1" min="0" max="1" required>
                                </div>
                                <div class="mb-3">
                                    <label for="apiRateLimit" class="form-label">API Rate Limit</label>
                                    <input type="number" class="form-control" id="apiRateLimit" min="1" max="1000" required>
                                </div>
                                <div class="mb-3">
                                    <label for="memoryCleanupInterval" class="form-label">Memory Cleanup Interval</label>
                                    <input type="number" class="form-control" id="memoryCleanupInterval" min="1" max="60" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Brand Mode</label>
                                    <div>
                                        <input type="radio" name="brandMode" value="single" id="brandModeSingle" checked>
                                        <label for="brandModeSingle" class="form-label-inline">Single Brand</label>
                                    </div>
                                    <div>
                                        <input type="radio" name="brandMode" value="multi" id="brandModeMulti">
                                        <label for="brandModeMulti" class="form-label-inline">Multi Brand</label>
                                    </div>
                                </div>
                                <div class="mb-3" id="singleBrandConfig">
                                    <label for="selectedBrand" class="form-label">Select Brand</label>
                                    <select class="form-select" id="selectedBrand"></select>
                                </div>
                                <div class="mb-3" id="multiBrandConfig" style="display:none;">
                                    <label for="brandList" class="form-label">Brand List (CSV)</label>
                                    <input type="file" class="form-control" id="brandList" accept=".csv">
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary" id="saveConfigBtn">Save Changes</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },
    
    setupEvents() {
        // Event listeners for configuration modal
        document.getElementById('configModal').addEventListener('show.bs.modal', () => {
            this.loadConfigToForm();
        });
        
        document.getElementById('saveConfigBtn').addEventListener('click', () => {
            this.saveConfig();
        });
        
        // Brand mode change
        document.querySelectorAll('input[name="brandMode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                const mode = e.target.value;
                if (mode === 'single') {
                    document.getElementById('singleBrandConfig').style.display = 'block';
                    document.getElementById('multiBrandConfig').style.display = 'none';
                } else {
                    document.getElementById('singleBrandConfig').style.display = 'none';
                    document.getElementById('multiBrandConfig').style.display = 'block';
                }
            });
        });
    },
    
    async loadConfigToForm() {
        // Load current config values into the form
        document.getElementById('baseUrl').value = AppState.config.baseUrl;
        document.getElementById('headers').value = JSON.stringify(AppState.config.headers, null, 2);
        document.getElementById('maxConcurrency').value = AppState.config.maxConcurrency;
        document.getElementById('temperature').value = AppState.config.temperature;
        document.getElementById('apiRateLimit').value = AppState.config.apiRateLimit;
        document.getElementById('memoryCleanupInterval').value = AppState.config.memoryCleanupInterval;
        
        // Set brand mode
        const brandModeRadios = document.querySelectorAll('input[name="brandMode"]');
        brandModeRadios.forEach(radio => {
            radio.checked = (radio.value === AppState.config.brandMode);
        });
        
        // Show/hide brand config
        if (AppState.config.brandMode === 'single') {
            document.getElementById('singleBrandConfig').style.display = 'block';
            document.getElementById('multiBrandConfig').style.display = 'none';
        } else {
            document.getElementById('singleBrandConfig').style.display = 'none';
            document.getElementById('multiBrandConfig').style.display = 'block';
        }
        
        // Load brand options
        await this.loadBrandOptions();
    },
    
    async loadBrandOptions() {
        // Load available brands from server
        try {
            const response = await api.callAPI('/api/brands');
            const select = document.getElementById('selectedBrand');
            select.innerHTML = '';
            
            response.forEach(brand => {
                const option = document.createElement('option');
                option.value = brand.id;
                option.textContent = brand.name;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Failed to load brands:', error);
        }
    },
    
    async saveConfig() {
        // Save configuration changes
        const form = document.getElementById('configForm');
        const formData = new FormData(form);
        
        // Convert headers JSON string to object
        try {
            const headers = JSON.parse(formData.get('headers'));
            AppState.config.headers = headers;
        } catch (error) {
            return utils.showNotification('Invalid headers format', 'error');
        }
        
        // Update AppState.config from form data
        AppState.config.baseUrl = formData.get('baseUrl');
        AppState.config.maxConcurrency = parseInt(formData.get('maxConcurrency'));
        AppState.config.temperature = parseFloat(formData.get('temperature'));
        AppState.config.apiRateLimit = parseInt(formData.get('apiRateLimit'));
        AppState.config.memoryCleanupInterval = parseInt(formData.get('memoryCleanupInterval'));
        AppState.config.brandMode = formData.get('brandMode');
        AppState.config.selectedBrand = formData.get('selectedBrand');
        
        // Save to server
        try {
            await api.callAPI('/api/config', 'POST', AppState.config);
            utils.showNotification('Configuration saved successfully', 'success');
        } catch (error) {
            utils.showNotification(`Failed to save configuration: ${error.message}`, 'error');
        }
    }
};

// Performance management
const PerformanceManager = {
    init() {
        // Initialize performance monitoring
        this.startMonitoring();
    },
    
    startMonitoring() {
        // Start periodic performance updates
        this.interval = setInterval(() => {
            this.updateMetrics();
        }, 5000);
    },
    
    stopMonitoring() {
        // Stop performance monitoring
        clearInterval(this.interval);
    },
    
    updateMetrics() {
        // Update performance metrics display
        api.callAPI('/api/performance-metrics')
            .then(metrics => {
                elements.cpuMetric.textContent = `${metrics.cpuUsage.toFixed(1)}%`;
                elements.memoryMetric.textContent = utils.formatBytes(metrics.memoryUsage);
                elements.throughputMetric.textContent = `${metrics.throughput.toFixed(1)} req/s`;
                elements.cacheMetric.textContent = `${metrics.cacheHitRate.toFixed(1)}%`;
            })
            .catch(error => {
                console.error('Failed to fetch performance metrics:', error);
            });
    }
};

// Evaluation management
const EvaluationManager = {
    init() {
        // Initialize evaluation controls and events
        this.setupEvents();
    },
    
    setupEvents() {
        // Main evaluation button
        elements.evaluateBtn.addEventListener('click', this.handleEvaluate);
        
        // Streaming results tab
        elements.tabButtons.forEach(button => {
            button.addEventListener('click', this.handleTabSwitch);
        });
    },
    
    async handleEvaluate() {
        if (AppState.isEvaluating || AppState.conversationIds.length === 0) return;
        
        AppState.isEvaluating = true;
        AppState.streamingResults = [];
        
        // Show progress section
        elements.progressSection.style.display = 'block';
        elements.progressBar.style.width = '0%';
        
        // Show performance metrics if enabled
        if (AppState.config.showPerformanceMetrics) {
            elements.performanceMetrics.style.display = 'block';
            performance.startMonitoring();
        }
        
        try {
            const config = {
                brand_mode: AppState.config.brandMode,
                selected_brand: AppState.config.selectedBrand,
                max_concurrency: AppState.config.maxConcurrency,
                temperature: AppState.config.temperature,
                use_progressive_batching: AppState.config.useProgressiveBatching,
                use_high_performance_api: AppState.config.useHighPerformanceApi,
                enable_caching: AppState.config.enableCaching,
                apply_diagnostics: AppState.config.applyDiagnostics,
                base_url: AppState.config.baseUrl,
                headers: AppState.config.headers
            };
            
            await evaluation.startStreaming(AppState.conversationIds, config);
            
        } catch (error) {
            utils.showNotification(`Evaluation failed: ${error.message}`, 'error');
        } finally {
            AppState.isEvaluating = false;
            if (AppState.config.showPerformanceMetrics) {
                performance.stopMonitoring();
            }
        }
    },
    
    handleTabSwitch(e) {
        const targetTab = e.target.dataset.tab;
        
        // Update tab buttons
        elements.tabButtons.forEach(button => {
            button.classList.remove('active');
        });
        e.target.classList.add('active');
        
        // Update tab contents
        elements.tabContents.forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(targetTab).classList.add('active');
        
        // Load content based on tab
        switch (targetTab) {
            case 'resultsTable':
                results.displayTable();
                break;
            case 'analytics':
                results.displayAnalytics();
                break;
            case 'performance':
                results.displayPerformance();
                break;
            case 'export':
                results.displayExport();
                break;
        }
    }
};

// Evaluation handling with streaming
const evaluation = {
    startTime: null,
    updateInterval: null,
    
    async startStreaming(conversationIds, config) {
        this.startTime = Date.now();
        
        // Initialize progress
        this.updateProgress(0, 0, conversationIds.length);
        
        // Start periodic updates
        this.updateInterval = setInterval(() => {
            this.updateProgress(
                AppState.streamingResults.length / conversationIds.length,
                AppState.streamingResults.length,
                conversationIds.length
            );
        }, 1000);
        
        try {
            // Mock streaming evaluation (replace with actual WebSocket or polling)
            await this.simulateStreaming(conversationIds, config);
            
            // Final update
            this.updateProgress(1, conversationIds.length, conversationIds.length);
            
            // Display final results
            AppState.evaluationResults = AppState.streamingResults;
            AppState.summaryData = this.generateSummary(AppState.streamingResults);
            
            elements.resultsSection.style.display = 'block';
            results.displayTable();
            
            utils.showNotification(`✅ Evaluation completed! ${AppState.streamingResults.length} results`, 'success');
            
        } finally {
            if (this.updateInterval) {
                clearInterval(this.updateInterval);
                this.updateInterval = null;
            }
        }
    },
    
    async simulateStreaming(conversationIds, config) {
        // This is a simulation - replace with actual API calls
        for (let i = 0; i < conversationIds.length; i++) {
            // Simulate processing delay
            await new Promise(resolve => setTimeout(resolve, Math.random() * 2000 + 500));
            
            // Simulate result
            const result = {
                conversation_id: conversationIds[i],
                result: {
                    detected_flow: 'booking_inquiry',
                    total_score: Math.random() * 100,
                    label: Math.random() > 0.5 ? 'good' : 'acceptable',
                    confidence: Math.random(),
                    criteria: {
                        greeting: { score: Math.random() * 100, note: 'Sample note' },
                        info_gathering: { score: Math.random() * 100, note: 'Sample note' },
                        closing: { score: Math.random() * 100, note: 'Sample note' }
                    }
                },
                metrics: {
                    policy_violations: Math.floor(Math.random() * 3),
                    total_turns: Math.floor(Math.random() * 20 + 5),
                    first_response_latency_seconds: Math.random() * 10
                }
            };
            
            AppState.streamingResults.push(result);
            this.updateStreamingDisplay();
        }
    },
    
    updateProgress(progress, current, total) {
        const elapsed = (Date.now() - this.startTime) / 1000;
        const speed = current > 0 ? current / elapsed : 0;
        const eta = speed > 0 ? (total - current) / speed : 0;
        const successRate = AppState.streamingResults.length > 0 
            ? AppState.streamingResults.filter(r => !r.error).length / AppState.streamingResults.length 
            : 0;
        
        // Update progress bar
        elements.progressBar.style.width = `${progress * 100}%`;
        
        // Update status
        elements.progressStatus.textContent = current < total 
            ? `⚡ Evaluating: ${current}/${total} (${(progress * 100).toFixed(1)}%) - ETA: ${utils.formatTime(eta)}`
            : '✅ Evaluation completed!';
        
        // Update metrics
        elements.speedMetric.textContent = `${speed.toFixed(1)} conv/s`;
        elements.elapsedMetric.textContent = utils.formatTime(elapsed);
        elements.progressMetric.textContent = `${current}/${total}`;
        elements.successRateMetric.textContent = `${(successRate * 100).toFixed(1)}%`;
    },
    
    updateStreamingDisplay() {
        const recentResults = AppState.streamingResults.slice(-6);
        elements.streamingResults.innerHTML = `
            <h4>Recent Results (${AppState.streamingResults.length} total)</h4>
            ${recentResults.map(result => `
                <div class="streaming-result-item">
                    <strong>${result.conversation_id.slice(-10)}</strong>: 
                    ${result.error ? 
                        `<span class="text-error">Error</span>` : 
                        `<span class="text-success">${result.result.total_score.toFixed(1)} pts</span>`
                    }
                </div>
            `).join('')}
        `;
    },
    
    generateSummary(results) {
        const successful = results.filter(r => !r.error);
        const total = results.length;
        
        if (successful.length === 0) {
            return {
                count: total,
                successful_count: 0,
                avg_total_score: 0,
                policy_violation_rate: 0,
                criteria_avg: {},
                flow_distribution: {},
                diagnostics_top: []
            };
        }
        
        const totalScore = successful.reduce((sum, r) => sum + r.result.total_score, 0);
        const avgScore = totalScore / successful.length;
        
        const policyViolations = successful.filter(r => r.metrics.policy_violations > 0).length;
        const violationRate = policyViolations / successful.length;
        
        // Calculate criteria averages
        const criteriaAvg = {};
        const criteriaData = {};
        
        successful.forEach(result => {
            Object.entries(result.result.criteria).forEach(([criterion, data]) => {
                if (!criteriaData[criterion]) criteriaData[criterion] = [];
                criteriaData[criterion].push(data.score);
            });
        });
        
        Object.entries(criteriaData).forEach(([criterion, scores]) => {
            criteriaAvg[criterion] = scores.reduce((sum, score) => sum + score, 0) / scores.length;
        });
        
        // Flow distribution
        const flowDist = {};
        successful.forEach(result => {
            const flow = result.result.detected_flow;
            flowDist[flow] = (flowDist[flow] || 0) + 1;
        });
        
        return {
            count: total,
            successful_count: successful.length,
            avg_total_score: avgScore,
            policy_violation_rate: violationRate,
            criteria_avg: criteriaAvg,
            flow_distribution: flowDist,
            diagnostics_top: [],
            latency_stats: {
                avg_first_response: successful.reduce((sum, r) => 
                    sum + (r.metrics.first_response_latency_seconds || 0), 0) / successful.length
            }
        };
    }
};

// Results display
const results = {
    displayTable() {
        if (!AppState.evaluationResults) {
            document.getElementById('resultsTableContent').innerHTML = '<p>No results available</p>';
            return;
        }
        
        const successful = AppState.evaluationResults.filter(r => !r.error);
        
        let tableHTML = `
            <div class="results-summary">
                <h3>Results Summary</h3>
                <div class="metrics-row">
                    <div class="metric-card">
                        <div class="metric-label">Total</div>
                        <div class="metric-value">${AppState.evaluationResults.length}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Successful</div>
                        <div class="metric-value">${successful.length}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Avg Score</div>
                        <div class="metric-value">${AppState.summaryData.avg_total_score.toFixed(1)}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Success Rate</div>
                        <div class="metric-value">${(successful.length / AppState.evaluationResults.length * 100).toFixed(1)}%</div>
                    </div>
                </div>
            </div>
            
            <table class="results-table">
                <thead>
                    <tr>
                        <th>Conversation ID</th>
                        <th>Flow</th>
                        <th>Score</th>
                        <th>Label</th>
                        <th>Confidence</th>
                        <th>Policy Violations</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        successful.forEach(result => {
            tableHTML += `
                <tr>
                    <td>${result.conversation_id.slice(-15)}</td>
                    <td>${result.result.detected_flow}</td>
                    <td><span class="score-badge">${result.result.total_score.toFixed(1)}</span></td>
                    <td><span class="label-badge label-${result.result.label}">${result.result.label}</span></td>
                    <td>${(result.result.confidence * 100).toFixed(1)}%</td>
                    <td>${result.metrics.policy_violations || 0}</td>
                    <td><button class="btn btn-secondary" onclick="results.showDetails('${result.conversation_id}')">Details</button></td>
                </tr>
            `;
        });
        
        tableHTML += '</tbody></table>';
        
        document.getElementById('resultsTableContent').innerHTML = tableHTML;
    },
    
    displayAnalytics() {
        if (!AppState.summaryData) {
            document.getElementById('analyticsContent').innerHTML = '<p>No analytics data available</p>';
            return;
        }
        
        let analyticsHTML = `
            <div class="analytics-overview">
                <h3>📊 Batch Analytics</h3>
                
                <div class="insights-section">
                    <h4>💡 Key Insights</h4>
                    <div class="insights-list">
                        ${this.generateInsights().map(insight => `<div class="insight-item">${insight}</div>`).join('')}
                    </div>
                </div>
                
                <div class="charts-container">
                    <div class="chart-card">
                        <h4>Criteria Performance</h4>
                        <canvas id="criteriaChart"></canvas>
                    </div>
                    
                    <div class="chart-card">
                        <h4>Score Distribution</h4>
                        <canvas id="scoreChart"></canvas>
                    </div>
                    
                    <div class="chart-card">
                        <h4>Flow Distribution</h4>
                        <canvas id="flowChart"></canvas>
                    </div>
                </div>
            </div>
        `;
        
        document.getElementById('analyticsContent').innerHTML = analyticsHTML;
        
        // Create charts
        setTimeout(() => {
            this.createCharts();
        }, 100);
    },
    
    displayPerformance() {
        const performanceHTML = `
            <div class="performance-dashboard">
                <h3>⚡ Performance Dashboard</h3>
                
                <div class="perf-metrics-grid">
                    <div class="perf-metric-card">
                        <div class="perf-metric-label">Total Processed</div>
                        <div class="perf-metric-value">${AppState.evaluationResults?.length || 0}</div>
                    </div>
                    <div class="perf-metric-card">
                        <div class="perf-metric-label">Success Rate</div>
                        <div class="perf-metric-value">${AppState.evaluationResults ? 
                            (AppState.evaluationResults.filter(r => !r.error).length / AppState.evaluationResults.length * 100).toFixed(1) : 0}%</div>
                    </div>
                    <div class="perf-metric-card">
                        <div class="perf-metric-label">Avg Score</div>
                        <div class="perf-metric-value">${AppState.summaryData?.avg_total_score?.toFixed(1) || 0}</div>
                    </div>
                    <div class="perf-metric-card">
                        <div class="perf-metric-label">Configuration</div>
                        <div class="perf-metric-value">Concurrency: ${AppState.config.maxConcurrency}</div>
                    </div>
                </div>
                
                <div class="performance-recommendations">
                    <h4>💡 Performance Recommendations</h4>
                    ${this.generatePerformanceRecommendations()}
                </div>
            </div>
        `;
        
        document.getElementById('performanceContent').innerHTML = performanceHTML;
    },
    
    displayExport() {
        const exportHTML = `
            <div class="export-options">
                <h3>⬇️ Export Options</h3>
                
                <div class="export-cards">
                    <div class="export-card">
                        <h4>📄 JSON Results</h4>
                        <p>Complete evaluation results with all details</p>
                        <button class="btn btn-primary" onclick="results.exportJSON()">Download JSON</button>
                    </div>
                    
                    <div class="export-card">
                        <h4>📊 CSV Summary</h4>
                        <p>Tabular summary for spreadsheet analysis</p>
                        <button class="btn btn-primary" onclick="results.exportCSV()">Download CSV</button>
                    </div>
                    
                    <div class="export-card">
                        <h4>📑 HTML Report</h4>
                        <p>Comprehensive report with charts</p>
                        <button class="btn btn-primary" onclick="results.exportHTML()">Download HTML</button>
                    </div>
                </div>
            </div>
        `;
        
        document.getElementById('exportContent').innerHTML = exportHTML;
    },
    
    generateInsights() {
        if (!AppState.summaryData) return [];
        
        const insights = [];
        const summary = AppState.summaryData;
        
        if (summary.avg_total_score > 80) {
            insights.push('🎉 Excellent overall performance with high average scores');
        } else if (summary.avg_total_score < 60) {
            insights.push('⚠️ Below-target performance detected, review conversation quality');
        }
        
        if (summary.policy_violation_rate > 0.2) {
            insights.push('🚨 High policy violation rate - review compliance procedures');
        } else if (summary.policy_violation_rate < 0.05) {
            insights.push('✅ Low policy violation rate - good compliance');
        }
        
        // Find best and worst criteria
        const criteria = Object.entries(summary.criteria_avg);
        if (criteria.length > 1) {
            const best = criteria.reduce((max, curr) => curr[1] > max[1] ? curr : max);
            const worst = criteria.reduce((min, curr) => curr[1] < min[1] ? curr : min);
            
            insights.push(`🏆 Best performing criterion: ${best[0]} (${best[1].toFixed(1)})`);
            insights.push(`📈 Improvement opportunity: ${worst[0]} (${worst[1].toFixed(1)})`);
        }
        
        return insights;
    },
    
    generatePerformanceRecommendations() {
        if (!AppState.evaluationResults) return '<p>No performance data available</p>';
        
        const totalResults = AppState.evaluationResults.length;
        const successfulResults = AppState.evaluationResults.filter(r => !r.error).length;
        const successRate = successfulResults / totalResults;
        
        let recommendations = '<ul>';
        
        if (successRate < 0.9) {
            recommendations += '<li class="warning">⚠️ Low success rate detected. Check API connectivity and error logs.</li>';
        }
        
        if (AppState.config.maxConcurrency < 20 && totalResults > 20) {
            recommendations += '<li class="info">💡 Consider increasing concurrency to 20-25 for better throughput.</li>';
        }
        
        if (!AppState.config.useHighPerformanceApi) {
            recommendations += '<li class="info">🚀 Enable High-Performance API for 30-50% speed improvement.</li>';
        }
        
        if (!AppState.config.enableCaching && totalResults > 10) {
            recommendations += '<li class="info">📦 Enable Redis caching for repeated evaluations.</li>';
        }
        
        recommendations += '</ul>';
        
        return recommendations;
    },
    
    createCharts() {
        // Criteria performance chart
        if (AppState.summaryData?.criteria_avg) {
            const criteriaCtx = document.getElementById('criteriaChart');
            if (criteriaCtx) {
                new Chart(criteriaCtx, {
                    type: 'bar',
                    data: {
                        labels: Object.keys(AppState.summaryData.criteria_avg),
                        datasets: [{
                            label: 'Average Score',
                            data: Object.values(AppState.summaryData.criteria_avg),
                            backgroundColor: '#4f46e5',
                            borderColor: '#7c3aed',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            y: { beginAtZero: true, max: 100 }
                        }
                    }
                });
            }
        }
        
        // Score distribution chart
        if (AppState.evaluationResults) {
            const scores = AppState.evaluationResults
                .filter(r => !r.error)
                .map(r => r.result.total_score);
            
            const scoreCtx = document.getElementById('scoreChart');
            if (scoreCtx && scores.length > 0) {
                new Chart(scoreCtx, {
                    type: 'histogram',
                    data: {
                        datasets: [{
                            label: 'Score Distribution',
                            data: scores,
                            backgroundColor: '#10b981',
                            borderColor: '#059669',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false } }
                    }
                });
            }
        }
        
        // Flow distribution chart
        if (AppState.summaryData?.flow_distribution) {
            const flowCtx = document.getElementById('flowChart');
            if (flowCtx) {
                new Chart(flowCtx, {
                    type: 'pie',
                    data: {
                        labels: Object.keys(AppState.summaryData.flow_distribution),
                        datasets: [{
                            data: Object.values(AppState.summaryData.flow_distribution),
                            backgroundColor: [
                                '#4f46e5', '#7c3aed', '#ec4899', 
                                '#f59e0b', '#10b981', '#0ea5e9'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'bottom' }
                        }
                    }
                });
            }
        }
    },
    
    showDetails(conversationId) {
        const result = AppState.evaluationResults.find(r => r.conversation_id === conversationId);
        if (!result) return;
        
        // Create detailed view modal
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Conversation Details: ${conversationId.slice(-15)}</h3>
                    <span class="close-modal">&times;</span>
                </div>
                <div class="modal-body">
                    ${this.renderConversationDetails(result)}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        modal.querySelector('.close-modal').onclick = () => {
            document.body.removeChild(modal);
        };
        
        modal.onclick = (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        };
    },
    
    renderConversationDetails(result) {
        const evalResult = result.result;
        const metrics = result.metrics;
        
        let detailsHTML = `
            <div class="conversation-details">
                <div class="details-header">
                    <div class="detail-metric">
                        <label>Flow</label>
                        <value>${evalResult.detected_flow}</value>
                    </div>
                    <div class="detail-metric">
                        <label>Confidence</label>
                        <value>${(evalResult.confidence * 100).toFixed(1)}%</value>
                    </div>
                    <div class="detail-metric">
                        <label>Total Score</label>
                        <value>${evalResult.total_score.toFixed(1)}/100</value>
                    </div>
                </div>
                
                <div class="details-section">
                    <h4>Label & Comment</h4>
                    <p><strong>Label:</strong> ${evalResult.label}</p>
                    <p><strong>Comment:</strong> ${evalResult.final_comment || 'N/A'}</p>
                </div>
                
                <div class="details-section">
                    <h4>Criteria Breakdown</h4>
                    <div class="criteria-list">
        `;
        
        Object.entries(evalResult.criteria).forEach(([criterion, details]) => {
            detailsHTML += `
                <div class="criteria-item">
                    <div class="criteria-header">
                        <span class="criteria-name">${criterion}</span>
                        <span class="criteria-score">${details.score?.toFixed(0) || 0}/100</span>
                    </div>
                    <div class="criteria-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${Math.min(details.score || 0, 100)}%"></div>
                        </div>
                    </div>
                    ${details.note ? `<div class="criteria-note">${details.note}</div>` : ''}
                </div>
            `;
        });
        
        detailsHTML += `
                    </div>
                </div>
                
                <div class="details-section">
                    <h4>Additional Information</h4>
                    <div class="info-grid">
                        <div class="info-item">
                            <label>Policy Violations</label>
                            <value>${metrics.policy_violations || 0}</value>
                        </div>
                        <div class="info-item">
                            <label>Total Turns</label>
                            <value>${metrics.total_turns || 0}</value>
                        </div>
                        <div class="info-item">
                            <label>First Response Latency</label>
                            <value>${(metrics.first_response_latency_seconds || 0).toFixed(1)}s</value>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        return detailsHTML;
    },
    
    exportJSON() {
        if (!AppState.evaluationResults) {
            utils.showNotification('No results to export', 'warning');
            return;
        }
        
        const dataStr = JSON.stringify(AppState.evaluationResults, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = `batch_evaluation_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
        link.click();
        
        URL.revokeObjectURL(url);
        utils.showNotification('JSON exported successfully', 'success');
    },
    
    exportCSV() {
        if (!AppState.evaluationResults) {
            utils.showNotification('No results to export', 'warning');
            return;
        }
        
        const successful = AppState.evaluationResults.filter(r => !r.error);
        const headers = [
            'conversation_id', 'detected_flow', 'total_score', 'label', 'confidence',
            'policy_violations', 'total_turns', 'first_response_latency'
        ];
        
        // Add criteria headers
        const allCriteria = new Set();
        successful.forEach(result => {
            Object.keys(result.result.criteria).forEach(criterion => {
                allCriteria.add(criterion);
            });
        });
        
        allCriteria.forEach(criterion => {
            headers.push(`${criterion}_score`, `${criterion}_note`);
        });
        
        let csvContent = headers.join(',') + '\n';
        
        successful.forEach(result => {
            const row = [
                result.conversation_id,
                result.result.detected_flow,
                result.result.total_score.toFixed(2),
                result.result.label,
                (result.result.confidence * 100).toFixed(1),
                result.metrics.policy_violations || 0,
                result.metrics.total_turns || 0,
                (result.metrics.first_response_latency_seconds || 0).toFixed(2)
            ];
            
            // Add criteria data
            allCriteria.forEach(criterion => {
                const criteriaData = result.result.criteria[criterion];
                if (criteriaData) {
                    row.push(criteriaData.score?.toFixed(2) || 0);
                    row.push(`"${(criteriaData.note || '').replace(/"/g, '""')}"`);
                } else {
                    row.push(0, '""');
                }
            });
            
            csvContent += row.join(',') + '\n';
        });
        
        const dataBlob = new Blob([csvContent], { type: 'text/csv' });
        const url = URL.createObjectURL(dataBlob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = `batch_summary_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.csv`;
        link.click();
        
        URL.revokeObjectURL(url);
        utils.showNotification('CSV exported successfully', 'success');
    },
    
    exportHTML() {
        if (!AppState.evaluationResults || !AppState.summaryData) {
            utils.showNotification('No results to export', 'warning');
            return;
        }
        
        const htmlContent = `
            <!DOCTYPE html>
            <html>
            <head>
                <title>Bus QA Evaluation Report</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; color: #333; }
                    .header { color: #2e4057; border-bottom: 2px solid #2e4057; padding-bottom: 10px; }
                    .metric { background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 5px; }
                    .insight { background: #e3f2fd; padding: 10px; border-radius: 5px; margin: 5px 0; }
                    table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #f2f2f2; }
                    .score-good { color: #28a745; font-weight: bold; }
                    .score-warn { color: #ffc107; font-weight: bold; }
                    .score-poor { color: #dc3545; font-weight: bold; }
                </style>
            </head>
            <body>
                <h1 class="header">Bus QA Evaluation Batch Report</h1>
                <p>Generated on: ${new Date().toLocaleString()}</p>
                
                <h2>Executive Summary</h2>
                <div class="metric">Total Conversations: ${AppState.summaryData.count}</div>
                <div class="metric">Successful Evaluations: ${AppState.summaryData.successful_count}</div>
                <div class="metric">Average Score: ${AppState.summaryData.avg_total_score.toFixed(1)}/100</div>
                <div class="metric">Policy Violation Rate: ${(AppState.summaryData.policy_violation_rate * 100).toFixed(1)}%</div>
                
                <h2>Key Insights</h2>
                ${this.generateInsights().map(insight => `<div class="insight">${insight}</div>`).join('')}
                
                <h2>Results Summary</h2>
                <table>
                    <tr>
                        <th>Conversation ID</th>
                        <th>Flow</th>
                        <th>Score</th>
                        <th>Label</th>
                        <th>Confidence</th>
                        <th>Policy Violations</th>
                    </tr>
                    ${AppState.evaluationResults.filter(r => !r.error).map(result => `
                        <tr>
                            <td>${result.conversation_id}</td>
                            <td>${result.result.detected_flow}</td>
                            <td class="${result.result.total_score >= 80 ? 'score-good' : result.result.total_score >= 60 ? 'score-warn' : 'score-poor'}">
                                ${result.result.total_score.toFixed(1)}
                            </td>
                            <td>${result.result.label}</td>
                            <td>${(result.result.confidence * 100).toFixed(1)}%</td>
                            <td>${result.metrics.policy_violations || 0}</td>
                        </tr>
                    `).join('')}
                </table>
            </body>
            </html>
        `;
        
        const dataBlob = new Blob([htmlContent], { type: 'text/html' });
        const url = URL.createObjectURL(dataBlob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = `batch_report_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.html`;
        link.click();
        
        URL.revokeObjectURL(url);
        utils.showNotification('HTML report exported successfully', 'success');
    }
};

// Benchmark handling
const benchmark = {
    displayResults(results) {
        const benchmarkResultsDiv = document.getElementById('benchmarkResults');
        
        if (!results || results.length === 0) {
            benchmarkResultsDiv.innerHTML = '<p class="error">No benchmark results received</p>';
            return;
        }
        
        // Find best performing configuration
        const bestResult = results.reduce((best, current) => 
            current.throughput > best.throughput ? current : best
        );
        
        let resultsHTML = `
            <div class="benchmark-results-content">
                <h4>🎯 Benchmark Results</h4>
                
                <div class="benchmark-summary">
                    <div class="best-config">
                        <h5>🏆 Recommended Configuration</h5>
                        <p><strong>Concurrency:</strong> ${bestResult.concurrency}</p>
                        <p><strong>Throughput:</strong> ${bestResult.throughput.toFixed(2)} conv/s</p>
                        <p><strong>Avg Latency:</strong> ${bestResult.avg_latency.toFixed(2)}s</p>
                        <p><strong>Success Rate:</strong> ${(bestResult.success_rate * 100).toFixed(1)}%</p>
                    </div>
                </div>
                
                <table class="benchmark-table">
                    <thead>
                        <tr>
                            <th>Concurrency</th>
                            <th>Throughput (conv/s)</th>
                            <th>Avg Latency (s)</th>
                            <th>Success Rate</th>
                            <th>Total Time (s)</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        results.forEach(result => {
            const iseBest = result === bestResult;
            resultsHTML += `
                <tr class="${isBest ? 'best-row' : ''}">
                    <td>${result.concurrency}${isBest ? ' 🏆' : ''}</td>
                    <td>${result.throughput.toFixed(2)}</td>
                    <td>${result.avg_latency.toFixed(2)}</td>
                    <td>${(result.success_rate * 100).toFixed(1)}%</td>
                    <td>${result.total_time.toFixed(2)}</td>
                </tr>
            `;
        });
        
        resultsHTML += `
                    </tbody>
                </table>
                
                <div class="benchmark-actions">
                    <button class="btn btn-primary" onclick="benchmark.applyOptimalSettings(${bestResult.concurrency})">
                        Apply Optimal Settings
                    </button>
                </div>
            </div>
        `;
        
        benchmarkResultsDiv.innerHTML = resultsHTML;
    },
    
    applyOptimalSettings(concurrency) {
        elements.maxConcurrency.value = concurrency;
        elements.concurrencyValue.textContent = concurrency;
        AppState.config.maxConcurrency = concurrency;
        
        utils.showNotification(`Applied optimal concurrency setting: ${concurrency}`, 'success');
        handlers.handleBenchmarkClose();
    }
};

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    handlers.initializeEventListeners();
    handlers.updateBrandPolicy();
    
    // Load flows info
    document.getElementById('flowsInfo').innerHTML = 
        '<p class="caption">Flows hớp lệ: booking_inquiry, route_planning, customer_support, general_inquiry</p>';
    
    console.log('QA LLM Evaluator initialized');
});

// Global error handling
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    utils.showNotification(`Unexpected error: ${event.error.message}`, 'error');
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    utils.showNotification(`Promise error: ${event.reason}`, 'error');
});

/**
 * Bus QA LLM Evaluator - Flask Web App JavaScript
 * Main application logic for the web interface
 */

// Utility functions
const Utils = {
    formatTime: (seconds) => {
        if (seconds < 60) return `${seconds.toFixed(1)}s`;
        if (seconds < 3600) return `${Math.floor(seconds/60)}m ${Math.floor(seconds%60)}s`;
        return `${Math.floor(seconds/3600)}h ${Math.floor((seconds%3600)/60)}m`;
    },
    
    formatBytes: (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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
    async callAPI(endpoint, method = 'GET', data = null) {
        const config = {
            method,
            headers: {
                'Content-Type': 'application/json',
                ...AppState.config.headers
            }
        };
        
        if (data) {
            config.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(endpoint, config);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    },
    
    async evaluateConversations(conversationIds, config) {
        utils.showLoading('Starting batch evaluation...');
        
        try {
            const response = await this.callAPI('/api/evaluate-batch', 'POST', {
                conversation_ids: conversationIds,
                ...config
            });
            
            return response;
        } catch (error) {
            utils.showNotification(`Evaluation failed: ${error.message}`, 'error');
            throw error;
        } finally {
            utils.hideLoading();
        }
    },
    
    async fetchConversations(config) {
        utils.showLoading('Fetching conversations...');
        
        try {
            const response = await this.callAPI('/api/fetch-conversations', 'POST', config);
            return response;
        } catch (error) {
            utils.showNotification(`Failed to fetch conversations: ${error.message}`, 'error');
            throw error;
        } finally {
            utils.hideLoading();
        }
    },
    
    async testBearerToken(token, baseUrl) {
        utils.showLoading('Testing bearer token...');
        
        try {
            const response = await this.callAPI('/api/test-token', 'POST', {
                token,
                base_url: baseUrl
            });
            return response;
        } catch (error) {
            utils.showNotification(`Token test failed: ${error.message}`, 'error');
            throw error;
        } finally {
            utils.hideLoading();
        }
    },
    
    async runBenchmark(config) {
        utils.showLoading('Running performance benchmark...');
        
        try {
            const response = await this.callAPI('/api/benchmark', 'POST', config);
            return response;
        } catch (error) {
            utils.showNotification(`Benchmark failed: ${error.message}`, 'error');
            throw error;
        } finally {
            utils.hideLoading();
        }
    },
    
    async upload(endpoint, formData) {
        const url = endpoint.startsWith('http') ? endpoint : `/api${endpoint}`;
        
        try {
            utils.showLoading(true);
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
            utils.showNotification('API Upload Error', error.message, 'error');
            throw error;
        } finally {
            utils.hideLoading(false);
        }
    }
};

// Configuration management
const Config = {
    async load() {
        // Load configuration from server or default settings
        const defaultConfig = {
            baseUrl: 'http://103.141.140.243:14496',
            headers: {},
            brandMode: 'single',
            selectedBrand: 'son_hai',
            maxConcurrency: 30,
            temperature: 0.2,
            useProgressiveBatching: true,
            useHighPerformanceApi: true,
            enableCaching: false,
            showPerformanceMetrics: true,
            applyDiagnostics: true,
            flows: ['booking_inquiry', 'route_planning', 'customer_support', 'general_inquiry']
        };
        
        // Merge with server config if available
        try {
            const response = await api.callAPI('/api/config');
            Object.assign(defaultConfig, response);
        } catch (error) {
            console.warn('Failed to load config from server, using defaults:', error);
        }
        
        // Apply config
        Object.assign(AppState.config, defaultConfig);
        this.updateUI();
    },
    
    updateUI() {
        // Update UI elements based on config
        document.getElementById('baseUrl').value = AppState.config.baseUrl;
        document.getElementById('headers').value = JSON.stringify(AppState.config.headers, null, 2);
        document.getElementById('maxConcurrency').value = AppState.config.maxConcurrency;
        document.getElementById('temperature').value = AppState.config.temperature;
        document.getElementById('apiRateLimit').value = AppState.config.apiRateLimit;
        document.getElementById('memoryCleanupInterval').value = AppState.config.memoryCleanupInterval;
        
        // Update brand mode
        const brandModeRadios = document.querySelectorAll('input[name="brandMode"]');
        brandModeRadios.forEach(radio => {
            if (radio.value === AppState.config.brandMode) {
                radio.checked = true;
            } else {
                radio.checked = false;
            }
        });
        
        // Update flows info
        this.loadFlowsInfo();
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
        // Initialize configuration modal and events
        this.setupModal();
        this.setupEvents();
    },
    
    setupModal() {
        // Modal for configuration settings
        const modalHtml = `
            <div class="modal fade" id="configModal" tabindex="-1" aria-labelledby="configModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="configModalLabel">Configuration Settings</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="configForm">
                                <div class="mb-3">
                                    <label for="baseUrl" class="form-label">Base URL</label>
                                    <input type="text" class="form-control" id="baseUrl" required>
                                </div>
                                <div class="mb-3">
                                    <label for="headers" class="form-label">Headers (JSON)</label>
                                    <textarea class="form-control" id="headers" rows="4"></textarea>
                                </div>
                                <div class="mb-3">
                                    <label for="maxConcurrency" class="form-label">Max Concurrency</label>
                                    <input type="number" class="form-control" id="maxConcurrency" min="1" max="100" required>
                                </div>
                                <div class="mb-3">
                                    <label for="temperature" class="form-label">Temperature</label>
                                    <input type="number" class="form-control" id="temperature" step="0.1" min="0" max="1" required>
                                </div>
                                <div class="mb-3">
                                    <label for="apiRateLimit" class="form-label">API Rate Limit</label>
                                    <input type="number" class="form-control" id="apiRateLimit" min="1" max="1000" required>
                                </div>
                                <div class="mb-3">
                                    <label for="memoryCleanupInterval" class="form-label">Memory Cleanup Interval</label>
                                    <input type="number" class="form-control" id="memoryCleanupInterval" min="1" max="60" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Brand Mode</label>
                                    <div>
                                        <input type="radio" name="brandMode" value="single" id="brandModeSingle" checked>
                                        <label for="brandModeSingle" class="form-label-inline">Single Brand</label>
                                    </div>
                                    <div>
                                        <input type="radio" name="brandMode" value="multi" id="brandModeMulti">
                                        <label for="brandModeMulti" class="form-label-inline">Multi Brand</label>
                                    </div>
                                </div>
                                <div class="mb-3" id="singleBrandConfig">
                                    <label for="selectedBrand" class="form-label">Select Brand</label>
                                    <select class="form-select" id="selectedBrand"></select>
                                </div>
                                <div class="mb-3" id="multiBrandConfig" style="display:none;">
                                    <label for="brandList" class="form-label">Brand List (CSV)</label>
                                    <input type="file" class="form-control" id="brandList" accept=".csv">
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary" id="saveConfigBtn">Save Changes</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },
    
    setupEvents() {
        // Event listeners for configuration modal
        document.getElementById('configModal').addEventListener('show.bs.modal', () => {
            this.loadConfigToForm();
        });
        
        document.getElementById('saveConfigBtn').addEventListener('click', () => {
            this.saveConfig();
        });
        
        // Brand mode change
        document.querySelectorAll('input[name="brandMode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                const mode = e.target.value;
                if (mode === 'single') {
                    document.getElementById('singleBrandConfig').style.display = 'block';
                    document.getElementById('multiBrandConfig').style.display = 'none';
                } else {
                    document.getElementById('singleBrandConfig').style.display = 'none';
                    document.getElementById('multiBrandConfig').style.display = 'block';
                }
            });
        });
    },
    
    async loadConfigToForm() {
        // Load current config values into the form
        document.getElementById('baseUrl').value = AppState.config.baseUrl;
        document.getElementById('headers').value = JSON.stringify(AppState.config.headers, null, 2);
        document.getElementById('maxConcurrency').value = AppState.config.maxConcurrency;
        document.getElementById('temperature').value = AppState.config.temperature;
        document.getElementById('apiRateLimit').value = AppState.config.apiRateLimit;
        document.getElementById('memoryCleanupInterval').value = AppState.config.memoryCleanupInterval;
        
        // Set brand mode
        const brandModeRadios = document.querySelectorAll('input[name="brandMode"]');
        brandModeRadios.forEach(radio => {
            radio.checked = (radio.value === AppState.config.brandMode);
        });
        
        // Show/hide brand config
        if (AppState.config.brandMode === 'single') {
            document.getElementById('singleBrandConfig').style.display = 'block';
            document.getElementById('multiBrandConfig').style.display = 'none';
        } else {
            document.getElementById('singleBrandConfig').style.display = 'none';
            document.getElementById('multiBrandConfig').style.display = 'block';
        }
        
        // Load brand options
        await this.loadBrandOptions();
    },
    
    async loadBrandOptions() {
        // Load available brands from server
        try {
            const response = await api.callAPI('/api/brands');
            const select = document.getElementById('selectedBrand');
            select.innerHTML = '';
            
            response.forEach(brand => {
                const option = document.createElement('option');
                option.value = brand.id;
                option.textContent = brand.name;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Failed to load brands:', error);
        }
    },
    
    async saveConfig() {
        // Save configuration changes
        const form = document.getElementById('configForm');
        const formData = new FormData(form);
        
        // Convert headers JSON string to object
        try {
            const headers = JSON.parse(formData.get('headers'));
            AppState.config.headers = headers;
        } catch (error) {
            return utils.showNotification('Invalid headers format', 'error');
        }
        
        // Update AppState.config from form data
        AppState.config.baseUrl = formData.get('baseUrl');
        AppState.config.maxConcurrency = parseInt(formData.get('maxConcurrency'));
        AppState.config.temperature = parseFloat(formData.get('temperature'));
        AppState.config.apiRateLimit = parseInt(formData.get('apiRateLimit'));
        AppState.config.memoryCleanupInterval = parseInt(formData.get('memoryCleanupInterval'));
        AppState.config.brandMode = formData.get('brandMode');
        AppState.config.selectedBrand = formData.get('selectedBrand');
        
        // Save to server
        try {
            await api.callAPI('/api/config', 'POST', AppState.config);
            utils.showNotification('Configuration saved successfully', 'success');
        } catch (error) {
            utils.showNotification(`Failed to save configuration: ${error.message}`, 'error');
        }
    }
};

// Performance management
const PerformanceManager = {
    init() {
        // Initialize performance monitoring
        this.startMonitoring();
    },
    
    startMonitoring() {
        // Start periodic performance updates
        this.interval = setInterval(() => {
            this.updateMetrics();
        }, 5000);
    },
    
    stopMonitoring() {
        // Stop performance monitoring
        clearInterval(this.interval);
    },
    
    updateMetrics() {
        // Update performance metrics display
        api.callAPI('/api/performance-metrics')
            .then(metrics => {
                elements.cpuMetric.textContent = `${metrics.cpuUsage.toFixed(1)}%`;
                elements.memoryMetric.textContent = utils.formatBytes(metrics.memoryUsage);
                elements.throughputMetric.textContent = `${metrics.throughput.toFixed(1)} req/s`;
                elements.cacheMetric.textContent = `${metrics.cacheHitRate.toFixed(1)}%`;
            })
            .catch(error => {
                console.error('Failed to fetch performance metrics:', error);
            });
    }
};

// Evaluation management
const EvaluationManager = {
    init() {
        // Initialize evaluation controls and events
        this.setupEvents();
    },
    
    setupEvents() {
        // Main evaluation button
        elements.evaluateBtn.addEventListener('click', this.handleEvaluate);
        
        // Streaming results tab
        elements.tabButtons.forEach(button => {
            button.addEventListener('click', this.handleTabSwitch);
        });
    },
    
    async handleEvaluate() {
        if (AppState.isEvaluating || AppState.conversationIds.length === 0) return;
        
        AppState.isEvaluating = true;
        AppState.streamingResults = [];
        
        // Show progress section
        elements.progressSection.style.display = 'block';
        elements.progressBar.style.width = '0%';
        
        // Show performance metrics if enabled
        if (AppState.config.showPerformanceMetrics) {
            elements.performanceMetrics.style.display = 'block';
            performance.startMonitoring();
        }
        
        try {
            const config = {
                brand_mode: AppState.config.brandMode,
                selected_brand: AppState.config.selectedBrand,
                max_concurrency: AppState.config.maxConcurrency,
                temperature: AppState.config.temperature,
                use_progressive_batching: AppState.config.useProgressiveBatching,
                use_high_performance_api: AppState.config.useHighPerformanceApi,
                enable_caching: AppState.config.enableCaching,
                apply_diagnostics: AppState.config.applyDiagnostics,
                base_url: AppState.config.baseUrl,
                headers: AppState.config.headers
            };
            
            await evaluation.startStreaming(AppState.conversationIds, config);
            
        } catch (error) {
            utils.showNotification(`Evaluation failed: ${error.message}`, 'error');
        } finally {
            AppState.isEvaluating = false;
            if (AppState.config.showPerformanceMetrics) {
                performance.stopMonitoring();
            }
        }
    },
    
    handleTabSwitch(e) {
        const targetTab = e.target.dataset.tab;
        
        // Update tab buttons
        elements.tabButtons.forEach(button => {
            button.classList.remove('active');
        });
        e.target.classList.add('active');
        
        // Update tab contents
        elements.tabContents.forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(targetTab).classList.add('active');
        
        // Load content based on tab
        switch (targetTab) {
            case 'resultsTable':
                results.displayTable();
                break;
            case 'analytics':
                results.displayAnalytics();
                break;
            case 'performance':
                results.displayPerformance();
                break;
            case 'export':
                results.displayExport();
                break;
        }
    }
};

// Evaluation handling with streaming
const evaluation = {
    startTime: null,
    updateInterval: null,
    
    async startStreaming(conversationIds, config) {
        this.startTime = Date.now();
        
        // Initialize progress
        this.updateProgress(0, 0, conversationIds.length);
        
        // Start periodic updates
        this.updateInterval = setInterval(() => {
            this.updateProgress(
                AppState.streamingResults.length / conversationIds.length,
                AppState.streamingResults.length,
                conversationIds.length
            );
        }, 1000);
        
        try {
            // Mock streaming evaluation (replace with actual WebSocket or polling)
            await this.simulateStreaming(conversationIds, config);
            
            // Final update
            this.updateProgress(1, conversationIds.length, conversationIds.length);
            
            // Display final results
            AppState.evaluationResults = AppState.streamingResults;
            AppState.summaryData = this.generateSummary(AppState.streamingResults);
            
            elements.resultsSection.style.display = 'block';
            results.displayTable();
            
            utils.showNotification(`✅