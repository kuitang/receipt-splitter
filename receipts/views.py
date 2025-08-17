from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .decorators import rate_limit_upload, rate_limit_edit, rate_limit_view, rate_limit_claim, rate_limit_finalize
from django.core.exceptions import ValidationError
from django.conf import settings
from decimal import Decimal
import json

from .models import Receipt, LineItem, Claim, ActiveViewer
from .services import ReceiptService, ClaimService, ValidationPipeline
from .services.receipt_service import (
    ReceiptNotFoundError, 
    ReceiptAlreadyFinalizedError, 
    PermissionDeniedError
)
from .services.claim_service import (
    ClaimNotFoundError,
    InsufficientQuantityError,
    ReceiptNotFinalizedError,
    GracePeriodExpiredError
)


# Initialize services
receipt_service = ReceiptService()
claim_service = ClaimService()
validator = ValidationPipeline()


def index(request):
    """Home page"""
    return render(request, 'receipts/index.html')


@rate_limit_upload
@require_http_methods(["POST"])
def upload_receipt(request):
    """Handle receipt upload with OCR processing"""
    uploader_name = request.POST.get('uploader_name', '').strip()
    receipt_image = request.FILES.get('receipt_image')
    
    try:
        # Create receipt through service
        receipt = receipt_service.create_receipt(uploader_name, receipt_image)
        
        # Use new session management system
        user_context = request.user_context(receipt.id)
        user_context.mark_as_uploader()
        user_context.authenticate_as(uploader_name)
        edit_token = user_context.grant_edit_permission()
        
        # Create edit token in service for backwards compatibility
        receipt_service.create_edit_token(receipt.id, user_context.session_id)
        
        # Redirect to edit page
        return redirect('edit_receipt_by_slug', receipt_slug=receipt.slug)
        
    except ValidationError as e:
        # Check if this is a file size error
        error_message = str(e)
        if 'less than 10MB' in error_message or 'too large' in error_message.lower():
            messages.error(request, 'File too large')
            return HttpResponse('File too large', status=413)
        
        if hasattr(e, 'message_dict'):
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, error)
        else:
            messages.error(request, str(e))
        return HttpResponse('Validation error', status=400)
    except Exception as e:
        messages.error(request, f'Error uploading receipt: {str(e)}')
        return HttpResponse('Upload failed', status=500)


def edit_receipt(request, receipt_id):
    """Edit receipt page"""
    receipt = receipt_service.get_receipt_by_id(receipt_id)
    
    if not receipt:
        messages.error(request, 'Receipt not found')
        return redirect('index')
    
    if receipt.is_finalized:
        return redirect('view_receipt_by_slug', receipt_slug=receipt.slug)
    
    # Check edit permission using new session management
    user_context = request.user_context(receipt.id)
    
    if not user_context.can_edit:
        messages.error(request, 'You do not have permission to edit this receipt')
        return redirect('index')
    
    return render(request, 'receipts/edit_async.html', {
        'receipt': receipt,
        'items': receipt.items.all(),
        'is_processing': receipt.processing_status in ['pending', 'processing']
    })


def edit_receipt_by_slug(request, receipt_slug):
    """Edit receipt by slug - redirects to ID-based edit"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        messages.error(request, 'Receipt not found')
        return redirect('index')
    
    return edit_receipt(request, str(receipt.id))


@rate_limit_edit
@require_http_methods(["POST"])
def update_receipt(request, receipt_id):
    """Update receipt data via AJAX"""
    try:
        data = json.loads(request.body)
        
        # Get session context using new system
        user_context = request.user_context(receipt_id)
        session_context = user_context.get_session_context()
        
        # Update through service
        result = receipt_service.update_receipt(receipt_id, data, session_context)
        
        return JsonResponse(result)
        
    except ReceiptNotFoundError:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    except ReceiptAlreadyFinalizedError:
        return JsonResponse({'error': 'Receipt is already finalized'}, status=400)
    except PermissionDeniedError:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def update_receipt_by_slug(request, receipt_slug):
    """Update receipt by slug"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    
    return update_receipt(request, str(receipt.id))


