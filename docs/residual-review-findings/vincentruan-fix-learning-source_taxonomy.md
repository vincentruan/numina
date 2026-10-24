# Residual Review Findings

Source: `ce-code-review` run `20261021-211146-b8853b70` on branch
`vincentruan/fix-learning-source_taxonomy` at head `32fd138a`.

Reviewed plan: `docs/plans/2026-10-21-001-fix-learning-source-taxonomy-fallback-plan.md`
(implementation-ready). Reviewers: correctness, testing, data-migration.
Verdict: Ready to merge.

Applied in this branch (commit `32fd138a`):

- P2 — cluster index migration was not idempotent (`align_schema` creates the
  index before `alembic upgrade head` runs, so `op.create_index` would raise and
  pin `alembic_version`). Guarded with a `_has_index` check.
- P2 — no test covered session creation when the fallback triggers. Added
  `test_create_session_accepts_os_taxonomy_topic_under_fallback`.

## Open residuals

- **P2** `server/apps/backend/app/routers/learning.py:178` — `get_topic_graph`
  does not validate the topic's taxonomy, returning an empty graph instead of a
  404 for cross-taxonomy topics. Pre-existing. Filed: [#147](https://github.com/vincentruan/numina/issues/147)

- **P3** `server/apps/backend/app/services/learning/session_service.py:145` —
  redundant `child` re-query in `create_session` (already fetched at line 104).
  Pre-existing. Filed: [#148](https://github.com/vincentruan/numina/issues/148)

- **P3** `server/apps/backend/app/services/learning/topic_service.py:45` —
  the effective-taxonomy probe runs per request with no cache. Deliberately not
  applied: plan KTD3 rejects caching. Recorded for visibility.
  Filed: [#149](https://github.com/vincentruan/numina/issues/149)

## Residual risks carried forward

- **Taxonomy switch on seed.** Once beijing data is seeded, zh-CN clients
  transparently flip from `os-taxonomy` to `beijing`. Any client-side cached
  os-taxonomy topic IDs will 404 under the cross-source guard at
  `session_service.py:105`. Frontend cache invalidation should be verified at
  seed time.

- **Supabase standby DDL.** Replication does not carry DDL. The new
  `ix_learning_clusters_source_taxonomy` index must be created on the standby
  separately, via the host-python psycopg3 path.

- **No CI coverage for migrations.** `conftest.py` uses `create_all`, so no test
  runs alembic. The idempotency bug above was invisible to the suite and was
  caught only by review; it was verified ad hoc by simulating
  `align_schema`-then-alembic on SQLite.

## Testing gaps

- API-level fallback coverage exists only for the child router. The family and
  public routers share the helper but have no equivalent fallback test, so a
  router-specific wiring mistake would not be caught.
- Migration idempotency has no automated test.
