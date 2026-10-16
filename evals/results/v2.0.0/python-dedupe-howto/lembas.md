Sort by `updated_at`, then drop duplicates on the key columns and keep the last row in each group.

```python
import pandas as pd

df["updated_at"] = pd.to_datetime(df["updated_at"])

deduped = (
    df.sort_values("updated_at")
      .drop_duplicates(subset=["id"], keep="last")  # replace "id" with the column(s) that define a duplicate
      .reset_index(drop=True)
)
```

- Run `pd.to_datetime` first. If `updated_at` holds strings in a format like `"3/9/2026"`, a plain sort compares them as text and can keep the wrong row.
- If you leave out `subset`, a row only counts as a duplicate when every column matches. Rows that share an `id` but have different timestamps would then all survive. If the same `id` has two rows with the same `updated_at`, the one kept is effectively arbitrary. Add `kind="stable"` to `sort_values`, or put a tiebreaker column in the sort, to make the result predictable.