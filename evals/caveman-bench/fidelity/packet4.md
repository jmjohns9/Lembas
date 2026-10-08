# Review packet

## Q0: Why does my React component re-render every time the parent updates?

### Reference
That's React's default behavior. When a parent re-renders, React re-renders all of its children too, even if their props haven't changed. React doesn't check props unless you tell it to.

**How to stop it:**

1. **Wrap the child in `React.memo`.** It then re-renders only when its props change, using a shallow comparison.
   ```jsx
   const Child = React.memo(function Child({ value, onClick }) { ... });
   ```

2. **Keep prop references the same between renders.** `memo` won't help if the parent creates new objects, arrays or functions on every render, because `{}`, `[]` and `() => {}` are new references each time.
   ```jsx
   const handleClick = useCallback(() => doThing(id), [id]);
   const config = useMemo(() => ({ size: 10 }), []);
   <Child onClick={handleClick} config={config} />
   ```

3. **Move state down.** If the parent's state is only used in one part of the tree, put that state in a smaller component so fewer components re-render.

4. **Pass children as props.** Content passed in as `children` from higher up doesn't re-render when the wrapper's state changes.
   ```jsx
   <Wrapper><ExpensiveChild /></Wrapper>
   ```

**Other common causes:**
- **Context:** any component that uses a context re-renders whenever the context value changes, even with `memo`. Split contexts, or memoize the value you pass to the provider.
- **Inline `key` changes:** if a child's `key` changes, React unmounts and remounts it instead of just re-rendering.
- **StrictMode:** in development, components render twice on purpose.

**Notes:**
- Re-renders are usually cheap. Only optimize if you've measured a real slowdown with the React DevTools Profiler ("Highlight updates" / "Why did this render?").
- If you're using React Compiler (React 19+), it adds this memoization automatically.

If you share the component, I can point to the exact cause.

### Candidate A
By default, React re-renders every child whenever its parent renders, even if the child's props haven't changed. To skip that, wrap the child in `React.memo` so it re-renders only when its props change by shallow comparison.

```jsx
const Child = React.memo(function Child({ items, onSelect }) {
  return /* ... */;
});
```

`memo` only helps if the props stay referentially stable. Objects, arrays and functions created inline in the parent are new on every render, so `memo` sees changed props every time:

```jsx
const items = useMemo(() => data.filter(d => d.active), [data]);
const onSelect = useCallback(id => setSelected(id), []);
<Child items={items} onSelect={onSelect} />
```

A component also re-renders when a context it reads changes, and `memo` does not stop that. If you use the React Compiler, it adds this memoization for you.

### Candidate B
React default: parent render re-renders all children. Props unchanged doesn't matter.

Fix:
- Wrap child in `React.memo`. Skips render when props shallow-equal.
- `memo` breaks if props get new references each render:
  - Inline object/array (`style={{...}}`, `items={[...]}`): use `useMemo`.
  - Inline function (`onClick={() => ...}`): use `useCallback`.
  - `children` JSX: new elements every render, so `memo` won't help.
- Context consumer: re-renders on every provider `value` change. Memoize `value`, or split contexts.
- Move state down into the component that uses it, or pass child as `children` from higher up. Then parent state change doesn't touch it.
- React Compiler (React 19+) auto-memoizes. Manual `memo`/`useMemo`/`useCallback` mostly unnecessary.

Find cause: React DevTools Profiler, enable "Record why each component rendered."

Re-render cheap? Ignore it. Re-render ≠ DOM update.

### Candidate C
That's React's default behavior. When a parent re-renders, all of its children re-render too, even if their props haven't changed. To skip those re-renders, wrap the child in `React.memo`. It then re-renders only when a prop changes by shallow comparison.

```jsx
const Child = React.memo(function Child({ items, onSelect }) {
  return <List items={items} onSelect={onSelect} />;
});

// In the parent: keep references stable across renders
const items = useMemo(() => data.filter(d => d.active), [data]);
const onSelect = useCallback(id => setSelected(id), []);
```

People often wrap a component in `memo` but still pass inline objects, arrays or arrow functions like `style={{...}}` or `onClick={() => ...}`. Those get a new reference on every render, so `memo` sees changed props and re-renders anyway. Context changes and the child's own state also cause re-renders, and `memo` doesn't stop those.

Re-renders are usually cheap. Measure with the React DevTools Profiler before you add memoization. If you're on React 19 with the React Compiler enabled, it handles most of this memoization for you.

## Q1: Explain database connection pooling.

### Reference
**Database connection pooling** means keeping a set of open database connections and reusing them, so you don't open a new one for every request.

**Why it matters**
Opening a connection is expensive. It takes a TCP handshake, often a TLS negotiation, authentication, and server-side setup such as a process or thread plus memory. That can add 10–100+ ms per request. Databases also cap how many connections they accept. In Postgres each connection is a separate OS process using several MB.

**How it works**
1. At startup, the pool opens some connections (a minimum, or "idle", count).
2. When the app needs one, it **borrows** a connection from the pool.
3. When the app finishes, it **returns** the connection. The connection stays open and goes back into the pool.
4. If every connection is busy, the pool either opens a new one (up to a max size) or makes the caller **wait** until one frees up or a timeout passes.
5. The pool also checks connections are still healthy, closes ones that have been idle too long, and replaces ones that have been open too long.

**Key settings**
- **Max pool size:** the most important one. Too small and requests queue up. Too large and the database gets overloaded. A common starting point is about `(CPU cores × 2) + effective disk spindles`, and it's usually smaller than people expect.
- **Min idle:** connections kept ready for traffic spikes.
- **Connection/acquire timeout:** how long a caller waits before giving up.
- **Idle timeout / max lifetime:** retire stale connections so firewalls or the database don't drop them silently.
- **Validation:** a test query or ping, either when a connection is borrowed or in the background.

