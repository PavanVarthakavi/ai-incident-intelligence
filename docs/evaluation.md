# Evaluation (Milestone 5)

The evaluation measures how well the investigation agent diagnoses incidents whose root
cause is known. It replays 24 frozen incidents through the same prompt and Claude client the
API uses and grades each diagnosis with exact checks. The baseline report is in
[`backend/eval/results/report.md`](../backend/eval/results/report.md).

## Cases

Each case is an incident report plus the evidence snapshot the backend collected while a
scenario ran on the demo stack, together with the expected answer. Cases are captured once
and frozen as JSON in `backend/eval/cases/`, so every run sees identical input and needs no
running stack. [`backend/eval/cases/CASES.md`](../backend/eval/cases/CASES.md) lists every
case with its report, expected answer, and evidence.

| Group | Cases | What it tests |
|---|---|---|
| `deploy-caused` | F01-F09 | A bad release causes errors or latency; find the service and name the release. Includes cascades, the entry-point service, and two subtle cases (about 7% errors; a mild slowdown with no slow traces). |
| `silent` | F10-F13 | A fault with no deploy; find the service without blaming a release. |
| `decoy-deploy` | F14-F16 | An unrelated deploy is visible (in F14 the report blames it); F16 has two deploys and one is at fault. |
| `missing-source` | F17-F18 | F01 without logs and F10 without traces, as if that backend had failed. |
| `healthy` | H01-H06 | No fault; the diagnosis must not name a root cause. Includes a recent good deploy, a rollback, a vague report, a report of an outage the data contradicts, and a one-service scope. |

Scenarios are defined in `backend/eval/scenarios.py`. `python -m eval.capture` resets the
stack to baseline releases, waits for earlier scenarios to age out of the metric windows,
records 90 seconds of healthy traffic, applies the scenario's faults or deploys, records 150
seconds of symptoms, and collects evidence with the backend's own collectors. Deploy events
from other scenarios are filtered out. Derived cases are built from captured ones by removing
a source and recording a source error. Capture is free (no model calls) and takes about two
hours for all scenarios.

The host must stay awake during capture: a sleeping laptop pauses the containers and
produces impossible telemetry (traces lasting minutes behind 2-3 second timeouts). Capture
fails if a window runs more than 30 seconds past its plan; run it under `caffeinate -dims`
on macOS.

## Grading

Exact checks only; no model grades another model.

| Metric | Applies to | Passes when |
|---|---|---|
| `correct` | all | Faulty case: root cause names the expected service. Healthy case: root cause is null. |
| `recall` | faulty | `correct` on faulty cases: the expected service was found. |
| `specificity` | healthy | Root cause is null. |
| `release` | deploy-caused | Root-cause statement names the bad release (exact version match). |
| `citations` | all | The backend's citation check passes (every claim cites IDs in the snapshot). |

Scores are reported with 95% Wilson intervals, overall and per group. Two free checks keep the
grader honest: `--check oracle` grades the known answers (must score 100%) and `--check null`
grades an "always healthy" answer (scores 25% correct, the healthy share, and 0% recall).

Citations are checked for validity, not completeness: the grader does not check that the
root cause cites every relevant evidence item.

## Running

From `backend/` with the virtualenv active:

```bash
python -m eval.run --check oracle                  # free
python -m eval.run --check null                    # free
python -m eval.run --variant baseline --max-usd 2  # paid, about $1.25 for 24 cases
python -m eval.report                              # writes eval/results/report.md
python -m eval.overview                            # writes eval/cases/CASES.md
```

Safeguards in the runner:

- Paid runs refuse to start until the current runner, grader, prompt, client, validator, and
  case files are approved with `--approve-harness` (a hash, stored locally and not committed).
- A spend cap: each call reserves its worst-case cost; a call that does not fit waits for
  in-flight calls to settle and is skipped only if it cannot fit alone.
- Results are written per case as they finish; rerunning a variant resumes. A variant name
  cannot be reused with a different model, effort, prompt, or harness.
- API errors, timeouts (300 seconds per case), and replies from a different model than
  requested go to `errors.jsonl`, not into the scores.
- Each call's full prompt and reply are kept in `traces/`.

Variants are `baseline` or `v<N>`; `--model` and `--effort` override the settings.

## Baseline results

Claude Opus 5.5, medium effort, prompt version 1, one run per case (October 2026):

| Metric | Score (95% interval) |
|---|---|
| Correct | 24/24 (86%-100%) |
| Recall | 18/18 (82%-100%) |
| Specificity | 6/6 (61%-100%) |
| Release named | 11/11 (74%-100%) |
| Citations valid | 23/24 (80%-99%) |

Cost $1.22 in total, $0.051 per case; median latency 17 seconds, maximum 33.

Findings:

- **F17 fails the citation check.** With logs unavailable, the diagnosis recommends re-running
  the log query once the backend recovers and cites nothing, because a missing source is a
  source error, not evidence. The diagnosis is correct, but the API would store it as
  `invalid`. Fixed in prompt version 3; see Variants.
- **The model did not follow misleading reports or decoy deploys.** In F14 it stated that the
  gateway release preceded the errors but that nothing linked it to them; in H05 it reported
  that the data contradicts a reported outage.
- **Confidence tracks difficulty.** `high` on four deploy-caused cases (F01, F03, F05, F09),
  `low` only on F08 (mild slowdown, no slow traces), and `medium` on the other faulty cases.

## Variants

The F17 finding led to one change in two steps, each measured on the cases it targets plus a
regression sample. Both runs used the baseline model and effort.

| Variant | Prompt | Change | Runs | Correct | Citations valid | Cost |
|---|---|---|---|---|---|---|
| `v1` | 2 | A source that failed to collect is citable as `src-<source>` | F17 x3, F18 x3, F01, F14, H05 | 9/9 | 8/9 | $0.53 |
| `v2` | 3 | A source that was queried and returned nothing is citable too | H05 x3, F17, F18 | 5/5 | 5/5 | $0.25 |

- **v1** fixed the target: all six F17 and F18 runs cited the failed source in their re-run
  actions and passed. It exposed the same gap in another form: H05 recommended pulling
  deployment records the snapshot lacked, but deployments had not failed, they had returned
  nothing, so there was nothing to cite.
- **v2** made those sources citable as well. All five runs passed, citing for example
  `src-deployments` when ruling out a deploy ("no deployment records were found in the
  window") and the empty trace and log sources for an action to re-run them.
- Not measured: prompt version 3 on the other 19 cases. The change adds one instruction and an
  `<empty_sources>` list, so regressions are unlikely but not ruled out; a full run costs about
  $1.25.

## Known limitations

- **Little headroom.** The baseline scores at or near the ceiling, so this set detects
  regressions (prompt, model, or effort changes) better than it ranks improvements. Harder
  cases are needed to compare stronger configurations.
- **Small samples.** 24 cases and one run each; per-group intervals are wide, and run-to-run
  variance is not measured (`--reps` supports it).
- **One synthetic system.** All cases come from the three-service demo stack and its fault
  types; results say little about larger or real systems.
- **Exact checks only.** Explanation quality, calibration of confidence, and the usefulness of
  recommended actions are not scored. Naming a decoy release is not penalized when the
  expected release is none (F15 mentions the decoy deploy as a possible, unproven factor).
- **Frozen evidence.** Cases record what the collectors produced at capture time. After a
  collector change, recapture so cases match what the API would collect.
