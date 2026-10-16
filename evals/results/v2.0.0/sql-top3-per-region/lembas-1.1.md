Rank each region's rows with `ROW_NUMBER()` and keep ranks 1 to 3.

```sql
WITH ranked AS (
    SELECT region, rep, amount, sale_date,
           ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC, sale_date DESC) AS rn
    FROM Sales
)
SELECT region, rep, amount, sale_date
FROM ranked
WHERE rn <= 3
ORDER BY region, rn;
```

If two sales have the same amount, `ROW_NUMBER()` still returns exactly 3 rows and drops one of the tied sales. Use `DENSE_RANK()` if you want to keep every tied sale. You can't filter on `rn` in the same `SELECT` that defines it, which is why the query uses a CTE.