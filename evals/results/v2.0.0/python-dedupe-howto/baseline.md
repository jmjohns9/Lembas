To keep the latest row in each group, sort by `updated_at` and then call `drop_duplicates` with `keep='last'`:

```python
import pandas as pd

df['updated_at'] = pd.to_datetime(df['updated_at'])  # make sure dates sort as dates, not strings

deduped = (
    df.sort_values('updated_at')
      .drop_duplicates(subset=['id'], keep='last')   # 'id' = the column(s) that define a duplicate
)
```

**Notes:**

- **`subset`** names the columns that make two rows "the same record," such as `['id']` or `['customer_id', 'order_id']`. If you leave it out, a row only counts as a duplicate when every column matches, and that never happens when the `updated_at` values differ.
- **Convert to datetime first.** If `updated_at` holds strings, they sort alphabetically, which gives the wrong order for formats like `"1/5/2026"` vs `"12/1/2025"`.
- **Ties:** if two rows have the same `updated_at`, which one survives is arbitrary. Add `kind='stable'` to `sort_values` to keep the one that appears last in the original data. You can also sort by a second column, e.g. `sort_values(['updated_at', 'version'])`.
- **NaT values:** missing timestamps sort to the end by default, so `keep='last'` would pick them. Use `sort_values('updated_at', na_position='first')` to avoid that.
- **Restore the original order** afterwards with `.sort_index()` if you need it.

**Alternative using `idxmax`:** this is handy if you don't want to re-sort:

```python
deduped = df.loc[df.groupby('id')['updated_at'].idxmax()]
```

It returns the row with the latest timestamp in each group. One catch: on recent pandas versions, `idxmax` raises an error if a group's `updated_at` values are all NaT, so on dirty data the `sort_values` + `drop_duplicates` version is safer.