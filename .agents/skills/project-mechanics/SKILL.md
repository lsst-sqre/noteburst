---
name: project-mechanics
description: Project-specific build/test/lint/typing commands for this repo. Read this skill at the start of any phase that runs validation (`stoker-work`, `stoker-fixup`, `stoker-rebase`).
---

# Project mechanics

This file is the source of truth for how this repo runs tests, lint,
and type-checking. Profile-shipped phase skills read it at the start
of each phase and use the named commands verbatim.

## Test commands

- `focused_test`: `uv run --only-group=tox tox run -e py -- tests/path/test_file.py::test_name` (tox sets the required `NOTEBURST_*` / `METRICS_*` env vars from `tox.ini`; pass any pytest args after `--`)
- `complete_test`: `uv run --only-group=tox tox run -e py,coverage-report`

## Lint

- `lint_touched`: `uv run --only-group=lint prek run --files {files}`
- `lint_all`: `uv run --only-group=tox tox run -e lint`

## Typing

- `typing`: `uv run --only-group=tox tox run -e typing`

## Final validation

End-of-task validation runs `uv run --only-group=tox tox run -e py,coverage-report` + `uv run --only-group=tox tox run -e lint` + `uv run --only-group=tox tox run -e typing` in that order, in the foreground. This is a single-package repo, so `complete_test` is the full suite; the Docker image build (`build` job in `ci.yaml`) is CI's responsibility, not the in-iteration gate. Plus `uv run --only-group=tox tox run -e docs` for docs changes (files under `docs/`).

<!-- stoker-onboarded-from: builtin:default
     prompt-hash: 348ec538f8f7f6fa42da3569d855eab629174668ef28ea225f8b37511daac9d4
     onboarded-at: 2026-08-25T14:38:02Z -->
