Sort by `updated_at`, then drop duplicates and keep the last row for each key:

```python
import pandas as pd

df["updated_at"] = pd.to_datetime(df["updated_at"])

deduped = (
    df.sort_values("updated_at")
      .drop_duplicates(subset=["id"], keep="last")
      .reset_index(drop=True)
)
```

Replace `["id"]` with whatever column or columns define a duplicate, for example `["customer_id", "order_id"]`.

A few things to watch for:

- **Convert to datetime first.** If `updated_at` is stored as text, the sort is alphabetical, and formats like `9/1/2026` vs `10/1/2026` will come out in the wrong order.
- **Nulls.** `sort_values` puts `NaT` at the end by default, so a row with a missing timestamp could win. Add `na_position="first"` to the sort if you want those treated as oldest.
- **Ties.** If two rows share the same key and the same `updated_at`, which one survives depends on the sort. Use `kind="stable"` in `sort_values` to keep the original order as the tiebreaker, or add a second sort column.

An alternative that skips the full sort and works well on large frames:

```python
deduped = df.loc[df.groupby("id")["updated_at"].idxmax()]
```

This picks the row with the latest `updated_at` per `id` directly. Note that `idxmax` will error or skip groups where every `updated_at` is null, so the first approach is the safer default.
