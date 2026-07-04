from ninja import NinjaAPI, Schema

api = NinjaAPI(title="Online Store API", version="1.0.0")


class HealthOut(Schema):
    status: str


@api.get("/health", response=HealthOut, tags=["health"], operation_id="health")
def health(request):
    """Liveness probe used to verify the API is up."""
    return {"status": "ok"}
