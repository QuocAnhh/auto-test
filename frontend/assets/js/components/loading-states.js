/**
 * Loading States Component
 * Better UX during operations with loading indicators
 */

class LoadingStates {
    constructor() {
        this.activeLoaders = new Map();
        this.loadingQueue = [];
        this.isProcessingQueue = false;
    }

    /**
     * Show loading state
     */
    show(elementId, options = {}) {
        const {
            message = 'Loading...',
            type = 'spinner',
            overlay = false,
            size = 'normal',
            color = 'primary'
        } = options;

        const element = document.getElementById(elementId);
        if (!element) {
            console.warn(`Element with id '${elementId}' not found`);
            return;
        }

        const loaderId = `${elementId}_loader_${Date.now()}`;
        const loaderHTML = this.createLoaderHTML(message, type, size, color, overlay);

        // Store original content
        const originalContent = element.innerHTML;
        element.setAttribute('data-original-content', originalContent);

        // Add loader
        element.innerHTML = loaderHTML;
        element.classList.add('loading-state');

        // Store loader info
        this.activeLoaders.set(loaderId, {
            elementId,
            element,
            originalContent,
            startTime: Date.now()
        });

        return loaderId;
    }

    /**
     * Hide loading state
     */
    hide(loaderId) {
        const loader = this.activeLoaders.get(loaderId);
        if (!loader) {
            console.warn(`Loader with id '${loaderId}' not found`);
            return;
        }

        // Restore original content
        loader.element.innerHTML = loader.originalContent;
        loader.element.classList.remove('loading-state');

        // Remove from active loaders
        this.activeLoaders.delete(loaderId);
    }

    /**
     * Hide all loaders for an element
     */
    hideAll(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;

        // Find and hide all loaders for this element
        for (const [loaderId, loader] of this.activeLoaders.entries()) {
            if (loader.elementId === elementId) {
                this.hide(loaderId);
            }
        }
    }

    /**
     * Create loader HTML
     */
    createLoaderHTML(message, type, size, color, overlay) {
        const sizeClass = this.getSizeClass(size);
        const overlayClass = overlay ? 'loading-overlay' : '';

        switch (type) {
            case 'spinner':
                return `
                    <div class="loading-container ${overlayClass}">
                        <div class="text-center">
                            <div class="spinner-border text-${color} ${sizeClass}" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <div class="mt-2">${message}</div>
                        </div>
                    </div>
                `;

            case 'dots':
                return `
                    <div class="loading-container ${overlayClass}">
                        <div class="text-center">
                            <div class="loading-dots">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                            <div class="mt-2">${message}</div>
                        </div>
                    </div>
                `;

            case 'pulse':
                return `
                    <div class="loading-container ${overlayClass}">
                        <div class="text-center">
                            <div class="loading-pulse">
                                <div class="pulse-circle"></div>
                            </div>
                            <div class="mt-2">${message}</div>
                        </div>
                    </div>
                `;

            case 'skeleton':
                return `
                    <div class="loading-container ${overlayClass}">
                        <div class="skeleton-loader">
                            <div class="skeleton-line"></div>
                            <div class="skeleton-line"></div>
                            <div class="skeleton-line short"></div>
                        </div>
                    </div>
                `;

            case 'progress':
                return `
                    <div class="loading-container ${overlayClass}">
                        <div class="text-center">
                            <div class="progress mb-2" style="height: 8px;">
                                <div class="progress-bar progress-bar-striped progress-bar-animated bg-${color}" 
                                     role="progressbar" style="width: 0%"></div>
                            </div>
                            <div class="small">${message}</div>
                        </div>
                    </div>
                `;

            default:
                return `
                    <div class="loading-container ${overlayClass}">
                        <div class="text-center">
                            <div class="spinner-border text-${color} ${sizeClass}" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <div class="mt-2">${message}</div>
                        </div>
                    </div>
                `;
        }
    }

    /**
     * Get size class
     */
    getSizeClass(size) {
        switch (size) {
            case 'small': return 'spinner-border-sm';
            case 'large': return 'spinner-border-lg';
            default: return '';
        }
    }

    /**
     * Show button loading state
     */
    showButtonLoading(buttonId, options = {}) {
        const button = document.getElementById(buttonId);
        if (!button) return;

        const {
            text = 'Loading...',
            icon = 'spinner-border-sm'
        } = options;

        // Store original content
        button.setAttribute('data-original-content', button.innerHTML);
        button.disabled = true;

        // Show loading state
        button.innerHTML = `
            <span class="spinner-border ${icon} me-2" role="status" aria-hidden="true"></span>
            ${text}
        `;

        return buttonId;
    }

    /**
     * Hide button loading state
     */
    hideButtonLoading(buttonId) {
        const button = document.getElementById(buttonId);
        if (!button) return;

        const originalContent = button.getAttribute('data-original-content');
        if (originalContent) {
            button.innerHTML = originalContent;
            button.removeAttribute('data-original-content');
        }
        button.disabled = false;
    }

