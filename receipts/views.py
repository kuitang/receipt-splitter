from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django_ratelimit.decorators import ratelimit
from django.core.files.base import ContentFile
from django.core.signing import Signer, BadSignature
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import escape
from django.conf import settings
from decimal import Decimal
import json
import base64
from datetime import datetime
import os
import hashlib

from .models import Receipt, LineItem, Claim, ActiveViewer
from .ocr_service import process_receipt_with_ocr
from .async_processor import process_receipt_async, create_placeholder_receipt
from .validation import validate_receipt_balance
from .image_storage import get_receipt_image_from_memory
from .validators import FileUploadValidator, InputValidator


# Access Control Functions
def create_edit_token(receipt_id, session_key):
    """Create a secure edit token for a receipt"""
    signer = Signer()
    data = f"{receipt_id}:{session_key}"
    return signer.sign(data)


def verify_edit_permission(request, receipt):
    """Verify user has permission to edit receipt"""
    if receipt.is_finalized:
        return False
    
    # Check if user uploaded this receipt (stored in session)
    if request.session.get('receipt_id') == str(receipt.id):
        return True
    
    # Check for edit token
    stored_token = request.session.get(f'edit_token_{receipt.id}')
    if not stored_token:
        return False
    
    try:
        signer = Signer()
        unsigned = signer.unsign(stored_token)
        receipt_id, session_key = unsigned.split(':')
        return str(receipt.id) == receipt_id and request.session.session_key == session_key
    except (BadSignature, ValueError):
        return False


def index(request):
    return render(request, 'receipts/index.html')


@ratelimit(key='ip', rate='10/m', method='POST')
@require_http_methods(["POST"])
def upload_receipt(request):
    uploader_name = request.POST.get('uploader_name', '').strip()
    receipt_image = request.FILES.get('receipt_image')
    
    # Basic validation to maintain backward compatibility with tests
    if not uploader_name or len(uploader_name) < 2 or len(uploader_name) > 50:
        messages.error(request, 'Please provide a valid name (2-50 characters)')
        return HttpResponse('Invalid name', status=400)
    
    if not receipt_image:
        messages.error(request, 'Please upload a receipt image')
        return HttpResponse('No image provided', status=400)
    
    if receipt_image.size == 0:
        messages.error(request, 'Image file is empty')
        return HttpResponse('Empty file', status=400)
    
    if receipt_image.size > 10 * 1024 * 1024:
        messages.error(request, 'Image size must be less than 10MB')
        return HttpResponse('File too large', status=413)
    
    # Comprehensive file validation using FileUploadValidator
    try:
        receipt_image = FileUploadValidator.validate_image_file(receipt_image)
    except ValidationError as e:
        messages.error(request, str(e))
        return HttpResponse(str(e), status=400)
    
    # Escape HTML to prevent XSS
    uploader_name = escape(uploader_name)
    
    # Create placeholder receipt immediately
    receipt = create_placeholder_receipt(uploader_name, receipt_image)
    
    # Store session info and create edit token
    request.session['uploader_name'] = uploader_name
    request.session['receipt_id'] = str(receipt.id)
    
    # Create edit token for this receipt
    if not request.session.session_key:
        request.session.create()
    edit_token = create_edit_token(receipt.id, request.session.session_key)
    request.session[f'edit_token_{receipt.id}'] = edit_token
    
    # Start async processing
    process_receipt_async(receipt.id, receipt_image)
    
    # Redirect to edit page using slug (will show loading state)
    return redirect('edit_receipt_by_slug', receipt_slug=receipt.slug)


def edit_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    
    if receipt.is_finalized:
        return redirect('view_receipt_by_slug', receipt_slug=receipt.slug)
    
    if not verify_edit_permission(request, receipt):
        messages.error(request, 'You do not have permission to edit this receipt')
        return redirect('index')
    
    return render(request, 'receipts/edit_async.html', {
        'receipt': receipt,
        'items': receipt.items.all(),
        'is_processing': receipt.processing_status in ['pending', 'processing']
    })


