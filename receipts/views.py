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
import logging

logger = logging.getLogger(__name__)

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
        return redirect('edit_receipt', receipt_slug=receipt.slug)
        
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


def edit_receipt(request, receipt_slug):
    """Edit receipt by slug"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        messages.error(request, 'Receipt not found')
        return redirect('index')
    
    if receipt.is_finalized:
        return redirect('view_receipt', receipt_slug=receipt.slug)
    
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


@rate_limit_edit
@require_http_methods(["POST"])
def update_receipt(request, receipt_slug):
    """Update receipt data via AJAX"""
    try:
        receipt = receipt_service.get_receipt_by_slug(receipt_slug)
        
        if not receipt:
            return JsonResponse({'error': 'Receipt not found'}, status=404)
        
        data = json.loads(request.body)
        
        # Get session context using new system
        user_context = request.user_context(receipt.id)
        session_context = user_context.get_session_context()
        
        # Update through service
        result = receipt_service.update_receipt(str(receipt.id), data, session_context)
        
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


@rate_limit_finalize
@require_http_methods(["POST"])
def finalize_receipt(request, receipt_slug):
    """Finalize a receipt"""
    try:
        receipt = receipt_service.get_receipt_by_slug(receipt_slug)
        
        if not receipt:
            return JsonResponse({'error': 'Receipt not found'}, status=404)
        
        user_context = request.user_context(receipt.id)
        session_context = user_context.get_session_context()
        
        result = receipt_service.finalize_receipt(str(receipt.id), session_context)
        
        # Build absolute URL for sharing
        receipt = receipt_service.get_receipt_by_id(str(receipt.id))
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


@rate_limit_view
def view_receipt(request, receipt_slug):
    """View and claim items on a receipt"""
    try:
        # Single optimized query instead of double fetch!
        receipt_data = receipt_service.get_receipt_for_viewing_by_slug(receipt_slug)
        receipt = receipt_data['receipt']
        receipt_id = str(receipt.id)
        
        user_context = request.user_context(receipt_id)
        viewer_name = user_context.name
        is_uploader = user_context.is_uploader
        
        # For uploaders, use their uploader name as viewer name
        if is_uploader and not viewer_name:
            viewer_name = receipt.uploader_name
        
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
            
            # Check for name collision using already-fetched data (no extra queries!)
            existing_names = receipt_service.get_existing_names(receipt_id, receipt_data)
            
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
        
        # Extract user's claims from already-fetched data (no additional queries!)
        my_claims = []
        my_total = Decimal('0')
        my_claims_by_item = {}  # Map item_id -> quantity_claimed
        is_user_finalized = False
        
        if viewer_name:
            # Extract claims from prefetched data instead of making 3 separate queries
            for item_data in receipt_data['items_with_claims']:
                item = item_data['item']
                for claim in item_data['claims']:
                    # Check if this claim belongs to the current viewer
                    if claim.claimer_name == viewer_name:
                        my_claims.append(claim)
                        my_claims_by_item[str(item.id)] = claim.quantity_claimed
                        # Calculate share amount inline (avoid another query)
                        unit_price = item.total_price / item.quantity if item.quantity else Decimal('0')
                        prorated_tax = item.prorated_tax / item.quantity if item.quantity else Decimal('0')
                        prorated_tip = item.prorated_tip / item.quantity if item.quantity else Decimal('0')
                        my_total += claim.quantity_claimed * (unit_price + prorated_tax + prorated_tip)
                        # Check if claim is finalized
                        if claim.is_finalized:
                            is_user_finalized = True
        
        # Add user's existing claims to items_with_claims data
        for item_data in receipt_data['items_with_claims']:
            item_id = str(item_data['item'].id)
            item_data['my_existing_claim'] = my_claims_by_item.get(item_id, 0)
        
        # Prepare context
        context = {
            'receipt': receipt,
            'items_with_claims': receipt_data['items_with_claims'],
            'viewer_name': viewer_name,
            'is_uploader': is_uploader,
            'my_claims': my_claims,
            'my_claims_by_item': my_claims_by_item,
            'my_total': my_total,
            'is_user_finalized': is_user_finalized,
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
        # Log the full exception with traceback
        logger.exception(f"Exception in view_receipt for slug '{receipt_slug}'")
        
        # Return a proper error response instead of redirecting
        # This prevents confusing redirects and maintains REST principles
        return HttpResponse('An error occurred while loading the receipt. Please try again later.', status=500)


@rate_limit_claim
@require_http_methods(["POST"])
def claim_item(request, receipt_slug):
    """Finalize claims on a receipt (new total claims protocol)"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    
    receipt_id = str(receipt.id)
    user_context = request.user_context(receipt_id)
    viewer_name = user_context.name
    
    if not viewer_name:
        # Check if uploader
        if user_context.is_uploader:
            viewer_name = receipt.uploader_name
    
    if not viewer_name:
        return JsonResponse({'error': 'Please enter your name first'}, status=400)
    
    
    try:
        data = json.loads(request.body)
        
        # New protocol: accept multiple claims or single claim
        if 'claims' in data:
            # New format: {"claims": [{"line_item_id": "123", "quantity": 2}]}
            claims_data = data['claims']
        else:
            # Legacy format: {"line_item_id": "123", "quantity": 1}
            claims_data = [{
                'line_item_id': data.get('line_item_id'),
                'quantity': int(data.get('quantity', 1))
            }]
        
        
        # Finalize all claims at once
        result = claim_service.finalize_claims(
            receipt_id=receipt_id,
            claimer_name=viewer_name,
            claims_data=claims_data,
            session_id=user_context.session_id
        )
        
        
        return JsonResponse(result)
        
    except ReceiptNotFinalizedError:
        return JsonResponse({'error': 'Receipt must be finalized first'}, status=400)
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def check_processing_status(request, receipt_slug):
    """Check if receipt OCR processing is complete"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    
    return JsonResponse({
        'status': receipt.processing_status,
        'is_complete': receipt.processing_status == 'completed',
        'error': receipt.processing_error if receipt.processing_status == 'failed' else None
    })


@rate_limit_view
@require_http_methods(["GET"])
def get_claim_status(request, receipt_slug):
    """Get current claim status for real-time updates"""
    try:
        # Single optimized query instead of double fetch!
        receipt_data = receipt_service.get_receipt_for_viewing_by_slug(receipt_slug)
        receipt = receipt_data['receipt']
        receipt_id = str(receipt.id)
        
        # Get current user context
        user_context = request.user_context(receipt_id)
        viewer_name = user_context.name
        
        
        if not viewer_name and user_context.is_uploader:
            viewer_name = receipt.uploader_name
        
        # Calculate user's total from prefetched data (no extra queries!)
        my_total = Decimal('0')
        is_user_finalized = False
        if viewer_name:
            # Extract from already-fetched receipt_data instead of making 2 queries
            for item_data in receipt_data['items_with_claims']:
                item = item_data['item']
                for claim in item_data['claims']:
                    if claim.claimer_name == viewer_name:
                        # Calculate share amount inline
                        unit_price = item.total_price / item.quantity if item.quantity else Decimal('0')
                        prorated_tax = item.prorated_tax / item.quantity if item.quantity else Decimal('0')
                        prorated_tip = item.prorated_tip / item.quantity if item.quantity else Decimal('0')
                        my_total += claim.quantity_claimed * (unit_price + prorated_tax + prorated_tip)
                        # Check finalization status
                        if claim.is_finalized and claim.session_id == user_context.session_id:
                            is_user_finalized = True
        
        # Prepare response data
        response_data = {
            'success': True,
            'viewer_name': viewer_name,
            'is_finalized': is_user_finalized,
            'participant_totals': [
                {'name': participant['name'], 'amount': float(participant['amount'])}
                for participant in receipt_data['participant_totals']
            ],
            'total_claimed': float(receipt_data['total_claimed']),
            'total_unclaimed': float(receipt_data['total_unclaimed']),
            'my_total': float(my_total),
            'items_with_claims': []
        }
        
        # Add item-level claim data
        for item_data in receipt_data['items_with_claims']:
            item_info = {
                'item_id': str(item_data['item'].id),
                'available_quantity': item_data['available_quantity'],
                'claims': [
                    {
                        'claimer_name': claim.claimer_name,
                        'quantity_claimed': claim.quantity_claimed
                    }
                    for claim in item_data['claims']
                ]
            }
            response_data['items_with_claims'].append(item_info)
        
        return JsonResponse(response_data)
        
    except ReceiptNotFoundError:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def unclaim_item(request, receipt_slug, claim_id):
    """Unclaim an item by receipt slug"""
    if request.method in ['POST', 'DELETE']:
        receipt = receipt_service.get_receipt_by_slug(receipt_slug)
        
        if not receipt:
            return JsonResponse({'error': 'Receipt not found'}, status=404)
        
        receipt_id = str(receipt.id)
        user_context = request.user_context(receipt_id)
        if not user_context.session_id:
            return JsonResponse({'error': 'Session not found'}, status=400)
        
        viewer_name = user_context.name
        
        try:
            # Call service directly since claim_id is in URL
            success = claim_service.undo_claim(claim_id, user_context.session_id)
            
            if success:
                # Get updated totals
                my_total = claim_service.calculate_name_total(
                    receipt_id,
                    viewer_name
                ) if viewer_name else Decimal('0')
                
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


def get_receipt_content(request, receipt_slug):
    """Get the receipt content partial for HTMX"""
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return HttpResponse("", status=404)
    
    # Only return content if processing is complete
    if receipt.processing_status != 'completed':
        return HttpResponse("")
    
    return render(request, 'receipts/partials/receipt_content.html', {
        'receipt': receipt,
        'items': receipt.items.all()
    })


def serve_receipt_image(request, receipt_slug):
    """
    Serve receipt image from memory.
    Only accessible to the uploader during editing.
    """
    from .image_storage import get_receipt_image_from_memory
    
    receipt = receipt_service.get_receipt_by_slug(receipt_slug)
    
    if not receipt:
        return HttpResponse('Receipt not found', status=404)
    
    receipt_id = str(receipt.id)
    
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


def ratelimit_exceeded(request, exception):
    """Handle rate limit exceeded responses"""
    return JsonResponse({
        'error': 'Rate limit exceeded. Please try again later.'
    }, status=429)