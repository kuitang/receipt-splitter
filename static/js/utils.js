/**
 * Receipt Splitter - Shared JavaScript Utilities
 * =============================================
 */

// ==========================================================================
// Constants and Configuration
// ==========================================================================
const CONFIG = {
  API_TIMEOUT: 30000,
  DEBOUNCE_DELAY: 300,
  VALIDATION_TOLERANCE: 0.01,
  CURRENCY_FORMAT: {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }
};

// ==========================================================================
// Security Utilities
// ==========================================================================

/**
 * Security: HTML escaping function for user content
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==========================================================================
// DOM Utilities
// ==========================================================================

/**
 * Safely query DOM element with error handling
 */
function $(selector, context = document) {
  return context.querySelector(selector);
}

/**
 * Query all matching DOM elements
 */
function $$(selector, context = document) {
  return Array.from(context.querySelectorAll(selector));
}

/**
 * Add event listener with automatic cleanup
 */
function on(element, event, handler, options = {}) {
  if (typeof element === 'string') {
    element = $(element);
  }
  if (element) {
    element.addEventListener(event, handler, options);
    return () => element.removeEventListener(event, handler, options);
  }
}

/**
 * Add delegated event listener
 */
function delegate(parent, selector, event, handler) {
  return on(parent, event, (e) => {
    const target = e.target.closest(selector);
    if (target) {
      handler.call(target, e);
    }
  });
}

// ==========================================================================
// Form Utilities
// ==========================================================================

/**
 * Get form data as object
 */
function getFormData(form) {
  const formData = new FormData(form);
  const data = {};
  for (const [key, value] of formData.entries()) {
    data[key] = value;
  }
  return data;
}

/**
 * Serialize form to JSON
 */
function serializeForm(form) {
  const data = {};
  const inputs = $$('input, select, textarea', form);
  
  inputs.forEach(input => {
    if (input.name && !input.disabled) {
      if (input.type === 'checkbox') {
        data[input.name] = input.checked;
      } else if (input.type === 'number') {
        data[input.name] = parseFloat(input.value) || 0;
      } else {
        data[input.name] = input.value;
      }
    }
  });
  
  return data;
}

/**
 * Validate required fields
 */
function validateRequired(form) {
  const required = $$('[required]', form);
  let isValid = true;
  
  required.forEach(field => {
    if (!field.value.trim()) {
      field.classList.add('input-error');
      isValid = false;
    } else {
      field.classList.remove('input-error');
    }
  });
  
  return isValid;
}

// ==========================================================================
// Number and Currency Utilities
// ==========================================================================

/**
 * Format number as currency
 */
function formatCurrency(amount) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    ...CONFIG.CURRENCY_FORMAT
  }).format(amount);
}

/**
 * Parse currency string to number
 */
function parseCurrency(str) {
  if (typeof str === 'number') return str;
  return parseFloat(str.replace(/[^0-9.-]/g, '')) || 0;
}

/**
 * Round to 2 decimal places
 */
function roundCurrency(amount) {
  return Math.round(amount * 100) / 100;
}

/**
 * Calculate percentage
 */
function calculatePercentage(amount, percentage) {
  return roundCurrency(amount * (percentage / 100));
}

// ==========================================================================
// API Utilities
// ==========================================================================

/**
 * Get cookie value by name
 */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Get CSRF token from cookies
 */
function getCsrfToken() {
  return getCookie('csrftoken');
}

/**
 * Make API request with standard error handling
 */
async function apiRequest(url, options = {}) {
  const defaults = {
    headers: {
      'X-CSRFToken': getCsrfToken(),
      'Content-Type': 'application/json'
    },
    credentials: 'same-origin'
  };
  
  const config = { ...defaults, ...options };
  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }
  
  try {
    const response = await fetch(url, config);
    const data = await response.json();
    
    if (!response.ok) {
      throw new ApiError(data.error || 'Request failed', response.status, data);
    }
    
    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError('Network error', 0, { message: error.message });
  }
}