@ratelimit(key='ip', rate='30/m', method='POST')
@require_http_methods(["POST"])
def update_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    
    if receipt.is_finalized:
        return JsonResponse({'error': 'Receipt is already finalized'}, status=400)
    
    if not verify_edit_permission(request, receipt):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    
    try:
        data = json.loads(request.body)
        
        # Validate input data using InputValidator
        try:
            validated_data = InputValidator.validate_receipt_data(data)
        except ValidationError as e:
            # Return validation errors but don't block saving
            validation_errors = e.messages if hasattr(e, 'messages') else [str(e)]
        else:
            validated_data = data
            validation_errors = []
        
        # Validate the receipt balance
        is_valid, balance_errors = validate_receipt_balance(data)
        if balance_errors:
            if isinstance(validation_errors, list):
                validation_errors.extend(balance_errors.values())
            else:
                validation_errors = balance_errors
        
        # Always save the data (even if invalid) so user doesn't lose work
        receipt.restaurant_name = validated_data.get('restaurant_name', receipt.restaurant_name)
        receipt.subtotal = validated_data.get('subtotal', receipt.subtotal)
        receipt.tax = validated_data.get('tax', receipt.tax)
        receipt.tip = validated_data.get('tip', receipt.tip)
        receipt.total = validated_data.get('total', receipt.total)
        receipt.save()
        
        receipt.items.all().delete()
        
        for item_data in validated_data.get('items', []):
            line_item = LineItem.objects.create(
                receipt=receipt,
                name=item_data['name'],  # Already validated and escaped
                quantity=item_data['quantity'],  # Already validated
                unit_price=item_data['unit_price'],  # Already validated as Decimal
                total_price=item_data['total_price']  # Already validated as Decimal
            )
            line_item.calculate_prorations()
            line_item.save()
        
        # Return validation status along with success
        response = {'success': True, 'is_balanced': is_valid}
        if validation_errors:
            response['validation_errors'] = validation_errors if isinstance(validation_errors, dict) else {'errors': validation_errors}
        
        return JsonResponse(response)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
def finalize_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    
    if receipt.is_finalized:
        return JsonResponse({'error': 'Receipt is already finalized'}, status=400)
    
    if request.session.get('receipt_id') != str(receipt_id):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Validate the receipt before finalizing
    receipt_data = {
        'subtotal': str(receipt.subtotal),
        'tax': str(receipt.tax),
        'tip': str(receipt.tip),
        'total': str(receipt.total),
        'items': [
            {
                'name': item.name,
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'total_price': str(item.total_price)
            }
            for item in receipt.items.all()
        ]
    }
    
    is_valid, validation_errors = validate_receipt_balance(receipt_data)
    
    if not is_valid:
        # Don't allow finalization if receipt doesn't balance
        error_message = "Receipt doesn't balance. Please fix the following issues:\n"
        if validation_errors:
            for key, value in validation_errors.items():
                if key == 'items':
                    for item_error in value:
                        error_message += f"- {item_error['message']}\n"
                elif key != 'warnings':
                    error_message += f"- {value}\n"
        
        return JsonResponse({
            'error': error_message,
            'validation_errors': validation_errors
        }, status=400)
    
    receipt.is_finalized = True
    receipt.save()
    
    return JsonResponse({
        'success': True,
        'share_url': request.build_absolute_uri(receipt.get_absolute_url())
    })


