# Review packet

## Q0: Why does my React component re-render every time the parent updates?

### Reference
That's React's default behavior. When a parent re-renders, React re-renders all of its children, even if their props haven't changed. React doesn't compare props unless you ask it to.

**To skip re-renders when props are the same:**

1. **Wrap the child in `React.memo`:**
   ```jsx
   const Child = React.memo(function Child({ value }) { ... });
   ```
   React then does a shallow comparison of props and skips the render if they're equal.

2. **Keep prop references stable.** `memo` has no effect if you pass a new object, array or function on every render:
   ```jsx
   // ❌ new reference every render
   <Child style={{ color: 'red' }} onClick={() => doThing()} />

   // ✅ stable references
   const style = useMemo(() => ({ color: 'red' }), []);
   const onClick = useCallback(() => doThing(), []);
   <Child style={style} onClick={onClick} />
   ```

3. **Watch `children`.** JSX passed as `children` is a new object on every render, so it defeats `memo`.

**Other causes that `memo` won't stop:**
- The child uses a **context** whose value changes. A context value like `value={{ user, setUser }}` is a new object every render unless you wrap it in `useMemo`.
- The child's own **state** or a **custom hook** inside it changes.
- The child's **`key`** changes, which makes React remount it instead of just re-rendering it.

**Other options:**
- **Move state down** into the component that actually uses it, so the parent doesn't re-render.
- **Pass components as `children`** from higher up. Elements created higher up aren't re-created when the parent's state changes.
- **React Compiler:** if your project uses it, memoization is automatic and you mostly don't need `memo`, `useMemo` or `useCallback`.

**Finding the cause:** In the React DevTools Profiler, turn on "Record why each component rendered while profiling" to see which prop or hook triggered each render.

Also, a re-render is usually cheap. Only optimize if the profiler shows it's actually slow.

### Candidate A
That's React's default. When a parent re-renders, every child re-renders too, even if its props haven't changed. To skip those re-renders, wrap the child in `React.memo`, which compares props shallowly:

```jsx
const Child = React.memo(function Child({ items, onSelect }) {
  /* ... */
});
```

The common trap is that `memo` does nothing if the parent creates new objects, arrays or functions on every render. `{}`, `[]` and inline arrow functions get a new identity each time, so the shallow comparison fails. Keep those references stable with `useMemo` and `useCallback`:

```jsx
const items = useMemo(() => data.filter(d => d.active), [data]);
const onSelect = useCallback(id => setSelected(id), []);
```

A child also re-renders when a context it uses changes, and `memo` doesn't stop that. If you use the React Compiler, it adds this memoization for you.

### Candidate B
That's React's default behavior. When a parent re-renders, React re-renders all of its children too, even if their props haven't changed.

To skip those re-renders, wrap the child in `React.memo` so it re-renders only when its props change:

```jsx
const Child = React.memo(function Child({ items, onSelect }) {
  return <List items={items} onClick={onSelect} />;
});
```

`React.memo` compares props by reference, so it won't help if the parent creates new objects, arrays or functions on every render. Wrap those in `useMemo` and `useCallback`:

```jsx
const items = useMemo(() => data.filter(d => d.active), [data]);
const onSelect = useCallback(id => setSelected(id), []);
```

Context can also cause re-renders. A component that reads a context re-renders whenever that context's value changes, even when wrapped in `React.memo`.

If you use React Compiler, it adds this memoization automatically.

### Candidate C
React default: parent renders, every child renders too. Props changed or not.

Fix: wrap child in `React.memo`. Then it skips re-render when props are shallow-equal.

`React.memo` still re-renders if any prop is a new reference on each parent render:
- Inline object or array (`style={{...}}`, `items={[...]}`): wrap in `useMemo`.
- Inline function (`onClick={() => ...}`): wrap in `useCallback`.
- `children` JSX: new elements every render, so memo can't skip.

Other causes `memo` doesn't stop:
- Child uses a context whose value changed. Memoize the provider `value`.
- Child's own state or hooks changed.
- Changing `key` remounts the child, not just re-renders it.

Find it: React DevTools Profiler, "Record why each component rendered".

Re-render is cheap and fine unless it's slow. Measure before memoizing.

## Q1: Explain database connection pooling.

### Reference
Connection pooling means keeping a set of open database connections and reusing them, instead of opening a new connection for every request.

**Why it matters:** Opening a connection is expensive. It takes a TCP handshake, often a TLS negotiation, authentication, and setting up a session on the server. That can take tens of milliseconds or more. Each open connection also uses memory on the database server. In Postgres, for example, every connection is its own process.

**How it works:**
1. At startup, the pool opens some connections (a minimum, which can be zero).
2. When the app needs the database, it **borrows** a connection that is free.
3. When the query or transaction finishes, the app **returns** the connection to the pool instead of closing it.
4. If every connection is busy, the pool opens a new one if it is still under its maximum. Otherwise the request **waits**, and fails with an error if the wait runs past a timeout.
5. The pool checks connection health (validation queries or keepalives). It also closes connections that have been idle too long or are too old (idle timeout, max lifetime).

**Key settings:**
- **Max pool size:** the most important one. If it's too small, requests queue up. If it's too large, the database is overloaded and slows down from contention. A common starting point is about `cores × 2` per database instance, then tune based on measurements.
- **Min idle:** how many connections to keep ready.
- **Connection/acquire timeout:** how long a request waits for a free connection.
- **Idle timeout and max lifetime:** close stale connections before the database, a firewall or a load balancer drops them.

**Types:**
- **In-app pools:** HikariCP (Java), SQLAlchemy's pool (Python), pgx/database/sql (Go), node-postgres `Pool`.
- **External poolers:** PgBouncer, pgpool, RDS Proxy. These sit between many app instances and the database. They matter with serverless functions or many replicas, where each app's own pool would add up to too many connections.
- **Pooling modes (PgBouncer):** *session* (one client holds a connection for its whole session), *transaction* (a connection is returned after each transaction, which is the most efficient), and *statement*. Transaction mode breaks session state such as `SET`, advisory locks and some prepared statements.

