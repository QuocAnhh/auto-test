/**
 * Real-time Streaming Component
 * Handles Server-Sent Events (SSE) for real-time updates
 */

class StreamingManager {
    constructor() {
        this.eventSource = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.listeners = new Map();
        this.buffer = [];
        this.isBuffering = false;
    }

    /**
     * Connect to streaming endpoint
     */
    connect(endpoint, options = {}) {
        if (this.isConnected) {
            this.disconnect();
        }

        const {
            onMessage = null,
            onError = null,
            onOpen = null,
            onClose = null,
            autoReconnect = true
        } = options;

        try {
            this.eventSource = new EventSource(endpoint);
            this.setupEventListeners({ onMessage, onError, onOpen, onClose, autoReconnect });
            this.isConnected = true;
            this.reconnectAttempts = 0;
        } catch (error) {
            console.error('Failed to connect to streaming endpoint:', error);
            if (onError) onError(error);
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners({ onMessage, onError, onOpen, onClose, autoReconnect }) {
        if (!this.eventSource) return;

        this.eventSource.onopen = (event) => {
            console.log('Streaming connection opened');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            if (onOpen) onOpen(event);
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data, onMessage);
            } catch (error) {
                console.error('Error parsing streaming message:', error);
                if (onError) onError(error);
            }
        };

        this.eventSource.onerror = (event) => {
            console.error('Streaming connection error:', event);
            this.isConnected = false;
            
            if (onError) onError(event);
            
            if (autoReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.scheduleReconnect({ onMessage, onError, onOpen, onClose, autoReconnect });
            } else if (onClose) {
                onClose(event);
            }
        };

        // Custom event listeners
        this.eventSource.addEventListener('summary', (event) => {
            try {
                const data = JSON.parse(event.data);
                this.emit('summary', data);
            } catch (error) {
                console.error('Error parsing summary event:', error);
            }
        });

        this.eventSource.addEventListener('error', (event) => {
            try {
                const data = JSON.parse(event.data);
                this.emit('error', data);
            } catch (error) {
                console.error('Error parsing error event:', error);
            }
        });

        this.eventSource.addEventListener('end', (event) => {
            this.emit('end', event);
            if (onClose) onClose(event);
        });
    }

    /**
     * Handle incoming message
     */
    handleMessage(data, onMessage) {
        if (this.isBuffering) {
            this.buffer.push(data);
        } else {
            if (onMessage) onMessage(data);
            this.emit('message', data);
        }
    }

    /**
     * Start buffering messages
     */
    startBuffering() {
        this.isBuffering = true;
        this.buffer = [];
    }

    /**
     * Stop buffering and process messages
     */
    stopBuffering() {
        this.isBuffering = false;
        const bufferedMessages = [...this.buffer];
        this.buffer = [];
        return bufferedMessages;
    }

    /**
     * Schedule reconnection
     */
    scheduleReconnect(options) {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);
        
        setTimeout(() => {
            if (!this.isConnected) {
                this.connect(options.endpoint, options);
            }
        }, delay);
    }

    /**
     * Disconnect from streaming
     */
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this.isConnected = false;
        this.buffer = [];
        this.isBuffering = false;
    }

    /**
     * Add event listener
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
    }

    /**
     * Remove event listener
     */
    off(event, callback) {
        if (this.listeners.has(event)) {
            const callbacks = this.listeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    /**
     * Emit event to listeners
     */
    emit(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error('Error in event callback:', error);
                }
            });
        }
    }

    /**
     * Get connection status
     */
    getStatus() {
        return {
            connected: this.isConnected,
            reconnectAttempts: this.reconnectAttempts,
            buffering: this.isBuffering,
            bufferSize: this.buffer.length
        };
    }
}

/**
 * Progress Tracker Component
 * Tracks and displays real-time progress
 */
