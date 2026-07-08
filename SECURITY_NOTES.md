# Security Notes

This repository contains prompt and workflow guidance, not executable application code.

## Sensitive Data

Do not store the following in lessons, examples, project memory, or user memory:

- API keys, tokens, cookies, passwords, SSH keys, or credentials
- private user data that is not needed for future execution
- large raw logs containing secrets or private paths
- unverified guesses presented as facts

## Persistent Writes

Agents using this skill should not silently modify:

- user-level memory
- repository instructions such as `AGENTS.md` or `CLAUDE.md`
- project rules such as `.cursor/rules/` or `.clinerules`
- other skills

If the user did not explicitly ask to save or update the lesson, present the proposed lesson and destination first.

## Reporting Issues

Open a GitHub issue if the skill encourages unsafe persistence, over-broad triggering, or accidental disclosure of sensitive information.