**Common problems:**
- **Leaks:** forgetting to return connections, which uses up the pool. Use `try/finally`, `with` or `defer`.
- **Holding connections during slow non-database work,** such as HTTP calls inside a transaction.
- **Total connections = pool size × number of app instances.** This number has to stay under the database's `max_connections`.
- **Leftover session state:** temp tables or `SET` variables carrying over to the next user of the connection.

In short: opening connections is expensive, so open them once, share them, and set a limit so the database isn't overloaded.

### Candidate A
Connection pooling keeps a set of open database connections and reuses them across requests instead of opening a new one each time. Opening a connection is slow because it needs a TCP handshake, often TLS, authentication and server-side process setup. A query that takes 2 ms can easily spend 20 to 50 ms just connecting.

When your code needs the database, it borrows an idle connection from the pool, runs its queries and returns it. If every connection is busy, the request waits until one is free or times out.

The main settings are:
- **Max size** caps how many connections your app opens, which keeps it under the database's connection limit.
- **Min idle** keeps some connections open and ready.
- **Timeouts** control how long a request waits for a connection and when idle connections close.

HikariCP in Java and SQLAlchemy in Python have built-in pools. PgBouncer is a separate proxy that pools Postgres connections for many app instances.

The most common mistake is not returning a connection to the pool, for example when an error skips the cleanup code. That connection is lost to the pool, and once enough are lost, requests start hanging.

### Candidate B
Connection pooling keeps a set of open database connections ready for reuse, so the app doesn't pay to open a new one on every request. Opening a connection is expensive. It takes a TCP handshake, often TLS, authentication, and on Postgres a new server process.

When your code needs the database, it borrows a connection from the pool, runs its queries, and returns it. If every connection is busy, the request waits until one frees up or a timeout hits. Most libraries do this for you, for example HikariCP, SQLAlchemy and pgBouncer.

The main settings are pool size, the wait timeout and the idle timeout.

The most common mistake is forgetting to return a connection, often on an error path. The pool slowly drains, and then every request hangs. Use `with` or try/finally so the connection always goes back.

The second is making pools too large. Total connections equal pool size × app instances, and that total can go past the database's `max_connections`.

### Candidate C
Opening a DB connection is expensive: TCP handshake, TLS, auth, session setup. That's often 10–100ms or more each time.

A pool keeps a set of connections open and reuses them:
1. App borrows an idle connection from the pool.
2. Runs its queries.
3. Returns the connection to the pool. The connection is not closed.

**Gains:**
- No handshake on each request, so latency drops.
- Total connections are capped, so the DB isn't flooded. Each Postgres connection is its own process and uses several MB of RAM.
- Predictable load under traffic spikes.

**Key settings:**
- `max` / pool size: upper limit on open connections. Too high overloads the DB. Too low makes requests queue.
- `min` / idle: connections kept warm.
- Acquire timeout: how long a request waits for a free connection before it errors.
- Idle timeout: closes connections that sit unused.
- Max lifetime: recycles old connections, which avoids stale connections and helps with failover or DNS changes.
- Validation: tests a connection on borrow, e.g. `SELECT 1`.

**Pitfalls:**
- Leaks: a connection is never returned, the pool runs dry and requests hang. Always release in `finally` or use a context manager.
- Session state carries over: temp tables, `SET` variables or an open transaction stay on the connection for the next user. Reset on return.
- Many app instances × pool size can exceed the DB's `max_connections`.
- Serverless (Lambda) can't keep a local pool between invocations, so use an external pooler.

**Where the pool lives:**
- In the app's library: HikariCP (Java), SQLAlchemy pool, `pg-pool` (Node), Go `database/sql`.
- In an external proxy: PgBouncer, RDS Proxy, ProxySQL. Many apps share one pool. PgBouncer's transaction mode multiplexes many clients over a few server connections, but it breaks session features such as prepared statements (in older versions) and advisory locks.

**Sizing rule of thumb** (from the HikariCP/Postgres guidance): about `cores * 2 + effective_spindles`. A small pool is usually faster than a large one.

```python
engine = create_engine(url, pool_size=10, max_overflow=5,
                       pool_timeout=30, pool_recycle=1800, pool_pre_ping=True)
with engine.connect() as conn:   # borrowed
    conn.execute(text("SELECT 1"))
# returned to pool here
```

## Q2: What's the difference between TCP and UDP?

### Reference
**TCP (Transmission Control Protocol)**
- **Connection-oriented:** a handshake (SYN, SYN-ACK, ACK) sets up the connection before any data is sent.
- **Reliable:** it acknowledges what arrives and resends anything lost, so data arrives complete and in order.
- **Flow and congestion control:** it adjusts the send rate so it doesn't overwhelm the receiver or the network.
- **Byte stream:** data has no message boundaries, so the application has to mark where each message starts and ends.
- **More overhead:** the header is 20+ bytes, and the handshake and retransmissions add latency.
- **Used for:** HTTP/1.1 and HTTP/2, SSH, email (SMTP/IMAP), file transfer and databases.

**UDP (User Datagram Protocol)**
- **Connectionless:** there is no handshake, so it sends packets straight away.
- **Unreliable:** it doesn't acknowledge or resend, and packets can be lost, duplicated or arrive out of order.
- **No flow or congestion control:** it sends as fast as the application asks it to.
- **Message-based:** each datagram keeps its boundaries.
- **Low overhead:** the header is 8 bytes, which keeps latency low.
- **Used for:** DNS, video and voice calls, online games, streaming, DHCP and QUIC (which HTTP/3 runs on, and which builds its own reliability on top of UDP).

**In short:** use TCP when every byte must arrive correctly and in order. Use UDP when speed and low latency matter more than perfect delivery, or when the application handles reliability itself.

### Candidate A
TCP is connection-based and reliable, while UDP is connectionless and fast but gives no delivery guarantees.