**Where pooling happens**
- **In the app:** HikariCP (Java), SQLAlchemy's pool (Python), `pg-pool` (Node), Go's `database/sql`.
- **External proxy:** PgBouncer, ProxySQL, RDS Proxy. These share connections across many app instances, which is essential for serverless or heavily scaled-out deployments where each instance's own pool would add up to too many connections.

**PgBouncer pooling modes**
- *Session:* a client keeps the same connection until it disconnects.
- *Transaction:* the connection goes back to the pool after each transaction. This is the most efficient, but session state like prepared statements, `SET`, and advisory locks doesn't carry over.
- *Statement:* the connection goes back after every statement. This is the strictest mode.

**Common pitfalls**
- **Leaks:** forgetting to return a connection. Use `try/finally`, `with`, or `defer`.
- **Leftover state:** a borrowed connection can still carry the previous user's open transaction or session variables.
- **Too many pools:** for example, 50 pods × a pool of 20 = 1,000 connections to the database.
- **Holding connections during slow work:** keeping a connection while calling an external API wastes it.

In short, pooling turns a costly setup step on every request into a cheap borrow-and-return, while capping how much load reaches the database.

### Candidate A
A connection pool keeps a set of open database connections and reuses them across requests instead of opening a new one each time. Opening a connection is expensive: it needs a TCP handshake, often TLS, authentication, and session setup on the server, which can take tens of milliseconds.

When your code needs the database, it borrows an idle connection from the pool, runs its queries, and returns it. If every connection is busy, the request waits until one is free or a timeout runs out. The pool can also replace dead connections and close ones that have sat idle too long.

The main settings are the minimum and maximum pool size, the wait timeout and the idle timeout. Keep the maximum below the database's own connection limit, counted across all app instances. Postgres in particular slows down with too many connections, so a small pool often performs better than a large one.

Examples include HikariCP (Java), SQLAlchemy's built-in pool (Python) and PgBouncer, which runs as a separate pooling proxy.

### Candidate B
Connection pooling keeps a set of open database connections and reuses them across requests, instead of opening and closing a new connection each time. Opening a connection is expensive. It takes a TCP handshake, often TLS, authentication, and server-side setup such as a process or memory allocation. That can cost several milliseconds per query.

When the app needs a connection, it borrows an idle one from the pool. When it finishes, it returns the connection to the pool instead of closing it. If every connection is busy, the request waits until one frees up or a timeout expires. The main settings are minimum idle connections, maximum pool size, acquire timeout and idle or max lifetime.

The most common mistake is forgetting to release connections, for example on an error path. The pool then drains and every request hangs. Another frequent trap is setting the maximum too high. Pool size multiplied by app instances can go over the database's `max_connections`. A small pool usually performs better.

### Candidate C
Pool keeps set of open DB connections; requests borrow one, return it. Skips per-request TCP + TLS + auth handshake, often 10–100 ms each.

**Flow:**
1. App starts. Pool opens `min` connections.
2. Request calls `acquire()`. Gets idle connection, or a new one if under `max`. At `max`, waits in queue until timeout.
3. Query runs.
4. `release()` returns connection to pool. Connection stays open.

**Key settings:**
- `max`: hard cap. Protects DB; Postgres default `max_connections` = 100, shared across all app instances.
- `min` / idle: warm connections kept ready.
- `idleTimeout`: closes unused extras.
- `acquireTimeout`: max wait for free connection, then error.
- `maxLifetime`: recycles old connections. Avoids stale ones after DB, firewall, or LB drops.
- Validation: `SELECT 1` or driver ping before handing out.

**Sizing:** Bigger not better. Start near `cores * 2 + effective_spindles` (HikariCP rule). Total across instances must stay under DB limit.

**Pitfalls:**
- Leak: missing `release()`. Pool drains, everything hangs. Use `try/finally` or `with`.
- Session state (temp tables, `SET`, open txn) carries over to next borrower. Reset on release.
- Serverless: each instance has its own pool, so connection count explodes. Use external pooler.

**Levels:**
- In-app: HikariCP (Java), `pg.Pool` (Node), SQLAlchemy `QueuePool` (Python).
- External proxy: PgBouncer, RDS Proxy, ProxySQL. PgBouncer `transaction` mode multiplexes many clients onto few server connections, but breaks session features like prepared statements and advisory locks unless configured.

```python
with pool.connect() as conn:   # acquire
    conn.execute(q)
# auto-release
```

## Q2: What's the difference between TCP and UDP?

### Reference
TCP and UDP are both protocols for sending data across networks. The main difference is that TCP guarantees delivery and order, and UDP trades those guarantees for speed and simplicity.

| | **TCP** | **UDP** |
|---|---|---|
| Connection | Opens a connection first with a 3-way handshake | Sends packets with no setup |
| Reliability | Confirms receipt with acknowledgments and resends anything lost | Fire-and-forget: lost packets stay lost |
| Ordering | Delivers bytes in the order they were sent | Packets can arrive out of order |
| Flow/congestion control | Yes: slows down to avoid overwhelming the receiver or the network | No: the application has to handle it |
| Data model | Continuous byte stream (no message boundaries) | Separate messages (datagrams) |
| Header size | 20–60 bytes | 8 bytes |
| Speed/latency | Slower, especially when packets get lost | Faster |
| Typical uses | Web (HTTP/1.1, HTTP/2), email, SSH, file transfer, databases | DNS, VoIP, video calls, online games, live streaming, DHCP; also QUIC/HTTP/3 |