class ProgressTracker {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.progress = {
            total: 0,
            completed: 0,
            failed: 0,
            current: 0,
            startTime: null,
            endTime: null,
            throughput: 0,
            eta: 0
        };
        this.isTracking = false;
        this.updateInterval = null;
    }

    /**
     * Start progress tracking
     */
    start(total) {
        this.progress = {
            total,
            completed: 0,
            failed: 0,
            current: 0,
            startTime: Date.now(),
            endTime: null,
            throughput: 0,
            eta: 0
        };
        this.isTracking = true;
        this.startUpdateInterval();
        this.render();
    }

    /**
     * Stop progress tracking
     */
    stop() {
        this.isTracking = false;
        this.progress.endTime = Date.now();
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        this.render();
    }

    /**
     * Update progress
     */
    update(update) {
        this.progress = { ...this.progress, ...update };
        this.calculateDerivedMetrics();
        this.render();
    }

    /**
     * Calculate derived metrics
     */
    calculateDerivedMetrics() {
        const elapsed = this.progress.endTime ? 
            (this.progress.endTime - this.progress.startTime) / 1000 :
            (Date.now() - this.progress.startTime) / 1000;

        if (elapsed > 0) {
            this.progress.throughput = this.progress.completed / elapsed;
        }

        if (this.progress.throughput > 0 && this.progress.total > this.progress.completed) {
            const remaining = this.progress.total - this.progress.completed;
            this.progress.eta = remaining / this.progress.throughput;
        }
    }

    /**
     * Start update interval
     */
    startUpdateInterval() {
        this.updateInterval = setInterval(() => {
            if (this.isTracking) {
                this.calculateDerivedMetrics();
                this.render();
            }
        }, 1000);
    }

    /**
     * Render progress display
     */
    render() {
        if (!this.container) return;

        const percentage = this.progress.total > 0 ? 
            (this.progress.completed / this.progress.total) * 100 : 0;

        this.container.innerHTML = `
            <div class="progress mb-3" style="height: 25px;">
                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                     role="progressbar" 
                     style="width: ${percentage}%"
                     aria-valuenow="${percentage}" 
                     aria-valuemin="0" 
                     aria-valuemax="100">
                    ${percentage.toFixed(1)}%
                </div>
            </div>

            <div class="row text-center">
                <div class="col-3">
                    <div class="border rounded p-2">
                        <div class="h5 mb-0 text-primary">${this.progress.completed}</div>
                        <small class="text-muted">Completed</small>
                    </div>
                </div>
                <div class="col-3">
                    <div class="border rounded p-2">
                        <div class="h5 mb-0 text-danger">${this.progress.failed}</div>
                        <small class="text-muted">Failed</small>
                    </div>
                </div>
                <div class="col-3">
                    <div class="border rounded p-2">
                        <div class="h5 mb-0 text-info">${this.progress.throughput.toFixed(2)}</div>
                        <small class="text-muted">conv/s</small>
                    </div>
                </div>
                <div class="col-3">
                    <div class="border rounded p-2">
                        <div class="h5 mb-0 text-warning">${this.formatTime(this.progress.eta)}</div>
                        <small class="text-muted">ETA</small>
                    </div>
                </div>
            </div>

            <div class="mt-3">
                <div class="d-flex justify-content-between">
                    <span>Progress: ${this.progress.completed}/${this.progress.total}</span>
                    <span>Elapsed: ${this.formatTime(this.getElapsedTime())}</span>
                </div>
            </div>
        `;
    }

    /**
     * Get elapsed time
     */
    getElapsedTime() {
        if (this.progress.startTime) {
            return this.progress.endTime ? 
                (this.progress.endTime - this.progress.startTime) / 1000 :
                (Date.now() - this.progress.startTime) / 1000;
        }
        return 0;
    }

    /**
     * Format time duration
     */
    formatTime(seconds) {
        if (seconds < 60) {
            return `${seconds.toFixed(0)}s`;
        } else if (seconds < 3600) {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = Math.floor(seconds % 60);
            return `${minutes}m ${remainingSeconds}s`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return `${hours}h ${minutes}m`;
        }
    }

    /**
     * Get progress summary
     */
    getSummary() {
        return {
            ...this.progress,
            percentage: this.progress.total > 0 ? 
                (this.progress.completed / this.progress.total) * 100 : 0,
            elapsed: this.getElapsedTime(),
            successRate: this.progress.completed > 0 ? 
                ((this.progress.completed - this.progress.failed) / this.progress.completed) * 100 : 0
        };
    }
}

