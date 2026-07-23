# Install for AI Agents

Goal: install the `learning-retrospective` skill from this repository into the user's agent harness. Follow these steps mechanically; do not improvise.

## Rules

- Do NOT install or register hooks unless the user explicitly asked for hooks.
- Do NOT modify persistent memory, agent rules, shell profiles, `settings.json`, `hooks.json`, or any global configuration. The only thing you may write is the target skill directory and, only on explicit request, the installer-managed hook bundle/config-example files.
- Run the test suite before copying.
- Copy only the nested `learning-retrospective/` folder, never the repository root.
- Report what was installed and what was deliberately not installed.

## Steps

1. Clone the repository:

   ```bash
   git clone https://github.com/Yingqi-Han/learning-retrospective-skill.git
   cd learning-retrospective-skill
   ```

2. Preferred: run the installer, which tests, copies, and verifies in one step:

   ```bash
   python install.py --agent codex    # or: --agent claude
   python install.py --agent project --target ./.agent-skills
   ```

   If the installer cannot be used, do the equivalent manually:

   ```bash
   python -S -m unittest discover -s learning-retrospective/tests -v
   # then copy learning-retrospective/ to:
   #   Codex:       ~/.codex/skills/learning-retrospective
   #   Claude Code: ~/.claude/skills/learning-retrospective
   #   Project:     ./.agent-skills/learning-retrospective
   ```

3. Verify the installed copy:
   - `<target>/SKILL.md` exists
   - `<target>/VERSION` exists and matches `learning-retrospective/VERSION` in the repo
   - `<target>/SECURITY_NOTES.md` exists

4. Optional, recommended for non-English users: add native-language trigger phrases. For Chinese, prefer the installer flag `--locale zh-CN` (idempotent and ASCII-safe through YAML escapes); for other languages follow `<target>/references/localization.md`. Ask the user which language they type in if unclear.

5. Report to the user: installed version, target path, test result, and that hooks were NOT installed.

## Hooks

- Never register hooks by default. A hook runs local code on every future tool call.
- If and only if the user explicitly asks for hooks: read `SECURITY_NOTES.md` and `learning-retrospective/references/hook-activation.md` first, show the user the exact config change before applying it, and remind them that Codex separately tracks enablement and trust. CLI/TUI builds may expose `/hooks`; Desktop builds use a Hooks settings panel whose controls vary by release. An enabled switch alone does not prove that the current hook hash is trusted.
- Prefer `python install.py --agent codex --with-hooks` (or `--agent claude`) to copy the complete hook bundle transactionally. It stages and verifies files, activates the detector last, rolls back partial failures, preserves an existing active reviewer config, and still does not register or trust the hook.

## Suggested user prompt

```text
Clone https://github.com/Yingqi-Han/learning-retrospective-skill and install it
for [Codex / Claude Code] following INSTALL_FOR_AGENTS.md. Do not install hooks
unless I confirm separately.
```
