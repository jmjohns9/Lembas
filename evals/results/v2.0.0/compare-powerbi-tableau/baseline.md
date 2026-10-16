**Go with Power BI.** For a Microsoft 365 shop starting self-service analytics, it's the default choice. Choose Tableau only if one of the exceptions below applies to you.

## Why Power BI fits you

- **Cost.** Power BI Pro is included in Microsoft 365 E5. On E3 or lower it's a cheap add-on per user. Tableau's Creator and Explorer licenses usually cost several times more per user. For a broad rollout, that gap gets large quickly.
- **Identity and governance come built in.** It uses Entra ID for sign-in, groups and conditional access, Purview sensitivity labels, and the tenant admin controls you already run. With Tableau you'd set up and maintain a separate identity and permissions layer.
- **People can share where they already work.** Reports embed in Teams, SharePoint and PowerPoint, and "Analyze in Excel" lets Excel users work with governed data in a tool they know. Self-service programs often fail because people don't adopt them, and this lowers that barrier.
- **Shared datasets.** Semantic models let a central team publish certified datasets that business users build on. That's the "governed self-service" pattern most rollouts aim for.
- **Microsoft Fabric.** If you might later consolidate data engineering or warehousing in Azure or Fabric, Power BI sits inside that platform.
- **Copilot.** If you're already paying for Copilot, it works with Power BI's semantic models.

## When Tableau is the better choice

- **Your data is mostly outside Microsoft.** For example, you're heavily invested in Salesforce or Snowflake, or your data team is standardized on non-Microsoft tools.
- **Your users already know Tableau.** Retraining skilled users has a real cost.
- **Visual exploration is the main need.** Tableau is still generally seen as more fluid for ad hoc visual analysis by analysts, whereas Power BI is stronger for standard business reporting.
- **You need Mac authoring.** Power BI Desktop runs only on Windows. Mac users have to author in the browser, which has fewer features.

## Downsides of Power BI to plan for

- **Uneven model quality.** DAX has a steep learning curve, and self-service users can create messy, duplicated models. Plan for certified semantic models, a center of excellence or champions network, and workspace naming and lifecycle rules from the start.
- **Capacity limits.** Large datasets or heavy refresh loads can push you into Premium or Fabric capacity (F SKUs), which has a very different cost profile. Size this early.
- **Sprawl.** Without governance, workspaces multiply quickly. Turn on tenant settings deliberately rather than leaving the defaults.

## Suggested next step

Before you commit, run a 4–6 week pilot with 2–3 real business teams. Use actual data sources and include at least one non-Microsoft source. Track build time, how many people actually use the reports, and admin effort. Unless you hit one of the Tableau exceptions above, Power BI will very likely win.

Licensing and pricing change often, so check current terms with your Microsoft and Salesforce/Tableau reps. If you need to present this to stakeholders, I can turn it into a shareable comparison page.