TCP sets up a connection with a handshake before sending anything. It guarantees that data arrives in order and without loss by retransmitting missing packets, and it slows down when the network is congested. That reliability adds latency and overhead. It suits web pages, email, file transfers and SSH.

UDP sends independent datagrams with no handshake. It has no retransmission or ordering and no congestion control. Lost or reordered packets are left for the application to deal with or ignore. Its smaller headers and lower latency suit video calls, online games, DNS and live streaming, where late data is worthless anyway.

Use TCP when correctness matters more than speed, and UDP when timeliness matters more than completeness. QUIC (HTTP/3) runs on UDP and adds its own reliability, which gives you the advantages of both.

### Candidate B
TCP is a reliable, connection-based protocol. UDP is a lightweight, connectionless protocol that sends packets with no delivery guarantees.

- **Connection:** TCP sets up a connection with a handshake before sending data. UDP sends packets right away.
- **Reliability:** TCP retransmits lost packets and delivers data in order. UDP may lose, duplicate or reorder packets.
- **Overhead:** TCP has a 20-byte minimum header and adds latency for acknowledgments and congestion control. UDP has an 8-byte header and adds very little delay.
- **Data model:** TCP is a byte stream with no message boundaries. UDP keeps each datagram separate.
- **Typical uses:** TCP is used for web pages, email, file transfer and SSH. UDP is used for DNS, video calls, gaming and streaming. QUIC, which carries HTTP/3, runs on UDP.

A common mistake is assuming one TCP `send()` matches one `recv()`. Because TCP has no message boundaries, your application has to frame its own messages.

### Candidate C
**TCP**: connection-oriented (handshake first). Reliable: retransmits lost packets, in-order delivery, no duplicates. Flow and congestion control. Byte stream. Bigger header (20+ bytes). More latency.

**UDP**: connectionless. No delivery guarantee, no ordering, no retransmit. Discrete datagrams. 8-byte header. Low latency, low overhead.

**Use TCP**: web (HTTP/1.1, HTTP/2), SSH, email, file transfer. Anything where every byte must arrive.

**Use UDP**: DNS, VoIP, video calls, gaming, streaming. Speed beats completeness, and a late packet is useless anyway. Also QUIC (HTTP/3), which builds its own reliability on top of UDP.

## Q3: How do I fix a memory leak in a long-running Node.js process?

### Reference
## 1. Confirm it's actually a leak
Watch memory over time:
```js
setInterval(() => console.log(process.memoryUsage()), 60_000);
```
If `heapUsed` keeps climbing even after GC (sawtooth pattern whose low points keep rising), you have a leak. If `rss` grows but `heapUsed` doesn't, look at Buffers and native addons instead.

## 2. Capture heap snapshots
- Start with `node --inspect app.js`, open `chrome://inspect`, go to **Memory**, and take a heap snapshot.
- Or take one from code: `require('v8').writeHeapSnapshot()`.
- Or have Node write one automatically near OOM: `node --heapsnapshot-near-heap-limit=2 app.js`.
- Or write one on a signal: `node --heapsnapshot-signal=SIGUSR2 app.js`, then `kill -USR2 <pid>`.

## 3. Compare snapshots
Take snapshot A, apply load, force GC, then take snapshot B. In DevTools, open B in **Comparison** view against A and sort by **# Delta** or **Size Delta**. Check the **Retainers** panel to see what is keeping objects alive.

**Allocation instrumentation on timeline** shows which allocations survive over time.

## 4. Common culprits
| Cause | Fix |
|---|---|
| Unbounded caches or Maps | Use an LRU (`lru-cache`) or a TTL, or a `WeakMap` |
| Event listeners never removed | Call `off()`/`removeListener`, use `{ once: true }`, or an `AbortSignal` |
| `setInterval` or timers never cleared | `clearInterval`, or `unref()` |
| Closures holding large objects | Null out references and keep closure scope small |
| Global arrays or log buffers | Cap their size or flush them |
| Promises that never settle | Add timeouts or an `AbortController` |
| DB or HTTP connections not released | Use pooling and `finally { release() }` |
| `AsyncLocalStorage` or request context stored globally | Scope it to the request |

A `MaxListenersExceededWarning` is a strong hint that listeners are leaking.

## 5. Tools
- **clinic.js** (`clinic heapprofiler`, `clinic doctor`)
- `node --trace-gc` to see how GC behaves
- **memlab** to find leaks automatically
- APM tools (Datadog, New Relic) to track heap trends in production

## 6. Mitigations while you find the root cause
- Raise the heap limit: `--max-old-space-size=4096`. This buys time but doesn't fix the leak.
- Restart the process on a memory threshold, for example PM2's `max_memory_restart` or a k8s memory limit plus restarts.

**Workflow:** reproduce under load, take a snapshot, run the load again, take another snapshot, diff them, follow the retainers, fix, and confirm the heap levels off.

### Candidate A
Confirm the leak with heap snapshots, find what keeps growing, then release the references that hold it.

1. **Confirm it.** Log `process.memoryUsage().heapUsed` over time. A sawtooth pattern that keeps climbing after garbage collection means a leak. Steady growth in `rss` with a flat heap points to native memory or buffers instead.
2. **Take snapshots.** Start with `node --inspect app.js`, open `chrome://inspect`, and take three heap snapshots a few minutes apart under load. In the Comparison view, look for object types whose count only goes up.
3. **Follow the retainers.** The Retainers panel shows which reference keeps each leaked object alive.
4. **Fix the usual causes:**
   - Caches or Maps with no limit. Add a size cap or TTL, for example with `lru-cache`, or use `WeakMap` for keys tied to an object's lifetime.
   - Event listeners that are added and never removed. Watch for `MaxListenersExceededWarning`.
   - `setInterval` timers that are never cleared, and closures that capture large objects.
   - Promises that never settle, or arrays that store data per request.

In production you can capture snapshots without a debugger using `node --heapsnapshot-signal=SIGUSR2` or `v8.writeHeapSnapshot()`. Taking a snapshot pauses the process and can roughly double its memory use for a moment, so take it from one instance at a time.

