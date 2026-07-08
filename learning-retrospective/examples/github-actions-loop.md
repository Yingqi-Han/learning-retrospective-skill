# Example: GitHub Actions Loop

## Loop Signal

The agent repeatedly edits code and pushes commits without reading the failing GitHub Actions log or without reproducing the failing command locally.

## Verified Facts

- A specific workflow, job, or test failed.
- The failure log is available through GitHub UI, CLI, connector, or downloaded logs.
- The next edit should target the first concrete failure, not a guessed cause.

## Failed Attempts To Avoid

- Do not patch unrelated files before reading the failing job log.
- Do not rerun CI repeatedly without changing the suspected cause.
- Do not treat every failure in a matrix as independent before checking the first shared error.

## Preferred Procedure

1. Identify the failing workflow, job, step, and exact command.
2. Read the first actionable error and the surrounding context.
3. Reproduce locally when practical, or make the smallest targeted edit.
4. Rerun the narrow local check first, then push or rerun CI.
5. Capture the root cause and the canonical local verification command if it is reusable.

## Lesson Surface

Project-level docs for test commands and CI conventions; user-level memory only for account/tooling setup.
