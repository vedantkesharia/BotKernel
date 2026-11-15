# Publication checklist

This is an owner review checklist, not an executed cleanup. No Git index, staging, commit, push or history-rewrite operation was performed by this documentation task.

## Preserve and reconcile

- Verify byte-for-byte originals and SHA-256 manifest under the ignored local publication archive before accepting rewrites. Public-document originals, both infrastructure READMEs, seven legacy guides and 23 one-off deployment scripts have been archived with hash manifests.
- The seven legacy guides identified in [the audit](DOCS_INDEX.md) are sanitized redirects. Use [demo guide](DEMO_GUIDE.md), [validation](VALIDATION.md) and [engineering results](ENGINEERING_RESULTS.md) as canonical pages.
- Verify canonical links before publication; legacy redirects are compatibility aids.
- `docs/PROJECT_HANDOFF.md` was verified absent from `git ls-files` and ignored by `git check-ignore`; it needs no manual untracking command.
- Retain failed/unknown model responses, failed test runs and original benchmark artifacts. Only report benchmark runs backed by recorded execution and artifacts.
- Confirm public text excludes account, instance, operational resource and operator identifiers, credential locations, approval logs and private screenshot links.
- Verify Kubernetes is described as disabled/runtime unaccepted, restore as unverified and single-host deployment as lacking HA. Historical stopped AWS monitoring is not live availability.

## Exact manual index-removal candidates

The following tracked deployment scripts capture one-off operations and account-specific state. Review each against the current index before acting; another owner may change HEAD. The local originals are archived; verify their hashes before any index removal. These are **manual candidate commands only**, shown individually for explicit review; none were executed here.

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

The seven legacy Markdown originals also require an owner disposition. Their originals are archived and the public paths now contain short sanitized redirects; no index changes were made. Keep those redirects tracked if compatibility is desired. If the owner instead elects to remove a legacy path from the public index after verifying its private archive and canonical replacement, these are the exact optional candidates:

```powershell
git rm --cached -- "docs/AWS_DEMO_READY.md"
git rm --cached -- "docs/DEMO_RECORDING_GUIDE.md"
git rm --cached -- "docs/IMPLEMENTATION_WALKTHROUGH.md"
git rm --cached -- "docs/DESIGN_DECISIONS.md"
git rm --cached -- "docs/PHASE2_DESIGN.md"
git rm --cached -- "docs/PORTFOLIO.md"
git rm --cached -- "docs/DEMO_WALKTHROUGH.md"
```

`git rm --cached` stages removal from the index while retaining working-tree files; it is not a private archive. **Adding an ignore rule does not untrack existing files.** Add appropriate ignore rules during owner-approved cleanup if private retained files should stay untracked. Review the resulting staged diff before any owner commit.

## History and credentials

Untracking or sanitizing a file does not remove prior commits, clones or cached copies. **History has not been rewritten.** The owner should inspect current content and reachable history for exposed secrets and revoke or rotate any credential that may have been disclosed. Identifiers alone are not credentials; a clean scoped text scan is not a comprehensive security certification.

No AWS calls, paid inference, application tests, deployment or action replay are needed for this document review. Record actual offline checks separately from historical runtime evidence. Publication requires final link/content checks and owner review.
