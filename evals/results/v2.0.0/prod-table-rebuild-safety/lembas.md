**Problem.** `DROP TABLE` deletes the data along with the table, so "drop and recreate" really means building a new table, copying the rows into it, and swapping it in. In production, the risks are losing rows written during the copy, losing dependent objects (indexes, constraints, foreign keys, triggers, grants, views, sequences), and holding locks long enough to block traffic.

**Fix.** Build the new table beside the old one, then swap them with a rename inside one transaction. Keep the old table until you've confirmed the new one works.

1. Back up the table and confirm the backup restores:
   ```bash
   pg_dump -h HOST -U USER -d DB -t public.orders -Fc -f orders_$(date +%F).dump
   pg_restore -l orders_$(date +%F).dump | head
   ```
2. List everything that depends on the table, because a rename won't carry these over to the new one:
   ```sql
   \d+ public.orders
   SELECT conname, conrelid::regclass FROM pg_constraint WHERE confrelid = 'public.orders'::regclass;  -- incoming FKs
   SELECT DISTINCT dependent_view.relname FROM pg_depend d
     JOIN pg_rewrite r ON d.objid = r.oid
     JOIN pg_class dependent_view ON r.ev_class = dependent_view.oid
     WHERE d.refobjid = 'public.orders'::regclass;                                                     -- views
   ```
3. Create and fill the new table. Stop writes to the table first (maintenance window or app flag), or rows written during the copy will be lost:
   ```sql
   CREATE TABLE public.orders_new (LIKE public.orders INCLUDING ALL);  -- then apply your schema changes
   INSERT INTO public.orders_new SELECT ... FROM public.orders;
   SELECT (SELECT count(*) FROM public.orders), (SELECT count(*) FROM public.orders_new);
   ```
4. Swap them with a lock timeout so the swap fails instead of queuing behind long queries:
   ```sql
   BEGIN;
   SET LOCAL lock_timeout = '5s';
   ALTER TABLE public.orders RENAME TO orders_old;
   ALTER TABLE public.orders_new RENAME TO orders;
   -- recreate incoming FKs, views, grants; reset sequence ownership:
   -- ALTER SEQUENCE orders_id_seq OWNED BY public.orders.id;
   -- SELECT setval('orders_id_seq', (SELECT max(id) FROM public.orders));
   COMMIT;
   ```
5. Check the app and the row counts, then run `DROP TABLE public.orders_old;` only after a few days.

Practice the whole procedure on a staging copy of production first.

**Alternatives.** If you only need to add, drop, retype or rename columns, use `ALTER TABLE` and skip the rebuild entirely. `ADD COLUMN` with a constant default is instant on Postgres 11 and later. If you're rebuilding to reclaim bloat, use `pg_repack`, which does it online without stopping writes. If the table is too large for a write freeze, use logical replication or triggers to sync writes into the new table, then do the cutover.

**Why this fix.** The swap can be undone with two renames for as long as `orders_old` exists, which a drop-first approach can't offer. The two most common mistakes are forgetting that `INCLUDING ALL` doesn't copy incoming foreign keys, grants or views, and leaving the sequence behind the copied IDs so the next insert fails with a duplicate key error.