**When to use which:**
- **TCP** fits when every byte must arrive correctly, such as files, web pages and transactions.
- **UDP** fits when a late packet is worse than a missing one, such as real-time audio, video and games. It's also used when you want to build your own reliability on top, which is what QUIC does.

### Candidate A
TCP is reliable and connection-based; UDP is fast and connectionless with no delivery guarantees.

TCP opens a connection with a handshake before sending anything. It guarantees that data arrives complete and in order, resends lost packets, and slows down when the network is congested. That makes it right for web pages, email, file transfers and SSH, where every byte has to arrive correctly.

UDP sends independent datagrams with no handshake, acknowledgments or retransmission. Packets can be lost, duplicated or arrive out of order, but there is less overhead and lower latency. It suits video calls, gaming, DNS and live streaming, where late data is useless anyway.

A common mistake is treating TCP as a stream of messages. TCP preserves bytes, not message boundaries, so your application has to frame its own messages. UDP keeps each datagram separate.

### Candidate B
**TCP**: connection-oriented (handshake first). Reliable: acks, retransmits, in-order delivery. Flow and congestion control. Byte stream, no message boundaries. More overhead and latency. Used for web, email, SSH, file transfer.

**UDP**: connectionless. No delivery, ordering, or duplicate guarantees. Preserves datagram boundaries. 8-byte header vs TCP's 20+. Lower latency. Used for DNS, VoIP, gaming, video streaming, QUIC.

Choose TCP when correctness matters, UDP when latency matters and some loss is acceptable.

### Candidate C
TCP is reliable and connection-based, while UDP is fast and connectionless.

TCP sets up a connection with a handshake before any data moves. It guarantees delivery and correct order, resends lost packets, and slows down when the network is congested. That makes it the right choice when every byte must arrive intact, as in web pages, email, file transfers and SSH.

UDP sends each packet on its own, with no handshake. It doesn't confirm delivery, fix ordering or resend lost packets. Its headers are smaller (8 bytes, against at least 20 for TCP) and it adds less delay. It suits traffic where speed matters more than a few lost packets, such as video calls, online games, DNS lookups and live streaming. QUIC, which carries HTTP/3, runs on UDP and adds its own reliability.

## Q3: How do I fix a memory leak in a long-running Node.js process?

### Reference
Start by confirming you actually have a leak, then find what's holding the memory and fix that.

**1. Confirm it's a leak**
- Log `process.memoryUsage()` (`heapUsed`, `rss`, `external`) on an interval.
- If `heapUsed` keeps climbing after GCs and never levels off, it's a leak. Memory that rises and then flattens out is normal.
- If `rss` grows while `heapUsed` stays flat, the memory is outside the JS heap. Look at native addons, Buffers, or fragmentation from glibc malloc.

**2. Capture heap snapshots**
- Run with `node --inspect app.js`, open `chrome://inspect`, go to Memory and take a heap snapshot.
- In production you can call `require('v8').writeHeapSnapshot()` or start with `--heapsnapshot-signal=SIGUSR2`. Writing a snapshot pauses the process and needs about as much free memory as the heap, so be careful.
- Take 3 snapshots spaced out while the app is under load. Compare them in the "Comparison" view and sort by **# Delta** or **Retained Size**.
- On the objects that keep growing, open the **Retainers** chain. It shows what is keeping them alive.

**3. Common causes and fixes**
| Cause | Fix |
|---|---|
| Unbounded caches or Maps keyed by request, user or ID | Use an LRU with a max size or TTL (e.g. `lru-cache`), or a `WeakMap` |
| Event listeners added repeatedly (`emitter.on` in a request handler) | `removeListener`/`off`, `once`, or `AbortSignal`. Watch for `MaxListenersExceededWarning` |
| `setInterval` or timers never cleared | `clearInterval`, or `timer.unref()` |
| Closures capturing large objects (req/res, buffers) | Keep only the fields you need. Null out references |
| Globals or module-level arrays that only grow | Bound them or flush them |
| Promises that never settle, or pending queues | Add timeouts and make sure every path resolves or rejects |
| Streams not consumed or destroyed | Use `stream.pipeline()` and handle errors so streams get destroyed |
| Request-scoped data stored in `AsyncLocalStorage` or on long-lived objects | Make sure the scope ends. Don't attach it to singletons |
| DB/HTTP clients created per request | Reuse one pooled client |

**4. Useful tools**
- `clinic heapprofiler` / `clinic doctor`
- `--heap-prof` for sampling allocation profiles
- Chrome DevTools "Allocation instrumentation on timeline" to see where allocations come from
- `--trace-gc` to watch how GC behaves

**5. Verify the fix**
- Run the same load test again and check that `heapUsed` levels off.
- Add a heap metric with alerts in production.

**Stopgaps, not fixes:** raising `--max-old-space-size`, or restarting the process when memory crosses a threshold (PM2 `max_memory_restart`, k8s memory limits). These keep you running while you look for the real cause.

If you can share a snippet or heap snapshot summary, I can help pinpoint the culprit.

### Candidate A
Confirm the leak first, then compare heap snapshots to see which objects keep growing, and remove whatever still holds references to them.

1. **Confirm it.** Log `process.memoryUsage().heapUsed` over time. Steady growth after garbage collection points to a leak, while a sawtooth pattern is normal.
2. **Take heap snapshots.** Start with `node --inspect app.js` and open `chrome://inspect`. Take a snapshot, run some load, then take a second one. In the Comparison view, sort by "Size Delta" and check the "Retainers" panel to see what keeps the growing objects alive.
3. **Look for the usual causes:**
   - Caches or Maps with no size limit. Use `lru-cache` or a `WeakMap`.
   - Event listeners added on every request but never removed with `removeListener`.
   - `setInterval` timers or closures that are never cleared.
   - Global arrays or module-level arrays that only grow.
