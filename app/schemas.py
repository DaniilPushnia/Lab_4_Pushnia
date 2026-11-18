"""Pydantic-схеми запитів і відповідей API."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.bookstore import OrderStatus


class BookCreate(BaseModel):
    isbn: str = Field(..., min_length=1, examples=["978-0-13-235088-4"])
    title: str = Field(..., min_length=1, examples=["Clean Code"])
    author: str = Field(..., min_length=1, examples=["Robert C. Martin"])
    price: float = Field(0.0, ge=0, examples=[450.0])
    quantity: int = Field(0, ge=0, examples=[10])
    description: str = Field("", examples=["A Handbook of Agile Software Craftsmanship"])


class BookUpdate(BaseModel):
    """Усі поля необов'язкові. ISBN змінювати не можна — якщо його передано
    і він відрізняється від поточного, API поверне 400."""

    model_config = ConfigDict(extra="forbid")

    isbn: str | None = None
    title: str | None = Field(None, min_length=1)
    author: str | None = Field(None, min_length=1)
    price: float | None = Field(None, ge=0)
    quantity: int | None = Field(None, ge=0)
    description: str | None = None


class BookOut(BaseModel):
    id: int
    isbn: str
    title: str
    author: str
    price: float
    quantity: int
    description: str


class OrderItemIn(BaseModel):
    book_id: int
    quantity: int = Field(..., gt=0)


class OrderCreate(BaseModel):
    customer_id: int = Field(..., examples=[1])
    items: list[OrderItemIn] = Field(..., min_length=1)


class OrderItemOut(BaseModel):
    book_id: int
    quantity: int
    unit_price: float
    subtotal: float


class OrderOut(BaseModel):
    id: int
    customer_id: int
    items: list[OrderItemOut]
    total: float
    status: OrderStatus
    created_at: str
    updated_at: str


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class DeleteResult(BaseModel):
    deleted: bool
    message: str
