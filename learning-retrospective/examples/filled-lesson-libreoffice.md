# Filled Lesson Example: LibreOffice DOCX-to-PDF on One Windows Machine

The other files in `examples/` are loop *patterns*. This one shows what a finished, stored lesson looks like after Post-Resolution Capture — concrete enough that a future agent can match the failure signature and act without re-deriving anything. Details are illustrative; write yours from the actual transcript.

```markdown
# Lesson: DOCX to PDF conversion on this Windows machine

## Trigger
- Any DOCX/ODT to PDF conversion task on this machine, or the error
  `soffice: command not found` / Word COM automation timing out.

## Verified Facts
- LibreOffice is installed at `E:\Apps\LibreOffice\program\soffice.exe`
  (not on PATH, not in `C:\Program Files`).
- Headless conversion works:
  `& "E:\Apps\LibreOffice\program\soffice.exe" --headless --convert-to pdf --outdir <dir> <file.docx>`
- Chinese filenames require UTF-8 handling in the calling shell.

## Failed Attempts To Avoid
- Do not probe Word COM or WPS COM first; both are slow and were not the
  intended tool on this machine.
- Do not scan whole drives for soffice.exe; the verified path above is
  the first check.
- Do not declare success from exit code alone; a zero-byte or zero-page
  PDF has happened.

## Preferred Procedure
1. `Test-Path "E:\Apps\LibreOffice\program\soffice.exe"` - if missing, stop
   and ask, do not fall through to other converters.
2. Run the headless conversion with an explicit `--outdir`.
3. Gate: output PDF exists, size > 0, page count > 0, first page renders.

## Validation Evidence
- Converted `report_v2.docx` to a 14-page PDF; first and last pages
  rendered correctly on 2026-07-06.

## Drift Risk
- LibreOffice may be moved or upgraded; the E: drive layout is
  user-managed. Re-run the Test-Path gate rather than trusting this path
  unconditionally.

## Last Verified
- 2026-07-06

## Scope
- Applies to: this Windows machine only.
- Does not apply to: servers, CI, or machines where LibreOffice is on PATH.
```

Why this works as a recall anchor: the Trigger names both the task shape and the exact error text; Verified Facts pin the machine-specific path; Failed Attempts encode what wasted time last time; the gates make the procedure self-checking; Drift Risk and Last Verified stop a future agent from treating a stale path as a hard rule.
