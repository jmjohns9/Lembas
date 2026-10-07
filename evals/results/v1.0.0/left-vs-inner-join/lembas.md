An INNER JOIN returns only rows that have a match in both tables. A LEFT JOIN returns every row from the left table, with matching data from the right table where it exists and NULLs where it doesn't.

```sql
-- Only customers who have placed at least one order
SELECT c.name, o.order_id
FROM customers c
INNER JOIN orders o ON o.customer_id = c.id;

-- All customers; order_id is NULL for customers with no orders
SELECT c.name, o.order_id
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id;
```

A filter on the right table in the WHERE clause, such as `WHERE o.status = 'shipped'`, removes the NULL rows and turns a LEFT JOIN back into an INNER JOIN. Put that condition in the ON clause if you want to keep unmatched rows.
