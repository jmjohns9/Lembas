Use a window function to rank sales within each region, then keep ranks 1 through 3:

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
    FROM dbo.Sales
)
SELECT region, rep, amount, sale_date, rn AS sale_rank
FROM ranked
WHERE rn <= 3
ORDER BY region, rn;
```

**How it works:** `PARTITION BY region` restarts the numbering for each region, and `ORDER BY amount DESC` puts the largest sale first. The `sale_date DESC` tiebreaker makes the result deterministic when two sales have the same amount.

**Handling ties:**
- `ROW_NUMBER()` always returns exactly 3 rows per region, even if the 3rd and 4th sales tie.
- Swap in `RANK()` to include every row tied at the cutoff (you may get more than 3).
- Use `DENSE_RANK()` if you want the top 3 distinct amounts.

**If you meant top 3 reps by total sales per region**, aggregate first:

```sql
WITH rep_totals AS (
    SELECT
        region,
        rep,
        SUM(amount) AS total_amount,
        ROW_NUMBER() OVER (
            PARTITION BY region
            ORDER BY SUM(amount) DESC
        ) AS rn
    FROM dbo.Sales
    GROUP BY region, rep
)
SELECT region, rep, total_amount, rn AS rep_rank
FROM rep_totals
WHERE rn <= 3
ORDER BY region, rn;
```

To limit to a time window, add a `WHERE sale_date >= '2026-01-01'` (or similar) inside the CTE. On a large table, an index on `(region, amount DESC)` that includes `rep` and `sale_date` will help.