/**
 * Authenticated fetch with CSRF token
 * Returns the raw response (for compatibility with existing code)
 */
async function authenticatedFetch(url, options = {}) {
  const defaults = {
    headers: {
      'X-CSRFToken': getCsrfToken()
    },
    credentials: 'same-origin'
  };
  
  const config = { ...defaults, ...options };
  if (options.headers) {
    config.headers = { ...defaults.headers, ...options.headers };
  }
  
  return fetch(url, config);
}

/**
 * Authenticated JSON fetch with CSRF token and Content-Type
 * Returns the raw response (for compatibility with existing code)
 */
async function authenticatedJsonFetch(url, options = {}) {
  const defaults = {
    headers: {
      'X-CSRFToken': getCsrfToken(),
      'Content-Type': 'application/json'
    },
    credentials: 'same-origin'
  };
  
  const config = { ...defaults, ...options };
  if (options.headers) {
    config.headers = { ...defaults.headers, ...options.headers };
  }
  
  return fetch(url, config);
}

/**
 * Custom API Error class
 */
class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

// ==========================================================================
// State Management
// ==========================================================================

/**
 * Simple state manager
 */
class StateManager {
  constructor(initialState = {}) {
    this.state = initialState;
    this.listeners = new Map();
  }
  
  get(key) {
    return key ? this.state[key] : this.state;
  }
  
  set(key, value) {
    const oldValue = this.state[key];
    this.state[key] = value;
    this.notify(key, value, oldValue);
  }
  
  update(updates) {
    Object.entries(updates).forEach(([key, value]) => {
      this.set(key, value);
    });
  }
  
  subscribe(key, callback) {
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key).add(callback);
    
    return () => this.listeners.get(key).delete(callback);
  }
  
  notify(key, value, oldValue) {
    if (this.listeners.has(key)) {
      this.listeners.get(key).forEach(callback => {
        callback(value, oldValue);
      });
    }
  }
}

// ==========================================================================
// UI Utilities
// ==========================================================================

/**
 * Show loading state
 */
function showLoading(element, message = 'Loading...') {
  element.classList.add('skeleton');
  element.setAttribute('aria-busy', 'true');
  if (message) {
    element.textContent = message;
  }
}

/**
 * Hide loading state
 */
function hideLoading(element) {
  element.classList.remove('skeleton');
  element.removeAttribute('aria-busy');
}

/**
 * Show/hide element with animation
 */
function toggleVisibility(element, show) {
  if (show) {
    element.classList.remove('hidden');
    element.classList.add('animate-fade-in');
  } else {
    element.classList.add('animate-fade-out');
    setTimeout(() => {
      element.classList.add('hidden');
      element.classList.remove('animate-fade-out');
    }, 200);
  }
}

/**
 * Display error message
 */
function showError(message, container = null) {
  const alert = document.createElement('div');
  alert.className = 'alert alert-danger animate-slide-down';
  alert.textContent = message;
  
  if (container) {
    container.appendChild(alert);
  } else {
    document.body.insertBefore(alert, document.body.firstChild);
  }
  
  setTimeout(() => {
    alert.classList.add('animate-fade-out');
    setTimeout(() => alert.remove(), 200);
  }, 5000);
}

/**
 * Display success message
 */
function showSuccess(message, container = null) {
  const alert = document.createElement('div');
  alert.className = 'alert alert-success animate-slide-down';
  alert.textContent = message;
  
  if (container) {
    container.appendChild(alert);
  } else {
    document.body.insertBefore(alert, document.body.firstChild);
  }
  
  setTimeout(() => {
    alert.classList.add('animate-fade-out');
    setTimeout(() => alert.remove(), 200);
  }, 3000);
}

/**
 * Show copy feedback toast
 */
