# Publication checklist

The owner approved the exact 23 operational-script removals below. They were executed with `git rm --cached`; only those 23 deletions are staged. Every local file and archived copy remains unchanged and ignored. No additional files were staged, and no commit, push or history rewrite occurred.

## Preserve and reconcile

- Verify byte-for-byte originals and SHA-256 manifest under the ignored local publication archive before accepting rewrites. Public-document originals, both infrastructure READMEs, seven legacy guides and 23 one-off deployment scripts have been archived with hash manifests.
- The seven legacy guides identified in [the audit](DOCS_INDEX.md) are sanitized redirects. Use [demo guide](DEMO_GUIDE.md), [validation](VALIDATION.md) and [engineering results](ENGINEERING_RESULTS.md) as canonical pages.
- Verify canonical links before publication; legacy redirects are compatibility aids.
- `docs/PROJECT_HANDOFF.md` was verified absent from `git ls-files` and ignored by `git check-ignore`; it needs no manual untracking command.
- Retain failed/unknown model responses, failed test runs and original benchmark artifacts. Only report benchmark runs backed by recorded execution and artifacts.
- Confirm public text excludes account, instance, operational resource and operator identifiers, credential locations, approval logs and private screenshot links.
- Describe local kind runtime as verified, Docker Desktop built-in Kubernetes as disabled, EKS as untested, restore as unverified and both deployments as lacking HA. Historical AWS monitoring is not current availability.

## Completed owner-approved tracking removals

The following formerly tracked scripts capture one-off operations and account-specific state. Their local files and byte-archived originals were hash-verified before and after the approved removal. No active tool or public documentation link depends on these paths. These exact commands were executed only after owner approval; they are retained below as the operation record. Do not repeat them.

```powershell
git rm --cached -- "infra/deploy/final-bedrock-attempt1.sh"
git rm --cached -- "infra/deploy/final-bedrock-diagnostics.sh"
git rm --cached -- "infra/deploy/final-disable-and-agent-proof.sh"
git rm --cached -- "infra/deploy/final-eight-action-demo.sh"
git rm --cached -- "infra/deploy/final-independent-agents.sh"
git rm --cached -- "infra/deploy/final-invariants.sh"
git rm --cached -- "infra/deploy/final-investigator-attempt2.sh"
git rm --cached -- "infra/deploy/final-investigator-log.sh"
git rm --cached -- "infra/deploy/final-investigator-release2.sh"
git rm --cached -- "infra/deploy/final-model-preflight.sh"
git rm --cached -- "infra/deploy/final-monitor-start.sh"
git rm --cached -- "infra/deploy/final-quota-release.sh"
git rm --cached -- "infra/deploy/final-regression-chunk-0.sh"
git rm --cached -- "infra/deploy/final-regression-chunk-1.sh"
git rm --cached -- "infra/deploy/final-regression-chunk-2.sh"
git rm --cached -- "infra/deploy/final-regression-chunk-3.sh"
git rm --cached -- "infra/deploy/final-regression-chunk-4.sh"
git rm --cached -- "infra/deploy/final-regression-chunk-5.sh"
git rm --cached -- "infra/deploy/final-regression-chunk-6.sh"
git rm --cached -- "infra/deploy/final-regression-chunk-7.sh"
git rm --cached -- "infra/deploy/final-regression-chunk-8.sh"
git rm --cached -- "infra/deploy/final-regression-chunk-9.sh"
git rm --cached -- "infra/deploy/submit-final-operation.ps1"
```

This list includes every currently tracked `infra/deploy/final*.sh`, its ten regression chunks, and `submit-final-operation.ps1`. No separate tracked `regressionchunk*.sh` paths were present in the inspected inventory. Retain reusable source/templates such as `runtime.env.example`; do not use a blanket directory removal.

The seven legacy Markdown paths are now short sanitized redirects. **Recommendation: keep them tracked** to preserve existing links; their archived originals remain private. They are not part of the proposed removal list. No public source, reusable tooling, benchmark evidence or diagram is proposed for removal.

`git rm --cached` stages removal from the index while retaining working-tree files; it is not a private archive. **Adding an ignore rule does not untrack existing files.** The operational-script ignore rules are already present. Explicit Kubernetes credential rules and narrow exceptions for two sanitized, manifest-referenced logs are also present. Review the resulting staged diff before any owner commit.

