`ROW_NUMBER()` in a CTE ranks each region's sales by amount, and the outer query keeps ranks 1 to 3.

```sql
WITH ranked AS (
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
FROM ranked
WHERE rn <= 3
ORDER BY region, rn;
```

- **Ties:** `ROW_NUMBER()` returns exactly 3 rows per region and drops tied amounts at the cutoff. Use `DENSE_RANK()` instead if every sale tied for third place should be included. The `sale_date DESC` tiebreaker makes the result the same on every run.
- **Performance:** On a large table, an index on `(region, amount DESC) INCLUDE (rep, sale_date)` lets SQL Server skip the sort.