4. **Check the fix.** Run the same load again and confirm `heapUsed` levels off.

In production, `node --heapsnapshot-signal=SIGUSR2 app.js` lets you take a snapshot with `kill -USR2 <pid>`. Taking a snapshot pauses the process and needs roughly as much memory as the heap itself.

### Candidate B
**1. Confirm leak.** Heap grows across GCs, never drops.
```js
setInterval(() => console.log(process.memoryUsage().heapUsed), 10000);
```
RSS rising, `heapUsed` flat? Native/Buffer leak, not JS heap.

**2. Capture heap snapshots.**
- `node --inspect app.js` → Chrome `chrome://inspect` → Memory tab.
- Or in code: `require('v8').writeHeapSnapshot()`.
- Or signal: `node --heapsnapshot-signal=SIGUSR2 app.js`, then `kill -USR2 <pid>`.

Take 3 snapshots: baseline, after load, after more load. Comparison view, sort by `# Delta` / Retained Size. Follow Retainers path to root.

**3. Common culprits:**
- Unbounded caches/Maps keyed by request/user. Fix: LRU (`lru-cache`), TTL, or `WeakMap`.
- Event listeners added per request, never removed. `MaxListenersExceededWarning` hints this. Fix: `off()`/`once()`.
- `setInterval`/timers never cleared.
- Closures capturing big objects (req/res, buffers).
- Global arrays/log buffers growing.
- Promises never settled, pending forever.
- DB/HTTP clients created per request instead of pooled.
- Native addons, unreleased streams (RSS growth).

**4. Fix, verify.** Load test (`autocannon`), watch heap plateau.

**Tools:** `clinic heapprofiler`, `memlab`, `--trace-gc`. Stopgap only: `--max-old-space-size` plus restarts (PM2 `max_memory_restart`). Hides leak, doesn't fix it.

### Candidate C
Confirm the leak, take heap snapshots and compare them to see what keeps growing, then remove the reference that keeps it alive.

1. **Confirm it.** Log `process.memoryUsage().heapUsed` over time. If it keeps rising after GC instead of leveling off, you have a leak. If `rss` grows but the heap doesn't, the leak is in native memory or Buffers.
2. **Capture snapshots.** Start with `node --inspect app.js`, open `chrome://inspect`, and take a heap snapshot. Run the load for a while and take another. In the Comparison view, sort by "# Delta" and follow the retainer chain of the objects that keep growing.
3. **Check the common causes first:**
   - Caches or Maps with no size limit or eviction. Use an LRU cache or a `WeakMap`.
   - Event listeners added on every request and never removed. Watch for `MaxListenersExceededWarning`.
   - `setInterval` timers or closures that hold large objects.
   - Globals or module-level arrays that only ever grow.
4. **Fix it and verify** by taking snapshots again under the same load.

The most common trap: `--max-old-space-size` only delays the crash. It doesn't fix the leak.

```bash
node --heapsnapshot-signal=SIGUSR2 app.js   # then: kill -USR2 <pid>
```

This takes a snapshot of a running production process without attaching a debugger. The process pauses while the snapshot is written.

## Q4: What does the SQL EXPLAIN command tell me?

### Reference
`EXPLAIN` shows the **execution plan**: how the database intends to run your query. It doesn't return the query's results.

**What it tells you:**
- **Access method for each table.** It shows whether the database reads the whole table (sequential or full scan) or uses an index (index scan or seek).
- **Join strategy and order.** This is nested loop, hash join or merge join, plus which table is read first.
- **Estimated row counts.** These are how many rows the planner expects at each step.
- **Estimated cost.** This is a relative number for comparing plans, not a time.
- **Other operations.** Sorts, aggregations, filters, temp tables and subqueries all appear in the plan.

**Variants:**
- `EXPLAIN ANALYZE` (PostgreSQL, and MySQL 8.0.18+) actually runs the query. It reports **real** row counts and timings next to the estimates. Be careful using it on `INSERT`, `UPDATE` or `DELETE`, because the changes really happen. Wrap it in a transaction and roll back.
- In PostgreSQL, `EXPLAIN (ANALYZE, BUFFERS)` also shows cache hits and disk reads.
- In MySQL, `EXPLAIN` shows a table with columns such as `type` (ALL means a full scan), `key` (the index used), `rows` and `Extra` (for example "Using filesort" or "Using temporary").

**What to look for:**
- **Full scans on large tables when you expected an index.** This usually means an index is missing or can't be used, for example because a function is applied to the column.
- **Estimated rows far from actual rows.** The table statistics are probably stale; run `ANALYZE`.
- **Expensive sorts or nested loops over many rows.**

**Example (PostgreSQL):**
```sql
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 42;
-- Index Scan using idx_orders_customer on orders (cost=0.29..8.31 rows=5) (actual time=0.02..0.03 rows=4 loops=1)
```

In short, `EXPLAIN` is your main tool for figuring out why a query is slow.

### Candidate A
`EXPLAIN` shows the plan the database will use to run a query, without running it. The plan tells you:

- **Access method:** whether each table is read with a full scan or through an index.
- **Join strategy:** nested loop, hash join or merge join, and the order tables are joined in.
- **Estimated cost and row counts:** the planner's guess at how expensive each step is and how many rows it returns.
- **Other operations:** sorts, aggregations and filters, and where each one happens.

Use it to find slow spots, such as a sequential scan on a large table where you expected an index.

In PostgreSQL, `EXPLAIN ANALYZE` actually runs the query and adds real timings and row counts next to the estimates. A large gap between estimated and actual rows usually means the table statistics are stale. Because it really executes the query, wrap `INSERT`, `UPDATE` or `DELETE` in a transaction and roll it back.

