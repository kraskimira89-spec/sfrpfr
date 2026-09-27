"""api.proverkastaza.ru закрыт от индексирования: robots.txt и X-Robots-Tag."""

from fastapi.testclient import TestClient

from sfrfr.api import create_app


def test_robots_txt_disallows_all() -> None:
    client = TestClient(create_app())
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "User-agent: *" in response.text
    assert "Disallow: /" in response.text.splitlines()


def test_x_robots_tag_on_every_response() -> None:
    client = TestClient(create_app())
    for path in ("/robots.txt", "/health", "/definitely-missing"):
        response = client.get(path)
        assert response.headers.get("x-robots-tag") == "noindex, nofollow", path
