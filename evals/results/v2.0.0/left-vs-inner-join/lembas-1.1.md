An INNER JOIN returns only rows that have a match in both tables. A LEFT JOIN returns every row from the left table, and where no match exists, the right table's columns are filled with NULL.

```sql
-- Only customers who have placed orders
SELECT c.name, o.id FROM customers c
INNER JOIN orders o ON o.customer_id = c.id;

-- All customers, with NULL order id for those without orders
SELECT c.name, o.id FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id;
```

A common mistake is filtering the right table in `WHERE`, as in `WHERE o.status = 'paid'`. That removes the NULL rows, so the LEFT JOIN behaves like an INNER JOIN. To keep all left rows, put that condition in the `ON` clause.