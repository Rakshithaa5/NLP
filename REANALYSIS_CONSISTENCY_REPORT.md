# Re-analysis consistency verification

The completed pipeline passed five fresh Groq analyses of the same navigation meeting fixture. Every run used the same input, prompt, schema, model and configuration. These were force=true API calls through candidate generation, reconciliation and persistence, not cache hits.

**Root cause and reproduction.** Before the change, two real calls returned 2 actions and then 1 for the existing fixture even with temperature 0 and a content-derived seed. The analysis endpoint replaced its saved report with whichever output arrived next. The prompt permitted false positives and left some task boundaries subjective; long meetings also used a generative synthesis pass that could omit candidates. Validation retained unmatched evidence, and malformed JSON could recover only early fields. There was no versioned cache or evidence-based reconciliation. The exact reported 10-to-3 production incident was not available as a recorded before/after pair, so its precise loss stages cannot be established retrospectively.

**LLM configuration.** Groq openai/gpt-oss-120b; temperature=0; top_p=1; content-hash seed; reasoning_effort=low; strict json_schema; max_completion_tokens=8192; no fallback model. The final effective input byte budget was 13356. The provider seed is best-effort, not a guarantee: https://console.groq.com/docs/api-reference . Request hashes, configuration, usage, finish reasons and backend fingerprints are logged without API keys or transcript text.

Analysis version: meeting-intelligence-v3. Prompt version: exhaustive-evidence-v1. Prompt/schema/configuration hashes also invalidate the cache when their contents change.

Input hash: `1615c5fecfbb465c9c2d0fe3b8c733743864902fb0f559bd67ca32a9417cd225`.

**Five-run consistency results (fresh candidates and persisted reports had identical core counts).**

| Category | R1 | R2 | R3 | R4 | R5 |
|---|---:|---:|---:|---:|---:|
| Actions | 2 | 2 | 2 | 2 | 2 |
| Decisions | 1 | 1 | 1 | 1 | 1 |
| Questions | 1 | 1 | 1 | 1 | 1 |
| Follow-ups | 0 | 0 | 0 | 0 | 0 |

**Pipeline loss, final runs 1 and 2.** Each cell lists actions / decisions / questions / follow-ups. Generated counts are the decoded provider arrays before local validation. A malformed or truncated provider response is rejected rather than counted as successful extraction.

| Stage | Run 1 | Run 2 |
|---|---|---|
| generated | 2 / 1 / 1 / 0 | 2 / 1 / 1 / 0 |
| parsed | 2 / 1 / 1 / 0 | 2 / 1 / 1 / 0 |
| validated | 2 / 1 / 1 / 0 | 2 / 1 / 1 / 0 |
| evidence_matched | 2 / 1 / 1 / 0 | 2 / 1 / 1 / 0 |
| deduplicated | 2 / 1 / 1 / 0 | 2 / 1 / 1 / 0 |
| persisted | 2 / 1 / 1 / 0 | 2 / 1 / 1 / 0 |

**Stable item overlap.** Minimum Jaccard overlap versus run 1 was 100% for actions, decisions and questions in both fresh candidates and persisted reports. The same source identities were actions at segments 3 and 6, a decision at segment 2, and a question at segment 5 (existing zero-based segment convention). This fixture contains no separate follow-up, so its empty-set overlap is not evidence of follow-up extraction accuracy; a dedicated offline regression verifies follow-up retention. Broad topic labels still varied and are not accumulated during reconciliation. Summary wording remains generative; the supported existing key takeaway is retained for an unchanged pipeline.

**Re-analysis behavior.** Ordinary POST retries reuse a complete saved result only when input, analysis version, prompt version and configuration match. The Dashboard Re-analyze action sends force=true. Canonical whitespace-normalized text, source ordering, IDs, timestamps and language determine the persisted input hash. Chunk boundaries and hashes are deterministic; every chunk is processed and merged locally without a second generative merge. Output length limits, refusals and incomplete JSON fail the attempt, preserving the last saved report.

Fresh results are saved as analysis_candidate.json before reconciliation. Previous output is preserved in analysis_previous.json; canonical input is stored in analysis_input.json. Stable IDs combine meeting, category and source IDs, with semantic disambiguation for multiple items sharing evidence. Matching also checks normalized semantics and conflicting assignments. Existing valid items omitted by a same-pipeline candidate are retained; unmatched evidence is removed. Legacy reports pass through current evidence validation. A changed pipeline does not automatically retain unmatched old AI items. OS file locks prevent concurrent writers on the same storage volume.

**User edit protection.** Each insight records ai_fields separately from user_edits. Explicit overrides and differences from the saved AI baseline win, including task text, owner, deadline, status and confirmation. Resolved questions with valid answer evidence do not regress merely because a new run omits the answer. Edited items that cannot be matched after source/pipeline changes are preserved in manual_review_items rather than discarded. Existing legacy edit markers and non-default task statuses are migrated. The existing application has no task-editing endpoint; unmarked historical edits cannot be reliably distinguished from old AI values.

**Validation.** 47 backend semantic/reconciliation tests passed, 6 frontend data tests passed, frontend production build passed, and git diff --check passed. Regression coverage includes deliberate omissions and paraphrases across five simulated runs, edited values, invalid evidence, multiple tasks/assignees sharing evidence, legacy migration, cache versus force semantics, snapshots, concurrency, follow-ups, malformed/truncated responses and deterministic long-input merging. The real five-call acceptance fixture is short and English; this is not a claim of universal model determinism or exhaustive long/multilingual live coverage. Matching is deterministic lexical/evidence matching, not an independent semantic-entailment verifier.

**Files changed.**

| File | Reason |
|---|---|
| backend/services/semantic.py | Exhaustive category definitions, canonical input, request diagnostics, strict incomplete-response rejection, deterministic chunk merge. |
| backend/services/intelligence.py | Follow-up schema, reject unsupported evidence, repeated-source disambiguation, stage counts and removal diagnostics, normalized matching. |
| backend/services/consistency.py | Version/config/input manifests, stable IDs, deterministic merge, reconciliation, legacy migration and user-edit baselines. |
| backend/services/meeting_store.py | Cross-worker analysis lock with automatic OS release. |
| backend/routes/analysis.py | Cache/force semantics, input/candidate/previous snapshots and reconciliation before save. |
| backend/routes/report.py | Include extracted follow-ups in PDF output. |
| frontend/src/services/api.js | Explicit force option for analysis calls. |
| frontend/src/pages/Dashboard.jsx | Re-analyze explicitly requests a fresh candidate. |
| frontend/src/components/meeting/Overview.jsx | Show follow-ups in the existing questions/follow-ups panel. |
| backend/scripts/test_semantic.py | Update tests for intentional cache and deterministic-merge behavior. |
| backend/scripts/test_consistency.py | Reconciliation, edit, source identity, follow-up, migration and lock regressions. |
| backend/scripts/validate_consistency_live.py | Five real calls, isolated storage, paced requests, persisted stage counts and raw/reconciled overlaps. |

Actual artifacts: [results.json](data/validation/consistency/results.json), run-1.json through run-5.json, candidate-1.json through candidate-5.json, and pipeline.log in the same directory. No expected item counts are enforced by the production code.

Reproduce the live test: `nlp\Scripts\python.exe -B -m backend.scripts.validate_consistency_live` (uses configured Groq credentials; makes five real calls).
