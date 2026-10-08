# Fidelity review packet

## Q0: Why does my React component re-render every time the parent updates?

### Reference
That's React's default behavior. When a parent re-renders, all of its children re-render too, whether or not their props changed. React doesn't check props unless you ask it to.

**Fixes:**

1. **Wrap the child in `React.memo`** so it skips re-rendering when its props are shallowly equal:
   ```jsx
   const Child = React.memo(function Child({ value }) { ... });
   ```

2. **Keep props stable.** `memo` doesn't help if the parent creates new objects, arrays or functions on every render. Each new reference counts as a change:
   ```jsx
   // ❌ new reference every render
   <Child onClick={() => doThing()} style={{ color: 'red' }} />

   // ✅ stable references
   const handleClick = useCallback(() => doThing(), []);
   const style = useMemo(() => ({ color: 'red' }), []);
   <Child onClick={handleClick} style={style} />
   ```

3. **Pass the child in as `children`.** If the state that changes lives in a wrapper component, elements passed in as `children` were created by the wrapper's parent. They don't re-render when only the wrapper's state changes:
   ```jsx
   function Wrapper({ children }) {
     const [x, setX] = useState(0);
     return <div onClick={() => setX(x + 1)}>{children}</div>;
   }
   ```

4. **Move state down.** If only part of the tree uses a piece of state, put that state in a smaller component so fewer components re-render.

**Other causes to check:**
- **Context:** A component that uses `useContext` re-renders whenever the context value changes. Creating that value inline, like `value={{a, b}}`, makes it change on every render.
- **Changing `key`:** A key that changes, such as `key={Math.random()}`, makes React remount the component instead of re-rendering it.
- **React Compiler:** If your project uses it, much of this memoization happens automatically.

**Is it actually a problem?** Re-renders are usually cheap. Use the React DevTools Profiler ("Highlight updates" / "Why did this render?") to confirm a re-render is slow before adding memoization.

If you share the component code, I can point to the exact cause.

### Candidate X
React re-renders every child when its parent renders. That is the default, even if the child's props haven't changed. To skip those renders, wrap the child in `React.memo`, which re-renders it only when its props change by shallow comparison.

```jsx
const Child = React.memo(function Child({ onClick, items }) {
  return <button onClick={onClick}>{items.length}</button>;
});

function Parent() {
  const handleClick = useCallback(() => {/* ... */}, []);
  const items = useMemo(() => [1, 2, 3], []);
  return <Child onClick={handleClick} items={items} />;
}
```

- `memo` won't help if the parent creates a new function, object or array on every render, because these fail the shallow comparison. Keep them stable with `useCallback` and `useMemo`.
- A child still re-renders if a context it uses changes, or if its own state changes.
- If you use React Compiler, it adds this memoization for you.

### Candidate Y
React default: parent renders, every child renders too. Props changed or not.

Fix: wrap child in `React.memo`. It then skips the render when props are shallow-equal.

`memo` still re-renders if:
- **Inline object/array prop** (`style={{...}}`, `items={[...]}`): new ref each render. Fix: `useMemo`, or hoist out of the component.
- **Inline function prop** (`onClick={() => ...}`): new ref each render. Fix: `useCallback`.
- **Context**: consumer re-renders whenever the context value changes. Inline provider `value={{...}}` changes every render. Fix: `useMemo` the value, or split contexts.
- **`children` prop**: new JSX each render, so `memo` is useless.

Alternative, no `memo`: move state down into the part that needs it, or pass the child as `children` from higher up. Then a parent state change doesn't re-create the child.

React Compiler (React 19+) auto-memoizes. Usually no manual `memo`/`useMemo`/`useCallback` needed.

Debug: React DevTools Profiler, "Record why each component rendered".

Re-render usually cheap. Optimize only if the Profiler shows a slow render.

## Q1: Explain database connection pooling.

### Reference
**Database connection pooling** means keeping a set of open database connections and reusing them, instead of opening a new connection for every request.

**Why it matters**
Opening a connection is slow. It takes a TCP handshake, often TLS negotiation, authentication, and the server setting up a session (in Postgres, a whole new process). That can take tens of milliseconds or more. A query often takes far less than that, so without a pool most of the time goes to connection setup.

**How it works**
1. At startup, the pool opens some connections (the minimum or "idle" count).
2. When the app needs the database, it **borrows** a connection from the pool.
3. When the work is done, the app **returns** the connection to the pool. It isn't closed.
4. If every connection is in use, the pool either opens a new one (up to a maximum) or makes the request **wait** until one is free, giving up after a timeout.
5. The pool also handles upkeep: it checks connections are still alive, replaces broken ones, closes idle ones and retires old ones.

