import os
from pathlib import Path

from fastapi.testclient import TestClient

from app import main


def test_api_flow(tmp_path: Path):
    main.CSV_PATH = "book1-100k.csv"
    main.STATE_PATH = str(tmp_path / "api-state.json")

    with TestClient(main.app) as client:
        root = client.get("/", follow_redirects=False)
        assert root.status_code == 307
        assert root.headers["location"] == "/docs"

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["items_loaded"] > 1000

        response = client.post("/users", json={"id": "api-user", "name": "Usuário API", "preferences": {"1": 5}})
        assert response.status_code == 201

        update = client.put("/users/api-user/preferences", json={"preferences": {"2": 4}})
        assert update.status_code == 200

        recommendations = client.get("/recommendations/api-user", params={"limit": 3})
        assert recommendations.status_code == 200
        assert len(recommendations.json()) == 3

        without_preferences = client.post("/users", json={"id": "new-user", "name": "Novo usuário"})
        assert without_preferences.status_code == 201
        assert without_preferences.json()["preferences"] == {}

        invalid_item = client.post("/users", json={"id": "bad-user", "name": "Erro", "preferences": {"additionalProp1": 5}})
        assert invalid_item.status_code == 400

        item = client.post("/items", json={
            "id": "livro-101",
            "name": "O Guia do Mochileiro das Galáxias",
            "authors": "Douglas Adams",
            "publisher": "Arqueiro",
            "language": "pt-BR",
            "year": 2004,
            "pages": 208,
            "rating": 4.5,
            "isbn": "9788576866113",
        })
        assert item.status_code == 201
        assert item.json()["id"] == "livro-101"
