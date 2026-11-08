# GHerrit native-stack experiments

Synthetic, disposable fixtures for [GHerrit design issue 518](https://github.com/joshlf/gherrit/issues/518).
This repository is an experiment, not GHerrit implementation or production work.
All PRs, reviews, branches, workflows and merges are experimental. No secrets or
production source are stored here.

Read [the findings and remaining questions](RESULTS.md) first. The reports,
original harnesses and selected machine evidence are preserved here; the
[publication manifest](PUBLICATION-MANIFEST.json) records their hashes. Complete
raw transcripts, downloaded Actions artifacts and local Git object stores are
also retained in the coordinating agent's experiment workspace. Some report
references name that deeper local evidence rather than files in this public
subset.

The trials established a first-CI path, canonical review continuity through an
F-before-B repeat workflow, structural parking controls, method-specific approval
behavior, signature controls and conservative lost-acknowledgement recovery.
They also contradicted the assumption that completed native groups cannot
accept append. Provider settlement, queue execution on an eligible repository,
native UI receipt capture and human reviewer usability remain unestablished.

These scripts are the record of one authorized synthetic campaign. Several bind
to this exact repository and its PRs, and intentionally stop on a previous write
intent. Do not rerun them as a general-purpose client. The local-only Git harness
creates a new evidence directory per invocation; hosted trials require fresh,
separately authorized fixtures and explicit ownership.

Remote lanes are `exp/api/**`, `exp/ci/**`, `exp/cli/**`, `exp/integration/**`,
`exp/queue/**` and `exp/auto/**`. Each lane had one owner.
No workflow has a schedule. Small event/dispatch workflows capture metadata;
a bot workflow creates synthetic PRs so the existing human account can supply
separate-author experimental reviews without involving another person. Its six
creation runs completed. The temporary feature flags were restored and
independently verified: workflow defaults are read-only, Actions cannot create
or approve PRs, and auto-merge is disabled. No auto-merge request was armed.
Synthetic branches, PRs, archives and exact trunk protections remain as evidence.

*Authored by an AI agent acting on joshlf's behalf.*
