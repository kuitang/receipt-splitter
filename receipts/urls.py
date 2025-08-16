from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_receipt, name='upload_receipt'),
    # Support both UUID and slug for backward compatibility
    path('edit/<uuid:receipt_id>/', views.edit_receipt, name='edit_receipt'),
    path('edit/<str:receipt_slug>/', views.edit_receipt_by_slug, name='edit_receipt_by_slug'),
    path('update/<uuid:receipt_id>/', views.update_receipt, name='update_receipt'),
    path('update/<str:receipt_slug>/', views.update_receipt_by_slug, name='update_receipt_by_slug'),
    path('finalize/<uuid:receipt_id>/', views.finalize_receipt, name='finalize_receipt'),
    path('finalize/<str:receipt_slug>/', views.finalize_receipt_by_slug, name='finalize_receipt_by_slug'),
    path('r/<uuid:receipt_id>/', views.view_receipt, name='view_receipt'),
    path('r/<str:receipt_slug>/', views.view_receipt_by_slug, name='view_receipt_by_slug'),
    path('claim/<uuid:receipt_id>/', views.claim_item, name='claim_item'),
    path('claim/<str:receipt_slug>/', views.claim_item_by_slug, name='claim_item_by_slug'),
    path('unclaim/<uuid:receipt_id>/<int:claim_id>/', views.unclaim_item, name='unclaim_item'),
    path('unclaim/<str:receipt_slug>/<int:claim_id>/', views.unclaim_item_by_slug, name='unclaim_item_by_slug'),
    path('status/<uuid:receipt_id>/', views.check_processing_status, name='check_processing_status'),
    path('status/<str:receipt_slug>/', views.check_processing_status_by_slug, name='check_processing_status_by_slug'),
    path('content/<uuid:receipt_id>/', views.get_receipt_content, name='get_receipt_content'),
    path('content/<str:receipt_slug>/', views.get_receipt_content_by_slug, name='get_receipt_content_by_slug'),
    path('image/<uuid:receipt_id>/', views.serve_receipt_image, name='serve_receipt_image'),
    path('image/<str:receipt_slug>/', views.serve_receipt_image_by_slug, name='serve_receipt_image_by_slug'),
]