**Key settings**
- **max pool size**: the most connections the pool will open. This is the most important setting.
- **min idle**: how many connections to keep open and ready.
- **connection/acquire timeout**: how long a request waits for a free connection before failing.
- **idle timeout / max lifetime**: when to close unused or old connections.
- **validation query / keepalive**: how the pool checks a connection still works.

**Where pools live**
- **In the app**: HikariCP (Java), SQLAlchemy's pool (Python), pgx/database/sql (Go), node-postgres `Pool`.
- **As a separate proxy**: PgBouncer, ProxySQL, RDS Proxy. These help when many app instances or serverless functions would otherwise open too many connections for the database to handle.

**Common pitfalls**
- **Pool too large**: more connections doesn't mean more speed. The database has a limited number of CPU cores and disks, so too many connections compete with each other and slow things down. A small pool, roughly a few times the number of cores, often performs best.
- **Too many app instances**: total connections = instances × pool size. That number can exceed the database's `max_connections`.
- **Leaks**: if code doesn't return a connection (for example, when an error skips the return), the pool slowly runs out. Use `with`, try-with-resources or `defer` so connections always go back.
- **Leftover session state**: temporary tables, `SET` variables or an open transaction can carry over to the next user of the connection. Good pools reset the connection when it's returned.
- **Transaction-mode proxies** like PgBouncer can break features that rely on the same session, such as prepared statements, advisory locks and `LISTEN`.

**In short:** opening connections is expensive, so open a limited number once, share them, and limit how many run at once to protect the database.

### Candidate X
Opening a DB connection is expensive: TCP, TLS, auth, session setup. That's often 10–100ms each time.

A pool keeps a set of connections open and reuses them across requests.

**Flow**
1. App starts and the pool opens `min` connections.
2. A request borrows an idle connection.
3. If none is idle and size < `max`, the pool opens a new one. At `max`, the request waits until `acquireTimeout`, then errors.
4. Request finishes and returns the connection. The connection stays open.

**Key settings**
- `max`: hard cap. Protects DB `max_connections`. Total = pool `max` × app instances.
- `min` / idle: warm connections kept ready.
- `idleTimeout`: closes connections unused too long.
- `maxLifetime`: recycles old connections, so they close before DB or firewall drops them.
- `acquireTimeout`: how long a request waits for a free connection.
- Validation: health check (`SELECT 1`) before handing out a connection.

**Pitfalls**
- Leaks: connection never returned and the pool runs dry. Always release in `finally` or use `try-with-resources`.
- Oversized pool: DB context-switching and slower throughput. A rough start: cores × 2 + disks (HikariCP guidance).
- Session state (temp tables, `SET`, open txn) carries over to the next borrower. Reset it on release.
- Serverless or many instances: many small pools exhaust the DB. Use an external pooler.

**Kinds**
- In-app: HikariCP (Java), `pg.Pool` (Node), SQLAlchemy pool (Python).
- External proxy: PgBouncer, RDS Proxy, ProxySQL. Modes: session, transaction, statement. Transaction mode breaks session features like prepared statements and `LISTEN`.

**Example (Node `pg`)**
```js
const pool = new Pool({ max: 10, idleTimeoutMillis: 30000 });
const client = await pool.connect();
try { await client.query('SELECT 1'); }
finally { client.release(); }
```

### Candidate Y
Connection pooling keeps a set of open database connections and reuses them across requests instead of opening a new one each time. Opening a connection is expensive: it takes a TCP handshake, often TLS, authentication, and server-side setup like allocating memory or forking a process.

How it works: when your code needs the database, it borrows an idle connection from the pool, runs its queries, and returns it. If every connection is busy, the request waits until one frees up or a timeout expires.

The main settings are the pool size (minimum and maximum), the idle timeout, and the acquire timeout. Keep the maximum pool size times the number of app instances below the database's connection limit. Postgres, for example, defaults to `max_connections = 100`.

Common tools are HikariCP (Java), SQLAlchemy's built-in pool (Python), and PgBouncer, which runs as an external pooler that many app instances share.

## Q2: What's the difference between TCP and UDP?

### Reference
**TCP (Transmission Control Protocol)**
- **Connection-oriented:** a handshake (SYN, SYN-ACK, ACK) sets up the connection before any data is sent.
- **Reliable:** lost packets are sent again, data arrives in order, and duplicates are removed.
- **Flow and congestion control:** it slows down so it doesn't overwhelm the receiver or the network.
- **Byte stream:** data arrives as a continuous stream with no message boundaries.
- **More overhead:** the header is 20 bytes or more, and the extra checks add latency.
- **Used for:** web (HTTP/1.1, HTTP/2), email, SSH, file transfer, and anything where every byte must arrive correctly.

