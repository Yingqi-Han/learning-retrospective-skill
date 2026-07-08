# Example: DOCX Conversion Loop

## Loop Signal

The agent tries Word automation, another office suite, and broad filesystem search before checking a known verified converter path or documented project conversion command.

## Verified Facts

- The source `.docx` exists and the target output path is known.
- The system may already have a verified converter path in memory or project docs.
- Unicode paths and filenames can require explicit encoding handling on Windows.

## Failed Attempts To Avoid

- Do not start with broad Office discovery when memory or project docs name a converter.
- Do not silently fall back from one converter to another without a failure gate.
- Do not declare success until the output file is verified.

## Preferred Procedure

1. Search existing memory or project docs for the verified converter path.
2. Check that exact path or command.
3. Convert one file with explicit output directory.
4. Verify output exists, size is plausible, page count is greater than zero, and sample rendering/text extraction works.
5. If a new converter path or encoding fix was needed, capture it as a verified lesson.

## Lesson Surface

User-level memory for machine-specific converter paths; project-level notes for project-specific output requirements.