### Candidate B
Confirm the leak, take heap snapshots and compare them to find what keeps growing, then fix the code that holds those references.

1. **Confirm it.** Log `process.memoryUsage().heapUsed` over time. A real leak keeps rising after garbage collection. Brief spikes that come back down are normal.
2. **Capture snapshots.** Start with `node --inspect app.js`, then take heap snapshots in Chrome DevTools (`chrome://inspect`). Take one at the start, one after some load, and one after more load. In production, you can call `require('v8').writeHeapSnapshot()` or run `node --heapsnapshot-signal=SIGUSR2 app.js` and send that signal.
3. **Compare them.** In DevTools, use the "Comparison" view and sort by "# Delta". Then follow the "Retainers" path to see which object keeps the growing data alive.
4. **Fix the usual causes:**
   - Caches or Maps that never evict entries. Use an LRU with a size limit, or a `WeakMap`.
   - Event listeners added on each request but never removed. Node's `MaxListenersExceededWarning` often points to this.
   - `setInterval` timers that are never cleared.
   - Closures that keep large objects, such as request or response objects, alive.

Taking a heap snapshot pauses the process and can briefly use about twice the heap size in memory. In production, take it from one instance that has been removed from the load balancer.

### Candidate C
**1. Confirm the leak**
- Track `process.memoryUsage()` over time: `heapUsed`, `rss`, `external`, `arrayBuffers`.
- Leak means memory keeps growing after GC and doesn't level off. If it plateaus, it isn't a leak.
- Check whether you hit `FATAL ERROR: ... JavaScript heap out of memory`.

**2. Capture heap snapshots**
- Run with `node --inspect app.js`, open `chrome://inspect`, then Memory tab.
- Take 3 snapshots: at baseline, after some load, after more load.
- No inspector access? Use `node --heapsnapshot-signal=SIGUSR2 app.js`, then `kill -USR2 <pid>`. Or call `v8.writeHeapSnapshot()` in code.
- Writing a snapshot pauses the process and needs about 2× heap. Avoid peak traffic in prod.

**3. Compare snapshots**
- Use the Comparison view and sort by `# Delta` / `Size Delta`.
- Check the retainers path. It shows what holds the objects in memory.
- Allocation timeline (`Allocation instrumentation on timeline`) shows which code allocates the objects that never get freed.

**4. Usual causes**
- Unbounded caches or `Map`s keyed per request. Fix: an LRU like `lru-cache`, a TTL, or `WeakMap`.
- Event listeners added repeatedly and never removed (`MaxListenersExceededWarning` is the hint). Fix: `off()`/`removeListener`, `once()`.
- `setInterval` or timers never cleared. Fix: `clearInterval`, `timer.unref()`.
- Closures holding large objects, such as a request or buffer captured in a long-lived callback.
- Global arrays used as logs or queues that keep growing.
- Promises that never settle and keep their context alive.
- Streams not consumed or destroyed. Fix: `stream.pipeline()`.
- DB or HTTP clients created per request instead of shared.
- `rss` grows while heap stays flat: the leak is native. Check `Buffer`s, native addons, or allocator fragmentation (try `jemalloc`).

**5. Tools**
- `clinic heapprofiler` / `clinic doctor`
- `memlab`, which finds leaks automatically
- `--trace-gc` to watch GC behavior

**6. Verify the fix**
- Run a load test (`autocannon`) and confirm the heap plateaus.

**Stopgap:** `--max-old-space-size=<MB>` plus restarts from PM2 (`max_memory_restart`) or k8s memory limits. This only hides the leak.

## Q4: What does the SQL EXPLAIN command tell me?

### Reference
`EXPLAIN` shows the **query plan**: the steps the database will take to run your query. It doesn't return any data.

**What it tells you:**
- **Access method:** whether each table is read with a full scan (`Seq Scan` / `ALL`) or through an index (`Index Scan`, `ref`, `range`).
- **Index usage:** which indexes the planner considered (`possible_keys` in MySQL) and which one it actually chose (`key`).
- **Join strategy and order:** nested loop, hash join or merge join, and which table drives the join.
- **Estimated rows:** how many rows the planner expects at each step.
- **Estimated cost:** a relative cost for each step (Postgres shows `cost=startup..total`).
- **Extra operations:** sorts, temporary tables, filesort, aggregation and filters (MySQL lists these under `Extra`, e.g. `Using filesort`, `Using temporary`).

**Variants:**
- `EXPLAIN ANALYZE` (Postgres, MySQL 8.0.18+) actually runs the query and adds real row counts and timings. Comparing these with the estimates shows where the planner guessed wrong. Be careful using it on `UPDATE` or `DELETE`, because the changes really happen.
- Postgres `EXPLAIN (ANALYZE, BUFFERS)` adds I/O and cache hit details.
- `FORMAT JSON` gives output a program can parse.

**Red flags to look for:**
- Full scans on large tables when you're filtering on a column (often a missing index).
- Estimated rows far from the actual rows (statistics are stale, so run `ANALYZE`).
- Expensive sorts or temp tables that an index could avoid.
- Nested loops over large row counts.

**Example (Postgres):**
```sql
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 42;
-- Index Scan using idx_orders_customer on orders (cost=0.43..8.45 rows=5) (actual time=0.02..0.03 rows=4 loops=1)
```

In short, it shows why a query is slow and whether your indexes are being used.

### Candidate A
EXPLAIN shows the plan the database will use to run a query, without running it. The plan includes:

- **Access method:** a full table scan, an index scan, or an index-only scan for each table.
- **Join strategy and order:** nested loop, hash join or merge join, and which table is read first.
- **Estimated cost:** the planner's relative cost for each step and for the whole query.
- **Estimated rows:** how many rows the planner expects each step to return.
- **Extra steps:** sorts, aggregations and filters, and where in the plan they happen.

You usually use it to find slow queries, missing indexes or bad join orders.

