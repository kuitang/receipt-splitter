#!/bin/bash

# Test script for Fly.io deployment
# Simulates key integration tests with curl

# Remove set -e to continue testing even if some tests fail
# set -e

APP_URL="https://receipt-splitter-demo.fly.dev"
echo "🧪 Testing deployed Receipt Splitter at $APP_URL"
echo "======================================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

test_passed() {
    echo -e "   ${GREEN}✓${NC} $1"
}

test_failed() {
    echo -e "   ${RED}✗${NC} $1"
}

test_warning() {
    echo -e "   ${YELLOW}⚠${NC} $1"
}

# Test 1: Basic Homepage Load
echo ""
echo "📱 Test 1: Homepage loads successfully"
response=$(curl -s -w "%{http_code}" -o /dev/null "$APP_URL/")
if [ "$response" = "200" ]; then
    test_passed "Homepage loads (HTTP $response)"
else
    test_failed "Homepage failed (HTTP $response)"
    exit 1
fi

# Test 2: HTTPS Redirect
echo ""
echo "🔒 Test 2: HTTP redirects to HTTPS"
response=$(curl -s -w "%{http_code}" -o /dev/null "http://receipt-splitter-demo.fly.dev/")
if [ "$response" = "301" ] || [ "$response" = "308" ]; then
    test_passed "HTTP redirects to HTTPS (HTTP $response)"
else
    test_warning "HTTP redirect status: $response"
fi

# Test 3: Static Files Work
echo ""
echo "🎨 Test 3: Static files are served"
response=$(curl -s -w "%{http_code}" -o /dev/null "$APP_URL/static/css/styles.css")
if [ "$response" = "200" ]; then
    test_passed "CSS static file loads (HTTP $response)"
else
    test_failed "Static file failed (HTTP $response)"
fi

# Test 4: Media Files Work
echo ""
echo "🖼️ Test 4: Media files are served"
response=$(curl -s -w "%{http_code}" -o /dev/null "$APP_URL/static/images/step_upload_mobile.png")
if [ "$response" = "200" ]; then
    test_passed "Media image loads (HTTP $response)"
else
    test_failed "Media file failed (HTTP $response)"
fi

# Test 5: Upload Endpoint Exists
echo ""
echo "📤 Test 5: Upload endpoint responds"
response=$(curl -s -w "%{http_code}" -o /dev/null "$APP_URL/upload/")
if [ "$response" = "405" ] || [ "$response" = "400" ]; then
    test_passed "Upload endpoint exists (HTTP $response - expected for GET)"
else
    test_warning "Upload endpoint response: HTTP $response"
fi

# Test 6: Admin Page Security
echo ""
echo "🛡️ Test 6: Admin requires authentication"
response=$(curl -s -w "%{http_code}" -o /dev/null "$APP_URL/admin/")
if [ "$response" = "302" ]; then
    test_passed "Admin redirects to login (HTTP $response)"
else
    test_warning "Admin page response: HTTP $response"
fi

# Test 7: Content Validation
echo ""
echo "💚 Test 7: Homepage content validation"
# Test if homepage contains expected content
content=$(curl -s "$APP_URL/")
if echo "$content" | grep -q "Communist Style"; then
    test_passed "Homepage contains expected content"
else
    test_failed "Homepage missing expected content"
fi

# Test 8: Response Headers
echo ""
echo "🔐 Test 8: Security headers present"
headers=$(curl -s -I "$APP_URL/")
if echo "$headers" | grep -q "X-Content-Type-Options"; then
    test_passed "Security headers present"
else
    test_warning "Some security headers missing"
fi

# Test 9: Database Connection (indirect)
echo ""
echo "🗄️ Test 9: Database connectivity (via Django admin)"
response=$(curl -s -w "%{http_code}" -o /dev/null "$APP_URL/admin/")
if [ "$response" = "302" ]; then
    test_passed "Database connection working (admin responds)"
else
    test_warning "Cannot verify database connection"
fi

# Test 10: Mobile Responsive Design
echo ""
echo "📱 Test 10: Mobile responsive images"
content=$(curl -s "$APP_URL/")
if echo "$content" | grep -q "step_upload_mobile.png"; then
    test_passed "Mobile responsive images configured"
else
    test_failed "Mobile images not found"
fi

echo ""
echo "======================================================"
echo "🎉 Deployment test completed!"
echo ""
echo "App URL: $APP_URL"
echo "Admin URL: $APP_URL/admin/"
echo ""
echo "To test manually:"
echo "1. Visit $APP_URL"
echo "2. Upload a receipt image"
echo "3. Test the complete workflow"
echo ""