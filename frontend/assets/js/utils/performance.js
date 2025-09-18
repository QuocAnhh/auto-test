/**
 * Performance Optimization Utilities
 * Code optimization and performance monitoring
 */

class PerformanceOptimizer {
    constructor() {
        this.metrics = {
            pageLoadTime: 0,
            domContentLoaded: 0,
            firstPaint: 0,
            firstContentfulPaint: 0,
            largestContentfulPaint: 0,
            cumulativeLayoutShift: 0,
            firstInputDelay: 0,
            totalBlockingTime: 0
        };
        this.observers = new Map();
        this.debounceTimers = new Map();
        this.throttleTimers = new Map();
        this.init();
    }

    /**
     * Initialize performance monitoring
     */
    init() {
        this.measurePageLoad();
        this.setupPerformanceObservers();
        this.optimizeImages();
        this.setupLazyLoading();
        this.optimizeScrollEvents();
        this.optimizeResizeEvents();
    }

    /**
     * Measure page load performance
     */
    measurePageLoad() {
        if (typeof window !== 'undefined' && window.performance) {
            window.addEventListener('load', () => {
                const navigation = performance.getEntriesByType('navigation')[0];
                if (navigation) {
                    this.metrics.pageLoadTime = navigation.loadEventEnd - navigation.loadEventStart;
                    this.metrics.domContentLoaded = navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart;
                }

                // Measure Core Web Vitals
                this.measureCoreWebVitals();
            });
        }
    }