**UDP (User Datagram Protocol)**
- **Connectionless:** there's no handshake, so it just sends.
- **Unreliable:** there's no guarantee packets arrive, arrive in order, or arrive only once.
- **No flow or congestion control:** it sends as fast as the application wants.
- **Message-based:** each datagram keeps its boundaries.
- **Low overhead:** the header is 8 bytes and latency is minimal.
- **Used for:** DNS, video and voice calls, live streaming, online games, and QUIC/HTTP/3, which builds its own reliability on top of UDP.

**Rule of thumb:** use TCP when correctness matters more than speed. Use UDP when low latency matters more and some loss is acceptable, or when you want to build your own reliability layer.

### Candidate X
TCP is connection-based and reliable. UDP is connectionless and faster, but it doesn't guarantee that data arrives.

TCP opens a connection with a handshake before sending anything. It numbers the bytes it sends, waits for acknowledgments and resends anything that gets lost, so data arrives complete and in order. It also slows down when the network or the receiver is overloaded. That makes it the choice for web pages, email, file transfers and SSH, where every byte has to be correct.

UDP sends separate packets with no handshake. Packets may arrive out of order, more than once, or not at all, and UDP itself does nothing about it. Each packet carries much less overhead, so latency is lower. Games, voice and video calls, live streaming and DNS use it because a late packet is worse than a lost one. Apps that need reliability on top of UDP build it themselves, as QUIC does for HTTP/3.

### Candidate Y
**TCP**: connection-oriented (handshake first). Reliable: acks, retransmits lost data, delivers in order. Flow and congestion control. Byte stream, no message boundaries. More overhead and latency. Used for HTTP/1.1, HTTP/2, SSH, email, file transfer.

**UDP**: connectionless. No delivery or ordering guarantee, no retransmits. Message-based: each datagram arrives whole or not at all. 8-byte header vs TCP's 20+. Low latency. Used for DNS, VoIP, video calls, gaming, streaming. QUIC (HTTP/3) runs on UDP and adds its own reliability.

**Choose**: TCP when every byte must arrive correctly. UDP when speed matters more and some loss is OK.

## Q3: How do I fix a memory leak in a long-running Node.js process?

### Reference
You fix it in three steps: confirm there really is a leak, find what is holding the memory, then remove the reference.

## 1. Confirm it's a leak
- Watch `process.memoryUsage()` over time. Check `heapUsed`, `rss` and `external`. If `heapUsed` keeps climbing after garbage collection (GC) and never levels off, you have a leak. A sawtooth pattern that goes up and back down is normal.
- If `rss` or `external` grows but the heap stays flat, the leak is native: Buffers, native addons, or malloc fragmentation. Heap snapshots won't show it.

## 2. Find what's holding the memory
- **Compare heap snapshots (most effective):**
  - Start with `node --inspect app.js`, then open `chrome://inspect` → Memory tab.
  - Or take snapshots in code: `require('v8').writeHeapSnapshot()`, or start with `node --heapsnapshot-signal=SIGUSR2 app.js` and run `kill -USR2 <pid>`.
  - Take snapshot A, run some load, take snapshot B, run more load, take snapshot C. Use the **Comparison** view and look for object types whose count keeps rising.
  - Open the **Retainers** panel for those objects. It shows the chain of references keeping them alive.
- **Allocation timeline / sampling profiler** in DevTools shows which code is allocating the objects that survive.
- **Tools:** `clinic heapprofiler` (from clinic.js), `memlab`, and `--trace-gc` for watching GC behaviour.

## 3. Common causes and fixes
| Cause | Fix |
|---|---|
| Caches or Maps that only grow | Use an LRU with a max size (`lru-cache`) or a TTL, or `WeakMap` / `WeakRef` |
| Event listeners added on every request | Call `removeListener`/`off`, use `once`, or pass an `AbortSignal` |
| `setInterval` or timers never cleared | `clearInterval`/`clearTimeout`, or `.unref()` |
| Closures capturing large objects | Set references to `null` and keep closure scope small |
| Global arrays used as logs or queues | Cap their size or flush them |
| Promises that never settle, or pending requests | Add timeouts and `AbortController` |
| Streams not consumed or destroyed | Use `pipeline()` and handle errors and close |
| DB connections or sockets not released | Release them in `finally` and check pool settings |
| AsyncLocalStorage or APM context buildup | Update the library and check how `run`/`enterWith` are used |

## 4. Check the fix and guard against it
- Run a load test with `autocannon` and confirm the heap levels off.
- Use `--max-old-space-size` to set the heap limit, not to hide a leak.
- In production, track heap metrics and alert on steady growth. Restarting the process (PM2 `max_memory_restart`, a k8s memory limit) is only a stopgap, not a fix.

If you share a heap snapshot comparison or the suspect code, I can help find the cause.

