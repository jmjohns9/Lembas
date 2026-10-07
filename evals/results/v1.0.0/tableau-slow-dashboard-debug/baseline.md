A 9x gap between Desktop and Server on the same live connection usually means something in the environment is different, not the workbook itself. If the workbook were the problem, Desktop would be slow too. Check these in order.

## 1. Measure before changing anything

Record performance on both sides so you're comparing the same thing.

- **Server:** add `?:record_performance=yes` to the view URL, load it, then click **Performance** in the toolbar. You'll see query time, compute layout, rendering and so on.
- **Desktop:** Help > Settings and Performance > Start Performance Recording. Close and reopen the workbook first so you aren't reading from a warm cache.

Compare the two. If the "Executing Query" events are slow only on Server, the issue is the data path. If queries are similar but layout or rendering is slow, the issue is on the Server side (VizQL load or rendering).

## 2. Confirm Desktop is actually hitting the database

Desktop is often fast because it's serving from its query cache. After a cold reopen, if Desktop jumps to 20+ seconds, the real problem is the queries themselves and Server isn't really the cause.

## 3. Check the data path from the Server node

These are the most common causes:

- **Different credentials or user context.** On Server, check whether the connection uses embedded credentials, prompts the user, or uses Kerberos/impersonation. Per user auth turns off shared caching and can send each user's queries through a different SQL Server security path.
- **User filters or row level security.** If you have `USERNAME()` calcs or entitlement joins, Server generates per user queries that Desktop never runs. Those can be much heavier.
- **Driver mismatch.** Compare the SQL Server ODBC driver version on each Server node with the one on your machine. Older drivers on Server are a real and frequent cause of slow queries.
- **Network.** Check latency between the Server node(s) running VizQL/Data Server and SQL Server. A different data center or a firewall hop adds up across 8 sheets' worth of round trips.
- **Published data source.** If the workbook uses a published data source, queries go through Data Server, which adds a hop. Test with an embedded copy to compare.
- **Different target.** It sounds obvious, but confirm Server points to the same database instance and not a busier prod copy.

## 4. Look at it from SQL Server's side

Have your DBA (or yourself, if you have access) capture the queries with Extended Events or Query Store while you load the view on Server. Compare duration, reads, and execution plans against the queries from your Desktop session. This tells you right away whether SQL Server is slow for the Server's queries or whether the time is being spent elsewhere.

## 5. Check Server load and rendering

- Look at the **Stats for Load Times** and **Performance of Views** admin views, or TS Events / Admin Insights, to see whether this view is slow all day or only at peak times. If it's slow only at peak, VizQL processes may be overloaded.
- Check whether the view is rendering server side. A high mark count can push rendering to Server, which is slower than the client side rendering you get in Desktop. The `vizqlserver.browser.render_threshold` setting controls this.
- Check the Data Connections cache setting. If Server is set to refresh often, every load goes back to the database.

## 6. Then tune the workbook

Once you know where the time goes, these help on any live connection:

- **LOD calcs:** FIXED LODs become subqueries joined back to the main query. Check whether you can replace some with simpler aggregates, or use context filters so the FIXED calcs run against less data.
- **Filters:** quick filters set to "Only Relevant Values" each run their own query. Switch to "All Values in Database" or use parameters where you can.
- **8 sheets:** each sheet is at least one query. Make sure sheets share the same filters and level of detail so Tableau can fuse queries. Remove any hidden sheets that are still on the dashboard.
- **Extract test:** publish a copy as an extract. If it drops to a few seconds, you've confirmed the bottleneck is the live query path, and you can decide whether an extract or a database side fix (indexes, a view, or a summary table) is the better answer.

If I had to bet, I'd start with the performance recording on Server and the credentials/user filter question. Those two explain most of the "fast in Desktop, slow on Server" cases. Send me what the recording shows and I can help narrow it down.