    /**
     * Measure Core Web Vitals
     */
    measureCoreWebVitals() {
        // Largest Contentful Paint
        if ('PerformanceObserver' in window) {
            const lcpObserver = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                const lastEntry = entries[entries.length - 1];
                this.metrics.largestContentfulPaint = lastEntry.startTime;
            });
            lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });

            // First Input Delay
            const fidObserver = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                entries.forEach((entry) => {
                    this.metrics.firstInputDelay = entry.processingStart - entry.startTime;
                });
            });
            fidObserver.observe({ entryTypes: ['first-input'] });

            // Cumulative Layout Shift
            const clsObserver = new PerformanceObserver((list) => {
                let clsValue = 0;
                for (const entry of list.getEntries()) {
                    if (!entry.hadRecentInput) {
                        clsValue += entry.value;
                    }
                }
                this.metrics.cumulativeLayoutShift = clsValue;
            });
            clsObserver.observe({ entryTypes: ['layout-shift'] });
        }
    }

    /**
     * Setup performance observers
     */
    setupPerformanceObservers() {
        // Observe long tasks
        if ('PerformanceObserver' in window) {
            const longTaskObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    this.metrics.totalBlockingTime += entry.duration - 50;
                }
            });
            longTaskObserver.observe({ entryTypes: ['longtask'] });
        }
    }

    /**
     * Optimize images
     */
    optimizeImages() {
        const images = document.querySelectorAll('img');
        images.forEach(img => {
            // Lazy loading
            if ('loading' in HTMLImageElement.prototype) {
                img.loading = 'lazy';
            }

            // Add error handling
            img.addEventListener('error', () => {
                img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEyIDJMMTMuMDkgOC4yNkwyMCA5TDEzLjA5IDE1Ljc0TDEyIDIyTDEwLjkxIDE1Ljc0TDQgOUwxMC45MSA4LjI2TDEyIDJaIiBmaWxsPSIjNjY2Ii8+Cjwvc3ZnPgo=';
            });
        });
    }

    /**
     * Setup lazy loading
     */
    setupLazyLoading() {
        if ('IntersectionObserver' in window) {
            const lazyElements = document.querySelectorAll('[data-lazy]');
            const lazyObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const element = entry.target;
                        const src = element.dataset.src;
                        if (src) {
                            element.src = src;
                            element.removeAttribute('data-src');
                        }
                        lazyObserver.unobserve(element);
                    }
                });
            });

            lazyElements.forEach(element => {
                lazyObserver.observe(element);
            });
        }
    }

    /**
     * Optimize scroll events
     */
    optimizeScrollEvents() {
        let scrollTimeout;
        const optimizedScrollHandler = () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                // Handle scroll events here
                this.handleScroll();
            }, 16); // ~60fps
        };

        window.addEventListener('scroll', optimizedScrollHandler, { passive: true });
    }

    /**
     * Optimize resize events
     */
    optimizeResizeEvents() {
        let resizeTimeout;
        const optimizedResizeHandler = () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.handleResize();
            }, 250);
        };

        window.addEventListener('resize', optimizedResizeHandler, { passive: true });
    }

    /**
     * Handle scroll events
     */
    handleScroll() {
        // Implement scroll-based optimizations
        const scrollTop = window.pageYOffset;
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;

        // Update scroll progress
        const scrollProgress = scrollTop / (documentHeight - windowHeight);
        document.documentElement.style.setProperty('--scroll-progress', scrollProgress);
    }

    /**
     * Handle resize events
     */
    handleResize() {
        // Implement resize-based optimizations
        const width = window.innerWidth;
        const height = window.innerHeight;

        // Update viewport variables
        document.documentElement.style.setProperty('--viewport-width', `${width}px`);
        document.documentElement.style.setProperty('--viewport-height', `${height}px`);
    }

    /**
     * Debounce function
     */
    debounce(func, wait, immediate = false) {
        const key = func.toString();
        
        return (...args) => {
            const later = () => {
                this.debounceTimers.delete(key);
                if (!immediate) func(...args);
            };

            const callNow = immediate && !this.debounceTimers.has(key);
            
            clearTimeout(this.debounceTimers.get(key));
            this.debounceTimers.set(key, setTimeout(later, wait));

            if (callNow) func(...args);
        };
    }

    /**
     * Throttle function
     */
    throttle(func, limit) {
        const key = func.toString();
        
        return (...args) => {
            if (!this.throttleTimers.has(key)) {
                func(...args);
                this.throttleTimers.set(key, setTimeout(() => {
                    this.throttleTimers.delete(key);
                }, limit));
            }
        };
    }

    /**
     * Optimize DOM queries
     */
    optimizeDOMQueries() {
        // Cache frequently accessed elements
        const cache = new Map();
        
        return (selector) => {
            if (cache.has(selector)) {
                return cache.get(selector);
            }
            
            const element = document.querySelector(selector);
            cache.set(selector, element);
            return element;
        };
    }

    /**
     * Optimize event listeners
     */
    optimizeEventListeners() {
        // Use event delegation for better performance
        document.addEventListener('click', (event) => {
            const target = event.target;
            
            // Handle button clicks
            if (target.matches('[data-action]')) {
                const action = target.dataset.action;
                this.handleAction(action, target);
            }
            
            // Handle form submissions
            if (target.matches('form')) {
                event.preventDefault();
                this.handleFormSubmission(target);
            }
        });
    }

    /**
     * Handle action events
     */
    handleAction(action, element) {
        switch (action) {
            case 'toggle':
                this.toggleElement(element);
                break;
            case 'close':
                this.closeElement(element);
                break;
            case 'submit':
                this.submitForm(element);
                break;
            default:
                console.log('Unknown action:', action);
        }
    }

    /**
     * Toggle element
     */
    toggleElement(element) {
        element.classList.toggle('active');
    }

    /**
     * Close element
     */
    closeElement(element) {
        element.style.display = 'none';
    }

    /**
     * Submit form
     */
    submitForm(form) {
        const formData = new FormData(form);
        console.log('Form submitted:', Object.fromEntries(formData));
    }

    /**
     * Handle form submission
     */
    handleFormSubmission(form) {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        
        // Validate form
        if (this.validateForm(data)) {
            this.submitFormData(data);
        }
    }

    /**
     * Validate form data
     */
    validateForm(data) {
        // Basic validation
        for (const [key, value] of Object.entries(data)) {
            if (!value || value.trim() === '') {
                console.error(`Field ${key} is required`);
                return false;
            }
        }
        return true;
    }

    /**
     * Submit form data
     */
    submitFormData(data) {
        console.log('Submitting form data:', data);
        // Implement form submission logic
    }

    /**
     * Optimize animations
     */
    optimizeAnimations() {
        // Use CSS transforms for better performance
        const animatedElements = document.querySelectorAll('[data-animate]');
        
        animatedElements.forEach(element => {
            element.style.willChange = 'transform, opacity';
        });
    }

    /**
     * Get performance metrics
     */
    getMetrics() {
        return {
            ...this.metrics,
            memoryUsage: this.getMemoryUsage(),
            connectionInfo: this.getConnectionInfo()
        };
    }

    /**
     * Get memory usage
     */
    getMemoryUsage() {
        if ('memory' in performance) {
            return {
                used: performance.memory.usedJSHeapSize,
                total: performance.memory.totalJSHeapSize,
                limit: performance.memory.jsHeapSizeLimit
            };
        }
        return null;
    }

    /**
     * Get connection info
     */
    getConnectionInfo() {
        if ('connection' in navigator) {
            return {
                effectiveType: navigator.connection.effectiveType,
                downlink: navigator.connection.downlink,
                rtt: navigator.connection.rtt
            };
        }
        return null;
    }

    /**
     * Generate performance report
     */
    generateReport() {
        const metrics = this.getMetrics();
        const report = {
            timestamp: new Date().toISOString(),
            url: window.location.href,
            userAgent: navigator.userAgent,
            metrics: metrics,
            recommendations: this.getRecommendations(metrics)
        };

        return report;
    }

    /**
     * Get performance recommendations
     */
    getRecommendations(metrics) {
        const recommendations = [];

        if (metrics.pageLoadTime > 3000) {
            recommendations.push('Page load time is slow. Consider optimizing images and reducing JavaScript bundle size.');
        }

        if (metrics.largestContentfulPaint > 2500) {
            recommendations.push('Largest Contentful Paint is slow. Optimize images and use efficient loading strategies.');
        }

        if (metrics.cumulativeLayoutShift > 0.1) {
            recommendations.push('Cumulative Layout Shift is high. Ensure images have dimensions and avoid dynamic content insertion.');
        }

        if (metrics.firstInputDelay > 100) {
            recommendations.push('First Input Delay is high. Reduce JavaScript execution time and use code splitting.');
        }

        return recommendations;
    }
}

// Export for global use
window.PerformanceOptimizer = PerformanceOptimizer;