function showCopyToast() {
    // Remove any existing toast
    const existingToast = document.getElementById('copy-toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.id = 'copy-toast';
    toast.className = 'fixed top-4 left-1/2 transform -translate-x-1/2 bg-gray-800 text-white px-4 py-2 rounded-full text-sm font-medium shadow-lg z-50 transition-all duration-300 opacity-0 flex items-center gap-2';
    
    // Add checkmark icon
    const checkIcon = document.createElement('span');
    checkIcon.innerHTML = '✓';
    checkIcon.className = 'text-green-400';
    
    // Add text
    const text = document.createElement('span');
    text.textContent = 'Link copied!';
    
    toast.appendChild(checkIcon);
    toast.appendChild(text);
    
    // Add to page
    document.body.appendChild(toast);
    
    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.remove('opacity-0');
        toast.classList.add('opacity-100', 'translate-y-2');
    });
    
    // Remove after delay
    setTimeout(() => {
        toast.classList.remove('opacity-100', 'translate-y-2');
        toast.classList.add('opacity-0', '-translate-y-2');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 2000);
}

/**
 * Copy text to clipboard with visual feedback
 */
function copyShareUrl(inputId, event) {
    inputId = inputId || 'share-url';
    const input = document.getElementById(inputId);
    input.select();
    input.setSelectionRange(0, 99999); // For mobile devices
    
    // Try modern clipboard API first, fall back to execCommand
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(input.value).then(() => {
            showCopyToast();
        }).catch(err => {
            // If clipboard API fails, try execCommand
            try {
                document.execCommand('copy');
                showCopyToast();
            } catch (e) {
                console.error('Failed to copy:', e);
            }
        });
    } else {
        // Use legacy execCommand for older browsers or non-HTTPS
        try {
            document.execCommand('copy');
            showCopyToast();
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    }
}

/**
 * Native share using Web Share API (mobile)
 */
async function nativeShare(inputId, event) {
    console.log('nativeShare called with inputId:', inputId);
    
    inputId = inputId || 'share-url';
    const input = document.getElementById(inputId);
    
    if (!input) {
        console.error('Share input not found:', inputId);
        return;
    }
    
    const url = input.value;
    console.log('Sharing URL:', url);
    
    // Get the receipt name from the page
    const restaurantName = document.getElementById('restaurant_name')?.value || 
                          document.querySelector('.text-3xl')?.textContent || 
                          'Receipt';
    
    console.log('Restaurant name:', restaurantName);
    
    if (navigator.share) {
        try {
            const shareData = {
                title: `${restaurantName} - Receipt Splitter`,
                text: `Let's split the receipt from ${restaurantName}`,
                url: url
            };
            console.log('Sharing data:', shareData);
            
            await navigator.share(shareData);
            console.log('Share successful');
        } catch (err) {
            // User cancelled or error occurred
            if (err.name !== 'AbortError') {
                console.error('Error sharing:', err);
                alert('Failed to share: ' + err.message);
            } else {
                console.log('User cancelled share');
            }
        }
    } else {
        console.error('navigator.share not available');
    }
}

/**
 * Initialize share functionality
 */
