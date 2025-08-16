from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import json
import base64
from datetime import datetime
import os

from .models import Receipt, LineItem, Claim, ActiveViewer
from .ocr_service import process_receipt_with_ocr
from .async_processor import process_receipt_async, create_placeholder_receipt
from .validation import validate_receipt_balance


def index(request):
    sample_images = []
    return render(request, 'receipts/index.html', {
        'sample_images': sample_images
    })


@require_http_methods(["POST"])
def upload_receipt(request):
    uploader_name = request.POST.get('uploader_name', '').strip()
    receipt_image = request.FILES.get('receipt_image')
    
    if not uploader_name or len(uploader_name) < 2 or len(uploader_name) > 50:
        messages.error(request, 'Please provide a valid name (2-50 characters)')
        return redirect('index')
    
    if not receipt_image:
        messages.error(request, 'Please upload a receipt image')
        return redirect('index')
    
    if receipt_image.size > 10 * 1024 * 1024:
        messages.error(request, 'Image size must be less than 10MB')
        return redirect('index')
    
    # Create placeholder receipt immediately
    receipt = create_placeholder_receipt(uploader_name, receipt_image)
    
    # Store session info
    request.session['uploader_name'] = uploader_name
    request.session['receipt_id'] = str(receipt.id)
    
    # Start async processing
    process_receipt_async(receipt.id, receipt_image)
    
    # Redirect to edit page using slug (will show loading state)
    return redirect('edit_receipt_by_slug', receipt_slug=receipt.slug)


def edit_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    
    if receipt.is_finalized:
        return redirect('view_receipt_by_slug', receipt_slug=receipt.slug)
    
    if request.session.get('receipt_id') != str(receipt_id):
        messages.error(request, 'You can only edit receipts you uploaded')
        return redirect('index')
    
    return render(request, 'receipts/edit_async.html', {
        'receipt': receipt,
        'items': receipt.items.all(),
        'is_processing': receipt.processing_status in ['pending', 'processing']
    })


@require_http_methods(["POST"])
def update_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    
    if receipt.is_finalized:
        return JsonResponse({'error': 'Receipt is already finalized'}, status=400)
    
    if request.session.get('receipt_id') != str(receipt_id):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        
        # Validate the receipt data before saving
        is_valid, validation_errors = validate_receipt_balance(data)
        
        # Always save the data (even if invalid) so user doesn't lose work
        receipt.restaurant_name = data.get('restaurant_name', receipt.restaurant_name)
        receipt.subtotal = Decimal(str(data.get('subtotal', receipt.subtotal)))
        receipt.tax = Decimal(str(data.get('tax', receipt.tax)))
        receipt.tip = Decimal(str(data.get('tip', receipt.tip)))
        receipt.total = Decimal(str(data.get('total', receipt.total)))
        receipt.save()
        
        receipt.items.all().delete()
        
        for item_data in data.get('items', []):
            line_item = LineItem.objects.create(
                receipt=receipt,
                name=item_data['name'],
                quantity=int(item_data['quantity']),
                unit_price=Decimal(str(item_data['unit_price'])),
                total_price=Decimal(str(item_data['total_price']))
            )
            line_item.calculate_prorations()
            line_item.save()
        
        # Return validation status along with success
        response = {'success': True, 'is_balanced': is_valid}
        if validation_errors:
            response['validation_errors'] = validation_errors
        
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
        
        if not name or len(name) < 2 or len(name) > 50:
            messages.error(request, 'Please provide a valid name (2-50 characters)')
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
            existing_claim.save()
        else:
            Claim.objects.create(
                line_item=line_item,
                claimer_name=viewer_name,
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