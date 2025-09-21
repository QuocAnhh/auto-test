/**
 * Main Application for BusQA LLM Evaluator
 * Handles UI interactions and application state
 */

class BusQAApp {
    constructor() {
        console.log('BusQAApp constructor called');
        console.log('APIClient available:', typeof APIClient);
        console.log('APIClient methods:', APIClient ? Object.getOwnPropertyNames(APIClient.prototype) : 'undefined');
        
        this.apiClient = new APIClient();
        console.log('APIClient instance created:', this.apiClient);
        console.log('evaluateBulk method:', typeof this.apiClient.evaluateBulk);
        
        this.eventEmitter = new EventEmitter();
        this.currentResults = null;
        this.currentSummary = null;
        this.isEvaluating = false;
        this.currentStream = null;
        
        // Initialize components
        this.resultsTable = null;
        this.analyticsDashboard = null;
        this.performanceMonitor = null;
        this.exportManager = null;
        this.inputMethods = null;
        this.streamingManager = null;
        this.progressTracker = null;
        this.streamingResults = null;
        this.errorHandler = null;
        this.loadingStates = null;
        this.performanceOptimizer = null;
        
        this.init();
    }

    /**
     * Initialize the application
     */
    async init() {
        this.setupEventListeners();
        this.setupFormControls();
        await this.loadBrands();
        await this.checkAPIStatus();
        this.setupTabNavigation();
        this.initializeComponents();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Navigation tabs
        document.querySelectorAll('[data-tab]').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchTab(tab.dataset.tab);
            });
        });

        // Form controls
        document.getElementById('temperature').addEventListener('input', (e) => {
            document.getElementById('tempValue').textContent = e.target.value;
        });

        document.getElementById('maxConcurrency').addEventListener('input', (e) => {
            document.getElementById('concurrencyValue').textContent = e.target.value;
        });

        // Action buttons
        document.getElementById('evaluateBtn').addEventListener('click', () => {
            this.startEvaluation();
        });

        document.getElementById('stopBtn').addEventListener('click', () => {
            this.stopEvaluation();
        });

        document.getElementById('refreshResults').addEventListener('click', () => {
            this.refreshResults();
        });

        document.getElementById('cancelEvaluation').addEventListener('click', () => {
            this.stopEvaluation();
        });

        // Input method changes
        document.querySelectorAll('input[name="inputMethod"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.updateInputMethod(radio.value);
            });
        });

        // Tab navigation
        document.querySelectorAll('.nav-link[data-tab]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const tabName = link.getAttribute('data-tab');
                this.switchTab(tabName);
            });
        });
    }

    /**
     * Setup form controls
     */
    setupFormControls() {
        // Initialize range values
        document.getElementById('tempValue').textContent = document.getElementById('temperature').value;
        document.getElementById('concurrencyValue').textContent = document.getElementById('maxConcurrency').value;
    }

    /**
     * Setup tab navigation
     */
    setupTabNavigation() {
        // Hide all tab panes
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });

        // Show results tab by default
        this.switchTab('results');
    }

    /**
     * Switch to specific tab
     */
    switchTab(tabName) {
        // Update navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        // Update content
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`).classList.add('active');

        // Load tab-specific content
        this.loadTabContent(tabName);
        
        // Update tab content with current data
        this.updateCurrentTabContent();
    }

    /**
     * Get current active tab
     */
    getCurrentActiveTab() {
        const activeLink = document.querySelector('.nav-link.active');
        return activeLink ? activeLink.getAttribute('data-tab') : 'results';
    }

    /**
     * Update current tab content with latest data
     */
    updateCurrentTabContent() {
        const currentTab = this.getCurrentActiveTab();
        
        if (this.currentResults) {
            if (currentTab === 'results' && this.resultsTable) {
                this.resultsTable.setData(this.currentResults);
            }
            
            if (currentTab === 'analytics' && this.analyticsDashboard) {
                this.analyticsDashboard.setData({
                    results: this.currentResults,
                    summary: this.currentSummary,
                    insights: this.currentSummary?.insights || []
                });
            }
            
            if (currentTab === 'export' && this.exportManager) {
                this.exportManager.setData(this.currentResults);
            }
            
            if (currentTab === 'prompt-suggestions' && this.promptSuggestions) {
                // Enable analyze button if we have results
                const analyzeBtn = document.getElementById('analyzePromptBtn');
                if (analyzeBtn) {
                    analyzeBtn.disabled = false;
                }
            }
        }
    }

    /**
     * Initialize components
     */
    initializeComponents() {
        this.resultsTable = new ResultsTable('resultsTable');
        this.analyticsDashboard = new AnalyticsDashboard('analyticsContent');
        this.performanceMonitor = new PerformanceMonitor('performanceContent');
        this.exportManager = new ExportManager('exportContent');
        this.inputMethods = new InputMethods('inputMethodsContainer');
        this.streamingManager = new StreamingManager();
        this.progressTracker = new ProgressTracker('progressTracker');
        this.streamingResults = new StreamingResults('streamingResults');
        this.errorHandler = new ErrorHandler();
        this.loadingStates = new LoadingStates();
        this.performanceOptimizer = new PerformanceOptimizer();
        this.promptSuggestions = new PromptSuggestions('promptSuggestionsContent');
        
        // Expose globally for onclick handlers
        window.errorHandler = this.errorHandler;
        window.resultsTable = this.resultsTable;
        window.promptSuggestions = this.promptSuggestions;
        
        // Add event listeners
        window.addEventListener('viewDetails', (event) => {
            this.showDetailsModal(event.detail.conversationId, event.detail.data);
        });
        
        this.resultsTable.init();
        this.analyticsDashboard.init();
        this.performanceMonitor.init();
        this.exportManager.init();
        this.inputMethods.init();
        this.promptSuggestions.init();
        this.progressTracker.render();
        this.streamingResults.render();
    }

    /**
     * Load content for specific tab
     */
    loadTabContent(tabName) {
        switch (tabName) {
            case 'results':
                this.loadResultsTab();
                break;
            case 'analytics':
                this.loadAnalyticsTab();
                break;
            case 'performance':
                this.loadPerformanceTab();
                break;
            case 'export':
                this.loadExportTab();
                break;
            case 'prompt-suggestions':
                this.loadPromptSuggestionsTab();
                break;
        }
    }

    /**
     * Check API status
     */
    async checkAPIStatus() {
        try {
            const isHealthy = await this.apiClient.healthCheck();
            const statusElement = document.getElementById('api-status');
            
            if (isHealthy) {
                statusElement.textContent = 'API Connected';
                statusElement.className = 'badge bg-success';
            } else {
                statusElement.textContent = 'API Disconnected';
                statusElement.className = 'badge bg-danger';
            }
        } catch (error) {
            console.error('API health check failed:', error);
            const statusElement = document.getElementById('api-status');
            statusElement.textContent = 'API Error';
            statusElement.className = 'badge bg-danger';
        }
    }

    /**
     * Load available brands
     */
    async loadBrands() {
        try {
            const response = await this.apiClient.getBrands();
            const brandSelect = document.getElementById('brandSelect');
            
            brandSelect.innerHTML = '<option value="">Select a brand...</option>';
            response.brands.forEach(brand => {
                const option = document.createElement('option');
                option.value = brand;
                option.textContent = brand;
                brandSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Failed to load brands:', error);
            document.getElementById('brandSelect').innerHTML = '<option value="">Error loading brands</option>';
        }
    }

    /**
     * Update input method UI
     */
    updateInputMethod(method) {
        // This will be implemented when we add the input components
        console.log('Input method changed to:', method);
    }

    /**
     * Start evaluation
     */
    async startEvaluation() {
        if (this.isEvaluating) return;

        const brandId = document.getElementById('brandSelect').value;
        if (!brandId) {
            this.showAlert('Please select a brand', 'warning');
            return;
        }

        // Get configuration
        const maxConcurrency = parseInt(document.getElementById('maxConcurrency').value);
        const model = document.getElementById('modelSelect').value;
        const temperature = parseFloat(document.getElementById('temperature').value);

        // Check if using bulk evaluation
        const inputMethod = this.inputMethods.getCurrentMethod();
        if (inputMethod === 'bulk') {
            // Check if conversations are already fetched
            const conversations = this.inputMethods.getConversations();
            console.log('Bulk method - conversations:', conversations);
            console.log('Bulk method - conversations length:', conversations ? conversations.length : 'undefined');
            
            if (conversations && conversations.length > 0) {
                await this.startBulkEvaluationWithData(conversations, brandId, maxConcurrency, model);
            } else {
                this.showAlert('Please fetch conversations first using "Fetch Conversations" button', 'warning');
            }
            return;
        }

        // Get conversations from input methods
        const conversations = this.inputMethods.getConversations();
        if (!conversations || conversations.length === 0) {
            this.showAlert('Please provide conversation data', 'warning');
            return;
        }

        this.isEvaluating = true;
        this.updateEvaluationUI(true);

        try {
            // Show progress card
            this.showProgressCard();

            // Initialize results array
            this.currentResults = [];

            // Start progress tracking
            this.progressTracker.start(conversations.length);
            this.streamingResults.start();

            // Start performance monitoring
            this.performanceMonitor.startMonitoring({
                totalConversations: conversations.length,
                maxConcurrency: maxConcurrency
            });

            // Start streaming evaluation
            await this.apiClient.evaluateBatchStream(
                conversations,
                brandId,
                maxConcurrency,
                (result) => this.handleEvaluationProgress(result),
                () => this.handleEvaluationComplete(),
                (error) => this.handleEvaluationError(error)
            );
        } catch (error) {
            this.handleEvaluationError(error);
        }
    }

    async startBulkEvaluationWithData(conversations, brandId, maxConcurrency, model) {
        // Debug: Check if apiClient has evaluateBulk method
        if (!this.apiClient || typeof this.apiClient.evaluateBulk !== 'function') {
            console.error('APIClient or evaluateBulk method not available:', this.apiClient);
            this.showAlert('API Client not properly initialized', 'error');
            return;
        }

        this.isEvaluating = true;
        this.updateEvaluationUI(true);

        try {
            // Show progress card
            this.showProgressCard();

            // Don't reset currentResults - preserve existing data
            // currentResults will be managed by handleEvaluationProgress

            // Start progress tracking
            this.progressTracker.start(conversations.length);
            this.streamingResults.start();

            // Start performance monitoring
            this.performanceMonitor.startMonitoring({
                totalConversations: conversations.length,
                maxConcurrency: maxConcurrency
            });

            // Start streaming evaluation for bulk data
            console.log('Starting streaming evaluation for bulk conversations:', { conversations: conversations.length, brandId, maxConcurrency, model });
            
            const response = await this.apiClient.evaluateBulkWithDataStream(
                conversations,
                brandId,
                maxConcurrency,
                model
            );

            // Process streaming response
            const decoder = new TextDecoder();
            let buffer = '';
            
            // Create reader once and reuse it
            const reader = response.body.getReader();

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Keep incomplete line in buffer

                    for (const line of lines) {
                        if (line.trim() === '') continue;
                        
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                console.log('📡 Raw SSE data:', data);
                                
                                // Handle different data types from backend
                                if (data.type === 'result' && data.data) {
                                    // Backend sends: {"type": "result", "data": actualResult}
                                    this.handleEvaluationProgress(data.data);
                                } else if (data.type === 'keepalive') {
                                    // Keep-alive message, ignore
                                    continue;
                                } else if (data.type === 'summary') {
                                    // Summary data, store for later
                                    this.currentSummary = data.data;
                                    continue;
                                } else if (data.type === 'complete') {
                                    // Evaluation complete
                                    this.handleEvaluationComplete();
                                    return;
                                } else if (data.type === 'error') {
                                    // Error occurred
                                    this.handleEvaluationError(new Error(data.data?.error || 'Unknown error'));
                                    return;
                                } else {
                                    // Direct result data (fallback)
                                    this.handleEvaluationProgress(data);
                                }
                            } catch (e) {
                                console.warn('Failed to parse SSE data:', line);
                            }
                        } else if (line.startsWith('event: summary')) {
                            // Handle summary event
                            continue;
                        } else if (line.startsWith('event: error')) {
                            try {
                                const errorData = JSON.parse(line.slice(6));
                                this.handleEvaluationError(new Error(errorData.message));
                            } catch (e) {
                                this.handleEvaluationError(new Error('Unknown error occurred'));
                            }
                            return;
                        } else if (line.startsWith('event: end')) {
                            this.handleEvaluationComplete();
                            return;
                        }
                    }
                }
            } finally {
                // Release the reader
                reader.releaseLock();
            }

        } catch (error) {
            this.handleEvaluationError(error);
        }
    }

    /**
     * Stop evaluation
     */
    stopEvaluation() {
        if (this.currentStream) {
            this.currentStream.cancel();
            this.currentStream = null;
        }
        
        this.isEvaluating = false;
        this.updateEvaluationUI(false);
        this.hideProgressCard();
    }

    /**
     * Get sample conversations for testing
     */
    getSampleConversations() {
        return [
            {
                conversation_id: 'sample-1',
                messages: [
                    { role: 'user', content: 'Hello, I need help with my booking' },
                    { role: 'assistant', content: 'Hello! I\'d be happy to help you with your booking. Could you please provide your booking reference number?' }
                ],
                metadata: { bot_id: 'test-bot' }
            },
            {
                conversation_id: 'sample-2',
                messages: [
                    { role: 'user', content: 'What are your cancellation policies?' },
                    { role: 'assistant', content: 'Our cancellation policy allows free cancellation up to 24 hours before departure. Would you like me to check your specific booking?' }
                ],
                metadata: { bot_id: 'test-bot' }
            }
        ];
    }

    /**
     * Handle evaluation progress
     */
    handleEvaluationProgress(result) {
        console.log('🔄 Evaluation progress received:', result);
        console.log('📊 Current results count BEFORE:', this.currentResults ? this.currentResults.length : 0);
        
        // Log the actual result structure
        console.log('🔍 Result structure:', {
            conversation_id: result.conversation_id,
            id: result.id,
            keys: Object.keys(result)
        });
        
        // Ensure conversation_id exists (but don't generate fake ones)
        if (!result.conversation_id) {
            console.warn('⚠️ Result missing conversation_id, checking other fields...');
            // Try to find conversation_id in nested data
            if (result.data && result.data.conversation_id) {
                result.conversation_id = result.data.conversation_id;
                console.log('✅ Found conversation_id in result.data:', result.conversation_id);
            } else if (result.id) {
                result.conversation_id = result.id;
                console.log('✅ Using result.id as conversation_id:', result.conversation_id);
            } else {
                console.error('❌ No conversation_id found anywhere in result!');
                result.conversation_id = `unknown-${Date.now()}`;
            }
        }
        
        console.log('🔍 Result conversation_id:', result.conversation_id);
        
        // Update progress tracker
        this.progressTracker.update({
            completed: this.progressTracker.progress.completed + 1,
            current: result.conversation_id
        });
        
        // Add to streaming results
        this.streamingResults.addResult(result);
        
        // Update performance monitor
        this.performanceMonitor.updateMetrics({
            completedConversations: this.progressTracker.progress.completed,
            currentConcurrency: Math.min(
                this.progressTracker.progress.completed,
                parseInt(document.getElementById('maxConcurrency').value)
            )
        });
        
        // Ensure currentResults exists
        if (!this.currentResults) {
            this.currentResults = [];
        }
        
        // Simple logic: find and update existing result, or add new one
        const existingIndex = this.currentResults.findIndex(r => r.conversation_id === result.conversation_id);
        
        if (existingIndex !== -1) {
            // Update existing result with completed data
            this.currentResults[existingIndex] = {
                ...this.currentResults[existingIndex],
                ...result,
                status: 'completed',
                timestamp: Date.now()
            };
        } else {
            // Add new completed result
            this.currentResults.push({
                ...result,
                status: 'completed',
                timestamp: Date.now()
            });
        }
        
        console.log('📊 Total results:', this.currentResults.length);
        console.log('🎯 Updating results table with', this.currentResults.length, 'results');
        
        // Update only the currently active tab
        const currentTab = this.getCurrentActiveTab();
        console.log('🎯 Current active tab:', currentTab);
        
        if (currentTab === 'results' && this.resultsTable) {
            this.resultsTable.setData(this.currentResults);
            console.log('✅ Results table updated');
        } else if (currentTab === 'analytics' && this.analyticsDashboard) {
            this.analyticsDashboard.setData({
                results: this.currentResults,
                summary: this.currentSummary,
                insights: this.currentSummary?.insights || []
            });
            console.log('✅ Analytics dashboard updated');
        } else if (currentTab === 'export' && this.exportManager) {
            this.exportManager.setData(this.currentResults);
            console.log('✅ Export manager updated');
        } else {
            console.warn('⚠️ No component available for tab:', currentTab);
        }
    }

    /**
     * Handle evaluation completion
     */
    handleEvaluationComplete() {
        console.log('Evaluation completed');
        this.isEvaluating = false;
        this.updateEvaluationUI(false);
        this.hideProgressCard();
        this.showAlert('Evaluation completed successfully!', 'success');
        
        // Stop tracking and monitoring
        this.progressTracker.stop();
        this.streamingResults.stop();
        this.performanceMonitor.stopMonitoring();
        
        // Update only the currently active tab
        const currentTab = this.getCurrentActiveTab();
        
        if (this.currentResults) {
            if (currentTab === 'results' && this.resultsTable) {
                this.resultsTable.setData(this.currentResults);
            }
            
            if (currentTab === 'analytics' && this.analyticsDashboard) {
                this.analyticsDashboard.setData({
                    results: this.currentResults,
                    summary: this.currentSummary,
                    insights: this.currentSummary?.insights || []
                });
            }
            
            if (currentTab === 'export' && this.exportManager) {
                this.exportManager.setData(this.currentResults);
            }
        }
    }

    /**
     * Handle evaluation error
     */
    handleEvaluationError(error) {
        console.error('Evaluation error:', error);
        this.isEvaluating = false;
        this.updateEvaluationUI(false);
        this.hideProgressCard();
        this.showAlert(`Evaluation failed: ${error.message}`, 'danger');
    }

    /**
     * Update evaluation UI state
     */
    updateEvaluationUI(isEvaluating) {
        const evaluateBtn = document.getElementById('evaluateBtn');
        const stopBtn = document.getElementById('stopBtn');

        evaluateBtn.disabled = isEvaluating;
        stopBtn.disabled = !isEvaluating;

        if (isEvaluating) {
            evaluateBtn.innerHTML = '<i class="bi bi-play-circle"></i> Evaluating...';
        } else {
            evaluateBtn.innerHTML = '<i class="bi bi-play-circle"></i> Start Evaluation';
        }
    }

    /**
     * Show progress card
     */
    showProgressCard() {
        const progressCard = document.getElementById('evaluationProgress');
        if (progressCard) {
            progressCard.style.display = 'block';
        }
    }

    /**
     * Hide progress card
     */
    hideProgressCard() {
        const progressCard = document.getElementById('evaluationProgress');
        if (progressCard) {
            progressCard.style.display = 'none';
        }
    }

    /**
     * Update progress display
     */
    updateProgress(result) {
        // This will be implemented when we have actual progress data
        console.log('Updating progress:', result);
    }

    /**
     * Load results tab content
     */
    loadResultsTab() {
        if (this.resultsTable) {
            this.resultsTable.render();
        }
    }

    /**
     * Load analytics tab content
     */
    loadAnalyticsTab() {
        if (this.analyticsDashboard) {
            this.analyticsDashboard.render();
        }
    }

    /**
     * Load performance tab content
     */
    loadPerformanceTab() {
        if (this.performanceMonitor) {
            this.performanceMonitor.render();
        }
    }

    /**
     * Load export tab content
     */
    loadExportTab() {
        if (this.exportManager) {
            this.exportManager.render();
        }
    }

    /**
     * Load prompt suggestions tab content
     */
    loadPromptSuggestionsTab() {
        if (this.promptSuggestions) {
            this.promptSuggestions.render();
            
            // Enable analyze button if we have evaluation results
            const analyzeBtn = document.getElementById('analyzePromptBtn');
            if (analyzeBtn && this.currentResults && this.currentResults.length > 0) {
                analyzeBtn.disabled = false;
                analyzeBtn.addEventListener('click', () => {
                    this.analyzePromptSuggestions();
                });
            }
        }
    }

    /**
     * Analyze prompt suggestions
     */
    async analyzePromptSuggestions() {
        if (!this.currentResults || this.currentResults.length === 0) {
            this.showAlert('No evaluation results available for analysis', 'warning');
            return;
        }

        const brandId = document.getElementById('brandSelect').value;
        if (!brandId) {
            this.showAlert('Please select a brand first', 'warning');
            return;
        }

        try {
            // Create evaluation summary from current results
            const summary = this.createEvaluationSummary(this.currentResults);
            
            // Load prompt suggestions
            await this.promptSuggestions.loadSuggestions(brandId, summary);
            
            this.showAlert('Prompt analysis completed!', 'success');
        } catch (error) {
            console.error('Error analyzing prompt suggestions:', error);
            this.showAlert(`Error analyzing prompt: ${error.message}`, 'danger');
        }
    }

    /**
     * Create evaluation summary from results
     */
    createEvaluationSummary(results) {
        const successfulResults = results.filter(r => !r.error);
        
        if (successfulResults.length === 0) {
            return {
                count: results.length,
                successful_count: 0,
                error_count: results.length,
                avg_total_score: 0,
                criteria_avg: {},
                diagnostics_top: [],
                flow_distribution: {},
                policy_violation_rate: 0
            };
        }

        // Calculate average scores
        const totalScores = successfulResults.map(r => r.result?.total_score || 0);
        const avgTotalScore = totalScores.reduce((a, b) => a + b, 0) / totalScores.length;

        // Calculate criteria averages
        const criteriaScores = {};
        successfulResults.forEach(result => {
            if (result.result?.criteria) {
                Object.entries(result.result.criteria).forEach(([criterion, details]) => {
                    if (!criteriaScores[criterion]) {
                        criteriaScores[criterion] = [];
                    }
                    criteriaScores[criterion].push(details.score || 0);
                });
            }
        });

        const criteriaAvg = {};
        Object.entries(criteriaScores).forEach(([criterion, scores]) => {
            criteriaAvg[criterion] = scores.reduce((a, b) => a + b, 0) / scores.length;
        });

        // Flow distribution
        const flows = successfulResults.map(r => r.result?.detected_flow || 'unknown');
        const flowDistribution = {};
        flows.forEach(flow => {
            flowDistribution[flow] = (flowDistribution[flow] || 0) + 1;
        });

        // Policy violations
        const policyViolations = successfulResults.map(r => r.metrics?.policy_violations || 0);
        const policyViolationRate = policyViolations.filter(v => v > 0).length / policyViolations.length;

        return {
            count: results.length,
            successful_count: successfulResults.length,
            error_count: results.length - successfulResults.length,
            avg_total_score: avgTotalScore,
            criteria_avg: criteriaAvg,
            diagnostics_top: [],
            flow_distribution: flowDistribution,
            policy_violation_rate: policyViolationRate
        };
    }

    /**
     * Refresh results
     */
    refreshResults() {
        this.loadResultsTab();
        this.showAlert('Results refreshed', 'info');
    }

    /**
     * Show alert message
     */
    showAlert(message, type = 'info') {
        // Create alert element
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Insert at top of main content
        const mainContent = document.querySelector('.col-md-9');
        mainContent.insertBefore(alertDiv, mainContent.firstChild);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }

    /**
     * Show details modal
     */
    showDetailsModal(conversationId, data) {
        // Create modal if it doesn't exist
        let modal = document.getElementById('detailsModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'detailsModal';
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Conversation Details</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body" id="detailsModalBody">
                            <!-- Content will be populated here -->
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        // Populate modal content
        const modalBody = document.getElementById('detailsModalBody');
        if (modalBody && data) {
            modalBody.innerHTML = this.formatDetailsContent(conversationId, data);
        }

        // Show modal
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    /**
     * Get score from data (handle different data structures)
     */
    getScore(data) {
        if (data.total_score !== undefined) {
            return data.total_score;
        }
        if (data.result && data.result.total_score !== undefined) {
            return data.result.total_score;
        }
        return 'N/A';
    }

    /**
     * Format details content for better readability
     */
    formatDetailsContent(conversationId, data) {
        const score = this.getScore(data);
        const result = data.result || data;
        
        // Extract key information
        const criteria = result.criteria || {};
        const diagnostics = result.diagnostics || [];
        const flow = result.flow || 'Unknown';
        const confidence = result.confidence || 'N/A';
        const evaluationTime = result.evaluation_time || 'N/A';
        
        // Format criteria scores
        const criteriaHtml = Object.entries(criteria).map(([key, value]) => `
            <div class="col-md-6 mb-2">
                <div class="d-flex justify-content-between">
                    <span class="fw-medium">${this.formatCriteriaName(key)}:</span>
                    <span class="badge bg-${this.getScoreColor(value)}">${value}/10</span>
                </div>
            </div>
        `).join('');

        // Format diagnostics
        const diagnosticsHtml = diagnostics.length > 0 ? diagnostics.map(diag => `
            <div class="alert alert-warning alert-sm mb-2">
                <i class="fas fa-exclamation-triangle"></i> ${diag}
            </div>
        `).join('') : '<div class="text-muted">No issues detected</div>';

        return `
            <div class="row">
                <div class="col-md-6">
                    <h6><i class="fas fa-comments"></i> Conversation ID</h6>
                    <p class="text-muted">${conversationId}</p>
                </div>
                <div class="col-md-6">
                    <h6><i class="fas fa-star"></i> Total Score</h6>
                    <p class="text-primary fs-4 fw-bold">${score}/10</p>
                </div>
            </div>
            
            <div class="row mt-3">
                <div class="col-md-6">
                    <h6><i class="fas fa-route"></i> Flow</h6>
                    <p class="text-info">${flow}</p>
                </div>
                <div class="col-md-6">
                    <h6><i class="fas fa-clock"></i> Evaluation Time</h6>
                    <p class="text-muted">${evaluationTime}ms</p>
                </div>
            </div>

            <div class="row mt-3">
                <div class="col-12">
                    <h6><i class="fas fa-chart-bar"></i> Criteria Scores</h6>
                    <div class="row">
                        ${criteriaHtml}
                    </div>
                </div>
            </div>

            <div class="row mt-3">
                <div class="col-12">
                    <h6><i class="fas fa-bug"></i> Diagnostics</h6>
                    ${diagnosticsHtml}
                </div>
            </div>

            <div class="row mt-3">
                <div class="col-12">
                    <h6><i class="fas fa-info-circle"></i> Raw Data</h6>
                    <div class="accordion" id="rawDataAccordion">
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#rawDataCollapse">
                                    View Raw JSON Data
                                </button>
                            </h2>
                            <div id="rawDataCollapse" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    <pre class="bg-light p-3 rounded"><code>${JSON.stringify(data, null, 2)}</code></pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Format criteria name for display
     */
    formatCriteriaName(key) {
        const names = {
            'greeting': 'Greeting',
            'understanding': 'Understanding',
            'response_quality': 'Response Quality',
            'problem_solving': 'Problem Solving',
            'closing': 'Closing',
            'empathy': 'Empathy',
            'professionalism': 'Professionalism'
        };
        return names[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    /**
     * Get color class for score
     */
    getScoreColor(score) {
        if (score >= 8) return 'success';
        if (score >= 6) return 'warning';
        return 'danger';
    }
}

// Initialize application when DOM is loaded and all scripts are ready
document.addEventListener('DOMContentLoaded', () => {
    // Wait for all components to be available
    const initApp = () => {
        console.log('Checking components:', {
            APIClient: typeof APIClient,
            StreamingManager: typeof StreamingManager,
            InputMethods: typeof InputMethods
        });
        
        if (typeof APIClient !== 'undefined' && 
            typeof StreamingManager !== 'undefined' && 
            typeof InputMethods !== 'undefined') {
            console.log('All components loaded, initializing BusQAApp...');
            window.busQAApp = new BusQAApp();
        } else {
            console.log('Components not ready, retrying...');
            // Retry after a short delay
            setTimeout(initApp, 100);
        }
    };
    initApp();
});
