An INNER JOIN returns only the rows where the join condition matches in both tables. A LEFT JOIN returns every row from the left table, and where no right-table row matches, the right-side columns come back as `NULL`.

```sql
-- Only customers who have at least one order
SELECT c.name, o.id FROM customers c INNER JOIN orders o ON o.customer_id = c.id;

-- All customers; o.id is NULL for those with no orders
SELECT c.name, o.id FROM customers c LEFT JOIN orders o ON o.customer_id = c.id;
```

Use INNER when you need the relationship to exist. Use LEFT when you need every left row, for example to find unmatched rows with `WHERE o.id IS NULL`.

The most common mistake is filtering a right-table column in `WHERE`, such as `WHERE o.status = 'paid'`. The `NULL` rows fail that test, so the LEFT JOIN quietly acts like an INNER JOIN. Put that condition in the `ON` clause instead: `LEFT JOIN orders o ON o.customer_id = c.id AND o.status = 'paid'`.