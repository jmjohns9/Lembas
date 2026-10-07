For a self-service rollout in an M365 shop, I'd lean Power BI. The one thing that could change that is if you already have a working Tableau Server with governance, certified data sources and trained users that you'd be walking away from.

**Why Power BI fits a self-service rollout better**

- **Cost per seat.** Power BI Pro is often already included through E5. If it isn't, it still costs much less per user than Tableau Creator or Explorer. Self-service only works when you can license lots of casual builders, and seat cost decides that.
- **Users already know the tools.** Excel users pick up Power Query and basic DAX quickly. "Analyze in Excel" also gives hesitant users an easy first step.
- **Distribution is built in.** Reports go out through Teams, SharePoint and Power BI apps. Access follows Entra ID groups and sensitivity labels follow Purview, so you don't run a separate identity and permissions layer.
- **AI and Copilot.** Copilot in Power BI, Fabric and Copilot Studio agents work directly against semantic models. Tableau has its own AI features, but they don't connect into your M365 tenant the same way.

**Where Tableau still wins**

- Visual flexibility and exploratory analysis. Analysts who think visually usually build faster and better in Tableau.
- Data source neutrality. It handles Teradata, Snowflake and mixed environments without leaning you toward Fabric.
- An existing Server platform with mature content and admin processes. Migrating that is real work and real risk, and it shouldn't count as a free side benefit of switching.

**Things to check before you commit**

1. **Cloud environment.** If you're on GCC High, confirm which Power BI, Fabric and Copilot features are actually available there today. Commercial features often arrive late or not at all, so don't plan the rollout around a feature you saw in a commercial demo.
2. **Licensing math.** Price it at real scale: Pro vs. Premium Per User vs. Fabric capacity, against Tableau Creator, Explorer and Viewer. Capacity licensing changes the numbers once you have a lot of viewers.
3. **Governance model.** Self-service fails because of sprawl more often than because of the tool. Decide early who publishes certified semantic models, how workspaces get named and owned, and what the promotion path looks like from personal work to shared content.
4. **Coexistence.** For a large organization, running both is common and reasonable. Power BI can be the self-service and M365 surface, while Tableau stays the place for advanced visual analytics and established enterprise dashboards. Set clear rules for what goes where so people aren't rebuilding the same report twice.

**My take:** If this is a new rollout for a broad, mostly non-technical audience living in Teams and Excel, go with Power BI and spend the effort on governance and certified data. If the audience is mainly analysts, or you'd be rebuilding a Tableau ecosystem that already works, keep Tableau as the core and add Power BI where M365 integration really matters.

If you tell me the audience size, your cloud environment and what you already have running, I can draft a short decision memo or a licensing comparison.