## History and credentials

Untracking or sanitizing a file does not remove prior commits, clones or cached copies. **History has not been rewritten.** The owner should inspect current content and reachable history for exposed secrets and revoke or rotate any credential that may have been disclosed. Identifiers alone are not credentials; a clean scoped text scan is not a comprehensive security certification.

No AWS calls, paid inference, application tests, deployment or action replay are needed for this document review. Record actual offline checks separately from historical runtime evidence. Publication requires final link/content checks and owner review.

## Individual operational-file review

All 23 working copies matched their byte-archived originals and manifest hashes. Classification below records the complete approved removal scope; all 23 removals are now staged and no other files were staged.

| File under `infra/deploy/` | Reason to remove from tracking |
|---|---|
| `final-bedrock-attempt1.sh` | Fixed live-inference fixture/checkpoint identities; enables paid gates and restarts API |
| `final-bedrock-diagnostics.sh` | Reads one historical report and budget date |
| `final-disable-and-agent-proof.sh` | One-run settings/process proof and historical checkpoint paths |
| `final-eight-action-demo.sh` | Historical target/version/quota assumptions and fixed run identity |
| `final-independent-agents.sh` | Fixed resources, checkpoint names and output paths |
| `final-invariants.sh` | Queries one historical run/resource/incident set |
| `final-investigator-attempt2.sh` | Paid call with fixed incident, budget counters and output identity |
| `final-investigator-log.sh` | One-run diagnostic log filter |
| `final-investigator-release2.sh` | Personal registry/account and fixed release digest; changes deployment |
| `final-model-preflight.sh` | Personal registry and historical fixtures; inspects runtime credentials |
| `final-monitor-start.sh` | Assumes a host-specific monitoring override and runtime secret mount |
| `final-quota-release.sh` | Historical target/version/allocation and state-changing gateway operation |
| `final-regression-chunk-0.sh` | Encoded historical source-transfer fragment 0 |
| `final-regression-chunk-1.sh` | Encoded historical source-transfer fragment 1 |
| `final-regression-chunk-2.sh` | Encoded historical source-transfer fragment 2 |
| `final-regression-chunk-3.sh` | Encoded historical source-transfer fragment 3 |
| `final-regression-chunk-4.sh` | Encoded historical source-transfer fragment 4 |
| `final-regression-chunk-5.sh` | Encoded historical source-transfer fragment 5 |
| `final-regression-chunk-6.sh` | Encoded historical source-transfer fragment 6 |
| `final-regression-chunk-7.sh` | Encoded historical source-transfer fragment 7 |
| `final-regression-chunk-8.sh` | Encoded historical source-transfer fragment 8 |
| `final-regression-chunk-9.sh` | Encoded historical source-transfer fragment 9 |
| `submit-final-operation.ps1` | Fixed instance/profile SSM command submitter |

The ten fragments were decoded in memory: their source bundle contains 61 members under application, tests, migrations, observability and project configuration. No sensitive path names or access-key/private-key signatures were found. Source already exists as ordinary repository files; these transport fragments are not a reproduction interface.

Keep `infra/deploy/runtime.env.example`, parameterized tools under `scripts/`, all application/infrastructure source and curated benchmark evidence. The reusable tools remain approval-gated; a tool's presence does not authorize deployment or paid inference.

## Reviewed commit and push sequence

1. Completed: the owner approved exactly the 23 script removals above. Local/archive hashes and ignore coverage were verified before and after `git rm --cached`; inspect the 23 staged deletions before proceeding.
2. Review the explicit source/chart/document/evidence additions in `git status`; confirm the SVG, new Kubernetes evidence, both sanitized logs and resume/runtime guides are included. Avoid blanket staging of private working files.
3. Inspect `git diff --cached --stat` and `git diff --cached`, rerun current-file secret/link/hash/whitespace checks on the exact candidate tree, then approve the commit. Suggested title: `Finalize Kubernetes acceptance and public release evidence`.
4. Review the configured remote and destination branch, commit contents and any historical exposure. Push only after separate owner approval. No force-push or history rewriting is proposed.

Current-file scanning does not certify prior history. This repository has no project license file; no open-source licensing permission is asserted or invented. Remote GitHub rendering and CI execution remain publication-time checks.
