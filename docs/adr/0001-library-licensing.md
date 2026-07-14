# ADR 0001 — Library corpus licensing

**Status:** Accepted  
**Date:** 2026-07-08

## Context

The `library` Qdrant collection stores instructional chess writing that the
tutor can cite to students. The corpus must be:
1. Legally distributable in the repo and freely indexable.
2. High-quality instructional content, not engine output.
3. Readily available in machine-readable form.

Lichess articles were considered. They are not under a public license — the
site's Terms of Service prohibit bulk reproduction.

## Decision

Use **Project Gutenberg public-domain texts only** for the POC corpus:

- José Raúl Capablanca, *Chess Fundamentals* (1921) — PD
- Emanuel Lasker, *Common Sense in Chess* (1896) — PD
- Optional third classic if chunk count feels thin (Nimzowitsch *My System*
  partial, or similar PD title available on Gutenberg)

Wikibooks chess articles (CC BY-SA) are acceptable as a secondary source with
attribution stored in the payload field `license`.

## Consequences

- Lichess articles are excluded.
- The `library` payload always stores `book`, `author`, `license`, `source_url`
  so attribution can be surfaced to the student.
- The corpus is static for the POC; expanding to CC-licensed sources is a
  post-POC step.
