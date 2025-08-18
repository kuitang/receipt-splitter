from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_receipt, name='upload_receipt'),
    path('edit/<str:receipt_slug>/', views.edit_receipt, name='edit_receipt'),
    path('update/<str:receipt_slug>/', views.update_receipt, name='update_receipt'),
    path('finalize/<str:receipt_slug>/', views.finalize_receipt, name='finalize_receipt'),
    path('r/<str:receipt_slug>/', views.view_receipt, name='view_receipt'),
    path('claim/<str:receipt_slug>/', views.claim_item, name='claim_item'),
    path('claim/<str:receipt_slug>/status/', views.get_claim_status, name='get_claim_status'),
    # path('unclaim/<str:receipt_slug>/<int:claim_id>/', views.unclaim_item, name='unclaim_item'),  # REMOVED: Violates total claims protocol
    path('status/<str:receipt_slug>/', views.check_processing_status, name='check_processing_status'),
    path('content/<str:receipt_slug>/', views.get_receipt_content, name='get_receipt_content'),
    path('image/<str:receipt_slug>/', views.serve_receipt_image, name='serve_receipt_image'),
]