```sql
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 42;
```

### Candidate B
The query plan: how the database will run the query, without running it.

Shows:
- **Access method** per table: full/sequential scan, index scan, index-only scan.
- **Join strategy and order**: nested loop, hash join, merge join.
- **Estimated cost**: startup and total, in planner units, not ms.
- **Estimated rows** per step, plus row width.
- **Other steps**: sorts, aggregates, filters, subqueries, temp tables.

`EXPLAIN ANALYZE` actually executes the query. It adds real time, actual rows and loop counts. Estimated rows far from actual rows usually means stale statistics, so run `ANALYZE`. Wrap writes in a transaction and roll back, or ANALYZE applies them.

Extras:
- Postgres: `EXPLAIN (ANALYZE, BUFFERS)` adds cache hits and disk reads.
- MySQL: `EXPLAIN FORMAT=JSON` or `EXPLAIN ANALYZE` (8.0.18+). The `type` column shows the access type, and `ALL` means a full scan.

Use it to find missing indexes, bad joins and slow sorts.

### Candidate C
`EXPLAIN` shows how the database plans to run your query without running it. The output covers:

- **Access method:** a full table scan or an index, and which index.
- **Join strategy:** nested loop, hash join or merge join, and the order tables are joined in.
- **Estimated rows and cost:** the planner's guess at how many rows each step handles and how expensive it is.
- **Extra operations:** sorts, aggregations and temporary tables.

```sql
EXPLAIN SELECT * FROM orders WHERE customer_id = 42;
```

Look for a sequential scan on a large table where you expected an index. That usually points to a missing index, or a function or type cast on the filtered column that stops the index from being used.

Plain `EXPLAIN` gives only estimates. In PostgreSQL, `EXPLAIN ANALYZE` runs the query and adds real row counts and timings, so wrap it in a transaction you roll back if the query is an `INSERT`, `UPDATE` or `DELETE`.

## Q5: How does a hash table handle collisions?

### Reference
A collision happens when two keys hash to the same slot. There are two main ways to handle it:

**1. Separate chaining**
- Each slot holds a list (or a tree) of all entries that hash there.
- Insert adds the entry to that slot's list. Lookup scans the list for a matching key.
- It still works when the table is fairly full. Average cost is O(1 + α), where α (the load factor) is entries ÷ slots.
- Java's `HashMap` uses this. When one slot's list gets long, it turns that list into a red-black tree.

**2. Open addressing**
All entries live in the array itself. On a collision, the table checks other slots in a fixed order until it finds a free one:
- **Linear probing:** check `h, h+1, h+2, …`. It's fast because neighboring slots are close in memory, but occupied slots tend to bunch together ("clustering").
- **Quadratic probing:** check `h + 1², h + 2², …`. This reduces the bunching.
- **Double hashing:** check `h + i·h₂(key)`, where a second hash function sets the step size.
- **Deletion** needs "tombstones," markers that say "something was deleted here." Without them, a later lookup would stop at the empty slot and miss keys stored further along.
- Variants such as **Robin Hood hashing** and **cuckoo hashing** keep the number of probes low. Python's `dict` and Rust's `HashMap` (SwissTable) use open addressing.

**Both approaches also need:**
- **Resizing:** when the load factor passes a threshold (about 0.75 for chaining, often lower for open addressing), the table grows, usually doubling, and every entry is re-hashed into the new array.
- **A good hash function:** it spreads keys evenly so collisions stay rare. Some tables use a randomly seeded hash to resist attacks that deliberately feed in colliding keys.

With a good hash and resizing, operations average O(1). The worst case is O(n), when every key ends up in the same slot.

### Candidate A
A hash table handles collisions in one of two main ways: chaining or open addressing.

**Separate chaining** gives each bucket a list (or sometimes a tree) of entries. Keys that hash to the same bucket all go into that list, and a lookup scans it. Java's `HashMap` works this way and switches a long chain to a balanced tree.

**Open addressing** stores every entry in the array itself. When a slot is taken, the table probes other slots in a fixed order until it finds a free one:
- Linear probing checks the next slot, then the one after that.
- Quadratic probing jumps 1, 4, 9 and so on slots away, which reduces clustering.
- Double hashing uses a second hash function to set the step size.

Either way, the table resizes and rehashes all entries when the load factor gets too high, often around 0.75. This keeps collisions rare enough that lookups stay O(1) on average.

### Candidate B
Two main strategies.

**Separate chaining**: each bucket holds a list (or tree) of entries. Colliding keys get appended. Lookup hashes to the bucket, then scans for the key. Java `HashMap` turns a bucket into a tree once it holds more than 8 entries.

**Open addressing**: all entries live in the array itself. On a collision, probe for another slot:
- Linear probing: `i+1, i+2, …`. Cache-friendly, but entries bunch up in clusters.
- Quadratic probing: `i+1², i+2², …`. Less clustering.
- Double hashing: step size comes from a second hash.
- Robin Hood: swaps entries so no key sits too far from its home slot.

Deletion needs tombstones (markers left in deleted slots) or backward-shift; otherwise probe chains break.

**Both**: once load factor (entries / buckets) passes a threshold (~0.75 for chaining, ~0.5–0.7 for open addressing), the table grows, usually doubling, and rehashes every entry. That keeps average lookups O(1). Worst case is O(n) when every key lands in one bucket. Randomized hashes such as SipHash block attackers from forcing this.

### Candidate C
Hash tables usually handle collisions in one of two ways:

