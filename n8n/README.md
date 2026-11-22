# n8n workflow setup

The exported workflow accepts new rows from Google Sheets, normalizes common form column names, queues each lead through FastAPI, and reads back queue metrics and recent leads. The Facebook Lead Ads trigger is retained in the export for testing; Google Sheets is the intended current source.

## Import and configure

1. Import `n8n-workflow.json` into your n8n instance.
2. Configure the Google Sheets Trigger credentials, spreadsheet, and worksheet.
3. In every HTTP Request node, replace `https://YOUR_API_HOST` with the API address reachable **from the n8n container**. For local Docker on macOS, use `http://host.docker.internal:8000`; for a remote n8n instance, use a secure public tunnel or deployed HTTPS endpoint.
4. Replace `YOUR_API_AUTH_TOKEN` in each HTTP Request node with the `API_AUTH_TOKEN` configured for the API. Prefer n8n's Header Auth credential store instead of a literal value when available.
5. Save the workflow and test with a synthetic address you control. The API deduplicates email addresses, so a second run with the same address is ignored.

Do not commit real tokens, SMTP credentials, or Google credentials in the workflow export. The repository template contains placeholders only and does not alter a workflow already imported in your n8n instance.

## Field mapping

The Code node accepts common Google Form headings and maps them to:

`name`, `email`, `phone`, `job_title`, `company`, `company_website`, `comments`, `industry`, `linkedin_url`, `interest_area`, `challenge`, `company_size`, `country`, and `source`.

`name`, `email`, and `company` are required. A row with missing required data receives HTTP 422 and should be corrected at the sheet/mapping stage. Empty rows should be filtered before the HTTP Request node.

## Delivery controls

The workflow sends `dry_run=false` for the queued job template. Email drafts still wait for human approval by default (`REQUIRE_EMAIL_APPROVAL=true`). The approval action uses the API's configured dry-run setting. Keep `DRY_RUN_MODE=true` until SMTP is verified; to deliver live, set it to `false` and approve a reviewed draft in the dashboard. Do not use a production recipient for initial SMTP checks.

The workflow polls `/metrics` to display queue state; it does not send follow-ups. Reply detection and follow-up scheduling are planned separately and are not part of this export.

## Troubleshooting

- **Connection refused:** verify the API is running and that the URL is reachable from the n8n container; `localhost` inside a container points to that container.
- **401:** check the bearer token on every HTTP Request node against the API's `API_AUTH_TOKEN`.
- **422:** inspect the Code node output and confirm `name`, `email`, and `company` are non-empty.
- **Duplicate result:** that email was already received; use a different test address or inspect the existing lead in the dashboard.
- **No email delivered:** check `DRY_RUN_MODE`, approval status, SMTP configuration, and API/worker logs. A queued job does not mean the email was sent.
