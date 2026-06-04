# kyberESR — Automated Course Research Pipeline

## Project purpose

Automated pipeline to survey Finnish university study guides and assess which courses are relevant to a given research topic (initially: cybersecurity / ESR context). Produces a structured report with human-in-the-loop validation at two checkpoints.

## Pipeline overview

```
1. Crawl      → Filter courses from study guides by faculty / course level
                 (general | basic | intermediate | advanced)
                 → store raw course data in local SQLite DB

2. Screen     → Send each course description to LLM
                 → LLM answers a fixed question set to decide include/exclude
                 → produces: included course list + rationale per course

3. Evaluate   → For included courses, LLM answers a deeper question set
                 → produces: per-course structured evaluations

4. Report     → Generate final report from evaluations

5. HITL-A     → Human reviews the included/excluded course list
                 Two root causes for errors:
                   a) Silent knowledge — course guide lacked info → noted in report,
                      add human-curated answer + % stat on insufficient guides
                   b) LLM failure     → refine prompts → redo from step 2

6. HITL-B     → Human reviews the per-course evaluations
                 Same two root causes and remedies as HITL-A
```

## Key data flows

- **Input:** university study guide URLs + filter config (faculty, level, topic)
- **Storage:** local SQLite — raw course records, LLM answers, include/exclude decisions
- **LLM calls:** screening question set (step 2), evaluation question set (step 3)
- **Output:** structured report + statistics on guide quality

## Error taxonomy (critical for prompt design)

| Root cause | Signal | Remedy |
|---|---|---|
| Insufficient study guide | Correct answer not derivable from text | Note in report; human supplies answer; track % |
| LLM misunderstanding | Answer derivable but wrong | Refine prompt; rerun affected step |

## Development conventions

- Python project; keep dependencies minimal and explicit in `requirements.txt`
- SQLite for all local persistence — no external DB required
- LLM calls go through a single thin wrapper so the model/provider can be swapped
- Prompts live in dedicated files (not buried in code) so they can be iterated without touching logic
- Crawlers must be polite: respect `robots.txt`, add delays, do not hammer servers
- All pipeline steps are idempotent — rerunning a step should be safe
- DRY — no duplicated logic; shared utilities go in a common module, not copied across files
- File size limit: every file must be small enough for Claude to read in one shot (~500 lines is a practical ceiling); split earlier if a file is growing large

## Git workflow

- **Feature branches** for every non-trivial change — never commit directly to `main`
- **Small, focused commits** — each commit should represent one understandable unit of work
- All tests must pass before merging a branch

## Testing

- **Test-driven development:** write the test first, then implement until it passes
- Tests live alongside the code they cover (e.g. `tests/test_crawler.py` for `crawler.py`)
- Run the full test suite after every non-trivial change; no merge with failing tests
- Tests should be fast and not require network access — mock external calls (HTTP, LLM API)

## User interfaces

**Curses UI** — operator-facing terminal interface for running and monitoring the pipeline. Used by the person driving the process locally.

**Web UI** — localhost web server for presenting results to an audience over a shared WiFi network. Audience members connect via the local network address in their own browser. Designed for collaborative HITL annotation sessions:
- Display course list and per-course evaluations
- Allow multiple audience members to annotate and correct AI decisions in real time
- Annotations feed back into the report (see HITL-A / HITL-B steps)

The two UIs are independent: the curses UI controls pipeline execution; the web UI is read/write for results and annotations only.

## What "done" looks like for each step

1. **Crawl:** DB contains course rows with title, description, faculty, level, source URL
2. **Screen:** Every crawled course has an include/exclude decision + per-question LLM answers stored
3. **Evaluate:** Every included course has structured evaluation answers stored
4. **Report:** Human-readable report generated from DB state; includes % of guides flagged as insufficient
5. **HITL loops:** CLI or simple UI lets human mark errors and choose root cause; triggers re-run or annotation accordingly