def view_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    
    viewer_name = request.session.get(f'viewer_name_{receipt_id}')
    is_uploader = request.session.get('receipt_id') == str(receipt_id)
    
    if request.method == 'POST' and not viewer_name and not is_uploader:
        name = request.POST.get('viewer_name', '').strip()
        
        # Validate viewer name using InputValidator
        try:
            name = InputValidator.validate_name(name, field_name="Your name")
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('view_receipt_by_slug', receipt_slug=receipt.slug)
        
        existing_names = list(receipt.viewers.values_list('viewer_name', flat=True))
        existing_names.extend(receipt.items.filter(claims__isnull=False).values_list('claims__claimer_name', flat=True))
        
        if name in existing_names:
            # Create session if needed for suggestion
            if not request.session.session_key:
                request.session.create()
            
            suggestions = [
                f"{name} 2",
                f"{name}_{request.session.session_key[:4]}",
                f"{name} (Guest)"
            ]
            return render(request, 'receipts/name_collision.html', {
                'receipt': receipt,
                'original_name': name,
                'suggestions': suggestions
            })
        
        request.session[f'viewer_name_{receipt_id}'] = name
        viewer_name = name
        
        # Ensure session has a key
        if not request.session.session_key:
            request.session.create()
        
        ActiveViewer.objects.update_or_create(
            receipt=receipt,
            session_id=request.session.session_key,
            defaults={'viewer_name': name}
        )
    
    items_with_claims = []
    for item in receipt.items.all():
        claims = item.claims.all()
        items_with_claims.append({
            'item': item,
            'claims': claims,
            'available_quantity': item.get_available_quantity()
        })
    
    my_claims = []
    my_total = Decimal('0')
    
    if viewer_name:
        # Ensure session has a key for filtering claims
        if not request.session.session_key:
            request.session.create()
        
        my_claims = Claim.objects.filter(
            line_item__receipt=receipt,
            session_id=request.session.session_key
        )
        my_total = sum(claim.get_share_amount() for claim in my_claims)
    
    # Calculate participant totals
    all_claims = Claim.objects.filter(line_item__receipt=receipt)
    participant_totals = {}
    for claim in all_claims:
        name = claim.claimer_name
        if name not in participant_totals:
            participant_totals[name] = Decimal('0')
        participant_totals[name] += claim.get_share_amount()
    
    # Calculate total claimed and unclaimed
    total_claimed = sum(participant_totals.values())
    total_unclaimed = receipt.total - total_claimed
    
    # Sort participants by name for consistent display
    participant_list = sorted([
        {'name': name, 'amount': amount}
        for name, amount in participant_totals.items()
    ], key=lambda x: x['name'])
    
    return render(request, 'receipts/view.html', {
        'receipt': receipt,
        'items_with_claims': items_with_claims,
        'viewer_name': viewer_name or (receipt.uploader_name if is_uploader else None),
        'is_uploader': is_uploader,
        'my_claims': my_claims,
        'my_total': my_total,
        'show_name_form': not viewer_name and not is_uploader,
        'participant_totals': participant_list,
        'total_claimed': total_claimed,
        'total_unclaimed': total_unclaimed,
        'share_url': request.build_absolute_uri(receipt.get_absolute_url())
    })


@ratelimit(key='ip', rate='15/m', method='POST')
@require_http_methods(["POST"])
def claim_item(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    
    if not receipt.is_finalized:
        return JsonResponse({'error': 'Receipt must be finalized first'}, status=400)
    
    viewer_name = request.session.get(f'viewer_name_{receipt_id}')
    if not viewer_name:
        return JsonResponse({'error': 'Please enter your name first'}, status=400)
    
    try:
        data = json.loads(request.body)
        line_item_id = data.get('line_item_id')
        quantity = int(data.get('quantity', 1))
        
        line_item = get_object_or_404(LineItem, id=line_item_id, receipt=receipt)
        
        available = line_item.get_available_quantity()
        if quantity > available:
            return JsonResponse({'error': f'Only {available} available'}, status=400)
        
        # Ensure session has a key
        if not request.session.session_key:
            request.session.create()
        
        existing_claim = Claim.objects.filter(
            line_item=line_item,
            session_id=request.session.session_key
        ).first()
        
        if existing_claim:
            existing_claim.quantity_claimed = quantity
            existing_claim.claimer_name = viewer_name  # Already escaped from session
            existing_claim.save()
        else:
            Claim.objects.create(
                line_item=line_item,
                claimer_name=viewer_name,  # Already escaped from session
                quantity_claimed=quantity,
                session_id=request.session.session_key
            )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["DELETE"])
def unclaim_item(request, receipt_id, claim_id):
    claim = get_object_or_404(Claim, id=claim_id)
    
    # Ensure session has a key for comparison
    if not request.session.session_key:
        request.session.create()
    
    if claim.session_id != request.session.session_key:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if not claim.is_within_grace_period():
        return JsonResponse({'error': 'Grace period expired'}, status=400)
    
    claim.delete()
    return JsonResponse({'success': True})


