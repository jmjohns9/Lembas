Usually you shouldn't drop it. Build a new table, copy the data into it, and swap the two by renaming them inside one transaction. The original stays intact until you're sure the copy is good. Also check first whether `ALTER TABLE` can make the change, because that avoids all of this.

**1. Take a backup first.** This step is required.

```bash
pg_dump -h HOST -U USER -d DBNAME -t public.mytable -Fc -f mytable_backup.dump
```

Test that the backup restores by loading it into a scratch database. You can recover the data only if this file restores.

**2. Create the new table and copy the data.**

```sql
CREATE TABLE mytable_new (LIKE mytable INCLUDING ALL);
-- apply your schema changes to mytable_new here

BEGIN;
LOCK TABLE mytable IN EXCLUSIVE MODE;   -- blocks writes during copy; reads still work
INSERT INTO mytable_new SELECT * FROM mytable;  -- list columns explicitly if the schema changed
SELECT (SELECT count(*) FROM mytable), (SELECT count(*) FROM mytable_new);
ALTER TABLE mytable RENAME TO mytable_old;
ALTER TABLE mytable_new RENAME TO mytable;
COMMIT;
```

**3. Fix what didn't come along.**

- Sequences: `INCLUDING ALL` copies the column defaults, so the new table still uses the old table's sequence. If you made a new sequence, run `setval` to move it past the current max ID.
- Foreign keys from other tables, plus views and functions, follow the object they were created against. They now point at `mytable_old`, so you have to recreate them against the new table.
- Grants and triggers aren't copied by `LIKE`. Reapply them by hand.

**4. Verify, then drop the old table.** Run the app against the new table for a while before you run `DROP TABLE mytable_old;`. Never use `CASCADE` here. It silently drops dependent views.

The trap people hit most often is a dependent foreign key or view that keeps pointing at `mytable_old`. Run `\d+ mytable` and query `pg_depend` before you start so you know what needs repointing.

For a large table, the lock blocks writes for the whole copy. Run it in a maintenance window, or use logical replication or `pg_repack` instead.