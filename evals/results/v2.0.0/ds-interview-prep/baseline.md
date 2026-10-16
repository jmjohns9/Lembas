A week is enough if you focus on what this particular interview will test. Here's how I'd spend it.

## First: find out the format (do this today)
Ask the recruiter what the rounds are and who you'll meet. Data science interviews differ a lot. Some are heavy on SQL and product analytics, some on ML modeling, some on stats and experiments. Knowing the format tells you where to spend your time. Read the job description again and highlight the tools and skills it names.

## The core areas

**1. SQL (almost always tested)**
- Joins (including self-joins), GROUP BY / HAVING, CTEs, subqueries
- Window functions: `ROW_NUMBER`, `RANK`, `LAG/LEAD`, running totals
- Typical problems: retention, top N per group, rolling averages, deduplication
- Practice: 2–3 problems a day on LeetCode, StrataScratch or DataLemur

**2. Statistics and probability**
- Hypothesis testing, p-values, confidence intervals, Type I/II errors, power
- A/B testing end to end: choosing a metric, sample size, running time, pitfalls (peeking, novelty effects, multiple comparisons, sample ratio mismatch)
- Bayes' theorem, common distributions, CLT
- Be able to explain a p-value to someone who isn't technical

**3. Machine learning**
- Bias–variance tradeoff, overfitting, regularization (L1 vs L2)
- How the main models work and when to use each: linear/logistic regression, trees, random forests, gradient boosting
- Evaluation: precision/recall, ROC-AUC, why accuracy misleads on imbalanced data, cross-validation
- Feature engineering, data leakage, handling missing data
- Expect "walk me through how you'd build a model for X"

**4. Python / pandas**
- groupby, merge, pivot, apply; working with dates
- Some companies ask basic algorithm questions too (arrays, hash maps, strings)

**5. Product sense / case questions (common at tech companies)**
- "Metric X dropped 10%. How would you investigate?" Answer it in order: check the data is right → split by segment, platform and time → look at internal and external causes
- "How would you measure the success of feature Y?" Give a north-star metric, guardrail metrics and a way to test it
- Study the company's product and think about what it would measure

**6. Behavioral and your past projects**
- Prepare 2–3 projects you can explain in depth: the problem, your approach, tradeoffs, results with numbers, and what you'd do differently
- Have STAR stories ready for conflict, failure, influencing without authority, ambiguity, and explaining work to non-technical people
- Expect follow-up questions on anything on your resume

## Suggested schedule
| Day | Focus |
|---|---|
| 1 | Learn the format, research the company, outline your project stories |
| 2 | SQL (heavy) + Python/pandas |
| 3 | Stats + A/B testing |
| 4 | ML concepts + a mock "build a model" walkthrough |
| 5 | Product/case questions + more SQL |
| 6 | Full mock interview (with a friend, a peer platform, or me) and fix weak spots |
| 7 | Light review, prepare questions to ask them, rest |

## In the interview
- **Think out loud.** Interviewers care about how you reason as much as the final answer.
- **Ask clarifying questions** before you start on SQL or case problems.
- **State your assumptions** and check edge cases (NULLs, duplicates, ties).
- **Bring questions for them**, e.g. "What does success look like in the first 6 months?" or "How does the DS team work with product and engineering?"

If you tell me the company, the seniority level, or what the job description emphasizes, I can make this more specific. I can also run a mock interview with you: SQL problems, stats questions, a product case, or a behavioral round with feedback.