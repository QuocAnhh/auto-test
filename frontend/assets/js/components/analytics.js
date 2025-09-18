/**
 * Analytics Dashboard Component
 * Handles charts and analytics visualization
 */

class AnalyticsDashboard {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.charts = {};
        this.data = null;
    }

    /**
     * Initialize analytics dashboard
     */
    init() {
        this.render();
    }

    /**
     * Set analytics data
     */
    setData(data) {
        this.data = data;
        this.destroyCharts();
        this.render();
    }

    /**
     * Destroy existing charts
     */
    destroyCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.charts = {};
    }

    /**
     * Render analytics dashboard
     */
    render() {
        if (!this.data) {
            this.renderEmptyState();
            return;
        }

        this.container.innerHTML = `
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${this.data.summary?.count || 0}</div>
                        <div class="metric-label">Total Conversations</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${this.data.summary?.successful_count || 0}</div>
                        <div class="metric-label">Successful</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${(this.data.summary?.avg_total_score || 0).toFixed(1)}</div>
                        <div class="metric-label">Avg Score</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${((this.data.summary?.policy_violation_rate || 0) * 100).toFixed(1)}%</div>
                        <div class="metric-label">Policy Violations</div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-bar-chart"></i> Score Distribution</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="scoreDistributionChart"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-pie-chart"></i> Flow Distribution</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="flowDistributionChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-graph-up"></i> Average Criteria Scores</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="criteriaScoresChart"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-exclamation-triangle"></i> Top Diagnostic Issues</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="diagnosticIssuesChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-12 mb-4">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-speedometer2"></i> Performance Analysis</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="performanceChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            ${this.renderInsights()}
        `;

        // Initialize charts after DOM is updated
        setTimeout(() => {
            this.initializeCharts();
        }, 100);
    }

    /**
     * Render empty state
     */
    renderEmptyState() {
        this.container.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-bar-chart display-4"></i>
                <h4 class="mt-3">No Analytics Data</h4>
                <p>Run an evaluation to see analytics and insights.</p>
            </div>
        `;
    }

    /**
     * Render insights section
     */
    renderInsights() {
        if (!this.data.insights) return '';

        return `
            <div class="row">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="bi bi-lightbulb"></i> Key Insights</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                ${this.data.insights.map(insight => `
                                    <div class="col-md-6 mb-3">
                                        <div class="alert alert-info">
                                            <i class="bi bi-info-circle"></i>
                                            <strong>${insight.title}:</strong> ${insight.description}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Initialize all charts
     */
    initializeCharts() {
        this.createScoreDistributionChart();
        this.createFlowDistributionChart();
        this.createCriteriaScoresChart();
        this.createDiagnosticIssuesChart();
        this.createPerformanceChart();
    }

    /**
     * Create score distribution chart
     */
    createScoreDistributionChart() {
        const ctx = document.getElementById('scoreDistributionChart');
        if (!ctx) return;

        // Handle different data structures
        let scores = [];
        if (this.data.results) {
            scores = this.data.results.map(r => {
                if (r.total_score !== undefined) return r.total_score;
                if (r.result && r.result.total_score !== undefined) return r.result.total_score;
                return 0;
            });
        } else if (Array.isArray(this.data)) {
            scores = this.data.map(r => {
                if (r.total_score !== undefined) return r.total_score;
                if (r.result && r.result.total_score !== undefined) return r.result.total_score;
                return 0;
            });
        }
        
        const bins = this.createHistogramBins(scores, 0, 100, 10);
        
        this.charts.scoreDistribution = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: bins.map(bin => `${bin.min}-${bin.max}`),
                datasets: [{
                    label: 'Number of Conversations',
                    data: bins.map(bin => bin.count),
                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Distribution of Total Scores'
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
     * Create flow distribution chart
     */
    createFlowDistributionChart() {
        const ctx = document.getElementById('flowDistributionChart');
        if (!ctx) return;

        // Handle different data structures
        let flows = [];
        if (this.data.results) {
            flows = this.data.results.map(r => {
                if (r.detected_flow) return r.detected_flow;
                if (r.flow) return r.flow;
                if (r.result && r.result.flow) return r.result.flow;
                return 'Unknown';
            });
        } else if (Array.isArray(this.data)) {
            flows = this.data.map(r => {
                if (r.detected_flow) return r.detected_flow;
                if (r.flow) return r.flow;
                if (r.result && r.result.flow) return r.result.flow;
                return 'Unknown';
            });
        }
        
        const flowCounts = this.countOccurrences(flows);
        
        this.charts.flowDistribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(flowCounts),
                datasets: [{
                    data: Object.values(flowCounts),
                    backgroundColor: [
                        '#FF6384',
                        '#36A2EB',
                        '#FFCE56',
                        '#4BC0C0',
                        '#9966FF',
                        '#FF9F40'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Distribution by Flow Type'
                    },
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    /**
     * Create criteria scores chart
     */
    createCriteriaScoresChart() {
        const ctx = document.getElementById('criteriaScoresChart');
        if (!ctx) return;

        const criteriaData = this.calculateCriteriaAverages();
        
        this.charts.criteriaScores = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: Object.keys(criteriaData),
                datasets: [{
                    label: 'Average Score',
                    data: Object.values(criteriaData),
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Average Scores by Criteria'
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    }

    /**
     * Create diagnostic issues chart
     */
    createDiagnosticIssuesChart() {
        const ctx = document.getElementById('diagnosticIssuesChart');
        if (!ctx) return;

        const diagnosticData = this.analyzeDiagnosticIssues();
        
        this.charts.diagnosticIssues = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: diagnosticData.labels,
                datasets: [{
                    label: 'Number of Issues',
                    data: diagnosticData.counts,
                    backgroundColor: 'rgba(255, 99, 132, 0.6)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Most Common Diagnostic Issues'
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    /**
     * Create performance chart
     */
    createPerformanceChart() {
        const ctx = document.getElementById('performanceChart');
        if (!ctx) return;

        const performanceData = this.analyzePerformance();
        
        this.charts.performance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: performanceData.labels,
                datasets: [{
                    label: 'Processing Time (seconds)',
                    data: performanceData.processingTimes,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.1
                }, {
                    label: 'Score',
                    data: performanceData.scores,
                    borderColor: 'rgba(255, 99, 132, 1)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    tension: 0.1,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Performance vs Score Analysis'
                    }
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Processing Time (s)'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Score'
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
     * Calculate criteria averages
     */
    calculateCriteriaAverages() {
        const results = this.data.results || [];
        const criteriaTotals = {};
        const criteriaCounts = {};

        results.forEach(result => {
            if (result.criteria) {
                Object.entries(result.criteria).forEach(([criterion, data]) => {
                    if (typeof data === 'object' && data.score !== undefined) {
                        criteriaTotals[criterion] = (criteriaTotals[criterion] || 0) + data.score;
                        criteriaCounts[criterion] = (criteriaCounts[criterion] || 0) + 1;
                    }
                });
            }
        });

        const averages = {};
        Object.keys(criteriaTotals).forEach(criterion => {
            averages[criterion] = criteriaTotals[criterion] / criteriaCounts[criterion];
        });

        return averages;
    }

    /**
     * Analyze diagnostic issues
     */
    analyzeDiagnosticIssues() {
        const results = this.data.results || [];
        const issueCounts = {};

        results.forEach(result => {
            if (result.diagnostic_hits) {
                result.diagnostic_hits.forEach(hit => {
                    issueCounts[hit.key] = (issueCounts[hit.key] || 0) + 1;
                });
            }
        });

        const sortedIssues = Object.entries(issueCounts)
            .sort(([,a], [,b]) => b - a)
            .slice(0, 10);

        return {
            labels: sortedIssues.map(([key]) => key),
            counts: sortedIssues.map(([, count]) => count)
        };
    }

    /**
     * Analyze performance data
     */
    analyzePerformance() {
        const results = this.data.results || [];
        const sortedResults = results
            .filter(r => r.processing_time && r.total_score)
            .sort((a, b) => a.processing_time - b.processing_time);

        return {
            labels: sortedResults.map((_, index) => `Item ${index + 1}`),
            processingTimes: sortedResults.map(r => r.processing_time),
            scores: sortedResults.map(r => r.total_score)
        };
    }

    /**
     * Create histogram bins
     */
    createHistogramBins(data, min, max, numBins) {
        const binSize = (max - min) / numBins;
        const bins = [];

        for (let i = 0; i < numBins; i++) {
            const binMin = min + i * binSize;
            const binMax = min + (i + 1) * binSize;
            const count = data.filter(value => value >= binMin && value < binMax).length;
            bins.push({ min: binMin, max: binMax, count });
        }

        return bins;
    }

    /**
     * Count occurrences in array
     */
    countOccurrences(arr) {
        return arr.reduce((acc, item) => {
            acc[item] = (acc[item] || 0) + 1;
            return acc;
        }, {});
    }

    /**
     * Destroy all charts
     */
    destroy() {
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.destroy();
            }
        });
        this.charts = {};
    }
}

// Export for global use
window.AnalyticsDashboard = AnalyticsDashboard;
