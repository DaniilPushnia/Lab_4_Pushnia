"""FastAPI-застосунок книжкового магазину."""
from __future__ import annotations

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.bookstore import (
    Bookstore,
    DuplicateISBNError,
    ImmutableFieldError,
    InsufficientStockError,
    InvalidOrderError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from app.schemas import (
    BookCreate,
    BookOut,
    BookUpdate,
    DeleteResult,
    OrderCreate,
    OrderOut,
    OrderStatusUpdate,
)

app = FastAPI(
    title="Bookstore API",
    description="API для керування інвентарем книжкового магазину, "
    "обробки покупок та відстеження замовлень клієнтів.",
    version="1.0.0",
)

_store = Bookstore()


def get_store() -> Bookstore:
    """Залежність, яку тести підміняють на чистий Bookstore."""
    return _store


def _error(code: int, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=code, content={"detail": str(exc)})


@app.exception_handler(NotFoundError)
async def not_found_handler(_: Request, exc: NotFoundError):
    return _error(status.HTTP_404_NOT_FOUND, exc)


@app.exception_handler(DuplicateISBNError)
async def duplicate_handler(_: Request, exc: DuplicateISBNError):
    return _error(status.HTTP_409_CONFLICT, exc)


@app.exception_handler(InsufficientStockError)
async def stock_handler(_: Request, exc: InsufficientStockError):
    return _error(status.HTTP_409_CONFLICT, exc)


@app.exception_handler(ImmutableFieldError)
@app.exception_handler(InvalidOrderError)
@app.exception_handler(InvalidStatusTransitionError)
async def bad_request_handler(_: Request, exc: Exception):
    return _error(status.HTTP_400_BAD_REQUEST, exc)


@app.get("/", tags=["service"])
def root():
    return {"service": "Bookstore API", "docs": "/docs"}


@app.post("/books/", response_model=BookOut, status_code=201, tags=["books"])
def add_book(book: BookCreate, store: Bookstore = Depends(get_store)):
    return store.add_book(**book.model_dump()).to_dict()


@app.get("/books/", response_model=list[BookOut], tags=["books"])
def get_books(store: Bookstore = Depends(get_store)):
    return [b.to_dict() for b in store.list_books()]


@app.get("/books/isbn/{isbn}", response_model=BookOut, tags=["books"])
def get_book_by_isbn(isbn: str, store: Bookstore = Depends(get_store)):
    return store.get_book_by_isbn(isbn).to_dict()


@app.get("/books/{book_id}", response_model=BookOut, tags=["books"])
def get_book(book_id: int, store: Bookstore = Depends(get_store)):
    return store.get_book(book_id).to_dict()


@app.put("/books/{book_id}", response_model=BookOut, tags=["books"])
def update_book(book_id: int, changes: BookUpdate, store: Bookstore = Depends(get_store)):
    return store.update_book(book_id, **changes.model_dump(exclude_unset=True)).to_dict()


@app.delete("/books/isbn/{isbn}", response_model=DeleteResult, tags=["books"])
def delete_book_by_isbn(isbn: str, store: Bookstore = Depends(get_store)):
    deleted = store.delete_book_by_isbn(isbn)
    return {
        "deleted": deleted,
        "message": "Book deleted successfully" if deleted else "Book not found, nothing to delete",
    }


@app.delete("/books/{book_id}", response_model=DeleteResult, tags=["books"])
def delete_book(book_id: int, store: Bookstore = Depends(get_store)):
    deleted = store.delete_book(book_id)
    return {
        "deleted": deleted,
        "message": "Book deleted successfully" if deleted else "Book not found, nothing to delete",
    }


@app.post("/orders/", response_model=OrderOut, status_code=201, tags=["orders"])
def create_order(order: OrderCreate, store: Bookstore = Depends(get_store)):
    items = [i.model_dump() for i in order.items]
    return store.create_order(order.customer_id, items).to_dict()


@app.get("/orders/", response_model=list[OrderOut], tags=["orders"])
def get_orders(store: Bookstore = Depends(get_store)):
    return [o.to_dict() for o in store.list_orders()]


@app.get("/orders/{order_id}", response_model=OrderOut, tags=["orders"])
def get_order(order_id: int, store: Bookstore = Depends(get_store)):
    return store.get_order(order_id).to_dict()


@app.put("/orders/{order_id}/status", response_model=OrderOut, tags=["orders"])
def update_order_status(
    order_id: int, body: OrderStatusUpdate, store: Bookstore = Depends(get_store)
):
    return store.update_order_status(order_id, body.status).to_dict()


@app.get("/customers/{customer_id}/orders", response_model=list[OrderOut], tags=["customers"])
def get_customer_orders(customer_id: int, store: Bookstore = Depends(get_store)):
    return [o.to_dict() for o in store.get_customer_orders(customer_id)]
