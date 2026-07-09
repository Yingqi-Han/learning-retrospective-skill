# Example: Zotero Linked Attachment Loop

## Loop Signal

The agent imports large documents into Zotero storage, then the user clarifies that only one physical file copy should exist.

## Verified Facts

- Zotero can either store managed copies or link to external files.
- The user's goal is to avoid duplicate large files.
- The external project folder is the intended source of truth.

## Failed Attempts To Avoid

- Do not import both DOCX and PDF if the user asked for PDF only.
- Do not copy large files into Zotero storage when the user wants linked attachments.
- Do not edit Zotero's database while Zotero is running unless using a supported API.

## Preferred Procedure

1. Confirm the desired source file and output format.
2. Create or verify the external file in the project folder.
3. Use the Zotero UI or a supported API to link the external file rather than copy it. Do not edit the Zotero SQLite database directly unless Zotero is closed, the database is backed up, and the user explicitly approves.
4. Verify the Zotero item points to the external file and the storage copy does not exist.
5. Remove temporary backups only after the user confirms the library looks normal.

## Lesson Surface

User-level memory for Zotero data directory and attachment preference; project-level notes for specific library organization.
