# GHerrit native-stack experiments

Synthetic, disposable fixtures for [GHerrit design issue 518](https://github.com/joshlf/gherrit/issues/518).
This repository is an experiment, not GHerrit implementation or production work.
All PRs, reviews, branches, workflows and merges are experimental. No secrets or
production source are stored here. Results and exact evidence are retained by
the coordinating agent and summarized here when the experiments finish.

Remote lanes are `exp/api/**`, `exp/ci/**` and `exp/cli/**`. Each lane has one owner.
No workflow has a schedule. Small event/dispatch workflows capture metadata;
a bot workflow creates synthetic PRs so the existing human account can supply
separate-author experimental reviews without involving another person.

*Authored by an AI agent acting on joshlf's behalf.*
