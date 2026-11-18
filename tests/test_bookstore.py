"""Модульні тести бізнес-логіки (клас Bookstore) у стилі unittest."""
import unittest

from app.bookstore import (
    BookNotFoundError,
    Bookstore,
    DuplicateISBNError,
    ImmutableFieldError,
    InsufficientStockError,
    InvalidOrderError,
    InvalidStatusTransitionError,
    OrderNotFoundError,
    OrderStatus,
)


class TestInventory(unittest.TestCase):
    """1. Керування інвентарем: створення, оновлення, видалення книг."""

    def setUp(self):
        self.store = Bookstore()

    def test_add_new_book(self):
        result = self.store.add_book("123456789", "Python Programming", "John Doe")
        self.assertTrue(result)

    def test_added_book_is_saved(self):
        book = self.store.add_book("123456789", "Python Programming", "John Doe", 300, 5, "desc")
        saved = self.store.get_book(book.id)
        self.assertEqual(saved.isbn, "123456789")
        self.assertEqual(saved.title, "Python Programming")
        self.assertEqual(saved.author, "John Doe")
        self.assertEqual(saved.price, 300)
        self.assertEqual(saved.quantity, 5)
        self.assertEqual(saved.description, "desc")
        self.assertIn(saved, self.store.list_books())

    def test_duplicate_isbn(self):
        self.store.add_book("123456789", "Python Programming", "John Doe")
        with self.assertRaises(ValueError):
            self.store.add_book("123456789", "Another Book", "Jane Doe")

    def test_duplicate_isbn_ignores_hyphens(self):
        self.store.add_book("978-0-13-235088-4", "Clean Code", "R. Martin")
        with self.assertRaises(DuplicateISBNError):
            self.store.add_book("9780132350884", "Clean Code copy", "R. Martin")

    def test_duplicate_isbn_does_not_add_second_book(self):
        self.store.add_book("123456789", "Python Programming", "John Doe")
        with self.assertRaises(DuplicateISBNError):
            self.store.add_book("123456789", "Another Book", "Jane Doe")
        self.assertEqual(len(self.store.list_books()), 1)

    def test_add_book_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            self.store.add_book("", "T", "A")
        with self.assertRaises(ValueError):
            self.store.add_book("1", "T", "A", price=-1)
        with self.assertRaises(ValueError):
            self.store.add_book("1", "T", "A", quantity=-1)

    def test_book_ids_are_unique(self):
        a = self.store.add_book("1", "A", "X")
        b = self.store.add_book("2", "B", "Y")
        self.assertNotEqual(a.id, b.id)

    def test_get_book_by_isbn(self):
        book = self.store.add_book("123", "T", "A")
        self.assertIs(self.store.get_book_by_isbn("123"), book)

    def test_get_missing_book_raises(self):
        with self.assertRaises(BookNotFoundError):
            self.store.get_book(999)
        with self.assertRaises(BookNotFoundError):
            self.store.get_book_by_isbn("000")



    def test_update_book(self):
        book = self.store.add_book("123", "Old", "A", price=100, quantity=1)
        self.store.update_book(book.id, price=150.5, quantity=7, description="New desc")
        updated = self.store.get_book(book.id)
        self.assertEqual(updated.price, 150.5)
        self.assertEqual(updated.quantity, 7)
        self.assertEqual(updated.description, "New desc")
        self.assertEqual(updated.title, "Old")  # не змінене поле лишилося

    def test_isbn_cannot_be_changed(self):
        book = self.store.add_book("123", "T", "A")
        with self.assertRaises(ImmutableFieldError):
            self.store.update_book(book.id, isbn="999")
        self.assertEqual(self.store.get_book(book.id).isbn, "123")

    def test_isbn_cannot_be_changed_does_not_apply_other_fields(self):
        book = self.store.add_book("123", "T", "A", price=10)
        with self.assertRaises(ImmutableFieldError):
            self.store.update_book(book.id, isbn="999", price=20)
        self.assertEqual(self.store.get_book(book.id).price, 10)

    def test_update_with_same_isbn_is_allowed(self):
        book = self.store.add_book("123", "T", "A")
        self.store.update_book(book.id, isbn="123", title="New")
        self.assertEqual(self.store.get_book(book.id).title, "New")

    def test_update_rejects_invalid_values(self):
        book = self.store.add_book("123", "T", "A")
        with self.assertRaises(ValueError):
            self.store.update_book(book.id, price=-5)
        with self.assertRaises(ValueError):
            self.store.update_book(book.id, quantity=-5)
        with self.assertRaises(ValueError):
            self.store.update_book(book.id, id=42)

    def test_update_missing_book_raises(self):
        with self.assertRaises(BookNotFoundError):
            self.store.update_book(999, price=1)




    def test_delete_book_by_id(self):
        book = self.store.add_book("123", "T", "A")
        self.assertTrue(self.store.delete_book(book.id))
        with self.assertRaises(BookNotFoundError):
            self.store.get_book(book.id)

    def test_delete_book_by_isbn(self):
        self.store.add_book("123", "T", "A")
        self.assertTrue(self.store.delete_book_by_isbn("123"))
        self.assertEqual(self.store.list_books(), [])

    def test_delete_nonexistent_book_does_not_raise(self):
        self.assertFalse(self.store.delete_book(999))
        self.assertFalse(self.store.delete_book_by_isbn("000"))

    def test_delete_twice_does_not_raise(self):
        book = self.store.add_book("123", "T", "A")
        self.assertTrue(self.store.delete_book(book.id))
        self.assertFalse(self.store.delete_book(book.id))


