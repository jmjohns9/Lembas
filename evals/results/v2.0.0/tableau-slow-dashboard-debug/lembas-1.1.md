Start by recording performance on Server, because the 5-second Desktop time is probably cached. Desktop reuses query results from your session, while Server often runs every query cold. Close and reopen the workbook in Desktop, then time it again before comparing.

1. **Find the slow step.** Add `?:record_performance=yes` to the view URL. The performance recording shows whether the time goes to query execution, rendering or layout.
2. **Run the slow SQL on the server.** If queries dominate, run the captured SQL in SSMS from the Tableau Server machine. That shows network latency, driver differences and the cost of credentials on that path.
3. **Check row-level security and impersonation.** User filters, `USERNAME()` calcs and Run As User make each user's queries unique, so Server can't reuse its cache. They also add joins.
4. **Check rendering mode.** Heavy marks may render server-side. Check `tsvizql.ini` settings or the render threshold.
5. **Check Server load and cache.** Look for busy VizQL processes in the Admin views, and confirm the data cache isn't set to "refresh every time."

Of your LOD calcs, FIXED ones become correlated subqueries and often perform badly on a live connection. Context filters or an extract usually fix that.