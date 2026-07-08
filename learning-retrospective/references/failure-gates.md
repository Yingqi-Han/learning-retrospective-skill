# Failure Gates

A failure gate prevents a loop from turning into broad, unfocused fallback discovery.

## Gate Pattern

```text
Before trying: <next action>
Expected success: <observable result>
If success: <continue path>
If fail: <stop or one allowed fallback>
Do not: <unrelated retries to avoid>
```

## Examples

### Tool path

```text
Before trying: run Test-Path / command -v on the verified tool path.
Expected success: executable exists and reports a version.
If success: use that exact executable.
If fail: repair the configured path or ask for the intended tool.
Do not: scan the whole drive or try unrelated tools without evidence.
```

### Test command

```text
Before trying: run the smallest relevant test.
Expected success: the target test passes or fails with the expected assertion.
If success: run the broader suite.
If fail: inspect the first failure only.
Do not: rewrite unrelated modules.
```

### File conversion

```text
Before trying: convert one input with the verified converter.
Expected success: output exists, has nonzero size, page/item count is plausible, and a rendered/sample inspection works.
If success: continue batch or import.
If fail: capture converter output and fix that converter path or format issue.
Do not: cascade into unrelated converters without checking the failure.
```