class TestPurchases(unittest.TestCase):
    """2. Обробка покупок."""

    def setUp(self):
        self.store = Bookstore()
        self.book = self.store.add_book("111", "Book", "Author", price=100, quantity=5)

    def test_purchase_succeeds_when_in_stock(self):
        order = self.store.create_order(1, [{"book_id": self.book.id, "quantity": 2}])
        self.assertEqual(order.status, OrderStatus.PROCESSING)
        self.assertEqual(order.total, 200)

    def test_purchase_fails_when_book_not_in_inventory(self):
        with self.assertRaises(BookNotFoundError):
            self.store.create_order(1, [{"book_id": 999, "quantity": 1}])

    def test_purchase_fails_when_out_of_stock(self):
        self.store.update_book(self.book.id, quantity=0)
        with self.assertRaises(InsufficientStockError):
            self.store.create_order(1, [{"book_id": self.book.id, "quantity": 1}])

    def test_quantity_decreases_after_purchase(self):
        self.store.create_order(1, [{"book_id": self.book.id, "quantity": 3}])
        self.assertEqual(self.store.get_book(self.book.id).quantity, 2)

    def test_purchase_exact_stock_is_allowed(self):
        self.store.create_order(1, [{"book_id": self.book.id, "quantity": 5}])
        self.assertEqual(self.store.get_book(self.book.id).quantity, 0)

    def test_purchase_more_than_available_is_impossible(self):
        with self.assertRaises(InsufficientStockError):
            self.store.create_order(1, [{"book_id": self.book.id, "quantity": 6}])
        self.assertEqual(self.store.get_book(self.book.id).quantity, 5)
        self.assertEqual(self.store.list_orders(), [])

    def test_duplicate_items_are_summed_for_stock_check(self):
        with self.assertRaises(InsufficientStockError):
            self.store.create_order(
                1,
                [{"book_id": self.book.id, "quantity": 3}, {"book_id": self.book.id, "quantity": 3}],
            )

    def test_failed_multi_item_order_does_not_change_stock(self):
        other = self.store.add_book("222", "Other", "A", price=50, quantity=1)
        with self.assertRaises(InsufficientStockError):
            self.store.create_order(
                1,
                [{"book_id": self.book.id, "quantity": 2}, {"book_id": other.id, "quantity": 2}],
            )
        self.assertEqual(self.store.get_book(self.book.id).quantity, 5)
        self.assertEqual(self.store.get_book(other.id).quantity, 1)

    def test_invalid_order_data(self):
        with self.assertRaises(InvalidOrderError):
            self.store.create_order(1, [])
        with self.assertRaises(InvalidOrderError):
            self.store.create_order(1, [{"book_id": self.book.id, "quantity": 0}])

    def test_order_price_is_fixed_at_purchase_time(self):
        order = self.store.create_order(1, [{"book_id": self.book.id, "quantity": 1}])
        self.store.update_book(self.book.id, price=999)
        self.assertEqual(self.store.get_order(order.id).total, 100)