function initializeShareButtons() {
    try {
        console.log('Initializing share buttons...');
        
        // Detect mobile devices
        const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
        const isHTTPS = window.location.protocol === 'https:';
        
        console.log('Is mobile:', isMobile, 'Is HTTPS:', isHTTPS, 'Has Web Share:', !!navigator.share);
        
        // Check if Web Share API is available and we're on HTTPS
        if (navigator.share && isHTTPS) {
            console.log('Using native Web Share API');
            
            // Show native share buttons
            document.querySelectorAll('.mobile-share-btn').forEach(btn => {
                btn.classList.remove('hidden');
            });
            
            // Hide fallback buttons
            document.querySelectorAll('.mobile-fallback-share').forEach(div => {
                div.classList.add('hidden');
            });
            
            // Attach native share handlers
            document.querySelectorAll('[data-action="native-share"]').forEach(btn => {
                if (!btn.hasAttribute('data-initialized')) {
                    btn.setAttribute('data-initialized', 'true');
                    btn.addEventListener('click', function(event) {
                        event.preventDefault();
                        const widgetId = this.dataset.widgetId || 'share-url';
                        nativeShare(widgetId, event);
                    });
                }
            });
        } else if (isMobile && !isHTTPS) {
            console.log('Mobile on HTTP - showing fallback buttons');
            
            // Hide native share button
            document.querySelectorAll('.mobile-share-btn').forEach(btn => {
                btn.classList.add('hidden');
            });
            
            // Show fallback buttons
            document.querySelectorAll('.mobile-fallback-share').forEach(div => {
                div.classList.remove('hidden');
            });
            
            // Attach WhatsApp handlers
            document.querySelectorAll('[data-action="share-whatsapp"]').forEach(link => {
                if (!link.hasAttribute('data-initialized')) {
                    link.setAttribute('data-initialized', 'true');
                    link.addEventListener('click', function(event) {
                        event.preventDefault();
                        const widgetId = this.dataset.widgetId || 'share-url';
                        const input = document.getElementById(widgetId);
                        if (input) {
                            const url = input.value;
                            const text = encodeURIComponent(`Check out this receipt: ${url}`);
                            window.open(`https://wa.me/?text=${text}`, '_blank');
                        }
                    });
                }
            });
            
            // Attach Messenger handlers
            document.querySelectorAll('[data-action="share-messenger"]').forEach(link => {
                if (!link.hasAttribute('data-initialized')) {
                    link.setAttribute('data-initialized', 'true');
                    link.addEventListener('click', function(event) {
                        event.preventDefault();
                        const widgetId = this.dataset.widgetId || 'share-url';
                        const input = document.getElementById(widgetId);
                        if (input) {
                            const url = encodeURIComponent(input.value);
                            // Use Messenger's mobile web URL which auto-opens the app if installed
                            window.open(`https://m.me/?text=${url}`, '_blank');
                        }
                    });
                }
            });
            
            // Attach SMS handlers
            document.querySelectorAll('[data-action="share-sms"]').forEach(link => {
                if (!link.hasAttribute('data-initialized')) {
                    link.setAttribute('data-initialized', 'true');
                    link.addEventListener('click', function(event) {
                        event.preventDefault();
                        const widgetId = this.dataset.widgetId || 'share-url';
                        const input = document.getElementById(widgetId);
                        if (input) {
                            const url = input.value;
                            const text = encodeURIComponent(`Check out this receipt: ${url}`);
                            window.location.href = `sms:?&body=${text}`;
                        }
                    });
                }
            });
        }
        
        // Attach copy handlers (always available)
        document.querySelectorAll('[data-action="copy-share-url"]').forEach(btn => {
            if (!btn.hasAttribute('data-initialized')) {
                btn.setAttribute('data-initialized', 'true');
                btn.addEventListener('click', function(event) {
                    const widgetId = this.dataset.widgetId || 'share-url';
                    copyShareUrl(widgetId, event);
                });
            }
        });
        
        console.log('Share buttons initialized successfully');
    } catch (error) {
        console.error('Error initializing share buttons:', error);
    }
}

// ==========================================================================
// Receipt-Specific Utilities
// ==========================================================================

/**
 * Calculate item total from quantity and unit price
 */
function calculateItemTotal(quantity, unitPrice) {
  return roundCurrency(quantity * unitPrice);
}

/**
 * Calculate prorated amounts for tax and tip
 */
function calculateProrations(itemTotal, subtotal, tax, tip) {
  if (subtotal <= 0) {
    return { tax: 0, tip: 0 };
  }
  
  const proportion = itemTotal / subtotal;
  return {
    tax: roundCurrency(tax * proportion),
    tip: roundCurrency(tip * proportion)
  };
}

/**
 * Validate receipt balance
 */