/**
 * Real-time Results Display
 * Shows streaming results as they arrive
 */
class StreamingResults {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.results = [];
        this.isStreaming = false;
        this.autoScroll = true;
    }

    /**
     * Start streaming results
     */
    start() {
        this.results = [];
        this.isStreaming = true;
        this.render();
    }

    /**
     * Stop streaming results
     */
    stop() {
        this.isStreaming = false;
        this.render();
    }

    /**
     * Add result
     */
    addResult(result) {
        this.results.push({
            ...result,
            timestamp: Date.now(),
            id: result.conversation_id || `result-${this.results.length + 1}`
        });
        this.render();
        
        if (this.autoScroll) {
            this.scrollToBottom();
        }
    }

    /**
     * Update result
     */
    updateResult(id, updates) {
        const index = this.results.findIndex(r => r.id === id);
        if (index !== -1) {
            this.results[index] = { ...this.results[index], ...updates };
            this.render();
        }
    }

    /**
     * Render results
     */
    render() {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="streaming-results">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6>Real-time Results</h6>
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="autoScroll" checked>
                        <label class="form-check-label" for="autoScroll">
                            Auto-scroll
                        </label>
                    </div>
                </div>
                
                <div class="results-list" style="max-height: 400px; overflow-y: auto;">
                    ${this.results.map(result => this.renderResult(result)).join('')}
                </div>
                
                ${this.isStreaming ? `
                    <div class="text-center mt-3">
                        <div class="spinner-border spinner-border-sm text-primary" role="status">
                            <span class="visually-hidden">Streaming...</span>
                        </div>
                        <span class="ms-2">Receiving results...</span>
                    </div>
                ` : ''}
            </div>
        `;

        // Setup auto-scroll checkbox
        const autoScrollCheckbox = document.getElementById('autoScroll');
        if (autoScrollCheckbox) {
            autoScrollCheckbox.addEventListener('change', (e) => {
                this.autoScroll = e.target.checked;
            });
        }
    }

    /**
     * Render individual result
     */
    renderResult(result) {
        const scoreColor = this.getScoreColor(result.total_score);
        const statusColor = result.status === 'success' ? 'success' : 'danger';
        
        return `
            <div class="card mb-2 streaming-result" data-id="${result.id}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="card-title">${result.id}</h6>
                            <p class="card-text">
                                <span class="badge ${scoreColor}">${result.total_score?.toFixed(1) || 'N/A'}</span>
                                <span class="badge bg-${statusColor}">${result.status || 'processing'}</span>
                                <small class="text-muted">${new Date(result.timestamp).toLocaleTimeString()}</small>
                            </p>
                        </div>
                        <div>
                            <button class="btn btn-sm btn-outline-primary" onclick="streamingResults.viewDetails('${result.id}')">
                                <i class="bi bi-eye"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Get score color
     */
    getScoreColor(score) {
        if (score >= 80) return 'bg-success';
        if (score >= 60) return 'bg-warning';
        return 'bg-danger';
    }

    /**
     * Scroll to bottom
     */
    scrollToBottom() {
        const resultsList = this.container.querySelector('.results-list');
        if (resultsList) {
            resultsList.scrollTop = resultsList.scrollHeight;
        }
    }

    /**
     * View result details
     */
    viewDetails(id) {
        const result = this.results.find(r => r.id === id);
        if (result) {
            // Emit event for details view
            window.dispatchEvent(new CustomEvent('viewResultDetails', { 
                detail: { result } 
            }));
        }
    }

    /**
     * Get results
     */
    getResults() {
        return this.results;
    }

    /**
     * Clear results
     */
    clear() {
        this.results = [];
        this.render();
    }
}

// Export for global use
window.StreamingManager = StreamingManager;
window.ProgressTracker = ProgressTracker;
window.StreamingResults = StreamingResults;
