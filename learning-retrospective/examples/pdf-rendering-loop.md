# Example: PDF Rendering Loop

## Loop Signal

The agent tries to render or convert a document to PDF multiple times, but the converter command is missing or produces no output.

## Verified Facts

- The first converter command failed with command-not-found, missing executable, or empty output.
- A specific converter path or installation status can be checked cheaply.
- The task needs a real PDF, not just a successful command exit.

## Failed Attempts To Avoid

- Do not retry the same missing converter.
- Do not scan the whole machine before checking the expected install path.
- Do not switch to unrelated converters without inspecting the first converter failure.

## Preferred Procedure

1. Check whether the expected converter exists and reports a version.
2. Run one conversion with explicit input and output paths.
3. Verify the PDF exists, has nonzero size, has page count greater than zero, and renders a sample page.
4. If validation fails, report the failing gate and fix that converter path or format issue before trying another converter.

## Lesson Surface

User-level memory for installed converter paths; project-level notes for project-specific render commands.
