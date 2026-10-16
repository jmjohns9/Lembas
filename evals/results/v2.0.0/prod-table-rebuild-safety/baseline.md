Usually you don't need to drop the table at all. First check whether `ALTER TABLE` can make the change, because it keeps the data, indexes, grants and dependencies as they are. If you really do need a full rebuild, the safe pattern is **build the new table, copy into it, then swap names**. Don't drop first and restore afterwards.

## 0. Before anything
- **Take a backup** and confirm it restores:
  ```bash
  pg_dump -Fc -t public.my_table -d prod > my_table.dump
  ```
- **Rehearse the whole thing on a staging copy** of production.
- **Find what depends on the table**, since dropping it breaks or cascades these: views, foreign keys from other tables, triggers, grants, sequences, publications/replication.
  ```sql
  -- FKs pointing at this table
  SELECT conrelid::regclass, conname FROM pg_constraint
  WHERE confrelid = 'public.my_table'::regclass;
  -- Views/other objects depending on it
  SELECT DISTINCT dependent.relname
  FROM pg_depend d
  JOIN pg_rewrite r ON r.oid = d.objid
  JOIN pg_class dependent ON dependent.oid = r.ev_class
  WHERE d.refobjid = 'public.my_table'::regclass;
  ```
  `pg_dump -s -t my_table` also prints the full DDL, including indexes, constraints and grants.

## 1. Can `ALTER TABLE` do it instead?
Adding or dropping columns, changing types, renaming, and adding constraints (`NOT VALID` first, then `VALIDATE`) can all be done in place. To reclaim bloat or reorder physically without long locks, use **`pg_repack`**. Changing column order is about the only common reason left to rebuild.

## 2. The rebuild-and-swap pattern
```sql
BEGIN;
SET lock_timeout = '5s';          -- fail fast instead of queueing behind traffic

-- Block writes while copying so nothing is lost
LOCK TABLE public.my_table IN EXCLUSIVE MODE;

CREATE TABLE public.my_table_new (
  -- new definition here
);

INSERT INTO public.my_table_new (col_a, col_b, ...)
SELECT col_a, col_b, ... FROM public.my_table;

-- Sanity check before swapping
-- SELECT count(*) FROM public.my_table;  vs  my_table_new

ALTER TABLE public.my_table     RENAME TO my_table_old;
ALTER TABLE public.my_table_new RENAME TO my_table;

-- Recreate indexes, constraints, triggers, grants, and FKs from other tables.
-- Point sequences at the new table and keep their values:
-- ALTER SEQUENCE my_table_id_seq OWNED BY public.my_table.id;
-- ALTER TABLE public.my_table ALTER COLUMN id SET DEFAULT nextval('my_table_id_seq');

COMMIT;
```
Keep `my_table_old` for a while. Drop it only after the app has run cleanly against the new table:
```sql
DROP TABLE public.my_table_old;   -- days later, not minutes
```

Because everything runs in one transaction, any failure rolls back and the original table is left untouched.

## 3. Things that commonly go wrong
- **Downtime on large tables:** the copy holds a lock that blocks writes for the whole duration. For big or busy tables, use one of these instead:
  - Copy in batches, then use a trigger on the old table to mirror ongoing writes into the new one, and do a short final swap.
  - Use logical replication into the new table.
  - Use `pg_repack`, if the goal is just a rebuild.
- **Views and FKs follow the renamed table:** they reference the table by OID, so after the swap they point at `my_table_old`. Recreate them against the new table.
- **Sequences:** if `id` was `serial` or identity, don't let the new table start counting from 1. Reuse the old sequence, or `setval` it to `max(id)`.
- **Indexes:** build them *after* the bulk insert, which is much faster. Outside the transaction, use `CREATE INDEX CONCURRENTLY`.
- **Run `ANALYZE my_table;`** afterwards so the planner has statistics.

If you tell me what change you're trying to make, plus the table's rough size and write traffic, I can tell you whether `ALTER TABLE` will do it or write the exact migration.