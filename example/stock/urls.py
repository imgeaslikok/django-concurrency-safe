from django.urls import path

from . import views

urlpatterns = [
    path("buy-bad/<str:sku>/", views.buy_bad, name="buy_bad"),
    path("buy-safe-db/<str:sku>/", views.buy_safe_db_lock, name="buy_safe_db_lock"),
    path("buy-safe-lock/<str:sku>/", views.buy_safe_lock, name="buy_safe_lock"),
]