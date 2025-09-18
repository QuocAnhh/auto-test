/**
 * Performance Monitor Component
 * Handles real-time performance metrics and monitoring
 */

class PerformanceMonitor {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.metrics = {
            startTime: null,
            endTime: null,
            totalConversations: 0,
            completedConversations: 0,
            failedConversations: 0,
            throughput: 0,
            averageProcessingTime: 0,
            maxConcurrency: 0,
            currentConcurrency: 0,
            memoryUsage: 0,
            cpuUsage: 0
        };
        this.updateInterval = null;
        this.isMonitoring = false;
    }

    /**
     * Initialize performance monitor
     */
    init() {
        this.render();
    }

    /**
     * Start monitoring
     */
    startMonitoring(config) {
        this.metrics = {
            ...this.metrics,
            startTime: Date.now(),
            totalConversations: config.totalConversations || 0,
            maxConcurrency: config.maxConcurrency || 10,
            completedConversations: 0,
            failedConversations: 0
        };
        
        this.isMonitoring = true;
        this.startUpdateInterval();
        this.render();
    }

    /**
     * Stop monitoring
     */
    stopMonitoring() {
        this.isMonitoring = false;
        this.metrics.endTime = Date.now();
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        
        // Destroy charts before re-rendering
        if (this.performanceChart) {
            this.performanceChart.destroy();
            this.performanceChart = null;
        }
        
        this.render();
    }

    /**
     * Update metrics
     */
    updateMetrics(update) {
        this.metrics = { ...this.metrics, ...update };
        this.calculateDerivedMetrics();
        this.render();
    }

    /**
     * Calculate derived metrics
     */
    calculateDerivedMetrics() {
        const elapsed = this.metrics.endTime ? 
            (this.metrics.endTime - this.metrics.startTime) / 1000 :
            (Date.now() - this.metrics.startTime) / 1000;

        if (elapsed > 0) {
            this.metrics.throughput = this.metrics.completedConversations / elapsed;
        }

        if (this.metrics.completedConversations > 0) {
            this.metrics.averageProcessingTime = this.metrics.totalProcessingTime / this.metrics.completedConversations;
        }
    }

    /**
     * Render performance dashboard
     */
    render() {
        this.container.innerHTML = `
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <div class="h2 text-primary">${this.metrics.completedConversations}</div>
                            <div class="text-muted">Completed</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <div class="h2 text-success">${this.metrics.throughput.toFixed(2)}</div>
                            <div class="text-muted">Throughput (conv/s)</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <div class="h2 text-info">${this.metrics.averageProcessingTime.toFixed(2)}s</div>
                            <div class="text-muted">Avg Processing Time</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <div class="h2 text-warning">${this.metrics.currentConcurrency}</div>
                            <div class="text-muted">Current Concurrency</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-speedometer2"></i> Real-time Performance</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="performanceMonitorChart"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-cpu"></i> System Resources</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <div class="d-flex justify-content-between">
                                    <span>CPU Usage</span>
                                    <span>${this.metrics.cpuUsage.toFixed(1)}%</span>
                                </div>
                                <div class="progress">
                                    <div class="progress-bar bg-info" style="width: ${this.metrics.cpuUsage}%"></div>
                                </div>
                            </div>
                            <div class="mb-3">
                                <div class="d-flex justify-content-between">
                                    <span>Memory Usage</span>
                                    <span>${this.metrics.memoryUsage.toFixed(1)}%</span>
                                </div>
                                <div class="progress">
                                    <div class="progress-bar bg-warning" style="width: ${this.metrics.memoryUsage}%"></div>
                                </div>
                            </div>
                            <div class="mb-3">
                                <div class="d-flex justify-content-between">
                                    <span>Concurrency</span>
                                    <span>${this.metrics.currentConcurrency}/${this.metrics.maxConcurrency}</span>
                                </div>
                                <div class="progress">
                                    <div class="progress-bar bg-success" style="width: ${(this.metrics.currentConcurrency / this.metrics.maxConcurrency) * 100}%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-graph-up"></i> Performance Timeline</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="timelineChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            ${this.renderConfiguration()}
            ${this.renderRecommendations()}
        `;

        // Initialize charts after DOM is updated
        setTimeout(() => {
            this.initializeCharts();
        }, 100);
    }

    /**
     * Render configuration section
     */
    renderConfiguration() {
        return `
            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-gear"></i> Configuration Used</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <h6>Processing Settings</h6>
                                    <ul class="list-unstyled">
                                        <li><strong>Max Concurrency:</strong> ${this.metrics.maxConcurrency}</li>
                                        <li><strong>Total Conversations:</strong> ${this.metrics.totalConversations}</li>
                                        <li><strong>Model:</strong> Gemini 1.5 Flash</li>
                                        <li><strong>Temperature:</strong> 0.2</li>
                                    </ul>
                                </div>
                                <div class="col-md-6">
                                    <h6>Performance Features</h6>
                                    <ul class="list-unstyled">
                                        <li><strong>High-Performance API:</strong> <span class="badge bg-success">Enabled</span></li>
                                        <li><strong>Redis Caching:</strong> <span class="badge bg-warning">Disabled</span></li>
                                        <li><strong>API Rate Limit:</strong> 100 req/s</li>
                                        <li><strong>Connection Pooling:</strong> <span class="badge bg-success">Enabled</span></li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render recommendations section
     */
    renderRecommendations() {
        const recommendations = this.generateRecommendations();
        
        if (recommendations.length === 0) return '';

        return `
            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-lightbulb"></i> Performance Recommendations</h5>
                        </div>
                        <div class="card-body">
                            ${recommendations.map(rec => `
                                <div class="alert ${rec.type} alert-dismissible fade show">
                                    <i class="bi ${rec.icon}"></i>
                                    <strong>${rec.title}:</strong> ${rec.message}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Generate performance recommendations
     */
    generateRecommendations() {
        const recommendations = [];

        if (this.metrics.throughput < 10) {
            recommendations.push({
                type: 'alert-warning',
                icon: 'bi-exclamation-triangle',
                title: 'Low Throughput',
                message: 'Consider increasing max concurrency (try 25-30) or enabling Redis caching for better performance.'
            });
        }

        if (this.metrics.cpuUsage > 80) {
            recommendations.push({
                type: 'alert-danger',
                icon: 'bi-cpu',
                title: 'High CPU Usage',
                message: 'CPU usage is high. Consider reducing concurrency or optimizing the processing pipeline.'
            });
        }

        if (this.metrics.memoryUsage > 90) {
            recommendations.push({
                type: 'alert-danger',
                icon: 'bi-memory',
                title: 'High Memory Usage',
                message: 'Memory usage is very high. Consider reducing batch size or enabling garbage collection.'
            });
        }

        if (this.metrics.throughput > 20) {
            recommendations.push({
                type: 'alert-success',
                icon: 'bi-check-circle',
                title: 'Excellent Performance',
                message: 'Your configuration is well-optimized for the current workload.'
            });
        }

        if (this.metrics.totalConversations > 50) {
            recommendations.push({
                type: 'alert-info',
                icon: 'bi-info-circle',
                title: 'Large Batch Processing',
                message: 'For large batches, consider enabling Redis caching and monitoring system resources closely.'
            });
        }

        return recommendations;
    }

    /**
     * Initialize performance charts
     */
    initializeCharts() {
        this.createPerformanceChart();
        this.createTimelineChart();
    }

    /**
     * Create real-time performance chart
     */
    createPerformanceChart() {
        const ctx = document.getElementById('performanceMonitorChart');
        if (!ctx) return;

        // Destroy existing chart if it exists
        if (this.performanceChart) {
            this.performanceChart.destroy();
        }

        // Mock data for demonstration
        const data = {
            labels: ['0s', '10s', '20s', '30s', '40s', '50s'],
            datasets: [{
                label: 'Throughput (conv/s)',
                data: [0, 5, 12, 18, 22, 25],
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.1
            }, {
                label: 'Concurrency',
                data: [0, 3, 8, 12, 15, 18],
                borderColor: 'rgb(255, 99, 132)',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                tension: 0.1
            }]
        };

        this.performanceChart = new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Real-time Performance Metrics'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    /**
     * Create timeline chart
     */
    createTimelineChart() {
        const ctx = document.getElementById('timelineChart');
        if (!ctx) return;

        // Mock timeline data
        const data = {
            labels: ['Start', '25%', '50%', '75%', 'Complete'],
            datasets: [{
                label: 'Completed Conversations',
                data: [0, 25, 50, 75, 100],
                borderColor: 'rgb(54, 162, 235)',
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                fill: true
            }, {
                label: 'Processing Time (s)',
                data: [0, 15, 30, 45, 60],
                borderColor: 'rgb(255, 159, 64)',
                backgroundColor: 'rgba(255, 159, 64, 0.2)',
                yAxisID: 'y1'
            }]
        };

        // Destroy existing chart if it exists
        if (this.timelineChart) {
            this.timelineChart.destroy();
        }

        this.timelineChart = new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Processing Timeline'
                    }
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Conversations'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Time (seconds)'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                }
            }
        });
    }

    /**
     * Start update interval
     */
    startUpdateInterval() {
        this.updateInterval = setInterval(() => {
            if (this.isMonitoring) {
                this.updateSystemMetrics();
                this.render();
            }
        }, 1000);
    }

    /**
     * Update system metrics (mock implementation)
     */
    updateSystemMetrics() {
        // Mock system metrics - in real implementation, these would come from the backend
        this.metrics.cpuUsage = Math.random() * 100;
        this.metrics.memoryUsage = Math.random() * 100;
        this.metrics.currentConcurrency = Math.floor(Math.random() * this.metrics.maxConcurrency);
    }

    /**
     * Get performance summary
     */
    getPerformanceSummary() {
        return {
            totalTime: this.metrics.endTime ? 
                (this.metrics.endTime - this.metrics.startTime) / 1000 : 0,
            throughput: this.metrics.throughput,
            averageProcessingTime: this.metrics.averageProcessingTime,
            successRate: this.metrics.totalConversations > 0 ? 
                (this.metrics.completedConversations / this.metrics.totalConversations) * 100 : 0,
            efficiency: this.metrics.throughput > 0 ? 
                (this.metrics.completedConversations / this.metrics.totalConversations) * 100 : 0
        };
    }
}

// Export for global use
window.PerformanceMonitor = PerformanceMonitor;
