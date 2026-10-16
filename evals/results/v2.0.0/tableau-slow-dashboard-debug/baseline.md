A 9× gap between Desktop and Server usually comes from caching, the network path to SQL Server, or rendering. It's rarely the workbook logic, because the LOD calcs run the same SQL in both places. Measure first, then work through the likely causes.

## 1. Measure where the time goes

- **Make sure the Desktop number is a cold start.** Desktop keeps a query cache, so a second open often hits it. Close Desktop completely, reopen the workbook and time it again. If it's now 30+ seconds, the problem is the queries, not the Server.
- **Record performance on Server.** Turn on *Site Settings → Workbook Performance Metrics*. Then open the view with `?:record_performance=yes` added to the URL, load it, and click **Performance** in the toolbar. Compare the time spent on *Executing Query*, *Computing Layout*, *Rendering* and *Connecting to Data Source* with a Desktop recording (*Help → Settings and Performance → Start Performance Recording*).
- **Trace on the SQL Server side.** Use Extended Events or Query Store, filtered on the Tableau Server host or service account. This shows whether the same queries run slower, or whether Server sends different or extra queries.

## 2. Common causes, roughly in order of likelihood

**Network and connection**
- **Network path.** Your laptop may sit close to SQL Server while the Tableau Server box is in another data center, region or VNet. Run a test query from the Server machine itself.
- **Driver version.** Check that the SQL Server ODBC driver on Server is the same version as on your machine (ideally a current ODBC Driver 17 or 18).
- **Authentication.** Kerberos delegation, prompting for credentials or the "Viewer credentials" setting can add connection overhead on every load. Embedded credentials are usually fastest.
- **Published data source.** If the data source is published, queries take an extra hop through the Data Server process. Try an embedded connection as a test.

**Caching and per-user queries**
- **User-specific logic.** If you use `USERNAME()`, user filters, row-level security or Initial SQL with `[TableauServerUser]`, every user gets their own queries and nothing is shared from the cache. Every load is a cold load.
- **Server cache settings.** If the cache is set to "Refresh more often" (or `vizqlserver.data_refresh` is set low), Server re-queries more than you'd expect. Check *Server → Settings → Data Connections*.

**Queries**
- **Too many queries at once.** 8 sheets plus quick filters can mean 15–30 queries per load. Server may run fewer of them in parallel than Desktop does, so they line up one after another. The performance recording shows this.
- **Quick filters set to "Only Relevant Values".** Each of these runs its own query and makes the filters depend on each other. Switch them to "All Values in Database", or use parameters or action filters instead.
- **FIXED LODs.** These become subqueries or self-joins, and they ignore regular filters. If dimension filters should reduce the LOD data, make those filters context filters. Check the generated SQL for full table scans and add indexes or a pre-aggregated view if needed.

**Rendering and Server resources**
- **Server-side rendering.** Views with many marks (or above the complexity threshold set by `vizqlserver.browser.render_threshold`) are drawn on Server as image tiles. Your browser doesn't draw them. A high *Rendering* or *Computing Layout* time points here.
- **Busy Server.** Check VizQL Server CPU and memory, the number of VizQL processes, and whether backgrounder jobs (extract refreshes, subscriptions) run on the same node at the same time. Use the Admin Views or Tableau Resource Monitoring Tool.
- **Device layouts and dashboard size.** An "Automatic" dashboard size forces Server to recompute the layout for each browser window size. A fixed size also caches better.

## 3. Quick wins to try

1. Set a fixed dashboard size.
2. Change "Only Relevant Values" filters to "All Values".
3. Hide or remove any sheets that aren't needed on first load.
4. Consider an extract, even one refreshed every hour. A live connection to SQL Server is often the biggest single cost. If you need live data, a materialized or indexed view for the LOD logic helps a lot.
5. Add `?:refresh=no`-style cache warming, or schedule a subscription that loads the view so the cache is populated before users arrive.

Start with the Server performance recording. It will tell you whether the time is in queries, connecting or rendering, and that narrows this list to two or three items.