# Trigger-Phrase Localization

Description-based recall is language-sensitive: the skill fires far more reliably when the trigger words in `description:` match the language the user actually types. The repository copy of `SKILL.md` stays ASCII-only because at least one skill validator (Codex `quick_validate.py` on Windows) reads files with the locale default encoding and crashes on non-ASCII bytes under a GBK locale.

If your harness reads UTF-8 (Claude Code does), append native-language trigger phrases to the `description:` line of your **installed** copy. Keep the English text intact and add the phrases at the end, before the final "Do not use" sentence.

## Chinese trigger addendum

Copy-paste segment to append after "...retrospective or lesson to prevent future retry loops":

```text
 — including Chinese requests such as 复盘, 总结经验, 总结教训, 吸取教训, 记住这个坑, 避免重复踩坑, 别再重复试错.
```

## Other languages

The same pattern applies: pick the 5-8 short phrases a user of that language would actually type when asking for a retrospective, a lesson, or an end to repeated trial-and-error. Prefer everyday imperative phrasings over formal vocabulary — recall matches what users type, not what dictionaries prefer.

## Caveats

- Re-apply the addendum after re-installing or syncing from the repository; the repo copy will overwrite it.
- Do not add the addendum to a copy that a locale-default-encoding validator will read, or validation will fail on Windows GBK systems.