The common trap is that plain EXPLAIN only shows estimates. `EXPLAIN ANALYZE` (PostgreSQL, and MySQL 8.0.18+) shows real times and row counts, but it runs the query. To try it on an `UPDATE` or `DELETE` without keeping the changes, wrap it in a transaction and roll back:

```sql
BEGIN;
EXPLAIN ANALYZE DELETE FROM orders WHERE created_at < '2020-01-01';
ROLLBACK;
```

### Candidate B
EXPLAIN shows the execution plan the database will use to run a query, without running it. It tells you:

- **Access method:** whether each table is read with a full scan or through an index, and which index.
- **Join strategy and order:** nested loop, hash join or merge join, and which table drives the join.
- **Estimated cost and rows:** the planner's guess at how expensive each step is and how many rows it will return.
- **Extra operations:** sorts, aggregations, temporary tables and filters applied after rows are read.

You use it to find slow spots, such as a sequential scan on a large table that should use an index, or row estimates that are far off.

In PostgreSQL, `EXPLAIN ANALYZE` actually runs the query and adds real timings and row counts, so you can compare them with the estimates. MySQL 8.0.18+ also has `EXPLAIN ANALYZE`. Be careful using it on `INSERT`, `UPDATE` or `DELETE`, because the changes really happen. To avoid that, wrap it in a transaction and roll it back.

### Candidate C
The planner's execution plan for a query. It doesn't run the query unless you use `EXPLAIN ANALYZE`.

Shows:
- **Access method** per table: full/sequential scan, index scan, index-only scan.
- **Join strategy and order**: nested loop, hash join, merge join.
- **Estimated rows** per step, plus cost (Postgres) or `filtered` % (MySQL).
- **Extra ops**: sort, temporary table, filesort, aggregate.
- **Index chosen**: `key` and `possible_keys` (MySQL).

`EXPLAIN ANALYZE` actually runs the query. It adds real time and real row counts per node. A big gap between estimated and actual rows means stale statistics, so run `ANALYZE`.

Use it to find full scans on big tables, missing indexes, bad join order and costly sorts.

Postgres extra: `EXPLAIN (ANALYZE, BUFFERS)` shows cache hits vs disk reads.

Caution: `EXPLAIN ANALYZE` on `INSERT`/`UPDATE`/`DELETE` really changes data. Wrap it in `BEGIN; ... ROLLBACK;`.

## Q5: How does a hash table handle collisions?

### Reference
A collision happens when two keys hash to the same bucket. There are two main ways to handle it.

**1. Separate chaining**
- Each bucket holds a small list (or tree) of all the entries that hashed there.
- To insert, add the entry to that bucket's list. To look up, hash the key and then scan only that list.
- The table degrades gracefully as it fills up, and deletion is simple.
- The downside is extra memory for pointers and worse cache locality.
- Java's `HashMap` works this way. It switches a bucket's list to a red-black tree once the list gets long.

**2. Open addressing**
All entries live in the array itself. On a collision, the table checks other slots in a set order (called probing):
- **Linear probing:** try `i, i+1, i+2, …`. This is cache-friendly, but filled slots tend to bunch together ("primary clustering").
- **Quadratic probing:** try `i+1², i+2², …`. This reduces clustering.
- **Double hashing:** the step size comes from a second hash function, `i + k·h₂(key)`. This spreads entries out best.
- **Robin Hood hashing** and **cuckoo hashing** are variants that bound or even out probe lengths.

Deletion needs care here. You can't just empty a slot, because that would break the probe chain for keys stored after it. Instead you mark it with a "tombstone" or shift later entries back. Python's `dict` and Rust's `HashMap` (SwissTable) use open addressing.

**Keeping collisions rare**
- **Load factor:** when the ratio of entries to buckets passes a threshold (around 0.75 for chaining, often lower for open addressing), the table allocates a bigger array and rehashes every entry.
- **Good hash functions:** a function that spreads keys evenly, sometimes with a random seed, also guards against attackers deliberately causing collisions.

With a good hash function and a sensible load factor, insert, lookup and delete take O(1) time on average. The worst case, when every key collides, is O(n), or O(log n) if buckets use trees.

### Candidate A
A hash table handles collisions in one of two main ways: chaining or open addressing.

- **Separate chaining:** Each bucket holds a list or small tree of entries. Colliding keys get appended there, and a lookup scans that bucket's list. Java's `HashMap` uses this and switches a long bucket to a tree.
- **Open addressing:** All entries live in the array itself. When a slot is taken, the table probes other slots in a set order: linear probing (next slot), quadratic probing or double hashing. Python's `dict` uses this.

Both stay fast only while the load factor is kept low. Tables resize and rehash when it passes a threshold, usually around 0.75 for chaining and lower for open addressing. A common mistake with open addressing is deleting an entry by simply emptying its slot. That breaks the probe chain for keys stored after it, so implementations mark the slot with a tombstone instead.

### Candidate B
Two main families:

**Separate chaining.** Each bucket holds a list (or a tree). Colliding keys get appended to it. Lookup hashes to the bucket, then scans it. Java 8+ `HashMap` turns a long chain into a red-black tree once it reaches 8 entries.

**Open addressing.** All entries live in the array itself. On a collision, probe for another slot:
- **Linear probing:** `i+1, i+2, …`. Cache-friendly, but entries clump together (primary clustering).
- **Quadratic probing:** `i+1², i+2², …`. Less clumping.
- **Double hashing:** step size `h2(key)`. Least clumping.
- **Robin Hood hashing:** when inserting, a key that is far from its home slot takes the place of one that is closer. This evens out probe lengths.
- **Deletion:** needs tombstones or backward-shift. Simply emptying the slot breaks probe chains.

**Both:**
- **Load factor:** about 0.75 for chaining, lower for open addressing. Above it, the table resizes and rehashes. This keeps the average cost at O(1).
- **Worst case:** O(n) when many keys collide, through a bad hash or a deliberate attack. Defenses are a seeded hash (SipHash) and chains that turn into trees.

