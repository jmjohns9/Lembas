**Problem.** "Data scientist" covers very different jobs, so a week of generic study is easy to waste. Most interview loops test four areas: SQL and Python, statistics and A/B testing, ML concepts, and product sense with behavioral questions. How much each one counts depends on whether the role is analytics-heavy or modeling-heavy. Before you plan anything, email the recruiter and ask: "What are the rounds, and what does each one cover?" Recruiters usually tell you.

**Fix.** Use a 7-day plan, weighted toward the rounds the recruiter names:
- **Days 1–2, SQL and Python:** Focus on window functions (`ROW_NUMBER`, `LAG`), self-joins, `GROUP BY ... HAVING`, and pandas groupby and merge. Do 15–20 timed problems on DataLemur or StrataScratch.
- **Day 3, stats:** Cover p-values, power and sample size, Type I and II errors, Bayes' rule, and the CLT. Practice explaining each one in two sentences.
- **Day 4, experimentation:** Practice designing an A/B test end to end: metric, randomization unit, duration, and pitfalls like novelty effects, peeking, and SRM.
- **Day 5, ML:** Cover the bias-variance tradeoff, regularization, tree models vs. linear models, how to pick an evaluation metric when classes are imbalanced, and leakage.
- **Day 6, product and behavioral:** Pick 3 of the company's products and define success metrics for each. Write 5 STAR stories (conflict, failure, impact, ambiguity, influence).
- **Day 7:** Do one full mock interview out loud (Pramp, or a friend), then rest.

You'll know you're ready when you can solve a medium SQL problem in under 15 minutes and explain an A/B test design without notes.

**Alternatives.** If it's a modeling or ML-engineer role, swap Day 6 for coding practice (LeetCode easy/medium) and ML system design. If there's a take-home, spend more time on clean notebook structure and stating your assumptions clearly.

**Why this fix.** SQL and experimentation come up in almost every DS loop and are the fastest areas to improve in one week. The most common mistake is practicing silently: interviewers grade your reasoning out loud as much as the final answer.