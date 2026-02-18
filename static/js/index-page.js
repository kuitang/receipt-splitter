/**
 * Index page functionality for image upload and optimization
 * Depends on: utils.js
 */

/**
 * Resize image for optimal upload
 */
async function resizeImage(file, maxDimension = 2048, quality = 0.85) {
    return new Promise((resolve) => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const img = new Image();

        img.onload = function() {
            // Calculate new dimensions while preserving aspect ratio
            let { width, height } = img;

            if (width > maxDimension || height > maxDimension) {
                if (width > height) {
                    height = (height * maxDimension) / width;
                    width = maxDimension;
                } else {
                    width = (width * maxDimension) / height;
                    height = maxDimension;
                }
            }

            // Set canvas dimensions
            canvas.width = width;
            canvas.height = height;

            // Use high-quality downscaling (Lanczos in Chrome/Safari/Edge)
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(img, 0, 0, width, height);
            URL.revokeObjectURL(img.src);

            // Try WebP first (25-35% smaller than JPEG at equivalent quality)
            canvas.toBlob((blob) => {
                if (blob && blob.type === 'image/webp') {
                    resolve(blob);
                } else {
                    // Safari doesn't support WebP encoding — fall back to JPEG
                    canvas.toBlob(resolve, 'image/jpeg', quality);
                }
            }, 'image/webp', quality);
        };

        img.src = URL.createObjectURL(file);
    });
}

/**
 * Initialize file upload handler with validation and resizing
 */
function initializeFileUpload() {
    const fileInput = document.getElementById('receipt_image');
    if (!fileInput) return;
    
    fileInput.addEventListener('change', async function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        // Check file size
        const maxSize = 20 * 1024 * 1024; // 20MB (increased for pre-resize)
        if (file.size > maxSize) {
            alert('File size must be less than 20MB');
            e.target.value = '';
            return;
        }
        
        // Get file extension
        const fileName = file.name.toLowerCase();
        const validExtensions = ['.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp', '.bmp', '.gif'];
        const hasValidExtension = validExtensions.some(ext => fileName.endsWith(ext));
        
        if (!hasValidExtension) {
            // Check MIME type as fallback
            const validMimeTypes = ['image/jpeg', 'image/png', 'image/heic', 'image/heif', 'image/webp', 'image/bmp', 'image/gif'];
            if (!validMimeTypes.includes(file.type) && !file.type.startsWith('image/')) {
                alert('Please upload a valid image file (JPEG, PNG, HEIC, WebP, etc.)');
                e.target.value = '';
                return;
            }
        }
        
        // Remove any existing file info
        const existingInfo = e.target.parentElement.querySelector('.text-blue-600');
        if (existingInfo) existingInfo.remove();
        
        // Show processing message
        const processingInfo = document.createElement('p');
        processingInfo.className = 'text-sm text-blue-600 mt-2';
        processingInfo.textContent = 'Optimizing image for upload...';
        e.target.parentElement.appendChild(processingInfo);
        
        try {
            // Resize all formats (Safari/iOS decodes HEIC natively)
            const resizedBlob = await resizeImage(file);

            // Use correct extension for output format
            const ext = resizedBlob.type === 'image/webp' ? '.webp' : '.jpg';
            const resizedFile = new File([resizedBlob],
                file.name.replace(/\.[^/.]+$/, ext),
                { type: resizedBlob.type }
            );
            
            // Update file input
            const dt = new DataTransfer();
            dt.items.add(resizedFile);
            e.target.files = dt.files;
            
            // Remove processing message after optimization
            processingInfo.remove();
            
        } catch (error) {
            // If resizing fails, use original file
            console.warn('Image resizing failed, using original:', error);
            processingInfo.remove();
        }
    });
}

/**
 * Validate Venmo username input.
 * @ prefix is optional; the username portion must be 5-30 chars of [a-zA-Z0-9_-].
 * Returns true if valid or empty (optional field), false otherwise.
 */
function validateVenmo(input, errorEl) {
    const raw = input.value.trim();

    // Empty or just "@" means the user skipped it — that's fine
    if (!raw || raw === '@') {
        errorEl.classList.add('hidden');
        input.classList.remove('border-red-500', 'bg-red-50');
        return true;
    }

    const username = raw.replace(/^@/, '');
    const valid = /^[a-zA-Z0-9_\-]{5,30}$/.test(username);

    if (!valid) {
        let msg;
        if (username.length < 5) {
            msg = 'Venmo username must be at least 5 characters';
        } else if (username.length > 30) {
            msg = 'Venmo username must be 30 characters or less';
        } else {
            msg = 'Venmo username can only contain letters, numbers, hyphens, and underscores';
        }
        errorEl.textContent = msg;
        errorEl.classList.remove('hidden');
        input.classList.add('border-red-500', 'bg-red-50');
        return false;
    }

    errorEl.classList.add('hidden');
    input.classList.remove('border-red-500', 'bg-red-50');
    return true;
}

/**
 * Initialize Venmo username input: validate on blur and block invalid submit.
 */
function initializeVenmoInput() {
    const input = document.getElementById('venmo_username');
    if (!input) return;

    const errorEl = document.getElementById('venmo-error');

    // Validate on blur
    input.addEventListener('blur', () => {
        validateVenmo(input, errorEl);
    });

    // Validate and normalize on submit
    const form = input.closest('form');
    if (form) {
        form.addEventListener('submit', (e) => {
            const raw = input.value.trim();
            // Normalize: strip @ prefix so backend stores clean username
            if (raw === '@') {
                input.value = '';
            } else if (raw.startsWith('@')) {
                input.value = raw.slice(1);
            }
            if (!validateVenmo(input, errorEl)) {
                e.preventDefault();
            }
        });
    }
}

/**
 * Initialize index page on DOM ready
 */
function initializePage() {
    initializeFileUpload();
    initializeVenmoInput();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePage);
} else {
    initializePage();
}

// ==========================================================================
// Module Exports for Testing
// ==========================================================================

// Export for use in Node.js/ES modules (for testing)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        resizeImage,
        initializeFileUpload,
        validateVenmo,
        initializeVenmoInput
    };
}