**Real-world examples:**
- Chaining: Java `HashMap`, C++ `std::unordered_map`.
- Open addressing: Python `dict`, Rust `HashMap` (SwissTable), Go maps (SwissTable since Go 1.24).

### Candidate C
A hash table resolves collisions in one of two main ways.

**Separate chaining:** each bucket holds a list (or a small tree) of every entry that hashes to it. A lookup hashes the key, then scans that bucket's list. It is easy to implement and still works when the table is full, but the pointers cost extra memory and hurt cache performance.

**Open addressing:** every entry lives directly in the array. On a collision, the table probes other slots in a fixed sequence:
- Linear probing checks the next slot, then the one after that. It is cache-friendly but tends to form clusters.
- Quadratic probing jumps by growing amounts to reduce clustering.
- Double hashing takes its step size from a second hash function.

Deleting an entry under open addressing needs a "tombstone" marker so later lookups keep probing past the gap.

Both approaches resize the table and rehash every entry once the load factor gets too high, often around 0.75. This keeps the average cost of operations at O(1).

## Q6: Why am I getting CORS errors in my browser console?

### Reference
I can't see your code or console from here, but CORS errors almost always have the same cause: **your page's JavaScript requests a different origin, and that server's response doesn't allow it.** An origin is the scheme, host and port together, so `http://localhost:3000` and `http://localhost:8080` count as different origins. The browser enforces this rule, not the server. That's why the same request works in curl or Postman.

**Common causes**
1. **The server doesn't send `Access-Control-Allow-Origin`**, or sends a value that doesn't match your page's origin.
2. **The preflight request fails.** Requests that use methods like PUT or DELETE, custom headers like `Authorization`, or `Content-Type: application/json` make the browser send an `OPTIONS` request first. If the server returns a 404, 401 or 500 for it, or leaves out `Access-Control-Allow-Methods` or `Access-Control-Allow-Headers`, the real request is blocked.
3. **Credentials with a wildcard.** If you use `credentials: 'include'` or `withCredentials`, the server must name your exact origin (not `*`) and send `Access-Control-Allow-Credentials: true`.
4. **The server returned an error.** Error responses from a crash, an auth failure or a proxy often have no CORS headers, so a 500 shows up as a CORS error.
5. **Wrong URL or protocol**, such as `http` and `https` mixed, a missing port, or a redirect to another origin.

**Fixes**
- **Server you control:** add CORS middleware. Examples are `cors()` in Express, `django-cors-headers`, `CORSMiddleware` in FastAPI, and `@CrossOrigin` in Spring. Make sure it also handles `OPTIONS` requests.
- **Local development:** use a dev-server proxy so the request comes from the same origin, for example Vite's `server.proxy` or the `"proxy"` field in CRA's `package.json`.
- **Third-party API that doesn't allow browser calls:** send the request through your own backend.
- `mode: 'no-cors'` doesn't fix this. It only gives you an opaque response you can't read.

**To find the cause:** open DevTools, go to the Network tab and click the failed request. Check whether there's an `OPTIONS` request, what status it returned, and which `Access-Control-*` headers the response actually has.

If you paste the exact console error and tell me your frontend origin and backend stack, I can point to the fix. I can also open the page in Chrome and read the console and network requests myself, if you'd like.

### Candidate A
CORS errors mean your page tried to call a different origin (scheme, domain or port), and that server's response didn't include headers allowing your origin. The browser blocks it, not the server. Common causes, most likely first:

1. **The server sends no `Access-Control-Allow-Origin` header.** Add your frontend's origin on the server, for example `Access-Control-Allow-Origin: http://localhost:3000`.
2. **The preflight fails.** Requests with JSON bodies, custom headers or methods like PUT and DELETE send an `OPTIONS` request first. The server must answer it with a 2xx and the right `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`.
3. **Credentials are sent with a wildcard origin.** If you use `credentials: 'include'`, the server can't send `*`. It must name your exact origin and also send `Access-Control-Allow-Credentials: true`.
4. **A server error hides the real problem.** A 500 or a redirect often has no CORS headers, so it shows up as a CORS error. Check the Network tab for the actual status.

During development, a dev-server proxy (Vite `server.proxy`, CRA `proxy`) avoids CORS entirely.

### Candidate B
Your page's JavaScript is calling a different origin (scheme, host or port), and that server's response doesn't include the CORS headers that allow your origin. The browser enforces CORS, not the server, which is why the same request works in curl or Postman.

Most likely causes:

1. **The server doesn't send `Access-Control-Allow-Origin`** for your origin. Add your exact origin on the server, for example `http://localhost:3000`.
2. **The preflight `OPTIONS` request fails.** Custom headers like `Authorization`, or a `Content-Type: application/json` body, trigger a preflight. The server must answer it with a 2xx and the matching `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`.
3. **Credentials are sent with a wildcard.** With `credentials: 'include'`, `Access-Control-Allow-Origin: *` is rejected. The server must name the exact origin and send `Access-Control-Allow-Credentials: true`.
4. **The request is actually failing.** A 401, 404 or 500 from a proxy or framework often has no CORS headers, so the browser reports it as a CORS error and hides the real one. Check the status code in the Network tab.

You can't fix CORS from the frontend. During development, a dev-server proxy (Vite's `server.proxy`, for example) avoids it.

If you paste the exact error text, I can tell you which cause it is.

### Candidate C
Browser blocks cross-origin requests unless the server allows them. Page origin (scheme + host + port) differs from the API origin, and the server's response lacks the right headers.

**Common causes:**
1. **No `Access-Control-Allow-Origin` header.** Server must return your origin or `*`.
2. **Preflight failed.** Non-simple requests (`PUT`/`DELETE`, `Content-Type: application/json`, custom headers like `Authorization`) send `OPTIONS` first. Server must answer it with 2xx plus `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`.
3. **Credentials.** If you use `credentials: 'include'` or `withCredentials`, server needs `Access-Control-Allow-Credentials: true` and an exact origin, not `*`.
4. **Error responses.** A 401/404/500 from a proxy or gateway often lacks CORS headers, so the browser reports CORS and hides the real error.
5. **Origin mismatch.** `localhost` and `127.0.0.1` are different origins. So are `http` and `https`, and different ports.