def check_processing_status(request, receipt_id):
    """Check the processing status of a receipt"""
    receipt = get_object_or_404(Receipt, id=receipt_id)
    
    return JsonResponse({
        'status': receipt.processing_status,
        'error': receipt.processing_error,
        'restaurant_name': receipt.restaurant_name,
        'total': str(receipt.total),
        'items_count': receipt.items.count()
    })


def get_receipt_content(request, receipt_id):
    """Get the receipt content partial for HTMX"""
    receipt = get_object_or_404(Receipt, id=receipt_id)
    
    # Only return content if processing is complete
    if receipt.processing_status != 'completed':
        return HttpResponse("")
    
    return render(request, 'receipts/partials/receipt_content.html', {
        'receipt': receipt,
        'items': receipt.items.all()
    })


# Slug-based wrapper functions for backward compatibility
def edit_receipt_by_slug(request, receipt_slug):
    """Wrapper to support slug-based URLs"""
    receipt = get_object_or_404(Receipt, slug=receipt_slug)
    return edit_receipt(request, receipt.id)


def update_receipt_by_slug(request, receipt_slug):
    """Wrapper to support slug-based URLs"""
    receipt = get_object_or_404(Receipt, slug=receipt_slug)
    return update_receipt(request, receipt.id)


def finalize_receipt_by_slug(request, receipt_slug):
    """Wrapper to support slug-based URLs"""
    receipt = get_object_or_404(Receipt, slug=receipt_slug)
    return finalize_receipt(request, receipt.id)


def view_receipt_by_slug(request, receipt_slug):
    """Wrapper to support slug-based URLs"""
    receipt = get_object_or_404(Receipt, slug=receipt_slug)
    return view_receipt(request, receipt.id)


def claim_item_by_slug(request, receipt_slug):
    """Wrapper to support slug-based URLs"""
    receipt = get_object_or_404(Receipt, slug=receipt_slug)
    return claim_item(request, receipt.id)


def unclaim_item_by_slug(request, receipt_slug, claim_id):
    """Wrapper to support slug-based URLs"""
    receipt = get_object_or_404(Receipt, slug=receipt_slug)
    return unclaim_item(request, receipt.id, claim_id)


def check_processing_status_by_slug(request, receipt_slug):
    """Wrapper to support slug-based URLs"""
    receipt = get_object_or_404(Receipt, slug=receipt_slug)
    return check_processing_status(request, receipt.id)


def get_receipt_content_by_slug(request, receipt_slug):
    """Wrapper to support slug-based URLs"""
    receipt = get_object_or_404(Receipt, slug=receipt_slug)
    return get_receipt_content(request, receipt.id)


def serve_receipt_image(request, receipt_id):
    """
    Serve receipt image from memory.
    Only accessible to the uploader during editing.
    """
    receipt = get_object_or_404(Receipt, id=receipt_id)
    
    # Check if user is the uploader (for security)
    is_uploader = request.session.get('receipt_id') == str(receipt_id)
    if not is_uploader and not receipt.is_finalized:
        # Only uploader can see image during editing
        return HttpResponse(status=403)
    
    # Get image from memory
    image_bytes, content_type = get_receipt_image_from_memory(receipt_id)
    
    if image_bytes:
        response = HttpResponse(image_bytes, content_type=content_type)
        response['Cache-Control'] = 'private, max-age=3600'  # Cache for 1 hour
        return response
    
    # Return 404 if image not found
    return HttpResponse(status=404)


def serve_receipt_image_by_slug(request, receipt_slug):
    """Wrapper to support slug-based URLs"""
    receipt = get_object_or_404(Receipt, slug=receipt_slug)
    return serve_receipt_image(request, receipt.id)


def ratelimit_exceeded(request, exception):
    """Handle rate limit exceeded responses"""
    return JsonResponse({
        'error': 'Rate limit exceeded. Please try again later.'
    }, status=429)