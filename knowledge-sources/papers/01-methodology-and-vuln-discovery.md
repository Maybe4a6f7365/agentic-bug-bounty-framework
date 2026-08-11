---
source_type: papers
last_updated: 2026-07-22
reliability: medium   # landmark security whitepapers web-verified; academic cites from knowledge, verify DOIs before formal use
---

# Papers & Whitepapers on Bug-Finding Methodology

Two tiers: **(A) Industry whitepapers** that define web attack classes (web-verified in this
session), and **(B) Academic papers** on automated vulnerability discovery (cited from training
knowledge — **verify exact venue/year/DOI before citing formally**).

## A. Landmark industry whitepapers (verified)
| Title | Author | Where | Key finding / lesson |
|-------|--------|-------|----------------------|
| **HTTP Desync Attacks: Request Smuggling Reborn** | James Kettle | PortSwigger / Black Hat 2019 | CL/TE disagreement between front-end & back-end re-enables mass request smuggling → detect via behavioral discrepancy |
| **A New Era of SSRF** | Orange Tsai | Black Hat USA 2017 | URL-parser inconsistencies across libraries defeat SSRF allow/deny filters |
| **Confusion Attacks (Apache HTTP Server)** | Orange Tsai | 2024 (Top-10 #1) | Semantic ambiguity between modules crosses handler/trust boundaries |
| **Practical Web Cache Poisoning** / **Web Cache Entanglement** | James Kettle | PortSwigger 2018/2020 | Unkeyed inputs let attackers poison shared cached responses |
| **Web Cache Deception Attack** | Omer Gil | Black Hat 2017 | Path-based cache rules can cache authenticated pages for anyone |
| **Server-Side Template Injection** | James Kettle | Black Hat 2015 | Template syntax reaching a render engine → engine-specific RCE |

## B. Academic vulnerability-discovery papers (from knowledge — verify before formal cite)
| Title | Author(s) | Venue (approx.) | Key finding / lesson for an agent |
|-------|-----------|-----------------|-----------------------------------|
| **AFL (American Fuzzy Lop)** — technical whitepaper/docs | Michał Zalewski | 2013+ | Coverage-guided genetic fuzzing: evolve inputs by measured edge coverage — the dominant fuzzing paradigm |
| **Driller: Augmenting Fuzzing Through Selective Symbolic Execution** | Stephens, Grosen, Salls et al. | NDSS 2016 | Combine fuzzing (breadth) with concolic execution (to pass hard checks) — hybrid beats either alone |
| **Evaluating Fuzz Testing** | Klees, Ruef, Cooper, Wei, Hicks | CCS 2018 | Fuzzing evaluations are often statistically unsound — demands many trials, real bug metrics, fixed budgets. *Lesson: measure the agent's finders rigorously.* |
| **KLEE: Unassisted and Automatic Generation of High-Coverage Tests** | Cadar, Dunbar, Engler | OSDI 2008 | Symbolic execution can auto-generate high-coverage tests / find deep bugs — basis for path exploration |
| **SoK: (Statically) Detecting Web Application Vulnerabilities / Taint analysis** | various | S&P/USENIX SoKs | Taint tracking source→sink is the theoretical backbone of injection detection (XSS/SQLi/SSRF) |
| **Static Exploration of Taint-Style Vulnerabilities Found by Fuzzing** | (arXiv 1706.00206) | arXiv 2017 | Combine fuzzer diagnostics + static analysis to generalize a found bug into a vuln template. *Lesson: after one finding, auto-derive a signature.* |

## Cross-cutting lessons for the agent
1. **Coverage-guided + symbolic hybrid** (Driller/KLEE) is the reference architecture for getting past
   input-validation gates — analogous to the agent combining broad payload probing with targeted
   reasoning about which check blocks it.
2. **Taint source→sink** (SoK/taint papers) is the formal model behind every injection skill; encode
   each CWE skill as "identify sources, identify dangerous sinks, prove reachability".
3. **Rigorous evaluation** (Klees et al.) — track true/false positives per skill over fixed budgets,
   with repeated trials, to avoid overfitting the agent to a few CTF-style bugs.

## Source assessment
- **Value for skill training:** High for the whitepapers (directly operationalizable); the academic
  papers inform *architecture and evaluation* more than individual payloads.
- **Skill classes that benefit:** injection family (taint), fuzzing-adjacent inputs, agent evaluation.
- **Accessibility:** Whitepapers free (PortSwigger/DEF CON/blogs); academic papers mostly free via
  arXiv / author pages, some behind ACM/IEEE paywalls.
- **Next step to integrate:** Use taint source→sink as the skeleton for injection skills; adopt the
  Klees evaluation discipline for the agent's per-skill benchmark harness. **Verify each academic
  citation's exact venue/year before publishing or training on it.**