### Candidate X
**1. Confirm the leak.** Track `process.memoryUsage().heapUsed` over hours. Sawtooth pattern is normal GC. A floor that keeps rising is a leak. If `rss` grows but `heapUsed` stays flat, the leak is native (buffers, addons).

**2. Capture heap snapshots.**
- `node --inspect app.js`, then open Chrome `chrome://inspect` → Memory → take a heap snapshot.
- Or from code: `require('v8').writeHeapSnapshot()`.
- Or with a signal: `node --heapsnapshot-signal=SIGUSR2 app.js`, then `kill -USR2 <pid>`.

Take 3 snapshots: at baseline, after load, and after more load. Use the **Comparison** view, sort by `# Delta` / `Size Delta`, then follow the **Retainers** chain to the GC root.

**3. Usual culprits:**
- Unbounded caches or `Map`s used as a cache. Fix: LRU (`lru-cache`) or `WeakMap`.
- Event listeners added per request and never removed. Watch for `MaxListenersExceededWarning`. Fix: `off()`/`removeListener`, or `once()`.
- `setInterval`/`setTimeout` never cleared. Fix: `clearInterval`.
- Closures capturing large objects such as `req` or buffers.
- Globals or module-level arrays that only grow.
- Promises that never settle and hold their context.
- Streams that are never consumed or destroyed. Fix: `stream.pipeline()`.
- DB, HTTP or socket connections that are never closed.

**4. Tools:**
- `clinic heapprofiler` / `clinic doctor`
- `--heap-prof` for an allocation-sampling profile
- `memlab` for automated leak diffs
- `--trace-gc` to watch GC behavior

**5. Verify the fix.** Rerun the load and take snapshots again. The heap floor should flatten.

**Stopgap until it's fixed:** set `--max-old-space-size` and have a process manager restart the process (PM2 `max_memory_restart`, k8s memory limit). This only masks the leak. It doesn't fix it.

### Candidate Y
First confirm the leak, then compare heap snapshots to find which objects keep growing, and remove whatever is holding references to them.

1. Confirm it with `process.memoryUsage().heapUsed` logged over time. A leak keeps rising after GC instead of settling into a sawtooth.
2. Start the process with `node --inspect app.js`, open `chrome://inspect`, and take three heap snapshots a few minutes apart under load.
3. In the "Comparison" view, sort by "# Delta" or "Size Delta". The retainers panel shows what is keeping each growing object alive.
4. Fix the root cause. These are the usual ones:
   - Caches or Maps that grow without limit. Add a size cap or TTL (for example `lru-cache`), or use `WeakMap`.
   - Event listeners that are added again and again without being removed. A `MaxListenersExceededWarning` points to this.
   - `setInterval` timers or closures that never get cleared and keep large objects in scope.
   - Globals, or arrays at module level that collect requests or logs.

In production, `node --heapsnapshot-signal=SIGUSR2 app.js` lets you take a snapshot without attaching a debugger. Taking a snapshot pauses the process, and the snapshot file can be as large as the heap.

## Q4: What does the SQL EXPLAIN command tell me?

### Reference
`EXPLAIN` shows the **execution plan**: how the database intends to run your query. By default it doesn't actually run the query.

**What it shows:**
- **How each table is read:** a full table scan (`Seq Scan` in Postgres, `type=ALL` in MySQL) or an index scan, and which index it uses.
- **Join method and order:** nested loop, hash join or merge join, and which table drives the join.
- **Estimated rows** at each step, which is the planner's guess of how many rows will flow through.
- **Estimated cost** (in Postgres): relative startup and total cost units. These aren't milliseconds.
- **Extra operations:** sorts, aggregations, temp tables, filesorts, subquery handling.
- **Filters:** which conditions are applied at which step, and whether they use an index or are checked row by row.

**`EXPLAIN ANALYZE`** (Postgres; MySQL 8.0.18+) actually runs the query and adds:
- Actual time and actual row counts per step
- Number of loops
- Buffer and I/O usage (`BUFFERS` option in Postgres)

**What to look for:**
- **Full scans on large tables** where you expected an index to be used. This often means a missing index or a condition the index can't use, such as a function on the column.
- **Estimated rows very different from actual rows.** This usually means statistics are stale, so run `ANALYZE`.
- **Large sorts or hashes spilling to disk.**
- **Nested loops over many rows.**

**Example (Postgres):**
```sql
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 42;
-- Index Scan using idx_orders_customer on orders
--   (cost=0.29..8.31 rows=5 width=64) (actual time=0.02..0.03 rows=4 loops=1)
```

Be careful with `EXPLAIN ANALYZE` on `INSERT`, `UPDATE` or `DELETE`, because it really executes them. Wrap it in a transaction and roll back.