1. **Separate chaining:** Each bucket holds a small list (or tree) of entries. Colliding keys get added to that bucket's list, and a lookup scans only that list. Java's `HashMap` and C++'s `std::unordered_map` work this way.
2. **Open addressing:** Every entry sits directly in the array. On a collision, the table checks other slots in a fixed order (linear probing, quadratic probing or double hashing) until it finds an empty one. Python's `dict` and Rust's `HashMap` work this way.

Either way, the table resizes and rehashes all entries once the load factor passes a threshold (often 0.75), which keeps the average cost at O(1).

The common trap with open addressing is deletion. You can't simply empty a slot, because that breaks the probe chains for keys stored after it. Instead you mark the slot with a "tombstone."

## Q6: Why am I getting CORS errors in my browser console?

### Reference
CORS errors happen when your page's JavaScript (on one origin, e.g. `http://localhost:3000`) requests a resource on a different origin (e.g. `https://api.example.com`), and that server's response doesn't say your origin is allowed. The browser blocks your code from reading the response. The server still received the request, which is why the same call works fine from curl or Postman.

**Common causes:**

1. **The server sends no `Access-Control-Allow-Origin` header.** This is the most common one. The API has to send back `Access-Control-Allow-Origin: <your origin>` (or `*`).
2. **The preflight fails.** Requests that use methods like `PUT` or `DELETE`, custom headers like `Authorization`, or `Content-Type: application/json` trigger an `OPTIONS` preflight first. The server has to answer it with a 2xx status and the right `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`.
3. **Credentials are combined with a wildcard.** If you use `credentials: 'include'` or `withCredentials`, the server can't use `*`. It must send your exact origin and `Access-Control-Allow-Credentials: true`.
4. **The origin doesn't match exactly.** `http` vs `https`, a different port, or `www` vs no `www` all count as different origins.
5. **An error response is missing the headers.** A 401, 404 or 500 sent without CORS headers shows up as a CORS error and hides the real error.
6. **A redirect goes to another origin** that doesn't send CORS headers.

**How to fix it:**

- **If you control the server:** add CORS middleware, such as `cors()` in Express, `django-cors-headers`, `flask-cors`, or `@CrossOrigin` in Spring. Allow your frontend's origin and handle `OPTIONS`.
- **If it's only a local dev problem:** proxy API calls through your dev server (Vite's `server.proxy`, CRA's `"proxy"` or Next.js rewrites) so they come from the same origin.
- **If it's a third-party API you don't control:** call it from your own backend instead of from the browser.
- `mode: 'no-cors'` is **not** a fix. It just gives you a response you can't read.

**To find the exact cause:** open DevTools, go to the Network tab, and click the failed request (and its `OPTIONS` preflight if there is one). Check the response status and headers. The console message also names the specific reason, such as "No 'Access-Control-Allow-Origin' header" or "preflight did not succeed".

If you paste the exact error and tell me your stack, I can give you the specific fix. I can also look at the console in your Chrome directly if you'd like.

### Candidate A
Your page is making a request to a different origin, meaning a different scheme, domain or port, and that server's response doesn't include headers allowing your origin. The browser blocks the response. CORS is enforced by the browser, which is why the same request works from curl or Postman.

The most likely causes, in order:

1. **The server sends no `Access-Control-Allow-Origin` header**, or it doesn't match your origin. Add your origin (e.g. `http://localhost:3000`) on the server.
2. **The preflight `OPTIONS` request fails.** Requests with custom headers, JSON bodies or methods like PUT trigger a preflight. The server must answer it with a 2xx status and the right `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`.
3. **You're sending credentials.** With `credentials: 'include'`, the server can't use `*`. It must send your exact origin plus `Access-Control-Allow-Credentials: true`.
4. **The server is returning an error.** A 500 or 404 response often comes back without CORS headers, so it shows up as a CORS error. Check the Network tab for the real status.

You can only fix this on the server you're calling. If you don't control that server, use a dev-server proxy, such as Vite's `server.proxy`, or route the request through your own backend.

### Candidate B
Browser blocks cross-origin requests unless the server allows them. Your page's origin (scheme + host + port) differs from the API's, and the response is missing the right headers.

**Common causes:**
- **Missing `Access-Control-Allow-Origin`.** Server must send your origin (or `*`).
- **Preflight fails.** Non-simple requests (custom headers, `Content-Type: application/json`, PUT/DELETE) send `OPTIONS` first. Server must answer it with 2xx plus `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`.
- **Credentials.** With `credentials: 'include'`, `*` is not allowed. Server must echo the exact origin and send `Access-Control-Allow-Credentials: true`.
- **Error responses.** A 4xx/5xx or a redirect with no CORS headers also shows up as a CORS error, even when the real problem is something else.
- **Port mismatch.** `localhost:3000` calling `localhost:8080` counts as cross-origin.

**Fixes:**
- Server side, Express example: `app.use(require('cors')({ origin: 'http://localhost:3000', credentials: true }))`
- In dev, proxy API calls through your dev server, e.g. Vite `server.proxy` or CRA `"proxy"` in `package.json`. The browser then sees one origin.
- `mode: 'no-cors'` does not fix it. You get an opaque response you can't read.

**To diagnose:** open DevTools, go to the Network tab and look at the failed request or its `OPTIONS` preflight. Check the status code and which response headers are missing.

Paste the exact console error, the request code and your server stack, and I can find the specific cause.

### Candidate C
The browser blocked your page's request because the server didn't send headers allowing your page's origin. Your origin is the scheme, host and port, so `localhost:3000` calling `localhost:8080` counts as cross-origin. The browser enforces CORS, but the fix almost always goes on the server.

These are the most likely causes:

