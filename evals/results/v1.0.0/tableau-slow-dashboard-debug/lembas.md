Record performance on Server first, because it tells you whether the 40 extra seconds are spent on queries or on rendering. Add `?:record_performance=yes` to the view URL, load the dashboard, click Performance in the toolbar, and compare it with a Desktop recording from Help > Settings and Performance > Start Performance Recording.

1. Desktop was likely serving from its warm query cache, so close Desktop, reopen the workbook and time a cold load before comparing.
2. The Server host may reach SQL Server over a slower network path or an older SQL Server driver, so check latency from that machine and match driver versions.
3. Authentication can differ on Server, since impersonation, Kerberos delegation or user filters add a login per query and stop query results from being shared across users.
4. A busy VizQL process can push the view into server side rendering, so check the Background Tasks and Stats for Load Times admin views during the slow load.
