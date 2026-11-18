"""Інтеграційні тести HTTP-ендпоінтів (FastAPI TestClient)."""


class TestBooksAPI:
    def test_create_book(self, client):
        payload = {
            "isbn": "978-0-13-235088-4",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "price": 450,
            "quantity": 3,
            "description": "Agile craftsmanship",
        }
        resp = client.post("/books/", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == 1
        assert body["isbn"] == "9780132350884"
        assert body["title"] == "Clean Code"

        # книга дійсно збережена
        stored = client.get(f"/books/{body['id']}").json()
        assert stored == body

    def test_create_book_duplicate_isbn(self, client, make_book):
        make_book(isbn="111")
        resp = client.post("/books/", json={"isbn": "111", "title": "X", "author": "Y"})
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]
        assert len(client.get("/books/").json()) == 1

    def test_create_book_validation(self, client):
        assert client.post("/books/", json={"title": "No ISBN", "author": "A"}).status_code == 422
        assert (
            client.post("/books/", json={"isbn": "1", "title": "T", "author": "A", "price": -1})
            .status_code
            == 422
        )

    def test_get_all_books(self, client, make_book):
        assert client.get("/books/").json() == []
        make_book(title="A")
        make_book(title="B")
        titles = [b["title"] for b in client.get("/books/").json()]
        assert titles == ["A", "B"]

    def test_get_book_by_id_and_isbn(self, client, make_book):
        book = make_book(isbn="555")
        assert client.get(f"/books/{book['id']}").json() == book
        assert client.get("/books/isbn/555").json() == book

    def test_get_missing_book(self, client):
        assert client.get("/books/999").status_code == 404
        assert client.get("/books/isbn/000").status_code == 404

    def test_update_book(self, client, make_book):
        book = make_book(price=100, quantity=1)
        resp = client.put(
            f"/books/{book['id']}", json={"price": 199.99, "quantity": 20, "description": "Upd"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert (body["price"], body["quantity"], body["description"]) == (199.99, 20, "Upd")
        assert body["title"] == book["title"]

    def test_update_book_isbn_forbidden(self, client, make_book):
        book = make_book(isbn="777")
        resp = client.put(f"/books/{book['id']}", json={"isbn": "888", "price": 1})
        assert resp.status_code == 400
        assert "ISBN" in resp.json()["detail"]
        assert client.get(f"/books/{book['id']}").json() == book

    def test_update_book_unknown_field(self, client, make_book):
        book = make_book()
        assert client.put(f"/books/{book['id']}", json={"id": 5}).status_code == 422

    def test_update_missing_book(self, client):
        assert client.put("/books/999", json={"price": 1}).status_code == 404

    def test_delete_book_by_id(self, client, make_book):
        book = make_book()
        resp = client.delete(f"/books/{book['id']}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert client.get(f"/books/{book['id']}").status_code == 404

    def test_delete_book_by_isbn(self, client, make_book):
        make_book(isbn="321")
        resp = client.delete("/books/isbn/321")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert client.get("/books/").json() == []

    def test_delete_nonexistent_book_no_error(self, client):
        for url in ("/books/999", "/books/isbn/000"):
            resp = client.delete(url)
            assert resp.status_code == 200
            assert resp.json()["deleted"] is False


class TestPurchasesAPI:
    def test_purchase_in_stock(self, client, make_book):
        book = make_book(price=50, quantity=5)
        resp = client.post(
            "/orders/", json={"customer_id": 1, "items": [{"book_id": book["id"], "quantity": 2}]}
        )
        assert resp.status_code == 201
        assert resp.json()["total"] == 100

    def test_purchase_missing_book(self, client):
        resp = client.post(
            "/orders/", json={"customer_id": 1, "items": [{"book_id": 999, "quantity": 1}]}
        )
        assert resp.status_code == 404

    def test_purchase_out_of_stock(self, client, make_book):
        book = make_book(quantity=0)
        resp = client.post(
            "/orders/", json={"customer_id": 1, "items": [{"book_id": book["id"], "quantity": 1}]}
        )
        assert resp.status_code == 409

    def test_quantity_decreases_after_purchase(self, client, make_book):
        book = make_book(quantity=10)
        client.post(
            "/orders/", json={"customer_id": 1, "items": [{"book_id": book["id"], "quantity": 4}]}
        )
        assert client.get(f"/books/{book['id']}").json()["quantity"] == 6

    def test_cannot_buy_more_than_available(self, client, make_book):
        book = make_book(quantity=3)
        resp = client.post(
            "/orders/", json={"customer_id": 1, "items": [{"book_id": book["id"], "quantity": 4}]}
        )
        assert resp.status_code == 409
        assert "Not enough copies" in resp.json()["detail"]
        assert client.get(f"/books/{book['id']}").json()["quantity"] == 3
        assert client.get("/orders/").json() == []

    def test_order_validation(self, client, make_book):
        book = make_book()
        assert client.post("/orders/", json={"customer_id": 1, "items": []}).status_code == 422
        assert (
            client.post(
                "/orders/",
                json={"customer_id": 1, "items": [{"book_id": book["id"], "quantity": 0}]},
            ).status_code
            == 422
        )


class TestOrderTrackingAPI:
    @staticmethod
    def _create_order(client, customer_id, book_id, qty=1):
        resp = client.post(
            "/orders/",
            json={"customer_id": customer_id, "items": [{"book_id": book_id, "quantity": qty}]},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    def test_orders_have_unique_ids(self, client, make_book):
        book = make_book(quantity=100)
        ids = [self._create_order(client, 1, book["id"])["id"] for _ in range(5)]
        assert len(set(ids)) == 5

    def test_order_contains_required_details(self, client, make_book):
        b1 = make_book(price=10)
        b2 = make_book(price=25)
        resp = client.post(
            "/orders/",
            json={
                "customer_id": 42,
                "items": [
                    {"book_id": b1["id"], "quantity": 3},
                    {"book_id": b2["id"], "quantity": 1},
                ],
            },
        )
        order = resp.json()
        assert order["customer_id"] == 42
        assert order["status"] == "processing"
        assert order["items"] == [
            {"book_id": b1["id"], "quantity": 3, "unit_price": 10.0, "subtotal": 30.0},
            {"book_id": b2["id"], "quantity": 1, "unit_price": 25.0, "subtotal": 25.0},
        ]
        assert order["total"] == 55.0

    def test_get_order_by_id(self, client, make_book):
        book = make_book()
        order = self._create_order(client, 1, book["id"])
        assert client.get(f"/orders/{order['id']}").json() == order
        assert client.get("/orders/999").status_code == 404

    def test_change_status_paid_to_shipped(self, client, make_book):
        book = make_book()
        order = self._create_order(client, 1, book["id"])
        url = f"/orders/{order['id']}/status"
        assert client.put(url, json={"status": "paid"}).json()["status"] == "paid"
        assert client.put(url, json={"status": "shipped"}).json()["status"] == "shipped"
        assert client.put(url, json={"status": "completed"}).json()["status"] == "completed"
        assert client.get(f"/orders/{order['id']}").json()["status"] == "completed"

    def test_invalid_status_transition(self, client, make_book):
        book = make_book()
        order = self._create_order(client, 1, book["id"])
        url = f"/orders/{order['id']}/status"
        client.put(url, json={"status": "shipped"})
        resp = client.put(url, json={"status": "processing"})
        assert resp.status_code == 400

    def test_unknown_status(self, client, make_book):
        book = make_book()
        order = self._create_order(client, 1, book["id"])
        resp = client.put(f"/orders/{order['id']}/status", json={"status": "lost"})
        assert resp.status_code == 422

    def test_status_update_missing_order(self, client):
        assert client.put("/orders/999/status", json={"status": "paid"}).status_code == 404

    def test_cancel_restores_stock(self, client, make_book):
        book = make_book(quantity=5)
        order = self._create_order(client, 1, book["id"], qty=5)
        assert client.get(f"/books/{book['id']}").json()["quantity"] == 0
        client.put(f"/orders/{order['id']}/status", json={"status": "cancelled"})
        assert client.get(f"/books/{book['id']}").json()["quantity"] == 5

    def test_customer_orders(self, client, make_book):
        book = make_book(quantity=100)
        o1 = self._create_order(client, 1, book["id"])
        self._create_order(client, 2, book["id"])
        o3 = self._create_order(client, 1, book["id"], qty=2)

        orders = client.get("/customers/1/orders").json()
        assert [o["id"] for o in orders] == [o1["id"], o3["id"]]
        assert all(o["customer_id"] == 1 for o in orders)
        assert client.get("/customers/99/orders").json() == []

    def test_list_all_orders(self, client, make_book):
        book = make_book()
        self._create_order(client, 1, book["id"])
        self._create_order(client, 2, book["id"])
        assert len(client.get("/orders/").json()) == 2


def test_root(client):
    assert client.get("/").json()["docs"] == "/docs"


def test_default_store_dependency():
    from app.bookstore import Bookstore
    from app.main import get_store

    assert isinstance(get_store(), Bookstore)
    assert get_store() is get_store()