class TestOrderTracking(unittest.TestCase):
    """3. Відстеження замовлень клієнтів."""

    def setUp(self):
        self.store = Bookstore()
        self.b1 = self.store.add_book("111", "B1", "A", price=10, quantity=100)
        self.b2 = self.store.add_book("222", "B2", "A", price=20, quantity=100)

    def _order(self, customer_id=1, book=None, qty=1):
        book = book or self.b1
        return self.store.create_order(customer_id, [{"book_id": book.id, "quantity": qty}])

    def test_orders_have_unique_ids(self):
        ids = [self._order().id for _ in range(10)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_order_contains_all_details(self):
        order = self.store.create_order(
            7, [{"book_id": self.b1.id, "quantity": 2}, {"book_id": self.b2.id, "quantity": 1}]
        )
        data = order.to_dict()
        self.assertEqual(data["customer_id"], 7)
        self.assertEqual(
            [(i["book_id"], i["quantity"]) for i in data["items"]],
            [(self.b1.id, 2), (self.b2.id, 1)],
        )
        self.assertEqual(data["total"], 40)
        self.assertEqual(data["status"], "processing")
        self.assertIn("created_at", data)

    def test_get_missing_order_raises(self):
        with self.assertRaises(OrderNotFoundError):
            self.store.get_order(999)


    def test_status_paid_to_shipped(self):
        order = self._order()
        self.store.update_order_status(order.id, OrderStatus.PAID)
        self.store.update_order_status(order.id, "shipped")
        self.assertEqual(self.store.get_order(order.id).status, OrderStatus.SHIPPED)

    def test_full_status_lifecycle(self):
        order = self._order()
        for status in ("paid", "shipped", "completed"):
            self.store.update_order_status(order.id, status)
        self.assertEqual(order.status, OrderStatus.COMPLETED)

    def test_same_status_is_noop(self):
        order = self._order()
        self.store.update_order_status(order.id, "processing")
        self.assertEqual(order.status, OrderStatus.PROCESSING)

    def test_invalid_status_transition(self):
        order = self._order()
        self.store.update_order_status(order.id, "shipped")
        self.store.update_order_status(order.id, "completed")
        with self.assertRaises(InvalidStatusTransitionError):
            self.store.update_order_status(order.id, "processing")

    def test_unknown_status_value(self):
        order = self._order()
        with self.assertRaises(ValueError):
            self.store.update_order_status(order.id, "lost")

    def test_status_update_missing_order(self):
        with self.assertRaises(OrderNotFoundError):
            self.store.update_order_status(999, "paid")

    def test_cancel_returns_books_to_stock(self):
        order = self._order(qty=10)
        self.assertEqual(self.b1.quantity, 90)
        self.store.update_order_status(order.id, "cancelled")
        self.assertEqual(self.b1.quantity, 100)

    def test_cancel_after_book_deleted(self):
        order = self._order(qty=1)
        self.store.delete_book(self.b1.id)
        self.store.update_order_status(order.id, "cancelled")
        self.assertEqual(order.status, OrderStatus.CANCELLED)

    def test_shipped_order_cannot_be_cancelled(self):
        order = self._order()
        self.store.update_order_status(order.id, "shipped")
        with self.assertRaises(InvalidStatusTransitionError):
            self.store.update_order_status(order.id, "cancelled")

    def test_customer_sees_all_own_orders(self):
        o1 = self._order(customer_id=1)
        o2 = self._order(customer_id=1, book=self.b2)
        self._order(customer_id=2)
        orders = self.store.get_customer_orders(1)
        self.assertEqual([o.id for o in orders], [o1.id, o2.id])

    def test_customer_without_orders(self):
        self.assertEqual(self.store.get_customer_orders(42), [])


if __name__ == "__main__":
    unittest.main()