1. **Missing `Access-Control-Allow-Origin`.** The API doesn't return this header, or returns a different origin than yours.
2. **Failed preflight.** Requests with custom headers (such as `Authorization`), JSON bodies or methods like `PUT` and `DELETE` first send an `OPTIONS` request. The server must answer it with a 2xx status and the `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers` headers.
3. **Credentials with a wildcard.** If you send cookies (`credentials: 'include'`), the server can't use `*`. It must return your exact origin plus `Access-Control-Allow-Credentials: true`.
4. **An error response without the headers.** A 401, 404 or 500 from a proxy or framework often skips the CORS middleware, so a different server problem shows up as a CORS error.

Look at the failed request in the Network tab, including any `OPTIONS` request. During development, a dev-server proxy (Vite `server.proxy`, CRA `proxy`) avoids CORS entirely.

`mode: 'no-cors'` won't fix this, because it hides the response from your code.

If you paste the exact console error, I can narrow it down.

## Q7: What's the point of using a debouncer on a search input?

### Reference
A debouncer waits until the user stops typing for a short time (often 200–500 ms) before running the search. Without one, every keystroke fires a search.

**Why it helps:**

- **Fewer requests.** Typing "javascript" without debouncing sends 10 requests: "j", "ja", "jav", and so on. With debouncing it sends about 1. That reduces load on the server and on rate-limited APIs.
- **No out-of-order results.** When many requests are in flight, an older one can return after a newer one and overwrite the correct results. Debouncing makes this much less likely, though it doesn't prevent it entirely.
- **Less wasted work on the client.** You don't re-filter, re-render or update state for intermediate strings the user never wanted.
- **Smoother interface.** Results don't flicker on every keypress, and typing doesn't lag.

**Example:**
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

**Tradeoff:** results appear slightly later. For cheap, local filtering you may not need a debouncer at all. For network searches, also cancel stale requests with `AbortController` so results can't arrive out of order.

A related option is **throttling**, which runs the function at most once every N ms while the user is still typing. Use it when you want results to update during typing, not only after the user stops.

### Candidate A
A debouncer waits until the user stops typing for a short pause, usually 200 to 500 ms, before running the search. Without it, typing "laptop" sends six requests, one per keystroke. With it, you send one.

That gives you three benefits:

- **Less load:** fewer API calls and database queries, which also helps you stay under rate limits.
- **Fewer out-of-order results:** a slow response for "lap" can arrive after the response for "laptop" and overwrite it. Debouncing makes this less likely but doesn't prevent it.
- **Less flicker:** the results list doesn't redraw on every keystroke.

The common mistake is creating the debounced function inside a React component body. That makes a new timer on every render, so the debounce never works. Wrap it in `useMemo` or `useRef`. To prevent stale results completely, also cancel the previous request with `AbortController`.

### Candidate B
A debouncer waits until the user stops typing for a short pause, usually 200–500 ms, and only then runs the search. Without one, typing "laptop" fires six searches, one per keystroke, and five of them are wasted.

This gives you:

- **Fewer requests.** Your server and any rate-limited or paid API get far less traffic.
- **Correct results.** Responses can arrive out of order, so an older result for "lap" may overwrite the newer one for "laptop".
- **A smoother UI.** The results list doesn't flicker or re-render on every keystroke.

The cost is a short delay before results appear. If you want results to keep updating while the user types, a throttle is the better fit.

### Candidate C
Debouncing waits until typing pauses (about 300ms) before it searches, so only the final input fires.

- **Fewer requests:** typing "react" makes 1 API call instead of 5. That cuts server load, cost and rate-limit hits.
- **No stale results:** a slow reply for "rea" can't arrive late and overwrite the results for "react".
- **Smoother UI:** less re-rendering and filtering on every keystroke.

Downside: results show up a little later. Use throttle instead if you want updates at a steady rate while the user is still typing.

## Q8: How does git rebase differ from git merge?

### Reference
Both commands bring the changes from one branch into another. They differ in what happens to the commit history.

**`git merge`**
- Creates a new **merge commit** with two parents that joins the two branch histories.
- Keeps the history exactly as it happened. No existing commits are rewritten.
- The result is a non-linear, branching graph.
- It's safe on shared or public branches.

**`git rebase`**
- Takes your commits off the branch and **replays** them one by one on top of the target branch.
- Each replayed commit becomes a new commit with a new SHA.
- The result is a linear history with no merge commit.
- It rewrites history. Don't rebase commits other people have already pulled, because you'd then need `git push --force` and their copies would no longer match.
- `git rebase -i` also lets you squash, reorder or edit commits before sharing them.

**Example** (feature branched off main, then main moved ahead):
```
merge:   A---B---C---F---M   (main; M = merge commit)
              \         /
               D-------E      (feature)

rebase:  A---B---C---F---D'---E'   (feature, replayed onto main)
```

**Conflicts:** `merge` shows all conflicts at once. `rebase` can stop at each commit as it replays it, so you may resolve conflicts several times.

**Common practice:** rebase your local feature branch onto `main` to keep it up to date and tidy, and use merge to integrate shared branches.

### Candidate A
**Merge:** joins two branches with a new merge commit. Existing commits stay unchanged. History is non-linear, and the real branch topology is preserved.

**Rebase:** replays your commits onto the tip of the other branch. Each commit gets a new SHA. History is linear, with no merge commit.

**Trade-offs:**
- Merge: safe on shared branches and keeps context, but the history gets noisier.
- Rebase: gives a clean, bisect-friendly history but rewrites existing commits. Never rebase commits others have already pulled. If you do, they'll need to force-push and reconcile.
- Conflicts: merge resolves them once, while rebase may stop for each commit.

**Typical workflow:** rebase your local feature branch onto `main` (`git rebase main`), then merge it into `main`, optionally with `--no-ff`. `git pull --rebase` avoids extra merge commits on pull.

