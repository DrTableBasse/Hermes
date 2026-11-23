"""La documentation OpenAPI de web-api n'est jamais servie (constat M5)."""


def test_docs_redoc_openapi_absents(client):
    for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        assert client.get(path).status_code == 404, path