### Candidate X
`EXPLAIN` shows the query plan: how the database will run the query. It doesn't return the query's rows.

**What it shows:**
- **Access method per table:** full scan (`Seq Scan` / `ALL`) or index (`Index Scan`, `ref`, `range`).
- **Index choice:** which index is used, or none.
- **Join strategy and order:** nested loop, hash join or merge join, and which table is read first.
- **Estimated rows** at each step.
- **Estimated cost** (Postgres): startup..total, in planner units, not ms.
- **Extra steps:** sort, temp table, filesort, aggregate.

**Variants:**
- `EXPLAIN ANALYZE` (Postgres, MySQL 8.0.18+) actually runs the query and adds real times and row counts. Careful with `INSERT`/`UPDATE`/`DELETE`: the change really happens, so wrap it in a transaction and roll back.
- `EXPLAIN (ANALYZE, BUFFERS)` (Postgres) adds cache hits and disk reads.
- `EXPLAIN QUERY PLAN` (SQLite) gives a simplified plan.

**Problems to look for:**
- Seq scan on a big table with a selective `WHERE`: index likely missing.
- Estimated rows far from actual rows: stale stats, so run `ANALYZE`.
- Nested loop over many rows.
- Sort spilling to disk.

**Example (Postgres):**
```sql
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 42;
-- Seq Scan on orders (cost=0.00..1834.00 rows=10 ...) (actual time=... rows=12 ...)
```
Seq scan here means an index on `customer_id` would probably help.

### Candidate Y
`EXPLAIN` shows the query plan: how the database will run your query, without running it. It tells you:

- **Access method** for each table: full table scan, index scan or index-only scan. A full scan on a large table is often the cause of a slow query.
- **Join strategy and order**, such as nested loop, hash join or merge join.
- **Estimated cost and row counts** for each step, which the planner uses to pick the cheapest plan.
- **Extra operations** such as sorts, aggregations and temporary tables.

`EXPLAIN ANALYZE` (PostgreSQL, and MySQL 8.0.18+) actually runs the query and adds real timings and row counts. If the estimated row counts are far from the actual ones, your table statistics are often stale. Be careful with `EXPLAIN ANALYZE` on `INSERT`, `UPDATE` or `DELETE`, because those changes really happen. To avoid that, wrap the statement in a transaction and roll it back.

## Q5: How does a hash table handle collisions?

### Reference
A collision happens when two keys hash to the same bucket. There are two main ways to handle it.

**1. Separate chaining**
- Each bucket holds a list (or tree) of all the entries that hash to it.
- Insert: add the entry to that bucket's list.
- Lookup: hash the key, then search that bucket's list for it.
- It degrades gracefully, and the load factor (entries ÷ buckets) can go above 1.
- Java's `HashMap` uses this, and it turns a long chain into a red-black tree once the chain gets big enough.

**2. Open addressing**
All entries live in the array itself. On a collision, the table tries other slots in a fixed order until it finds an empty one:
- **Linear probing:** try `h, h+1, h+2, …`. This is cache-friendly but suffers from *primary clustering*, where filled slots bunch together.
- **Quadratic probing:** try `h + 1², h + 2², …`. This reduces clustering.
- **Double hashing:** try `h + i·h2(key)`, using a second hash function to set the step size.
- **Robin Hood hashing:** a variant of linear probing that evens out probe lengths by swapping entries.

Deleting an entry needs *tombstones* (markers saying "something was here"), because emptying the slot would break the probe chains that pass through it. Load factor must stay below 1, and these tables usually resize at around 0.7–0.9. Python's `dict` and Rust's `HashMap` (SwissTable) use open addressing.

**Keeping collisions rare in the first place**
- **Good hash function:** spreads keys evenly across buckets.
- **Resizing:** when the load factor passes a threshold, grow the array (usually doubling it) and rehash every entry.
- **Other schemes:** cuckoo hashing, for example, gives each key two possible slots and moves existing keys aside to make room.

**Cost:** with a good hash and a sensible load factor, operations take O(1) on average. In the worst case, when every key collides, they take O(n), or O(log n) with tree buckets.

### Candidate X
Two families.

**Separate chaining**: each bucket holds a list (or tree) of entries. Collision means append to the list. Lookup scans the bucket. Java `HashMap` turns a long bucket into a red-black tree at 8 entries.

**Open addressing**: all entries live in the array itself. On a collision, probe for another slot:
- Linear probing: `i+1, i+2, …`. Cache-friendly, but entries clump into clusters.
- Quadratic probing: `i+1², i+2², …`. Less clustering.
- Double hashing: step size comes from a second hash.
- Robin Hood: on insert, the entry farther from its home slot takes the spot, which evens out probe lengths.
- Deletion needs tombstones or backward-shift, otherwise probe chains break.

