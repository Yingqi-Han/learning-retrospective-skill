# Example: Dependency Install Loop

## Loop Signal

The agent cycles through package managers or install flags (`pip`, `conda`, `npm`, `--force`, version pins) after an install or build failure, without reading the first real error or checking which environment is actually active.

## Verified Facts

- The project declares its dependencies and supported versions somewhere (lockfile, `pyproject.toml`, `package.json`, docs).
- The machine may have multiple environments or toolchain versions; only one is the intended target.
- The first error line of the failed install usually names the real cause (compiler missing, version conflict, network/proxy, wrong Python/Node version).

## Failed Attempts To Avoid

- Do not switch package managers before reading the first error of the current one.
- Do not add `--force`, `--no-deps`, or blanket version pins to silence a conflict you have not diagnosed.
- Do not install into whichever environment happens to be active without confirming it is the intended one.

## Preferred Procedure

1. Confirm the intended environment and its version (`which python` / `node --version` / `conda env list`).
2. Read the first actionable error of the failed install, not the last line.
3. Check project docs or memory for a known-good install command for this machine.
4. Make one targeted fix (correct env, missing system dep, proxy setting) and rerun the same command.
5. Verify by importing/running the installed package, not by install exit code alone.
6. If the fix was machine-specific (proxy, compiler path, env name), capture it as a lesson.

## Lesson Surface

User-level memory for machine-specific environments, proxies, and toolchain paths; project-level docs for the canonical install command.
