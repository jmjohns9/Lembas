Rank each sale within its region with `ROW_NUMBER()` and keep ranks 1 through 3.

```sql
WITH ranked AS (
    SELECT
        region,
        rep,
        amount,
        sale_date,
        ROW_NUMBER() OVER (
            PARTITION BY region
            ORDER BY amount DESC, sale_date DESC  -- tiebreaker keeps results deterministic
        ) AS rn
    FROM Sales
)
SELECT region, rep, amount, sale_date, rn
FROM ranked
WHERE rn <= 3
ORDER BY region, rn;
```

`ROW_NUMBER()` returns exactly 3 rows per region even when amounts tie; use `DENSE_RANK()` instead if tied amounts should all be included.
