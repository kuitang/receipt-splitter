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
            
            // Draw and resize image
            ctx.drawImage(img, 0, 0, width, height);
            
            // Convert to blob
            canvas.toBlob(resolve, 'image/jpeg', quality);
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
        const existingInfo = e.target.parentElement.querySelector('.text-green-600, .text-blue-600');
        if (existingInfo) existingInfo.remove();
        
        // Show processing message
        const processingInfo = document.createElement('p');
        processingInfo.className = 'text-sm text-blue-600 mt-2';
        processingInfo.textContent = 'Optimizing image for upload...';
        e.target.parentElement.appendChild(processingInfo);
        
        try {
            // Only resize if it's not HEIC (let server handle HEIC conversion)
            if (fileName.endsWith('.heic') || fileName.endsWith('.heif')) {
                // Show file info for HEIC files (processed on server)
                processingInfo.className = 'text-sm text-green-600 mt-2';
                processingInfo.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB) - HEIC format will be processed on server`;
                return;
            }
            
            // Resize other image formats
            const resizedBlob = await resizeImage(file);
            
            // Create new file from resized blob
            const resizedFile = new File([resizedBlob], 
                file.name.replace(/\.[^/.]+$/, '.jpg'), 
                { type: 'image/jpeg' }
            );
            
            // Update file input
            const dt = new DataTransfer();
            dt.items.add(resizedFile);
            e.target.files = dt.files;
            
            // Show success info
            processingInfo.className = 'text-sm text-green-600 mt-2';
            processingInfo.textContent = `Optimized: ${resizedFile.name} (${(resizedFile.size / 1024 / 1024).toFixed(2)} MB) - Resized to max 2048px for GPT-4o vision processing`;
            
        } catch (error) {
            // If resizing fails, use original file
            console.warn('Image resizing failed, using original:', error);
            processingInfo.className = 'text-sm text-green-600 mt-2';
            processingInfo.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB) - Using original file`;
        }
    });
}

/**
 * Initialize index page on DOM ready
 */
document.addEventListener('DOMContentLoaded', () => {
    initializeFileUpload();
});