function validateReceiptBalance(data) {
  const itemsSum = data.items.reduce((sum, item) => {
    return sum + (item.total_price || calculateItemTotal(item.quantity, item.unit_price));
  }, 0);
  
  const calculatedTotal = data.subtotal + data.tax + data.tip;
  
  const errors = [];
  
  if (Math.abs(itemsSum - data.subtotal) > CONFIG.VALIDATION_TOLERANCE) {
    errors.push(`Items sum (${formatCurrency(itemsSum)}) doesn't match subtotal (${formatCurrency(data.subtotal)})`);
  }
  
  if (Math.abs(calculatedTotal - data.total) > CONFIG.VALIDATION_TOLERANCE) {
    errors.push(`Calculated total (${formatCurrency(calculatedTotal)}) doesn't match receipt total (${formatCurrency(data.total)})`);
  }
  
  return {
    isValid: errors.length === 0,
    errors,
    itemsSum,
    calculatedTotal
  };
}

// ==========================================================================
// Utility Functions
// ==========================================================================

/**
 * Debounce function calls
 */
function debounce(func, delay = CONFIG.DEBOUNCE_DELAY) {
  let timeoutId;
  return function(...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
}

/**
 * Throttle function calls
 */
function throttle(func, limit = 100) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

/**
 * Deep clone object
 */
function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

/**
 * Check if object is empty
 */
function isEmpty(obj) {
  return Object.keys(obj).length === 0;
}

/**
 * Generate unique ID
 */
function generateId() {
  return `id_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// ==========================================================================
// Export for use in other scripts
// ==========================================================================

// Make critical functions globally available for backward compatibility
window.escapeHtml = escapeHtml;
window.getCookie = getCookie;
window.getCsrfToken = getCsrfToken;
window.authenticatedFetch = authenticatedFetch;
window.authenticatedJsonFetch = authenticatedJsonFetch;
window.copyShareUrl = copyShareUrl;
window.nativeShare = nativeShare;
window.initializeShareButtons = initializeShareButtons;

// Auto-initialize share buttons on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOMContentLoaded - initializing share buttons');
        initializeShareButtons();
    });
} else {
    // DOM already loaded
    console.log('DOM already loaded - initializing share buttons immediately');
    initializeShareButtons();
}

window.ReceiptUtils = {
  // DOM
  $,
  $$,
  on,
  delegate,
  
  // Forms
  getFormData,
  serializeForm,
  validateRequired,
  
  // Numbers
  formatCurrency,
  parseCurrency,
  roundCurrency,
  calculatePercentage,
  
  // API
  getCsrfToken,
  apiRequest,
  authenticatedFetch,
  authenticatedJsonFetch,
  ApiError,
  
  // State
  StateManager,
  
  // UI
  showLoading,
  hideLoading,
  toggleVisibility,
  showError,
  showSuccess,
  initializeShareButtons,
  
  // Receipt
  calculateItemTotal,
  calculateProrations,
  validateReceiptBalance,
  
  // Utilities
  debounce,
  throttle,
  deepClone,
  isEmpty,
  generateId,
  
  // Config
  CONFIG
};

// ==========================================================================
// Module Exports for Testing
// ==========================================================================

// Export for use in Node.js/ES modules (for testing)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    // Security
    escapeHtml,
    
    // DOM
    $,
    $$,
    on,
    delegate,
    
    // Forms
    getFormData,
    serializeForm,
    validateRequired,
    
    // Numbers
    formatCurrency,
    parseCurrency,
    roundCurrency,
    calculatePercentage,
    
    // API
    getCookie,
    getCsrfToken,
    apiRequest,
    authenticatedFetch,
    authenticatedJsonFetch,
    ApiError,
    
    // State
    StateManager,
    
    // UI
    showLoading,
    hideLoading,
    toggleVisibility,
    showError,
    showSuccess,
    copyShareUrl,
    nativeShare,
    initializeShareButtons,
    
    // Receipt
    calculateItemTotal,
    calculateProrations,
    validateReceiptBalance,
    
    // Utilities
    debounce,
    throttle,
    deepClone,
    isEmpty,
    generateId,
    
    // Config
    CONFIG
  };
}