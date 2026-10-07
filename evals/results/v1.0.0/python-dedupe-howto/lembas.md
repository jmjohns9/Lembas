Sort by `updated_at`, then drop duplicates on your key columns and keep the last row.

```python
import pandas as pd

df["updated_at"] = pd.to_datetime(df["updated_at"])

df = (
    df.sort_values("updated_at")
      .drop_duplicates(subset=["id"], keep="last")  # replace "id" with your key column(s)
      .reset_index(drop=True)
)
```

Convert `updated_at` to datetime first, because sorting date strings in mixed formats gives the wrong order. If you leave out `subset`, pandas only removes rows that match in every column, so rows with different timestamps will all stay.
