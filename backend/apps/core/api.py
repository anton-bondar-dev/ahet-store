from ninja import NinjaAPI, Schema

from apps.cart.api import router as cart_router
from apps.catalog.api import router as catalog_router
from apps.orders.api import router as orders_router

api = NinjaAPI(title="Online Store API", version="1.0.0")


class HealthOut(Schema):
    status: str


@api.get("/health", response=HealthOut, tags=["health"], operation_id="health")
def health(request):
    """Liveness probe used to verify the API is up."""
    return {"status": "ok"}


api.add_router("/catalog", catalog_router)
api.add_router("/cart", cart_router)
api.add_router("/orders", orders_router)
