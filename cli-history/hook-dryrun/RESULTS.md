# Outer dry-run and inner hook publication

On `git version 2.54.0 (Apple Git-157)`, outer `git push --dry-run` invoked the
fixture pre-push hook. The hook successfully published to its separate local
inner sink. The outer sink remained empty. An actual outer push, starting from
identical source/sink refs, invoked the same hook and published to both sinks.

| Invocation | Hook ran | Inner sink afterward | Outer sink afterward |
| --- | --- | --- | --- |
| `git push --porcelain --dry-run outer refs/heads/source:refs/heads/outer-publication` | Yes | `inner-publication` at fixture SHA | Empty |
| Same command without `--dry-run` | Yes | `inner-publication` at fixture SHA | `outer-publication` at fixture SHA |

Fixture SHA: `84c1319eb11edec800e5c899ddd07fd9d1fedc96`. The commit uses the
required Josh Liebow-Feeser identity and agent-authorship trailer. The inner
sink ref and its source-side tracking ref were explicitly reset between phases;
all three repositories' before-state ref maps were then identical.

The hook's captured argv, stdin, working directory and all fifteen allowlisted
standard Git environment variables were identical between invocations. No dry-run
signal was present in those captured inputs. `dry-run-hook.json` and
`actual-hook.json` retain the exact observations and inner-push receipts.
The hook source is `pre-push.py`; its inner command uses `push --no-verify`.

Git's [pre-push documentation](https://git-scm.com/docs/githooks#_pre_push)
specifies destination name/location arguments and stdin ref records. Its
[push documentation](https://git-scm.com/docs/git-push) describes `--dry-run` as
skipping sent updates, and `--no-verify` as bypassing the pre-push hook. This
experiment demonstrates that the outer command's dry-run does not automatically
make a separate push issued by this hook a dry-run.

This is a bounded local-transport, one-ref observation. It does not prove that
no other detection mechanism exists. No GHerrit implementation, hosted resource,
global hook or global configuration was changed. Inherited `GIT_*` variables
were cleared only for fixture child processes, which used disabled system/global
configuration. All fixture hooks were local to the fresh source repository.

`run.py`, `commands.jsonl`, `RESULTS.json`, the hook and exact before/after refs
retain the experiment. Do not rerun the driver into the retained sinks: it
requires fresh repositories. The earlier CLI/history results remain unchanged.

*Authored by an AI agent acting on joshlf's behalf.*
