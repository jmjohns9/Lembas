Sort by `updated_at`, then drop duplicates and keep the last row in each group:

```python
df['updated_at'] = pd.to_datetime(df['updated_at'])

df = (
    df.sort_values('updated_at')
      .drop_duplicates(subset=['id'], keep='last')
)
```

Replace `['id']` with the column or columns that identify a duplicate. If you leave out `subset`, pandas only removes rows that match in every column. Rows that differ only in `updated_at` would never count as duplicates.

Convert the column with `pd.to_datetime` before sorting. If you sort timestamps stored as strings, the order is alphabetical, so a format like `"3/9/2025"` ends up in the wrong place.