**Both**: keep load factor bounded (about 0.75 for chaining, 0.5–0.9 for open addressing). Past the limit, resize, usually to 2×, and rehash every entry. Average cost stays O(1). Worst case is O(n) when all keys land in one bucket. Randomized or keyed hashes such as SipHash defend against attackers who craft colliding keys.

### Candidate Y
A collision happens when two keys hash to the same bucket. Hash tables handle it in one of two main ways:

1. **Separate chaining:** Each bucket holds a small list (or tree) of entries. Colliding keys are added to that list, and a lookup searches it. Java's `HashMap` works this way and turns long chains into trees.
2. **Open addressing:** Every entry sits in the array itself. On a collision, the table probes other slots until it finds an empty one. It can step one slot at a time (linear probing), jump by growing amounts (quadratic probing) or use a second hash (double hashing). Python's `dict` uses open addressing. Deleting an entry needs a "tombstone" marker so later lookups don't stop too early.

Both kinds of table keep collisions rare by resizing and rehashing once the load factor passes a limit, usually about 0.75. This keeps the average lookup at O(1).

## Q6: Why am I getting CORS errors in my browser console?

### Reference
CORS errors mean your page's JavaScript requested a resource from a **different origin** (a different scheme, domain or port), and the server's response didn't include headers saying your origin is allowed. The browser enforces this, not the server. The request often reaches the server and succeeds there, but the browser won't let your script read the response.

**Common causes (match them to your error message):**

1. **"No 'Access-Control-Allow-Origin' header is present"**: the server doesn't send CORS headers. Configure it to return `Access-Control-Allow-Origin: https://your-site.com`, or `*` for public, no-credentials APIs.
2. **Preflight failure ("Response to preflight request doesn't pass…")**: requests with custom headers (like `Authorization` or `Content-Type: application/json`) or methods like PUT or DELETE first send an `OPTIONS` request. The server must answer that `OPTIONS` request with a 2xx status plus `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`. Auth middleware rejecting `OPTIONS` is a frequent culprit.
3. **Credentials with a wildcard**: if you use `credentials: 'include'` or `withCredentials`, the server must name the exact origin (not `*`) and send `Access-Control-Allow-Credentials: true`.
4. **Origin mismatch**: `localhost:3000` and `localhost:8080` are different origins. So are `http` and `https`, and `www` and the bare domain.
5. **It's really a server error**: a 500 or 404 response, or a redirect, often lacks CORS headers, so the browser reports it as a CORS error. Check the actual status code in the Network tab.

**Fixes:**
- **If you control the server:** add CORS middleware, such as `cors` for Express, `django-cors-headers` or `flask-cors`, and make sure it also handles `OPTIONS` requests.
- **In local development:** use your dev server's proxy, such as Vite's `server.proxy` or CRA's `"proxy"` field, so requests come from the same origin.
- **If it's a third-party API you don't control:** call it from your own backend instead of the browser.

Paste the exact error text and tell me your frontend and backend setup, and I can point to the specific fix. I can also look at the console and network requests in your Chrome tab directly if you want.

### Candidate X
Your page is calling a different origin (another domain, port or protocol), and that server's response doesn't include headers allowing your origin. The browser blocks it; the server isn't rejecting the request.

The most common causes:

1. **No `Access-Control-Allow-Origin` header.** The API has to return your exact origin (for example `http://localhost:3000`) or `*`.
2. **Failed preflight.** Requests with custom headers, JSON bodies or methods like PUT and DELETE send an `OPTIONS` request first. The server must answer it with a 2xx status and the right `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`.
3. **Credentials with a wildcard.** If you use `credentials: 'include'`, the server can't use `*`. It must name your origin and send `Access-Control-Allow-Credentials: true`.
4. **The request failed for another reason.** A 404, 500 or redirect often comes back without CORS headers, so the browser reports it as a CORS error.

The fix belongs on the server. If you don't control the server, route the calls through a dev-server proxy or your own backend. Disabling CORS in the browser only hides the problem on your machine.

If you paste the exact console error, I can tell you which of these it is.

### Candidate Y
Browser blocks cross-origin request: page origin (scheme+host+port) differs from API origin, and server response lacks permission headers.

**Common causes:**
- No `Access-Control-Allow-Origin` header on response.
- Preflight (`OPTIONS`) fails: triggered by non-simple method (`PUT`, `DELETE`), custom headers (`Authorization`), or `Content-Type: application/json`. Server must answer `OPTIONS` with 2xx plus `Access-Control-Allow-Methods` / `Access-Control-Allow-Headers`.
- Credentials (`credentials: 'include'`) with `Access-Control-Allow-Origin: *`. Not allowed. Must echo exact origin plus `Access-Control-Allow-Credentials: true`.
- Server error (500, 404, redirect) returns without CORS headers. Real bug hidden behind a CORS message.
- `http` vs `https`, or `localhost` vs `127.0.0.1`: different origins.

