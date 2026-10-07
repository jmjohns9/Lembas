Don't drop the original table at all. Build a new copy, move the data into it, swap the names in one transaction, and keep the old table until you've verified the new one. If you only need to add, drop or retype columns, `ALTER TABLE` does that in place and is safer than any rebuild.

1. Take a backup and confirm it restores into a scratch database before you touch production.

   ```bash
   pg_dump -Fc -t public.orders -f orders_backup.dump mydb
   pg_restore -d scratch_db orders_backup.dump
   ```

2. Create the new table from the old definition, then apply your changes to it.

   ```sql
   CREATE TABLE orders_new (LIKE orders INCLUDING ALL);
   -- ALTER TABLE orders_new ... your schema changes here
   ```

3. Copy the data and swap names in one transaction. The lock blocks all reads and writes until commit, so run this in a maintenance window for large tables.

   ```sql
   BEGIN;
   LOCK TABLE orders IN ACCESS EXCLUSIVE MODE;
   INSERT INTO orders_new (id, customer_id, total, created_at)
     SELECT id, customer_id, total, created_at FROM orders;
   ALTER TABLE orders RENAME TO orders_old;
   ALTER TABLE orders_new RENAME TO orders;
   COMMIT;
   ```

   List columns explicitly if the order changed. For a `GENERATED ALWAYS` identity column, add `OVERRIDING SYSTEM VALUE` after the column list.

4. Recreate what `LIKE` does not copy: foreign keys, triggers, grants and row-level security policies.

5. Repoint dependents. Foreign keys in other tables and any views still reference `orders_old` after the rename, because Postgres binds them by object ID, not by name. Drop and recreate them against the new `orders`.

6. Fix sequences. A `serial` column's sequence is still owned by `orders_old`, and dropping that table would drop the sequence too.

   ```sql
   ALTER SEQUENCE orders_id_seq OWNED BY orders.id;
   SELECT setval('orders_id_seq', (SELECT max(id) FROM orders));
   ```

7. Compare row counts between `orders` and `orders_old`, run the application against the new table, and only then run `DROP TABLE orders_old;`. Waiting a few days before dropping is cheap insurance.

Rehearse the whole sequence on a staging copy first, since steps 4 through 6 are where data or access quietly goes missing.
