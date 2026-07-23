# Product & Business Thinking

## 1. Five weaknesses in the current product design

1. **No source verification or freshness signal.** The report cites URLs but
   never checks whether a claim is actually supported by the linked page, or how
   recent it is. A seller could walk into a meeting citing a stale or
   hallucinated fact — the most dangerous failure mode for this product.
2. **Research quality is invisible and untrusted.** There's a quality *score*
   internally, but the user sees a polished report with no confidence levels,
   no "how sure are we" per section, and no distinction between a fact grounded
   in a source vs. an inference. Uniform confidence reads as false authority.
3. **Single-shot, generic research.** Every run does the same thing regardless
   of objective. "Understand their security posture" and "find an expansion
   upsell" should trigger genuinely different research, not the same four queries
   with the company name swapped in.
4. **No user context or personalization.** The copilot knows nothing about *who*
   is selling — their product, their ICP, their prior meetings with this account.
   The output is company research, not *relationship-aware* meeting prep, which
   is where the real value is.
5. **Runs are ephemeral and un-shareable.** Reports live in one person's local
   session list. There's no export (PDF/CRM), no team sharing, no way to attach a
   briefing to an opportunity — so the work dies after one meeting instead of
   compounding as an account asset.

*(Runner-up: no cost/rate-limit controls — a burst of runs against a paid LLM +
search API has unbounded spend; and no auth/multi-tenancy.)*

## 2. Top 3 improvements to build next (prioritized)

1. **Grounded, citation-checked reports with per-claim confidence.**
   Attach each material claim to the specific source snippet that supports it,
   add a verification node that flags unsupported statements, and surface a
   confidence badge per section. *Why first:* it directly attacks the trust
   problem (#1, #2). A briefing you can't trust is worse than none — this is the
   difference between a demo and a tool a rep will actually rely on.
2. **Objective-driven, adaptive research plans.**
   Let the planner branch its strategy on the objective and let the user steer
   ("dig deeper on pricing", "add a competitor"). *Why second:* it turns a
   one-size template (#3) into something that feels bespoke, which is the felt
   difference between "a Google search wrapper" and "a copilot."
3. **Personalization + persistence that compounds.**
   Capture the seller's own product/ICP once, remember prior briefings per
   account, and make reports exportable/shareable (PDF + CRM push). *Why third:*
   it's what converts a single-use gadget into sticky, team-level workflow (#4,
   #5) — the foundation for retention and expansion revenue.

---

## Bonus — Business thinking

**Who buys, who uses, why they'd pay.**
The **buyer** is a VP of Sales / RevOps leader who owns rep productivity and win
rates. The **users** are AEs, SDRs, and CS managers prepping for meetings. They'd
pay because meeting prep is high-value but time-expensive (30–60 min of manual
research per meeting); a tool that produces a trustworthy briefing in two minutes
converts directly into more selling time and better-informed conversations —
i.e., pipeline and win-rate impact the buyer is measured on.

**Success metrics.**
- *Activation:* % of new users who complete ≥3 briefings in week one.
- *Core value:* briefings generated per active rep per week; median research
  time saved (self-reported + inferred).
- *Trust:* % of reports rated useful; edit/override rate on claims (lower = more
  trusted); citation-verification pass rate.
- *Business:* seat retention, expansion within accounts, and correlation between
  copilot usage and rep quota attainment.

**Biggest cost / scaling / reliability risks.**
- *Cost:* LLM + search API spend scales linearly with runs and is the dominant
  variable cost; a few heavy users or a retry storm can blow the budget. Mitigate
  with caching (companies are re-researched often), per-tenant quotas, and a
  cheaper model for early nodes.
- *Scaling:* the current single-process background-task model won't scale
  horizontally; needs a durable job queue + shared pub/sub.
- *Reliability:* dependence on third-party search/LLM uptime and rate limits, and
  the correctness risk of hallucinated facts — the reputational risk that most
  threatens adoption.

**One feature to remove:** the free-form follow-up chat *as currently scoped*.
It's the least differentiated part (any LLM chat does this) and invites
ungrounded answers. I'd replace it with **suggested, report-anchored actions**
("draft an outreach email", "generate the discovery-call agenda") that keep the
user in a grounded, high-value loop.

**One feature to add:** a **"meeting-ready" outputs layer** — one click turns a
briefing into a pre-call one-pager, a discovery-question checklist, and a draft
outreach email tailored to the seller's product. This is where research becomes
action, and action is what the buyer pays for.

**If I owned this product, what I'd change first:** make trust the headline
feature. Ship grounded citations + per-claim confidence before anything else,
because every other feature's value is capped by whether reps believe the output.
Trust is the product's moat; polish is not.
