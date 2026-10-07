The difference is what happens to rows that don't have a match.

**INNER JOIN** returns only rows where the join condition matches in both tables. If a row on either side has no partner, it's dropped.

**LEFT JOIN** returns every row from the left table, matched or not. When there's no match on the right, the right table's columns come back as NULL.

**Example**

`customers`

| customer_id | name  |
|-------------|-------|
| 1           | Ana   |
| 2           | Ben   |
| 3           | Cara  |

`orders`

| order_id | customer_id | amount |
|----------|-------------|--------|
| 101      | 1           | 50     |
| 102      | 1           | 20     |
| 103      | 2           | 75     |

```sql
SELECT c.name, o.order_id, o.amount
FROM customers c
INNER JOIN orders o ON o.customer_id = c.customer_id;
```

| name | order_id | amount |
|------|----------|--------|
| Ana  | 101      | 50     |
| Ana  | 102      | 20     |
| Ben  | 103      | 75     |

Cara has no orders, so she's gone.

```sql
SELECT c.name, o.order_id, o.amount
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id;
```

| name | order_id | amount |
|------|----------|--------|
| Ana  | 101      | 50     |
| Ana  | 102      | 20     |
| Ben  | 103      | 75     |
| Cara | NULL     | NULL   |

Cara stays, with NULLs for the order columns.

**When to use which**

* Use INNER JOIN when you only care about records that exist in both places, like "orders with their customer details."
* Use LEFT JOIN when the left table is your full population and you don't want to lose anyone, like "all customers and their order totals, including those with zero." It's also the standard way to find gaps: `LEFT JOIN ... WHERE o.order_id IS NULL` gives you customers with no orders.

**Two common gotchas**

1. **Filtering the right table in WHERE turns a LEFT JOIN into an INNER JOIN.** `WHERE o.amount > 30` throws out Cara's NULL row. If you want to keep unmatched rows, put that condition in the ON clause instead: `LEFT JOIN orders o ON o.customer_id = c.customer_id AND o.amount > 30`.
2. **Both joins can multiply rows.** Ana appears twice because she has two orders. If you then SUM a column from `customers`, it gets double counted. Aggregate the many side first, or join to a pre-summarized subquery.

In Tableau terms, it's the same distinction as the Inner vs. Left join options in the physical layer, and relationships behave more like a LEFT JOIN that's resolved per viz.
