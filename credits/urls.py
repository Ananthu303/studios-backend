from rest_framework.routers import DefaultRouter

from .views import CreditPackViewSet, TransactionViewSet

router = DefaultRouter()
router.register("credit-packs", CreditPackViewSet, basename="credit-pack")
router.register("credit-transactions", TransactionViewSet, basename="credit-transaction")

urlpatterns = router.urls
