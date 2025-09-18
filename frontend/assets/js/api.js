/**
 * API Client for BusQA LLM Evaluator
 * Handles all API communication with the backend
 */

class APIClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
        this.defaultHeaders = {
            'Content-Type': 'application/json',
        };
    }

    /**
     * Make HTTP request with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: { ...this.defaultHeaders, ...options.headers },
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    }

    /**
     * Health check
     */
    async healthCheck() {
        try {
            const result = await this.request('/health');
            return result.status === 'BusQA LLM API is running';
        } catch (error) {
            return false;
        }
    }

    /**
     * Get available brands
     */
    async getBrands() {
        return await this.request('/configs/brands');
    }

    /**
     * Evaluate single conversation
     */
    async evaluateSingle(conversation, brandId, model = 'gemini-1.5-flash', temperature = 0.2) {
        const payload = {
            conversation: conversation,
            brand_id: brandId,
            model: model,
            temperature: temperature
        };

        return await this.request('/evaluate/single', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    /**
     * Evaluate batch of conversations
     */
    async evaluateBatch(conversations, brandId, maxConcurrency = 10) {
        const payload = {
            conversations: conversations,
            brand_id: brandId,
            max_concurrency: maxConcurrency
        };

        return await this.request('/evaluate/batch', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    /**
     * Stream batch evaluation results
     */
    async evaluateBatchStream(conversations, brandId, maxConcurrency = 10, onProgress = null, onComplete = null, onError = null) {
        const payload = {
            conversations: conversations,
            brand_id: brandId,
            max_concurrency: maxConcurrency
        };

        try {
            const response = await fetch(`${this.baseUrl}/evaluate/batch/stream`, {
                method: 'POST',
                headers: this.defaultHeaders,
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

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
                            if (onProgress) onProgress(data);
                        } catch (e) {
                            console.warn('Failed to parse SSE data:', line);
                        }
                    } else if (line.startsWith('event: summary')) {
                        // Handle summary event
                        continue;
                    } else if (line.startsWith('event: error')) {
                        try {
                            const errorData = JSON.parse(line.slice(6));
                            if (onError) onError(new Error(errorData.message));
                        } catch (e) {
                            if (onError) onError(new Error('Unknown error occurred'));
                        }
                        return;
                    } else if (line.startsWith('event: end')) {
                        if (onComplete) onComplete();
                        return;
                    }
                }
            }
        } catch (error) {
            console.error('Streaming error:', error);
            if (onError) onError(error);
        }
    }

    /**
     * Evaluate from bulk list
     */
    async evaluateBulkList(startDate, endDate, limit, strategy, brandId, maxConcurrency, bearerToken) {
        const payload = {
            start_date: startDate,
            end_date: endDate,
            limit: limit,
            strategy: strategy,
            brand_id: brandId,
            max_concurrency: maxConcurrency,
            bearer_token: bearerToken
        };

        return await this.request('/evaluate/bulk-list', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    /**
     * Run performance benchmark
     */
    async runBenchmark(minConcurrency = 5, maxConcurrency = 30, step = 5, numTasks = 50) {
        const params = new URLSearchParams({
            min_concurrency: minConcurrency,
            max_concurrency: maxConcurrency,
            step: step,
            num_tasks: numTasks
        });

        return await this.request(`/benchmark?${params}`);
    }

    /**
     * Test bearer token
     */
    async testBearerToken(baseUrl, bearerToken) {
        try {
            const response = await fetch(`${baseUrl}/api/config`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${bearerToken}`,
                    'Content-Type': 'application/json'
                }
            });
            return response.ok;
        } catch (error) {
            return false;
        }
    }

    /**
     * Bulk evaluation - fetch and evaluate conversations
     */
    async evaluateBulk(botId, bearerToken, limit, strategy, brandId, maxConcurrency) {
        const formData = new FormData();
        formData.append('bot_id', botId);
        formData.append('bearer_token', bearerToken);
        formData.append('limit', limit);
        formData.append('strategy', strategy);
        formData.append('brand_id', brandId);
        formData.append('max_concurrency', maxConcurrency);

        const response = await fetch(`${this.baseUrl}/evaluate/bulk`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * Bulk evaluation with raw conversations data
     */
    async evaluateBulkWithData(conversations, brandId, maxConcurrency, model) {
        const response = await fetch(`${this.baseUrl}/evaluate/bulk-raw`, {
            method: 'POST',
            headers: this.defaultHeaders,
            body: JSON.stringify({
                conversations: conversations,
                brand_id: brandId,
                max_concurrency: maxConcurrency,
                model: model
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * Bulk evaluation with streaming
     */
    async evaluateBulkWithDataStream(conversations, brandId, maxConcurrency, model) {
        const response = await fetch(`${this.baseUrl}/evaluate/bulk-raw-stream`, {
            method: 'POST',
            headers: this.defaultHeaders,
            body: JSON.stringify({
                conversations: conversations,
                brand_id: brandId,
                max_concurrency: maxConcurrency,
                model: model
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        return response;
    }
}

/**
 * Utility functions for data processing
 */
class DataUtils {
    /**
     * Format conversation data for API
     */
    static formatConversation(conversationId, messages, metadata = {}) {
        return {
            conversation_id: conversationId,
            messages: messages.map(msg => ({
                role: msg.role,
                content: msg.content,
                timestamp: msg.timestamp || new Date().toISOString()
            })),
            metadata: metadata
        };
    }

    /**
     * Parse conversation from text
     */
    static parseConversationFromText(text) {
        const lines = text.trim().split('\n');
        const messages = [];
        let currentRole = null;
        let currentContent = [];

        for (const line of lines) {
            const trimmedLine = line.trim();
            if (!trimmedLine) continue;

            // Check if line starts with role indicator
            if (trimmedLine.match(/^(user|assistant|system):/i)) {
                // Save previous message if exists
                if (currentRole && currentContent.length > 0) {
                    messages.push({
                        role: currentRole,
                        content: currentContent.join('\n').trim()
                    });
                }

                // Start new message
                const roleMatch = trimmedLine.match(/^(user|assistant|system):/i);
                currentRole = roleMatch[1].toLowerCase();
                currentContent = [trimmedLine.replace(/^(user|assistant|system):\s*/i, '')];
            } else {
                // Continue current message
                if (currentRole) {
                    currentContent.push(trimmedLine);
                }
            }
        }

        // Add last message
        if (currentRole && currentContent.length > 0) {
            messages.push({
                role: currentRole,
                content: currentContent.join('\n').trim()
            });
        }

        return messages;
    }

    /**
     * Format file size
     */
    static formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Format duration
     */
    static formatDuration(seconds) {
        if (seconds < 60) {
            return `${seconds.toFixed(1)}s`;
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
     * Calculate throughput
     */
    static calculateThroughput(completed, total, elapsedTime) {
        if (elapsedTime === 0) return 0;
        return (completed / elapsedTime).toFixed(2);
    }

    /**
     * Generate unique ID
     */
    static generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
}

/**
 * Event emitter for real-time updates
 */
class EventEmitter {
    constructor() {
        this.events = {};
    }

    on(event, callback) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
    }

    off(event, callback) {
        if (this.events[event]) {
            this.events[event] = this.events[event].filter(cb => cb !== callback);
        }
    }

    emit(event, data) {
        if (this.events[event]) {
            this.events[event].forEach(callback => callback(data));
        }
    }
}

// Export for use in other modules
window.APIClient = APIClient;
window.DataUtils = DataUtils;
window.EventEmitter = EventEmitter;
