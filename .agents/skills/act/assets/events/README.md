# Sample event payloads for `act -e`

Copy one into the project (e.g. `.github/act/<event>.json`), edit it, then run:

```sh
act <event> -e .github/act/<event>.json -P ubuntu-latest=catthehacker/ubuntu:act-latest
```

| File | Run with | Notes |
|---|---|---|
| `push.json` | `act push -e push.json` | Branch push. `github.sha` comes from local HEAD (add `"after": "<sha>", "deleted": false` to force a sha) |
| `push-tag.json` | `act push -e push-tag.json` | Tag push. `github.ref_type == 'tag'` |
| `pull_request.json` | `act pull_request -e pull_request.json` (also `pull_request_target`) | Keep `number`, or `github.ref` renders as `refs/pull/%!f(<nil>)/merge`. Add `head.sha`/`base.sha` only if the workflow reads them (`pull_request_target` uses `base.sha` as `github.sha`) |
| `workflow_dispatch.json` | `act workflow_dispatch -e workflow_dispatch.json` | Input booleans must be strings `"true"`/`"false"` |
| `workflow_call.json` | `act workflow_call -W <reusable.yml> -e workflow_call.json` | Run a reusable workflow directly |
| `release.json` | `act release -e release.json` | `github.ref = refs/tags/<tag_name>` |
| `issue_comment.json` | `act issue_comment -e issue_comment.json` | ChatOps-style workflows |
| `repository_dispatch.json` | `act repository_dispatch -e repository_dispatch.json` | `github.event.client_payload.*` |
| `workflow_run.json` | `act workflow_run -e workflow_run.json` | |
| `schedule.json` | `act schedule -e schedule.json` | `-e` optional for schedule |

Every file includes `"act": true`, so jobs guarded with `if: ${{ !github.event.act }}` are skipped locally. Remove it to run those jobs.
Replace `owner/repo`, refs and `REPLACE_WITH_*` placeholders as needed, or delete fields the workflow doesn't read.
