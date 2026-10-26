# Badges

Shields.io always draws badge text in white, so values use the dark tokens only.
Labels are Anduin Night `#0E1719`. Every pair below meets WCAG AA for small text.

| Role | Value colour | White text contrast |
|---|---|---:|
| Label (all badges) | Anduin Night `#0E1719` | 18.18:1 |
| Primary: release, benchmark | Gilt `#7D5F16` | 5.97:1 |
| License | Lórien Green `#3E5C47` | 7.43:1 |
| Ithildin | Starlight `#4E6479` | 6.14:1 |

Never use Mallorn Gold `#C9A44C` or Ithildin `#DCE6EE` as a badge colour: white text on them is 2.3:1 and 1.2:1.
Style is always `flat-square`; it matches the mark's straight break better than the rounded default.

## Ready to paste

Replaces the three badges at the top of the README:

```markdown
[![Checks](https://img.shields.io/github/actions/workflow/status/jmjohns9/lembas/checks.yml?style=flat-square&label=checks&labelColor=0E1719)](https://github.com/jmjohns9/lembas/actions/workflows/checks.yml)
[![Release](https://img.shields.io/github/v/release/jmjohns9/lembas?style=flat-square&labelColor=0E1719&color=7D5F16)](https://github.com/jmjohns9/lembas/releases/latest)
[![License](https://img.shields.io/badge/license-Apache%202.0-3E5C47?style=flat-square&labelColor=0E1719)](LICENSE)
```

Optional extras:

```markdown
[![Replies 61–62% shorter](https://img.shields.io/badge/replies-61%E2%80%9362%25%20shorter-7D5F16?style=flat-square&labelColor=0E1719)](docs/BENCHMARKS.md)
[![Complete in blind review](https://img.shields.io/badge/blind%20review-19%20of%2020%20complete-7D5F16?style=flat-square&labelColor=0E1719)](docs/BENCHMARKS.md)
[![Ithildin](https://img.shields.io/badge/Ithildin-long%20documents-4E6479?style=flat-square&labelColor=0E1719)](docs/ITHILDIN.md)
[![Claude skill](https://img.shields.io/badge/Claude-skill-7D5F16?style=flat-square&labelColor=0E1719)](https://github.com/jmjohns9/lembas#install)
```

The `checks` badge deliberately has no `color`: shields would apply it whatever the run result, and a failing build must never look green. It keeps shields' own pass/fail colours.

While the repo is private, the README uses GitHub's own checks badge (`actions/workflows/checks.yml/badge.svg`): shields.io reads repos anonymously and shows "not found" for private ones. Switch to the shields version above when the repo goes public. The release badge also needs a public repo to resolve.
