"""
Simple but strict Content Security Policy middleware.
No nonces needed since we have no inline scripts!
"""

from django.utils.deprecation import MiddlewareMixin
from django.conf import settings


class SimpleStrictCSPMiddleware(MiddlewareMixin):
    """
    Implements a strict but simple Content Security Policy.
    
    Since we have no inline JavaScript after refactoring, we can use
    a very strict CSP without the complexity of nonces.
    """
    
    def process_response(self, request, response):
        # Skip CSP for admin pages to avoid breaking Django admin
        if request.path.startswith('/admin/'):
            return response
        
        # Build strict CSP directives
        csp_directives = []
        
        # Default: only same-origin
        csp_directives.append("default-src 'self'")
        
        # Scripts: only from self and specific trusted CDNs
        # NO 'unsafe-inline' needed!
        script_sources = [
            "'self'",
            "https://cdn.tailwindcss.com",
            "https://cdn.jsdelivr.net",
        ]
        csp_directives.append(f"script-src {' '.join(script_sources)}")
        
        # Styles: unfortunately still need unsafe-inline for Tailwind
        # Tailwind CDN generates inline <style> tags
        style_sources = [
            "'self'",
            "'unsafe-inline'",  # Required for Tailwind CDN
            "https://cdn.tailwindcss.com",
        ]
        csp_directives.append(f"style-src {' '.join(style_sources)}")
        
        # Images: self and data URIs (for base64 images)
        csp_directives.append("img-src 'self' data: blob:")
        
        # Fonts: self and data URIs
        csp_directives.append("font-src 'self' data:")
        
        # Connections: only same-origin (no WebSocket needed anymore)
        csp_directives.append("connect-src 'self'")
        
        # Forms: only submit to same origin
        csp_directives.append("form-action 'self'")
        
        # Frames: no one can iframe us (prevents clickjacking)
        csp_directives.append("frame-ancestors 'none'")
        
        # No frames/iframes in our app
        csp_directives.append("frame-src 'none'")
        csp_directives.append("child-src 'none'")
        
        # No plugins (Flash, Java, etc.)
        csp_directives.append("object-src 'none'")
        
        # Base tag restriction (prevents base tag injection)
        csp_directives.append("base-uri 'self'")
        
        # No workers except from same origin
        csp_directives.append("worker-src 'self'")
        
        # Media only from same origin
        csp_directives.append("media-src 'self'")
        
        # Manifest only from same origin
        csp_directives.append("manifest-src 'self'")
        
        # Upgrade insecure requests in production
        if not settings.DEBUG:
            csp_directives.append("upgrade-insecure-requests")
        
        # Build the complete CSP header
        csp_header = "; ".join(csp_directives)
        
        # Apply CSP
        if settings.DEBUG:
            # Report-only in development to identify issues
            response['Content-Security-Policy-Report-Only'] = csp_header
            print(f"CSP Report-Only: {csp_header[:100]}...")  # Debug logging
        else:
            # Enforce in production
            response['Content-Security-Policy'] = csp_header
        
        # Additional security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        
        # X-XSS-Protection is deprecated and can cause issues
        # Modern browsers ignore it in favor of CSP
        response['X-XSS-Protection'] = '0'
        
        # Referrer policy for privacy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Cross-origin isolation headers
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Resource-Policy'] = 'same-origin'
        
        # HSTS for HTTPS connections (2 years with subdomains)
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
        
        # Permissions Policy - disable unnecessary browser features
        permissions = [
            "accelerometer=()",      # Motion sensors
            "autoplay=()",           # Autoplay media
            "camera=()",             # Camera access
            "display-capture=()",    # Screen recording
            "encrypted-media=()",    # DRM content
            "fullscreen=(self)",     # Allow fullscreen only for our origin
            "geolocation=()",        # Location access
            "gyroscope=()",          # Motion sensors
            "magnetometer=()",       # Compass
            "microphone=()",         # Microphone access
            "midi=()",               # MIDI devices
            "payment=()",            # Payment request API
            "picture-in-picture=()", # PiP video
            "publickey-credentials-get=()", # WebAuthn
            "screen-wake-lock=()",   # Prevent screen sleep
            "sync-xhr=()",           # Synchronous XHR (deprecated)
            "usb=()",                # USB devices
            "web-share=()",          # Web share API
            "xr-spatial-tracking=()" # VR/AR
        ]
        response['Permissions-Policy'] = ", ".join(permissions)
        
        return response