**Fixes:**
- Server side (correct fix), e.g. Express: `app.use(require('cors')({ origin: 'http://localhost:3000', credentials: true }))`.
- Dev: proxy through dev server (Vite `server.proxy`, CRA `"proxy"` in `package.json`). Same origin, no CORS.
- Third-party API you don't control: call it from your backend, not the browser.

**Not fixes:** `mode: 'no-cors'` (response becomes opaque, unreadable). Setting `Access-Control-Allow-*` on the *request* (ignored; server must send them).

Paste exact console error and request details (method, headers, origin, API URL) for a specific diagnosis.

## Q7: What's the point of using a debouncer on a search input?

### Reference
A debouncer holds off running the search until the user stops typing for a short time, usually 200–500 ms. Without one, typing "react hooks" fires a search on every keystroke, which is 11 requests. With one, it fires about once.

**Why it helps:**

- **Lower server and API load:** You make far fewer requests, which matters with rate limits or paid APIs.
- **No out-of-order results:** With many requests in flight, an older, slower response can arrive last and replace the newer results. Debouncing makes this much less likely, though you still need to cancel requests with `AbortController` to rule it out.
- **Better performance:** It avoids re-rendering, filtering or recomputing on every keystroke. This helps even with local search over a large list.
- **Calmer UI:** Results don't flicker while the user is still typing.
- **Searches the real query:** Partial words like "rea" are mostly wasted searches.

**Minimal example:**
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

**Trade-off:** Results appear slightly later. If the dataset is small and local, searching on every keystroke can feel snappier. **Throttling** is a related technique: it runs at most once per interval instead of waiting for typing to stop. It suits live updates during continuous input, but for search inputs debouncing is usually the better fit.

### Candidate X
Waits until typing pauses (~200–300ms), then fires one search.

Without it, every keystroke fires a search. Typing "react" sends 5 requests.

Benefits:
- **Less load**: fewer API calls and DB queries, and lower rate-limit risk.
- **Fewer stale results**: slow responses to earlier keystrokes can arrive after newer ones and overwrite them. Debouncing reduces this but doesn't eliminate it. Also cancel old requests (`AbortController`) or ignore outdated responses.
- **Smoother UI**: fewer re-renders and less flicker.
- **Lower cost**: matters for paid APIs.

Trade-off: results show up a little later. Delay too long feels laggy. Throttle instead if you need updates at a steady rate while the user is still typing.

### Candidate Y
A debouncer waits until the user stops typing for a short pause, often 200 to 300 ms, before it runs the search. If you search on every keystroke, typing "laptop" sends six requests. A debouncer sends one.

That gives you three benefits:

- **Less load:** Fewer calls go to your API or database, which cuts server cost and keeps you under rate limits.
- **No stale results:** Slow responses for "lap" can't arrive after the results for "laptop" and overwrite them. This is less likely, but it can still happen, so cancel or ignore old requests too.
- **Smoother UI:** The results list doesn't flicker or redraw on every keystroke.

The cost is a short wait before results appear. Keep the delay short so search still feels instant.

## Q8: How does git rebase differ from git merge?

### Reference
Both commands bring the changes from one branch into another. The difference is what happens to the commit history.

**`git merge`**
- Adds a new merge commit that has two parents and ties both branches together.
- Keeps the history exactly as it happened. No existing commits are changed.
- Safe to use on shared or public branches.
- History can get cluttered with merge commits and a non-linear graph.

**`git rebase`**
- Takes your branch's commits and replays them one by one on top of the target branch, creating new commits with new SHAs.
- Gives a linear history with no merge commit.
- Rewrites history, so don't rebase commits that others have already pulled. If you do, you'll need `push --force` and their copies will diverge.
- With `-i` (interactive) you can squash, reorder or edit commits.
- You may have to resolve conflicts once for each replayed commit, while a merge has you resolve them once.

**Example**: `feature` branched off `main`, and `main` has moved forward since:

```
merge:   A---B---C---M  (main)      rebase:  A---B---C---D'---E'  (feature)
              \     /
               D---E   (feature)
```

**Rule of thumb**: rebase local or private branches to tidy them up before sharing. Merge (or use a PR merge) to integrate shared branches.

### Candidate X
**Merge:** combines branches with a new merge commit. History preserved and non-linear. Existing commits aren't rewritten, so it's safe on shared branches.

**Rebase:** replays your commits onto the new base, each as a new commit with a new SHA. History becomes linear with no merge commit. It rewrites history, so never rebase commits others have pulled.