**Fixes:**
- **Your API:** add CORS middleware, for example Express `cors({ origin: 'http://localhost:3000', credentials: true })`. Handle `OPTIONS`.
- **Third-party API:** call it from your backend or a dev proxy (Vite `server.proxy`, CRA `"proxy"`).
- **Don't use `mode: 'no-cors'`.** It gives an opaque response you can't read.

**Debug:** DevTools, Network tab. Check the `OPTIONS` request and the response headers.

For a specific fix, paste the exact console error, your frontend origin, the API URL and your server stack. I can also inspect it live in Chrome if you want.

## Q7: What's the point of using a debouncer on a search input?

### Reference
A debouncer waits until the user stops typing for a short time (often 200–500 ms) before it runs the search. Without one, the search runs on every keystroke.

**Why it helps:**
- **Fewer requests:** Typing "laptop" fires 6 searches without debouncing. With it, you get 1. That puts less load on your server or API, keeps you under rate limits, and lowers cost.
- **No wasted work:** Results for "l", "la", "lap" are useless because the user hasn't finished typing.
- **Fewer race conditions:** With many requests in flight, an older response can arrive after a newer one and overwrite the correct results. Fewer requests means fewer chances for this.
- **Smoother UI:** The results list doesn't flicker and re-render on every key, and you avoid running expensive filtering or rendering on each keystroke.

**Example:**
```js
let t;
input.addEventListener('input', e => {
  clearTimeout(t);
  t = setTimeout(() => search(e.target.value), 300);
});
```

**Trade-off:** It adds a small delay before results show up. Pick the delay to balance responsiveness against load. If the search is purely local and cheap, you may not need a debouncer at all.

### Candidate A
A debouncer waits until typing pauses (often ~300ms) before it fires the search, so you get one request per pause instead of one per keystroke.

- **Fewer API calls:** typing "react hooks" sends 1 request, not 11. This cuts server load, cost and rate-limit hits.
- **Less wasted work:** no filtering, rendering or result flicker for half-typed queries.
- **Fewer race conditions:** with fewer requests in flight, a slow old response is less likely to overwrite a newer one. The risk doesn't go away, though, so still cancel stale requests with `AbortController`.
- **Smoother UI:** input stays responsive because heavy work doesn't run on every keystroke.

Tradeoff: results arrive about one delay-length later. For instant local filtering of a small list, skip debouncing.

```js
function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
input.addEventListener('input', debounce(e => search(e.target.value), 300));
```

### Candidate B
A debouncer waits until the user stops typing for a short pause, often 200–300 ms, and only then runs the search. If you search on every keystroke, typing "laptop" sends six requests when you only wanted one.

This gives you:

- **Fewer requests**, which lowers server load, API costs and rate-limit hits.
- **A steadier UI**, because results don't flicker through partial matches like "l", "la" and "lap".
- **Better performance**, because expensive filtering or rendering doesn't run on every keystroke.

A debouncer does not stop responses from arriving out of order. A slow reply for "lap" can still overwrite the results for "laptop". To prevent that, cancel the earlier request with `AbortController` or ignore any response that doesn't match the current query. In React, create the debounced function once, for example with `useMemo` or `useRef`. If you create it on every render, the timer resets each time and the debounce stops working.

### Candidate C
A debouncer waits until the user stops typing for a short pause, usually 200 to 500 ms, and only then runs the search. Without it, typing "laptop" fires six searches, one per keystroke.

That gives you three benefits:

- **Less load:** Far fewer API calls or database queries, which cuts server costs and helps you avoid rate limits.
- **No stale results:** Fewer requests are in flight at once, so it's less likely an older, slower response lands after a newer one and overwrites it.
- **Smoother UI:** The results list doesn't flicker or re-render on every keystroke, and you skip expensive work on partial words like "lap".

The cost is a short delay before results appear. If you want results to update while the user is still typing, use throttling instead, which runs the search at most once per interval.

## Q8: How does git rebase differ from git merge?

### Reference
Both commands bring in changes from one branch to another. The difference is what happens to the history.

**`git merge`**
- Creates a new **merge commit** with two parents, which joins the two branches.
- Leaves existing commits unchanged, so the history shows that work happened in parallel.
- Safe on shared or public branches, because no commits get rewritten.
- History can get cluttered with many merge commits.

**`git rebase`**
- **Replays** your commits one by one on top of the target branch. Each one becomes a new commit with a new SHA.
- Gives a **linear** history with no merge commits.
- **Rewrites history.** Don't rebase commits others have already pulled, or you'll need a force-push and their copies will no longer match.
- Conflicts come up one commit at a time, so you may resolve several in a row. Merge shows them all at once.
- `git rebase -i` also lets you squash, reorder, edit or drop commits.

**Example** (feature branched from main, and main moved on since):
```
merge:   A---B---C---M   (main)       rebase:  A---B---C---D'---E'  (feature)
              \     /
               D---E     (feature)
```

**Rule of thumb:** rebase your own local or feature branches to keep them clean and up to date. Use merge to bring finished work into shared branches like `main`.

### Candidate A
Both combine work from one branch into another. They differ in how the history ends up looking.

**Merge** creates a new merge commit that joins the two branches. Every existing commit stays as it was, so the history is accurate but can branch and rejoin many times.

**Rebase** replays your commits one by one on top of the target branch, creating new commits with new hashes. The history ends up as a single straight line, as if you had started your work from the latest commit.

```
git merge main    # adds a merge commit
git rebase main   # rewrites your commits on top of main
```

Rebase rewrites history, so don't rebase commits that others have already pulled. Use it to tidy up your local or private branches, and use merge for shared branches.

