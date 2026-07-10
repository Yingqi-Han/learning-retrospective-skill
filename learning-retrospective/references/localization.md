# Trigger-Phrase Localization

Description-based recall is language-sensitive: the skill fires far more reliably when the trigger words in `description:` match the language the user actually types. The repository copy of `SKILL.md` stays ASCII-only because at least one skill validator (Codex `quick_validate.py` on Windows) reads files with the locale default encoding and crashes on non-ASCII bytes under a GBK locale.

Prefer the installer for Chinese localization. It stores non-ASCII trigger phrases as YAML `\uXXXX` escapes: a YAML-aware harness decodes the original Chinese text, while the on-disk `SKILL.md` remains ASCII and therefore readable by locale-default Windows validators. For other languages, use the same escaped-scalar approach or append native text only when the complete validation and discovery path is known to read UTF-8.

## Chinese trigger addendum

Decoded text represented by the installer after "...retrospective or lesson to prevent future retry loops":

```text
 — including Chinese requests such as 复盘, 总结经验, 总结教训, 吸取教训, 记住这个坑, 避免重复踩坑, 别再重复试错.
```

## Other languages

The same pattern applies: pick the 5-8 short phrases a user of that language would actually type when asking for a retrospective, a lesson, or an end to repeated trial-and-error. Prefer everyday imperative phrasings over formal vocabulary — recall matches what users type, not what dictionaries prefer.

## Automated via the installer

`python install.py --agent codex --locale zh-CN` (or `--agent claude`) applies the Chinese addendum to the installed copy automatically and idempotently. The resulting file stays ASCII-only because the description is emitted as a JSON-compatible YAML double-quoted scalar with Unicode escapes. After updating with `--force`, pass `--locale` again to re-apply.

## Caveats

- Re-apply the addendum after re-installing or syncing from the repository; the repo copy will overwrite it.
- If adding another language manually, escape non-ASCII characters or run every validator and discovery path in explicit UTF-8 mode before relying on the result.