### Candidate B
Merge combines two branches by adding a new merge commit that ties their histories together, while rebase replays your commits on top of the other branch so the history becomes one straight line.

- **Merge** keeps the true history: every commit stays as it was, and you resolve conflicts once. The downside is a cluttered graph with many merge commits.
- **Rebase** gives a clean, linear history, but it rewrites your commits as new commits with new hashes. You may also have to resolve conflicts once for each replayed commit.

The main trap is rebasing commits that others have already pulled. Because the hashes change, their history no longer matches yours, and you would need `git push --force`. Only rebase local or private branches, and use merge for shared ones.

### Candidate C
Both combine work from two branches. Merge preserves history, while rebase rewrites it.

- **Merge** adds a new merge commit that joins the two branches. Existing commits stay unchanged, so the history is accurate but can branch and tangle.
- **Rebase** replays your commits one by one on top of the target branch. Each one becomes a new commit with a new hash, which gives you a straight, linear history.

```bash
git checkout feature && git merge main    # adds a merge commit to feature
git checkout feature && git rebase main   # moves feature's commits on top of main
```

Use rebase to tidy up local or private branches before you share them. Use merge for branches other people have already pulled. Never rebase commits that are already pushed and shared, because the rewritten hashes will conflict with everyone else's copies.

## Q9: When should I use a queue vs a topic in messaging systems?

### Reference
**Queue (point-to-point):** each message goes to exactly one consumer.
- Use it to **spread work** across workers, such as background jobs, order processing or image resizing.
- You get load balancing for free: add consumers to increase throughput.
- Use it when a message stands for a **command or task** that should be done once ("resize this image").
- Retries and dead-letter queues make sense here, because one consumer owns the message.

**Topic (pub/sub):** every subscriber gets its own copy of each message.
- Use it to **broadcast events** to several independent parties, such as `OrderPlaced` going to billing, email and analytics.
- Producers don't know who the consumers are, so you can add new subscribers without touching the publisher.
- Use it when a message stands for an **event or fact** ("this happened") and any number of parties might care.

**Rule of thumb:**
- If the message is "do this," use a queue.
- If it's "this happened," use a topic.

**Common hybrid:** publish to a topic, and give each subscribing service its own queue. Each service gets every event, and the instances within a service share that service's load. This is how SNS→SQS fan-out works, and also Kafka consumer groups, Azure Service Bus subscriptions and RabbitMQ fanout exchanges bound to queues.

**Other factors:**
- **Ordering:** both can keep messages in order, usually per partition or session key.
- **Replay:** log-based topics (Kafka, Pulsar) keep messages after they're read, so you can replay them. Classic queues delete a message once it's acknowledged.
- **Coupling:** topics loosen the link between producers and consumers. With a queue, the producer usually knows which kind of worker will handle the message.

### Candidate A
**Queue** (point-to-point): each message goes to exactly one consumer.
- Work distribution, task jobs. Examples: send email, resize image, process order.
- Competing consumers let you scale workers horizontally.
- Load leveling: buffers bursts so slow workers don't get overwhelmed.
- Use it when a message must be handled once and the sender doesn't care which worker handles it.

**Topic** (pub/sub): every subscriber gets its own copy of each message.
- Event broadcast. Example: `OrderPlaced` goes to billing, inventory and analytics.
- Decouples the producer. New consumers can be added without changing it.
- Use it when several independent systems react to the same event.

**Hybrid** (most common in production): a topic fans out to one queue per subscriber service. Each service then scales with competing consumers on its own queue.
- SNS → SQS
- Kafka: topic plus consumer groups. Each group gets every message. Within a group, each partition goes to only one consumer.
- RabbitMQ: fanout exchange → queues
- Azure Service Bus: topic subscriptions

**Rule of thumb:**
- Command ("do X") → queue.
- Event ("X happened") → topic.

**Other factors:**
- Ordering: a queue gives FIFO only with a single consumer or message groups. In Kafka, ordering holds only within a partition.
- Replay: Kafka-style log topics keep messages after they're consumed, so you can replay. Classic queues delete a message once it's acknowledged.
- Delivery is usually at-least-once either way, so consumers should be idempotent.

### Candidate B
Use a queue when each message should be handled by exactly one consumer. Use a topic when every interested subscriber should get its own copy.

**Queue (point-to-point):** Several workers share one queue, and each message goes to only one of them. This suits work distribution, such as processing orders, resizing images or sending emails. To scale, add more workers.

**Topic (publish-subscribe):** Each subscriber gets every message. This suits events that several independent systems react to. For example, when an "order placed" event is published, billing, inventory and analytics each receive a copy. You can add new subscribers without changing the publisher.

**Combining them:** Many systems publish to a topic and give each subscribing service its own queue. SNS fanning out to SQS queues, Kafka consumer groups and RabbitMQ fanout exchanges all work this way. Each service gets a copy of every event, and that service's workers split the load between them.

### Candidate C
Use a **queue** when each message should be handled by exactly one consumer. Use a **topic** when every interested subscriber should get its own copy.

**Queue (point-to-point):** Good for distributing work, such as order processing, image resizing or sending emails. Adding consumers spreads the load, because they compete for messages. Each message is processed once and then removed.

**Topic (publish-subscribe):** Good for broadcasting events, such as "OrderPlaced", which billing, shipping and analytics each need to react to. Publishers don't need to know who is listening.

**Combining them:** Publish to a topic, then give each subscribing service its own queue. Examples are SNS to SQS, or Kafka consumer groups. Every service gets every event, and instances within a service share the work.

**Watch out:** A topic subscriber without a durable subscription misses any messages sent while it was offline.
