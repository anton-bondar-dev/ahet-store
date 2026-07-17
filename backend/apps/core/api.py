from ninja import NinjaAPI, Schema

from apps.analytics.api import router as analytics_router
from apps.accounts.api import router as accounts_router
from apps.accounts.profile_api import router as profile_router
from apps.cart.api import router as cart_router
from apps.catalog.api import router as catalog_router
from apps.catalog.viewed_api import router as viewed_router
from apps.orders.api import router as orders_router
from apps.reviews.api import router as reviews_router
from apps.support.api import router as support_router

api = NinjaAPI(title="Online Store API", version="1.0.0")


class HealthOut(Schema):
    status: str


@api.get("/health", response=HealthOut, tags=["health"], operation_id="health")
def health(request):
    """Liveness probe used to verify the API is up."""
    return {"status": "ok"}


api.add_router("/catalog", catalog_router)
api.add_router("/products", viewed_router)
api.add_router("/products", reviews_router)
api.add_router("/cart", cart_router)
api.add_router("/orders", orders_router)
api.add_router("/auth", accounts_router)
api.add_router("/accounts", profile_router)
api.add_router("/support", support_router)
api.add_router("/analytics", analytics_router)
