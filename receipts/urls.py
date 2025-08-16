from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_receipt, name='upload_receipt'),
    path('edit/<uuid:receipt_id>/', views.edit_receipt, name='edit_receipt'),
    path('update/<uuid:receipt_id>/', views.update_receipt, name='update_receipt'),
    path('finalize/<uuid:receipt_id>/', views.finalize_receipt, name='finalize_receipt'),
    path('r/<uuid:receipt_id>/', views.view_receipt, name='view_receipt'),
    path('claim/<uuid:receipt_id>/', views.claim_item, name='claim_item'),
    path('unclaim/<uuid:receipt_id>/<int:claim_id>/', views.unclaim_item, name='unclaim_item'),
]