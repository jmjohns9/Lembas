**Problem.** If Desktop and Server send the same queries, the 40-second gap comes from one of three places: the query path (the Server's network route or driver to SQL Server, or a per-user filter that stops the cache from being reused), server-side rendering, or a busy VizQL process. The likeliest is the query path. A performance recording shows which one it is.

**Fix.**
1. Allow recording under Site Settings > "Allow users to record workbook performance metrics". Then load the view with `?:record_performance=yes` added to the URL, click **Performance** in the toolbar, and compare the result with a Desktop recording (Help > Settings and Performance > Start Performance Recording).
2. If "Executing Query" is much slower on Server, open the Server's driver version and network route to SQL Server, check whether `USERNAME()` or Initial SQL is splitting the cache per user, and check whether the LOD calcs are running as `FIXED` subqueries over the whole table.
3. If "Computing Layout" or "Rendering" is slow, the dashboard has too many marks for server-side rendering. Reduce the marks or raise `vizqlserver.browser.render_threshold`.
4. If both are slow only when traffic is high, look at VizQL CPU and memory in the admin views.

To confirm the fix worked, record performance on Server again and check that the slow event has shrunk.

**Alternatives.** Use an extract on a schedule if the data can be a few hours old. Use a published data source if several workbooks repeat the same LOD queries.

**Why this fix.** The recording tells you which layer is slow before you change anything. The most common trap is trusting the 5-second Desktop time. Desktop may be answering from its warm query cache, so before you compare, close and reopen Desktop and record it from a cold start.