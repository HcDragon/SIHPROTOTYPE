from tests.api.test_rbac_matrix import PUBLIC_OPERATIONS, operations


def test_openapi_document_lists_endpoints_with_bearer_security(client, app):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert document["openapi"].startswith("3.")
    assert "HTTPBearer" in document["components"]["securitySchemes"]

    for method, path, _ in operations(app):
        operation = document["paths"][path][method.lower()]
        secured = bool(operation.get("security"))
        assert secured == ((method, path) not in PUBLIC_OPERATIONS), (method, path)
    assert all(path.startswith("/api/v1") for path in document["paths"])


def test_interactive_docs_served(client):
    assert client.get("/api/v1/docs").status_code == 200