```
# merge
git checkout feature && git merge main

# rebase
git checkout feature && git rebase main
```

- **Conflicts:** merge resolves them once. Rebase can stop at each replayed commit.
- **Traceability:** merge shows when branches joined. Rebase gives cleaner `git log` and easier `git bisect`.
- **Common workflow:** rebase local feature branch on `main`, then merge into `main` (often `--ff-only` or squash).
- **Recovery:** `git reflog` finds pre-rebase commits.

### Candidate Y
Both combine work from two branches, but merge keeps history as it happened while rebase rewrites it.

`git merge main` adds a merge commit that joins the two branches. Your existing commits stay unchanged, so the history is accurate but can get cluttered with merge commits.

`git rebase main` replays your commits on top of the tip of `main`, one by one. Each replayed commit gets a new hash. The result is a straight, linear history, but the original commits are replaced. You may also have to resolve conflicts once per commit instead of once overall.

Use rebase to tidy your own local or private branch before sharing it. Use merge on shared branches. Never rebase commits that others have already pulled, because rewriting them forces everyone else to reconcile diverged history.

## Q9: When should I use a queue vs a topic in messaging systems?

### Reference
**Use a queue when each message should be handled once, by one consumer (point-to-point).**
- **Work distribution:** jobs, tasks or commands such as "resize this image" or "charge this card".
- **Load balancing:** add more workers to handle more messages; each message goes to only one worker.
- **Backpressure and buffering:** messages wait in the queue until a worker is free.
- **Commands:** a message that asks for something to be done should be done exactly once.
- Examples: SQS, RabbitMQ queues, Azure Service Bus queues.

**Use a topic when each message should reach every interested subscriber (pub/sub).**
- **Events:** messages that report that something happened, like "OrderPlaced" or "UserSignedUp".
- **Fan-out:** several independent services react to the same event, such as billing, email and analytics.
- **Decoupling:** the publisher doesn't know or care who is listening, so you can add new consumers without changing it.
- Examples: SNS, Google Pub/Sub topics, Kafka topics, Azure Service Bus topics.

**Rule of thumb:**
- A **command** ("do X") goes to a queue, with one handler.
- An **event** ("X happened") goes to a topic, with many listeners.

**Common hybrid:** a topic that fans out into one queue per subscriber, such as SNS → SQS or Service Bus topic → subscriptions. Each service gets every event, and each service can still run several load-balanced workers on its own queue. Kafka does this natively with consumer groups: every group gets every message, and the consumers inside a group split the partitions between them.

**Other factors:**
- **Replay and retention:** use a log-based topic (Kafka, Kinesis) if consumers need to re-read history. Classic queues delete a message once it has been consumed.
- **Ordering:** both can keep messages in order only within a partition or message group.
- **Durability for subscribers:** on a plain topic, an offline subscriber can miss messages. Use durable subscriptions, or a queue per subscriber, if that matters.

### Candidate X
**Queue:** point-to-point. Each message goes to one consumer.
- Work distribution, load balancing: add workers, they split the load.
- Tasks: jobs, commands, order processing, emails to send.
- Each job runs only once per message (still make handlers idempotent, since redelivery happens).

**Topic:** pub/sub. Every subscriber gets its own copy of each message.
- Events many services care about, e.g. `OrderPlaced` going to billing, shipping and analytics.
- Decoupling: the publisher doesn't know who the subscribers are.
- Add new consumers without touching the producer.

**Rule of thumb:** a command that should be done once goes on a queue. A fact that others may react to goes on a topic.

**Hybrid (common):** topic fans out to one queue per subscriber service, and competing workers read each queue. Examples:
- SNS → SQS
- Kafka consumer groups: each group gets every message, and within a group each partition goes to one consumer.
- RabbitMQ: fanout exchange → queues.
- Azure Service Bus: topic subscriptions.

**Also consider:**
- Replay or event sourcing: use a log-based topic (Kafka, Pulsar). A classic queue deletes the message after ack.
- Ordering: queue FIFO modes, or Kafka partition key. Only ordered per partition or group, not globally.
- Backpressure and retries: queues usually have a built-in DLQ and visibility timeout.

### Candidate Y
Use a queue when each message should be handled by exactly one consumer. Use a topic when each message should reach every interested subscriber.

A queue fits work distribution. Examples are processing orders, resizing images or sending emails. Adding consumers spreads the load across them, and each job runs once.

A topic fits event broadcasting. For example, when "OrderPlaced" is published, billing, shipping and analytics each get their own copy. The publisher doesn't need to know who is listening, so you can add new subscribers without changing it.

You can combine the two by publishing to a topic and giving each subscribing service its own queue. Each service then gets every event, and its instances share the work. This is how SNS feeding SQS works, and how Kafka consumer groups behave.
