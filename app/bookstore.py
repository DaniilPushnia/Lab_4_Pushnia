"""Бізнес-логіка книжкового магазину (сховище в пам'яті)"""
from __future__ import annotations

import itertools
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum


class BookstoreError(Exception):
    """Базове виключення магазину."""


class NotFoundError(BookstoreError, LookupError):
    """Сутність не знайдена."""


class BookNotFoundError(NotFoundError):
    pass


class OrderNotFoundError(NotFoundError):
    pass


class DuplicateISBNError(BookstoreError, ValueError):
    """Книга з таким ISBN вже існує."""


class ImmutableFieldError(BookstoreError, ValueError):
    """Спроба змінити поле, яке не можна змінювати (ISBN)."""


class InsufficientStockError(BookstoreError, ValueError):
    """Недостатня кількість примірників на складі."""


class InvalidOrderError(BookstoreError, ValueError):
    """Некоректні дані замовлення."""


class InvalidStatusTransitionError(BookstoreError, ValueError):
    """Недопустима зміна статусу замовлення."""


class OrderStatus(str, Enum):
    PROCESSING = "processing"
    PAID = "paid"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PROCESSING: {OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.COMPLETED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
}

UPDATABLE_BOOK_FIELDS = {"title", "author", "price", "quantity", "description"}


@dataclass
class Book:
    id: int
    isbn: str
    title: str
    author: str
    price: float = 0.0
    quantity: int = 0
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OrderItem:
    book_id: int
    quantity: int
    unit_price: float

    @property
    def subtotal(self) -> float:
        return round(self.unit_price * self.quantity, 2)


@dataclass
class Order:
    id: int
    customer_id: int
    items: list[OrderItem]
    status: OrderStatus = OrderStatus.PROCESSING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total(self) -> float:
        return round(sum(item.subtotal for item in self.items), 2)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "items": [
                {
                    "book_id": i.book_id,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "subtotal": i.subtotal,
                }
                for i in self.items
            ],
            "total": self.total,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Bookstore:
    """Інвентар книг, покупки та замовлення клієнтів."""

    def __init__(self) -> None:
        self._books: dict[int, Book] = {}
        self._orders: dict[int, Order] = {}
        self._book_ids = itertools.count(1)
        self._order_ids = itertools.count(1)
        self._lock = threading.RLock()

    def add_book(
        self,
        isbn: str,
        title: str,
        author: str,
        price: float = 0.0,
        quantity: int = 0,
        description: str = "",
    ) -> Book:
        isbn = self._normalize_isbn(isbn)
        if not isbn:
            raise ValueError("ISBN must not be empty")
        if price < 0:
            raise ValueError("Price must be non-negative")
        if quantity < 0:
            raise ValueError("Quantity must be non-negative")
        with self._lock:
            if self._find_by_isbn(isbn) is not None:
                raise DuplicateISBNError(f"Book with ISBN {isbn} already exists")
            book = Book(
                id=next(self._book_ids),
                isbn=isbn,
                title=title,
                author=author,
                price=price,
                quantity=quantity,
                description=description,
            )
            self._books[book.id] = book
            return book

    def get_book(self, book_id: int) -> Book:
        book = self._books.get(book_id)
        if book is None:
            raise BookNotFoundError(f"Book {book_id} not found")
        return book

    def get_book_by_isbn(self, isbn: str) -> Book:
        book = self._find_by_isbn(self._normalize_isbn(isbn))
        if book is None:
            raise BookNotFoundError(f"Book with ISBN {isbn} not found")
        return book

    def list_books(self) -> list[Book]:
        return list(self._books.values())

    def update_book(self, book_id: int, **changes) -> Book:
        with self._lock:
            book = self.get_book(book_id)
            if "isbn" in changes:
                new_isbn = changes.pop("isbn")
                if new_isbn is not None and self._normalize_isbn(new_isbn) != book.isbn:
                    raise ImmutableFieldError("ISBN cannot be changed")
            unknown = set(changes) - UPDATABLE_BOOK_FIELDS
            if unknown:
                raise ValueError(f"Unknown fields: {', '.join(sorted(unknown))}")
            if changes.get("price") is not None and changes["price"] < 0:
                raise ValueError("Price must be non-negative")
            if changes.get("quantity") is not None and changes["quantity"] < 0:
                raise ValueError("Quantity must be non-negative")
            for key, value in changes.items():
                if value is not None:
                    setattr(book, key, value)
            return book

    def delete_book(self, book_id: int) -> bool:
        """Видаляє книгу. Повертає False (без помилки), якщо книги немає."""
        with self._lock:
            return self._books.pop(book_id, None) is not None

    def delete_book_by_isbn(self, isbn: str) -> bool:
        with self._lock:
            book = self._find_by_isbn(self._normalize_isbn(isbn))
            if book is None:
                return False
            del self._books[book.id]
            return True

    # ----------------------------- Замовлення ----------------------------- #
    def create_order(self, customer_id: int, items: list[dict]) -> Order:
        """Оформлює покупку. ``items`` - список {"book_id": int, "quantity": int}.

        Перевірка наявності виконується для всіх позицій ДО списання, тож
        замовлення або проходить повністю, або не змінює інвентар взагалі.
        """
        if not items:
            raise InvalidOrderError("Order must contain at least one item")

        requested: dict[int, int] = {}
        for item in items:
            qty = item["quantity"]
            if qty <= 0:
                raise InvalidOrderError("Quantity must be positive")
            requested[item["book_id"]] = requested.get(item["book_id"], 0) + qty

        with self._lock:
            books = {book_id: self.get_book(book_id) for book_id in requested}
            for book_id, qty in requested.items():
                if books[book_id].quantity < qty:
                    raise InsufficientStockError(
                        f"Not enough copies of book {book_id}: "
                        f"requested {qty}, available {books[book_id].quantity}"
                    )
            for book_id, qty in requested.items():
                books[book_id].quantity -= qty

            order = Order(
                id=next(self._order_ids),
                customer_id=customer_id,
                items=[
                    OrderItem(book_id=book_id, quantity=qty, unit_price=books[book_id].price)
                    for book_id, qty in requested.items()
                ],
            )
            self._orders[order.id] = order
            return order

    def get_order(self, order_id: int) -> Order:
        order = self._orders.get(order_id)
        if order is None:
            raise OrderNotFoundError(f"Order {order_id} not found")
        return order

    def list_orders(self) -> list[Order]:
        return list(self._orders.values())

    def get_customer_orders(self, customer_id: int) -> list[Order]:
        return [o for o in self._orders.values() if o.customer_id == customer_id]

    def update_order_status(self, order_id: int, status: OrderStatus | str) -> Order:
        new_status = OrderStatus(status)
        with self._lock:
            order = self.get_order(order_id)
            if new_status == order.status:
                return order
            if new_status not in ALLOWED_TRANSITIONS[order.status]:
                raise InvalidStatusTransitionError(
                    f"Cannot change status from '{order.status.value}' to '{new_status.value}'"
                )
            if new_status == OrderStatus.CANCELLED:
                for item in order.items:
                    book = self._books.get(item.book_id)
                    if book is not None:
                        book.quantity += item.quantity
            order.status = new_status
            order.updated_at = datetime.now(timezone.utc)
            return order

    @staticmethod
    def _normalize_isbn(isbn: str) -> str:
        return isbn.replace("-", "").replace(" ", "").strip()

    def _find_by_isbn(self, isbn: str) -> Book | None:
        return next((b for b in self._books.values() if b.isbn == isbn), None)
