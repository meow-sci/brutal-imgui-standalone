# Events and event payloads

## Contents
- [How act chooses what to run](#how-act-chooses-what-to-run)
- [Default event payload](#default-event-payload)
- [How github.ref / sha / repository are derived](#how-githubref--sha--repository-are-derived)
- [Payload recipes per event](#payload-recipes-per-event)
- [Skipping jobs or steps under act](#skipping-jobs-or-steps-under-act)

## How act chooses what to run

1. Load every `.yml`/`.yaml` under `-W` (default `./.github/workflows/`, recursive unless `--no-recurse`).
2. Pick the event (positional arg → single common event → `--detect-event` → `push`).
3. Plan: every workflow whose `on:` **lists the event name** contributes all its jobs, staged by `needs`.
   - `on: push`, `on: [push, pull_request]`, and `on: {push: {...}}` are all understood.
   - **Ignored filters:** `branches`, `branches-ignore`, `tags`, `tags-ignore`, `paths`, `paths-ignore`, `types`, and `schedule.cron`. A `pull_request` with `types: [closed]` still runs on `act pull_request`.
   - Job `if:` conditions **are** evaluated at runtime, so `if: github.event_name == 'push'` or `if: github.ref == 'refs/heads/main'` behave as expected given the simulated context.
4. `-j <job>` replaces step 3: that job id plus its transitive `needs` from every loaded workflow, regardless of event.

Any event name from GitHub's [events list](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows) can be used (`issues`, `issue_comment`, `release`, `create`, `delete`, `deployment`, `repository_dispatch`, `workflow_run`, `merge_group`, …). act doesn't synthesize their payloads, so supply one with `-e` if the workflow reads `github.event.*`.

## Default event payload

- With `-e file.json`: the file's JSON becomes `github.event` and is written to `$GITHUB_EVENT_PATH` (`/var/run/act/workflow/event.json` in containers).
- Without `-e` but with `--input`/`--input-file`: payload is `{"inputs": {...}}`.
- Otherwise: `{}`. act adds `repository.default_branch` (from `--defaultbranch`, else `master`) when it has to derive the ref.

`-e` and `--input` don't merge: when `-e` is given, put the inputs inside the JSON's `"inputs"` object.

## How github.ref / sha / repository are derived

| Event | `github.ref` | `github.sha` |
|---|---|---|
| `push`, `create`, `workflow_dispatch` | `event.ref` if present | `event.after` if `event.deleted == false` |
| `pull_request`, `pull_request_review`, `pull_request_review_comment` | `refs/pull/<event.number>/merge` | local HEAD |
| `pull_request_target` | `refs/heads/<event.pull_request.base.ref>` | `event.pull_request.base.sha` |
| `release` | `refs/tags/<event.release.tag_name>` | local HEAD |
| `deployment`, `deployment_status` | `event.deployment.ref` | `event.deployment.sha` |
| anything else | `refs/heads/<event.repository.default_branch>` if present | local HEAD |
| fallback when still empty | current local git ref (branch or tag at HEAD), else `refs/heads/<default branch>` | local `git rev-parse HEAD` |

- `github.ref_name` / `ref_type` are derived from the ref (`refs/heads/x` → branch `x`, `refs/tags/v1` → tag `v1`).
- `github.base_ref` / `head_ref` (PR events) come from `event.pull_request.base.ref` / `head.ref`.
- `github.repository` comes from the URL of git remote `origin` (`--remote-name` to change). It falls back to `nektos/act` if there's no git remote. Override with `--env GITHUB_REPOSITORY=owner/repo`.
- `github.actor` = `--actor` (default `nektos/act`). `run_id` / `run_number` / `run_attempt` default to `1`.
- In a repo with no commits you'll see `unable to get git ref/revision: reference not found` warnings. They're harmless, but commit something if the workflow needs a sha.

## Payload recipes per event

Copy-ready files live in [../assets/events/](../assets/events/).

### push to a branch (with before/after shas)
```json
{
  "ref": "refs/heads/main",
  "before": "0000000000000000000000000000000000000000",
  "after": "REPLACE_WITH_SHA",
  "deleted": false,
  "repository": { "default_branch": "main", "full_name": "owner/repo", "name": "repo", "owner": { "login": "owner" } },
  "head_commit": { "id": "REPLACE_WITH_SHA", "message": "test commit" }
}
```
`act push -e push.json`

### push of a tag
```json
{ "ref": "refs/tags/v1.2.3" }
```
`act push -e tag.json` → `github.ref_type == 'tag'`, `github.ref_name == 'v1.2.3'`, so `startsWith(github.ref, 'refs/tags/')` is true.

### pull_request
Minimum the docs require is `head.ref` and `base.ref`. Add `number` so `github.ref` becomes `refs/pull/<n>/merge`:
```json
{
  "action": "opened",
  "number": 42,
  "pull_request": {
    "number": 42,
    "title": "Test PR",
    "draft": false,
    "head": { "ref": "feature-branch", "sha": "REPLACE_WITH_SHA", "repo": { "full_name": "owner/repo" } },
    "base": { "ref": "main", "sha": "REPLACE_WITH_BASE_SHA", "repo": { "full_name": "owner/repo" } },
    "labels": [ { "name": "run-e2e" } ],
    "user": { "login": "octocat" }
  },
  "repository": { "default_branch": "main", "full_name": "owner/repo" }
}
```
`act pull_request -e pr.json`

Without `number`, the ref renders as `refs/pull/%!f(<nil>)/merge`. Include `number` whenever a workflow reads `github.ref`.

### pull_request_target
Same payload. `github.ref` = `refs/heads/<base.ref>`, `github.sha` = `base.sha`.

### workflow_dispatch with inputs
```json
{ "inputs": { "environment": "staging", "dry_run": "true" }, "ref": "refs/heads/main" }
```
`act workflow_dispatch -e dispatch.json` or `act workflow_dispatch --input environment=staging --input dry_run=true`.
- `inputs.<name>` falls back to the `default:` declared in the workflow when not supplied.
- For `type: boolean` inputs, `inputs.x` is a real boolean computed as `value == "true"`. **In event JSON, write booleans as strings** (`"dry_run": "true"`): a JSON `true` evaluates to `false` (verified act v0.2.89 quirk). `--input x=true` works. `github.event.inputs.x` stays the raw value.
- Inputs only populate when the event name is `workflow_dispatch`.

### workflow_call (run a reusable workflow directly as top level)
```json
{ "inputs": { "config-path": "configs/a.yml", "debug": "true" } }
```
`act workflow_call -W .github/workflows/reusable.yml -e call.json`. Defaults from `on.workflow_call.inputs` fill missing values. Boolean inputs must be the **string** `"true"` (JSON `true` → `false`). Supply its `secrets` with `-s`.

### release
```json
{ "action": "published", "release": { "tag_name": "v2.0.0", "name": "v2.0.0", "draft": false, "prerelease": false } }
```
`act release -e release.json` → `github.ref = refs/tags/v2.0.0`.

### schedule
No payload needed: `act schedule`. Cron expressions are not evaluated (and nothing runs on a timer).

### issue_comment (e.g. ChatOps)
```json
{
  "action": "created",
  "issue": { "number": 7, "pull_request": { "url": "https://api.github.com/repos/owner/repo/pulls/7" } },
  "comment": { "body": "/deploy staging", "user": { "login": "octocat" } }
}
```

### repository_dispatch
```json
{ "action": "my-event-type", "client_payload": { "version": "1.2.3" } }
```

### workflow_run
```json
{ "action": "completed", "workflow_run": { "name": "CI", "conclusion": "success", "head_branch": "main", "head_sha": "REPLACE_WITH_SHA", "id": 1 } }
```

### merge_group
```json
{ "merge_group": { "head_ref": "refs/heads/gh-readonly-queue/main/pr-1-abc", "base_ref": "refs/heads/main", "head_sha": "REPLACE_WITH_SHA" } }
```

Tip: to capture a real payload, add a temporary step `run: cat "$GITHUB_EVENT_PATH"` to a workflow on GitHub, or copy one from the webhook delivery log, then trim it.

## Skipping jobs or steps under act

**Steps:** act sets `ACT=true`.
```yaml
- name: Notify Slack
  if: ${{ !env.ACT }}
  run: ./notify.sh
```

**Jobs:** the `env` context isn't available in job-level `if`. Use a custom event property instead:
```yaml
jobs:
  deploy:
    if: ${{ !github.event.act }}   # skip during local testing
```
Run with `act -e event.json` where `event.json` contains `{"act": true}` (merge it into whatever payload you need). Tip: put `-e .github/act-event.json` in `./.actrc`.

**Run only under act:** `if: ${{ env.ACT }}` (step) / `if: ${{ github.event.act }}` (job).

**Alternative job-level switch:** `if: ${{ vars.SKIP_DEPLOY != 'true' }}`, then run `act --var SKIP_DEPLOY=true`.