### Candidate B
Both put one branch's changes onto another. They differ in how history comes out.

**Merge** (`git merge feature`)
- Makes a merge commit with two parents.
- Keeps history exactly as it happened, including when branches split and joined.
- Never rewrites existing commits, so it's safe on shared branches.
- History can get cluttered with merge commits.

**Rebase** (`git rebase main`)
- Replays your commits one by one on top of the target branch.
- Gives a straight, linear history with no merge commit.
- Rewrites commits, so they get new SHAs. Pushing afterwards needs `git push --force-with-lease`.
- Conflicts can come up once per replayed commit.
- `git rebase -i` lets you squash, reorder or edit commits.

**Rule:** never rebase commits that others have already pulled. Rebase is fine for tidying a local branch before a PR. Use merge to bring work into shared branches.

**Common workflow:** rebase your feature branch onto `main`, then merge it with a fast-forward or squash.

### Candidate C
Both combine work from one branch into another. Merge keeps history as it happened, and rebase rewrites it to look linear.

- **Merge** (`git merge main`) creates a merge commit that joins the two histories. Existing commits stay unchanged, so it's safe on shared branches, but the history shows every branch and join.
- **Rebase** (`git rebase main`) replays your commits one at a time on top of the target branch. This gives a clean, linear history, but each replayed commit gets a new hash, and you may have to resolve the same conflict once per commit.

A common workflow is to rebase your local feature branch to keep it current, then merge it into `main`.

The main pitfall is rebasing commits that others have already pulled. Their copies no longer match yours, so you'd need to force-push. If you do, use `--force-with-lease`.

## Q9: When should I use a queue vs a topic in messaging systems?

### Reference
Pick based on **how many consumers should handle each message**.

**Queue (point-to-point)**
- Each message goes to **one** consumer.
- Several consumers on the same queue are *competing consumers*: they split the work between them.
- Use a queue when:
  - You're handing out work, like background jobs, order processing or sending emails.
  - Each task should be handled once, not by every worker.
  - You want to scale by adding more workers.
  - You need to absorb load spikes, with the backlog waiting in the queue.
- Examples: RabbitMQ queues, AWS SQS, Azure Service Bus queues.

**Topic (publish/subscribe)**
- Each message goes to **every** subscriber.
- The publisher doesn't know who is listening.
- Use a topic when:
  - You're broadcasting events, like "OrderPlaced" or "UserSignedUp".
  - Several separate systems react to the same event, such as billing, analytics and notifications.
  - You want to add new consumers later without changing the producer.
- Examples: Kafka topics, SNS, Google Pub/Sub, RabbitMQ fanout exchanges.

**Quick test:** if one message should be handled once, use a queue. If one event should be seen by everyone interested, use a topic.

**Hybrid (very common):** one topic fans out to several queues, with one queue per subscribing service. Each service gets its own copy of every event, and that service's instances share the work from its queue. Examples:
- SNS sending to multiple SQS queues
- Kafka consumer groups, where each group gets every message but within a group each partition goes to only one consumer
- Azure Service Bus topics with subscriptions

**Other things to weigh:**
- **Ordering:** queues usually give only best-effort ordering. Kafka keeps order within a partition.
- **Replay:** Kafka-style logs let consumers re-read old messages. Classic queues delete a message once it's acknowledged.
- **Late subscribers:** with plain pub/sub, a subscriber that wasn't connected misses messages unless its subscription is durable.

### Candidate A
Use a queue when each message should be handled by exactly one consumer. Use a topic when every interested subscriber should get its own copy.

**Queue (point-to-point):**
- Work distribution, such as jobs, orders to process, or emails to send.
- Several workers can read from the same queue to share the load, and each message is still processed only once.
- Messages wait in the queue until a consumer takes them.

**Topic (publish-subscribe):**
- Event broadcasting, such as "order placed", where billing, shipping and analytics all need to react.
- New subscribers can be added without changing the publisher.
- Subscribers that aren't connected may miss messages unless they use a durable subscription.

The two are often combined. A publisher sends to a topic, and each subscribing service has its own queue that its workers share. Examples are SNS feeding SQS, and Kafka consumer groups.

### Candidate B
Use a queue when each message should be handled by exactly one consumer. Use a topic when every interested subscriber should get its own copy.

- **Queue (point-to-point):** Good for distributing work, such as order processing, image resizing or sending emails. Adding consumers spreads the load across them, and each job runs once.
- **Topic (publish-subscribe):** Good for broadcasting events, such as "OrderPlaced" going to billing, shipping and analytics at the same time. You can add subscribers without changing the publisher.

A common pattern combines them: publish to a topic, then give each subscribing service its own queue. That way every service sees each event, and each service can still run several load-balanced workers. Examples are SNS fanning out to SQS, or Kafka consumer groups.

The usual mistake is pointing several services at one queue. They then compete for messages, so each service sees only part of the events.

### Candidate C
**Queue**: point-to-point. Each message goes to exactly one consumer.
- Work distribution, load balancing across workers.
- Task/job processing: send email, resize image, charge card.
- Need each message handled only once (one consumer per message).
- Competing consumers scale throughput.

**Topic**: pub/sub. Every subscriber gets its own copy.
- Event broadcast: `OrderPlaced` goes to billing, shipping and analytics.
- Decoupling: producer doesn't know who consumes.
- Adding a new consumer needs no producer change.

**Rule of thumb**:
- Command ("do X") → queue.
- Event ("X happened") → topic.

**Hybrid**: topic fans out to one queue per subscriber service. Each service gets its own copy, and its instances compete on that queue. Examples: SNS→SQS, RabbitMQ fanout exchange→queues, Kafka consumer groups (topic per event, group per service), Azure Service Bus topic subscriptions.

**Other factors**:
- Replay or history needed? Log-based topic (Kafka, Pulsar). Classic queues delete messages once acked.
- Ordering: per queue, or per partition/key on a topic. Not global once you have several consumers.
- Delivery is usually at-least-once either way. Make consumers idempotent.