    /**
     * Show table loading state
     */
    showTableLoading(tableId, options = {}) {
        const table = document.getElementById(tableId);
        if (!table) return;

        const {
            rows = 5,
            columns = 4
        } = options;

        const skeletonRows = Array(rows).fill().map(() => 
            `<tr>${Array(columns).fill().map(() => '<td><div class="skeleton-line"></div></td>').join('')}</tr>`
        ).join('');

        table.innerHTML = `
            <thead>
                <tr>
                    ${Array(columns).fill().map(() => '<th><div class="skeleton-line"></div></th>').join('')}
                </tr>
            </thead>
            <tbody>
                ${skeletonRows}
            </tbody>
        `;

        table.classList.add('loading-state');
    }

    /**
     * Hide table loading state
     */
    hideTableLoading(tableId) {
        const table = document.getElementById(tableId);
        if (!table) return;

        table.classList.remove('loading-state');
    }

    /**
     * Show card loading state
     */
    showCardLoading(cardId, options = {}) {
        const card = document.getElementById(cardId);
        if (!card) return;

        const {
            lines = 3
        } = options;

        const skeletonContent = Array(lines).fill().map(() => 
            '<div class="skeleton-line"></div>'
        ).join('');

        card.innerHTML = `
            <div class="card-body">
                <div class="skeleton-loader">
                    ${skeletonContent}
                </div>
            </div>
        `;

        card.classList.add('loading-state');
    }

    /**
     * Hide card loading state
     */
    hideCardLoading(cardId) {
        const card = document.getElementById(cardId);
        if (!card) return;

        card.classList.remove('loading-state');
    }

    /**
     * Show page loading state
     */
    showPageLoading(options = {}) {
        const {
            message = 'Loading page...',
            overlay = true
        } = options;

        const loaderHTML = `
            <div class="page-loading-overlay">
                <div class="page-loading-content">
                    <div class="spinner-border text-primary mb-3" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="h5">${message}</div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', loaderHTML);
    }

    /**
     * Hide page loading state
     */
    hidePageLoading() {
        const overlay = document.querySelector('.page-loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    }

    /**
     * Show inline loading state
     */
    showInlineLoading(elementId, options = {}) {
        const {
            message = 'Loading...',
            position = 'after'
        } = options;

        const element = document.getElementById(elementId);
        if (!element) return;

        const loaderHTML = `
            <div class="inline-loading">
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                ${message}
            </div>
        `;

        if (position === 'before') {
            element.insertAdjacentHTML('beforebegin', loaderHTML);
        } else {
            element.insertAdjacentHTML('afterend', loaderHTML);
        }
    }

    /**
     * Hide inline loading state
     */
    hideInlineLoading(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const inlineLoader = element.parentNode.querySelector('.inline-loading');
        if (inlineLoader) {
            inlineLoader.remove();
        }
    }

    /**
     * Get active loaders
     */
    getActiveLoaders() {
        return Array.from(this.activeLoaders.keys());
    }

    /**
     * Clear all loaders
     */
    clearAll() {
        for (const loaderId of this.activeLoaders.keys()) {
            this.hide(loaderId);
        }
    }
}

// Add CSS for loading states
const loadingStyles = `
    .loading-state {
        position: relative;
        overflow: hidden;
    }

    .loading-overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.9);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }

    .loading-container {
        padding: 2rem;
        text-align: center;
    }

    .loading-dots {
        display: inline-block;
    }

    .loading-dots span {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #007bff;
        margin: 0 2px;
        animation: loading-dots 1.4s infinite ease-in-out both;
    }

    .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
    .loading-dots span:nth-child(2) { animation-delay: -0.16s; }

    @keyframes loading-dots {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1); }
    }

    .loading-pulse {
        display: inline-block;
    }

    .pulse-circle {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #007bff;
        animation: loading-pulse 1.5s infinite;
    }

    @keyframes loading-pulse {
        0% { transform: scale(0); opacity: 1; }
        100% { transform: scale(1); opacity: 0; }
    }

    .skeleton-loader {
        animation: skeleton-loading 1.5s infinite;
    }

    .skeleton-line {
        height: 12px;
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: skeleton-shimmer 1.5s infinite;
        border-radius: 4px;
        margin-bottom: 8px;
    }

    .skeleton-line.short {
        width: 60%;
    }

    @keyframes skeleton-shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    .page-loading-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.9);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
    }

    .page-loading-content {
        text-align: center;
        padding: 2rem;
    }

    .inline-loading {
        display: inline-flex;
        align-items: center;
        color: #6c757d;
        font-size: 0.875rem;
    }
`;

// Inject styles
const styleSheet = document.createElement('style');
styleSheet.textContent = loadingStyles;
document.head.appendChild(styleSheet);

// Export for global use
window.LoadingStates = LoadingStates;
