This uses `ROW_NUMBER()` to rank sales within each region, then keeps the top 3:

```sql
WITH RankedSales AS (
    SELECT
        region,
        rep,
        amount,
        sale_date,
        ROW_NUMBER() OVER (
            PARTITION BY region
            ORDER BY amount DESC, sale_date DESC
        ) AS rn
    FROM Sales
)
SELECT region, rep, amount, sale_date, rn AS sale_rank
FROM RankedSales
WHERE rn <= 3
ORDER BY region, rn;
```

**How it works:**
- `PARTITION BY region` restarts the numbering for each region.
- `ORDER BY amount DESC` puts the largest sale first. `sale_date DESC` breaks ties, so a more recent sale ranks above an older one with the same amount.
- The CTE is needed because SQL Server doesn't let you filter on a window function in `WHERE` directly.

**Handling ties:** pick the ranking function based on what you want when amounts are equal.

| Function | Behavior when amounts are equal | Rows per region |
|---|---|---|
| `ROW_NUMBER()` | Breaks the tie and gives each row its own number | Exactly 3 (if there are at least 3 sales) |
| `RANK()` | Gives tied rows the same rank, then skips numbers (1, 1, 3) | Can be more than 3 |
| `DENSE_RANK()` | Gives tied rows the same rank without skipping (1, 1, 2, 3) | Top 3 *distinct amounts*, which can be many rows |

**Another way, using `CROSS APPLY`:** this can run faster if you have a separate `Regions` table and an index on `Sales(region, amount DESC)`:

```sql
SELECT r.region, s.rep, s.amount, s.sale_date
FROM (SELECT DISTINCT region FROM Sales) r
CROSS APPLY (
    SELECT TOP (3) rep, amount, sale_date
    FROM Sales s
    WHERE s.region = r.region
    ORDER BY amount DESC, sale_date DESC
) s
ORDER BY r.region, s.amount DESC;
```

If you meant top 3 *reps* by total sales per region instead of the 3 biggest single sales, run `GROUP BY region, rep` with `SUM(amount)` first, then rank those totals the same way.