**Problem.** For a Microsoft 365 shop, licensing and identity matter more than chart quality. Power BI already uses your Entra ID groups, Teams, SharePoint and Excel. Tableau would need a separate identity, governance and licensing setup.

**Fix.** Choose Power BI.
1. Check which users already have Power BI Pro. It is included in Microsoft 365 E5. Otherwise it was $14 per user per month after the April 2025 price change, so confirm current pricing with your Microsoft rep.
2. Give the self-service rollout a backbone of certified semantic models in shared workspaces, so users build reports on governed data rather than their own copies.
3. Before go-live, set tenant settings in the admin portal to control who can create workspaces and who can publish to the web.
4. To confirm it works, run a 4 to 6 week pilot with one department and measure how many reports reuse the certified models.

**Alternatives.** Use Tableau if your analysts already know it well, or if visual exploration and design control matter more than cost, since Creator licenses cost several times more than Power BI Pro. Use Fabric capacity (F64 or higher) instead of per-user Pro if you have many view-only users, because at that size viewers don't need Pro licenses.

**Why this fix.** Power BI costs less per user and fits the governance you already run. The common trap is ungoverned self-service: hundreds of duplicate datasets with conflicting numbers. Certified models and workspace rules prevent that.