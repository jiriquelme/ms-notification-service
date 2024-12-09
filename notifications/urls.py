from django.urls import path
from .views import SendNotificationView, GenerarQRView

urlpatterns = [
    path('send/', SendNotificationView.as_view(), name='send-notification'),
    path('generar-qr/', GenerarQRView.as_view(), name='generar-qr'),
]