@rate_limit_finalize
@require_http_methods(["POST"])
def finalize_receipt(request, receipt_id):
    """Finalize a receipt"""
    try:
        user_context = request.user_context(receipt_id)
        session_context = user_context.get_session_context()
        
        result = receipt_service.finalize_receipt(receipt_id, session_context)
        
        # Build absolute URL for sharing
        receipt = receipt_service.get_receipt_by_id(receipt_id)
        result['share_url'] = request.build_absolute_uri(receipt.get_absolute_url())
        
        return JsonResponse(result)
        
    except ReceiptNotFoundError:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    except ReceiptAlreadyFinalizedError:
        return JsonResponse({'error': 'Receipt is already finalized'}, status=400)
    except PermissionDeniedError:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    except ValidationError as e:
        error_message = str(e)
        validation_errors = {}
        
        if hasattr(e, 'params') and 'validation_errors' in e.params:
            validation_errors = e.params['validation_errors']
        
        return JsonResponse({
            'error': error_message,
            'validation_errors': validation_errors
        }, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def finalize_receipt_by_slug(request, receipt_slug):
    """Finalize receipt by slug"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    
    return finalize_receipt(request, str(receipt.id))


@rate_limit_view
def view_receipt(request, receipt_id):
    """View and claim items on a receipt"""
    try:
        receipt_data = receipt_service.get_receipt_for_viewing(receipt_id)
        receipt = receipt_data['receipt']
        
        user_context = request.user_context(receipt_id)
        viewer_name = user_context.name
        is_uploader = user_context.is_uploader
        
        # Handle name submission
        if request.method == 'POST' and not viewer_name and not is_uploader:
            name = request.POST.get('viewer_name', '').strip()
            
            try:
                validated_name = validator.validate_name(name, "Your name")
            except ValidationError as e:
                messages.error(request, str(e))
                # Re-render the same page with error instead of redirecting
                context = {
                    'receipt': receipt,
                    'items_with_claims': receipt_data['items_with_claims'],
                    'viewer_name': None,
                    'is_uploader': is_uploader,
                    'my_claims': [],
                    'my_total': Decimal('0'),
                    'show_name_form': True,
                    'participant_totals': receipt_data['participant_totals'],
                    'total_claimed': receipt_data['total_claimed'],
                    'total_unclaimed': receipt_data['total_unclaimed'],
                    'share_url': request.build_absolute_uri(receipt.get_absolute_url())
                }
                return render(request, 'receipts/view.html', context)
            
            # Check for name collision
            existing_names = receipt_service.get_existing_names(receipt_id)
            
            if validated_name in existing_names:
                suggestions = [
                    f"{validated_name} 2",
                    f"{validated_name}_{user_context.session_id[:4]}",
                    f"{validated_name} (Guest)"
                ]
                
                return render(request, 'receipts/name_collision.html', {
                    'receipt': receipt,
                    'original_name': validated_name,
                    'suggestions': suggestions
                })
            
            # Store viewer name using new system
            user_context.authenticate_as(validated_name)
            viewer_name = validated_name
            
            # Register viewer
            receipt_service.register_viewer(
                receipt_id, 
                validated_name, 
                user_context.session_id
            )
        
        # Get user's claims
        my_claims = []
        my_total = Decimal('0')
        
        if viewer_name and user_context.session_id:
            my_claims = claim_service.get_claims_for_session(
                receipt_id, 
                user_context.session_id
            )
            my_total = claim_service.calculate_session_total(
                receipt_id,
                user_context.session_id
            )
        
        # Prepare context
        context = {
            'receipt': receipt,
            'items_with_claims': receipt_data['items_with_claims'],
            'viewer_name': viewer_name or (receipt.uploader_name if is_uploader else None),
            'is_uploader': is_uploader,
            'my_claims': my_claims,
            'my_total': my_total,
            'show_name_form': not viewer_name and not is_uploader,
            'participant_totals': receipt_data['participant_totals'],
            'total_claimed': receipt_data['total_claimed'],
            'total_unclaimed': receipt_data['total_unclaimed'],
            'share_url': request.build_absolute_uri(receipt.get_absolute_url())
        }
        
        return render(request, 'receipts/view.html', context)
        
    except ReceiptNotFoundError:
        # Return 404 instead of redirecting for better REST behavior
        return HttpResponse('Receipt not found', status=404)
    except Exception as e:
        messages.error(request, f'Error viewing receipt: {str(e)}')
        return redirect('index')


def view_receipt_by_slug(request, receipt_slug):
    """View receipt by slug"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        messages.error(request, 'Receipt not found')
        return redirect('index')
    
    return view_receipt(request, str(receipt.id))


@rate_limit_claim
@require_http_methods(["POST"])
def claim_item(request, receipt_id):
    """Claim items on a receipt"""
    user_context = request.user_context(receipt_id)
    viewer_name = user_context.name
    
    if not viewer_name:
        # Check if uploader
        if user_context.is_uploader:
            receipt = receipt_service.get_receipt_by_id(receipt_id)
            if receipt:
                viewer_name = receipt.uploader_name
    
    if not viewer_name:
        return JsonResponse({'error': 'Please enter your name first'}, status=400)
    
    try:
        data = json.loads(request.body)
        line_item_id = data.get('line_item_id')
        quantity = int(data.get('quantity', 1))
        
        # Process claim through service
        claim = claim_service.claim_items(
            receipt_id=receipt_id,
            line_item_id=line_item_id,
            claimer_name=viewer_name,
            quantity=quantity,
            session_id=user_context.session_id
        )
        
        # Get updated totals
        my_total = claim_service.calculate_session_total(
            receipt_id,
            user_context.session_id
        )
        
        participant_totals = claim_service.get_participant_totals(receipt_id)
        
        return JsonResponse({
            'success': True,
            'claim_id': str(claim.id),
            'my_total': float(my_total),
            'participant_totals': {
                name: float(amount) 
                for name, amount in participant_totals.items()
            }
        })
        
    except ReceiptNotFinalizedError:
        return JsonResponse({'error': 'Receipt must be finalized first'}, status=400)
    except InsufficientQuantityError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def claim_item_by_slug(request, receipt_slug):
    """Claim item by receipt slug"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    
    return claim_item(request, str(receipt.id))


@require_http_methods(["POST", "DELETE"])
def undo_claim(request, receipt_id):
    """Undo a claim within grace period"""
    try:
        # Handle both POST with JSON body and our synthetic body from unclaim_item
        if request.body:
            data = json.loads(request.body)
            claim_id = data.get('claim_id')
        else:
            # Empty body - claim_id should be set by unclaim_item wrapper
            claim_id = None
        
        user_context = request.user_context(receipt_id)
        if not user_context.session_id:
            return JsonResponse({'error': 'Session not found'}, status=400)
        
        # Undo through service
        success = claim_service.undo_claim(claim_id, user_context.session_id)
        
        if success:
            # Get updated totals
            my_total = claim_service.calculate_session_total(
                receipt_id,
                user_context.session_id
            )
            
            participant_totals = claim_service.get_participant_totals(receipt_id)
            
            return JsonResponse({
                'success': True,
                'my_total': float(my_total),
                'participant_totals': {
                    name: float(amount)
                    for name, amount in participant_totals.items()
                }
            })
        else:
            return JsonResponse({'error': 'Failed to undo claim'}, status=400)
            
    except ClaimNotFoundError:
        return JsonResponse({'error': 'Claim not found'}, status=404)
    except PermissionError as e:
        return JsonResponse({'error': str(e)}, status=403)
    except GracePeriodExpiredError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def undo_claim_by_slug(request, receipt_slug):
    """Undo claim by receipt slug"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    
    return undo_claim(request, str(receipt.id))


@require_http_methods(["GET"])
def check_processing_status(request, receipt_id):
    """Check if receipt OCR processing is complete"""
    receipt = receipt_service.get_receipt_by_id(receipt_id)
    
    if not receipt:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    
    return JsonResponse({
        'status': receipt.processing_status,
        'is_complete': receipt.processing_status == 'completed',
        'error': receipt.processing_error if receipt.processing_status == 'failed' else None
    })


def check_processing_status_by_slug(request, receipt_slug):
    """Check processing status by slug"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    
    return check_processing_status(request, str(receipt.id))


@require_http_methods(["GET"])
def get_receipt_image(request, receipt_id):
    """Get receipt image from memory storage"""
    from .image_storage import get_receipt_image_from_memory
    
    receipt = receipt_service.get_receipt_by_id(receipt_id)
    
    if not receipt:
        return HttpResponse('Receipt not found', status=404)
    
    image_data = get_receipt_image_from_memory(receipt_id)
    
    if image_data:
        return HttpResponse(image_data, content_type='image/jpeg')
    else:
        return HttpResponse('Image not found', status=404)


def get_receipt_image_by_slug(request, receipt_slug):
    """Get receipt image by slug"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return HttpResponse('Receipt not found', status=404)
    
    return get_receipt_image(request, str(receipt.id))


# Legacy unclaim_item functions for URL compatibility
def unclaim_item(request, receipt_id, claim_id):
    """Legacy unclaim function - calls claim service directly"""
    if request.method in ['POST', 'DELETE']:
        user_context = request.user_context(receipt_id)
        if not user_context.session_id:
            return JsonResponse({'error': 'Session not found'}, status=400)
        
        try:
            # Call service directly since claim_id is in URL
            success = claim_service.undo_claim(claim_id, user_context.session_id)
            
            if success:
                # Get updated totals
                my_total = claim_service.calculate_session_total(
                    receipt_id,
                    user_context.session_id
                )
                
                participant_totals = claim_service.get_participant_totals(receipt_id)
                
                return JsonResponse({
                    'success': True,
                    'my_total': float(my_total),
                    'participant_totals': {
                        name: float(amount)
                        for name, amount in participant_totals.items()
                    }
                })
            else:
                return JsonResponse({'error': 'Failed to undo claim'}, status=400)
                
        except ClaimNotFoundError:
            return JsonResponse({'error': 'Claim not found'}, status=404)
        except PermissionError as e:
            return JsonResponse({'error': str(e)}, status=403)
        except GracePeriodExpiredError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def unclaim_item_by_slug(request, receipt_slug, claim_id):
    """Legacy unclaim by slug - redirects to undo_claim"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    
    return unclaim_item(request, str(receipt.id), claim_id)


def get_receipt_content(request, receipt_id):
    """Get the receipt content partial for HTMX"""
    receipt = receipt_service.get_receipt_by_id(receipt_id)
    
    if not receipt:
        return HttpResponse("", status=404)
    
    # Only return content if processing is complete
    if receipt.processing_status != 'completed':
        return HttpResponse("")
    
    return render(request, 'receipts/partials/receipt_content.html', {
        'receipt': receipt,
        'items': receipt.items.all()
    })


def get_receipt_content_by_slug(request, receipt_slug):
    """Get receipt content by slug"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return HttpResponse("", status=404)
    
    return get_receipt_content(request, str(receipt.id))


def serve_receipt_image(request, receipt_id):
    """
    Serve receipt image from memory.
    Only accessible to the uploader during editing.
    """
    from .image_storage import get_receipt_image_from_memory
    
    receipt = receipt_service.get_receipt_by_id(receipt_id)
    
    if not receipt:
        return HttpResponse('Receipt not found', status=404)
    
    # Check if user is the uploader (for security)
    user_context = request.user_context(receipt_id)
    if not user_context.is_uploader and not receipt.is_finalized:
        # Only uploader can see image during editing
        return HttpResponse(status=403)
    
    # Get image from memory
    image_bytes, content_type = get_receipt_image_from_memory(receipt_id)
    
    if image_bytes:
        return HttpResponse(image_bytes, content_type=content_type)
    else:
        return HttpResponse('Image not found in memory', status=404)


def serve_receipt_image_by_slug(request, receipt_slug):
    """Serve receipt image by slug"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return HttpResponse('Receipt not found', status=404)
    
    return serve_receipt_image(request, str(receipt.id))


def ratelimit_exceeded(request, exception):
    """Handle rate limit exceeded responses"""
    return JsonResponse({
        'error': 'Rate limit exceeded. Please try again later.'
    }, status=429)