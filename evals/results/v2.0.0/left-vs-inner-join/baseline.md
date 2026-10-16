**INNER JOIN** returns only the rows that have a match in both tables.

**LEFT JOIN** (also called LEFT OUTER JOIN) returns every row from the left table. When a left row has no match in the right table, the right table's columns come back as `NULL`.

### Example

`customers`
| id | name  |
|----|-------|
| 1  | Alice |
| 2  | Bob   |
| 3  | Carol |

`orders`
| id | customer_id | total |
|----|-------------|-------|
| 10 | 1           | 50    |
| 11 | 1           | 20    |
| 12 | 3           | 75    |

```sql
SELECT c.name, o.total
FROM customers c
INNER JOIN orders o ON o.customer_id = c.id;
```
| name  | total |
|-------|-------|
| Alice | 50    |
| Alice | 20    |
| Carol | 75    |

Bob is missing because he has no orders.

```sql
SELECT c.name, o.total
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id;
```
| name  | total |
|-------|-------|
| Alice | 50    |
| Alice | 20    |
| Bob   | NULL  |
| Carol | 75    |

Bob now appears, with `NULL` for the order columns.

### Things to watch for
- **Finding rows with no match:** a LEFT JOIN plus `WHERE o.id IS NULL` returns customers who have no orders.
- **A WHERE filter can undo a LEFT JOIN:** with `LEFT JOIN orders o ... WHERE o.total > 30`, the `NULL` rows fail the filter and are dropped, so the result is the same as an INNER JOIN. To keep the unmatched left rows, put the condition in the `ON` clause instead: `ON o.customer_id = c.id AND o.total > 30`.
- **Duplicates:** both join types repeat a left row once for each matching right row. Alice appears twice above for this reason.
- **Table order:** with a LEFT JOIN, the order of the tables changes the result. With an INNER JOIN it doesn't.