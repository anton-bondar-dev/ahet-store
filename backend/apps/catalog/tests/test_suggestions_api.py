"""GET /api/catalog/suggestions — autocomplete.

Public. A blank/whitespace query short-circuits to an empty list before any DB
work. The scored trigram path is Postgres-only (WORD_SIMILARITY) and raises on
sqlite, so it is skipped with a reason.
"""
import pytest

URL = "/api/catalog/suggestions"


@pytest.mark.django_db
class TestSuggestions:
    def test_missing_query_returns_empty(self, api):
        resp = api.get(URL)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_blank_query_returns_empty(self, api, product_factory):
        product_factory()
        assert api.get(URL, {"q": ""}).json() == []

    def test_whitespace_query_returns_empty(self, api, product_factory):
        product_factory()
        resp = api.get(URL, {"q": "   "})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_is_public_no_auth(self, api):
        assert api.get(URL, {"q": ""}).status_code == 200

    @pytest.mark.skip(
        reason="Non-empty suggestions use TrigramWordSimilarity (WORD_SIMILARITY), "
        "Postgres-only; raises 'no such function' on the sqlite test DB."
    )
    def test_scored_suggestions(self, api, product_factory):
        product_factory()
        api.get(URL, {"q": "prod"})
