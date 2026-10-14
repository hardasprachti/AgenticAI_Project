# Problem Statement: Groww Weekly Review Pulse

## Overview

Build an AI workflow/agent for the **Groww** platform ([Groww Stocks, Mutual Fund, IPO on Google Play](https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en_IN)) that turns raw mobile-store reviews into a **weekly pulse** a team can scan in minutes:

- what users care about
- what they actually said
- what to do next

Reviews are already public. The job is to aggregate, theme, summarize, and deliver the insight through familiar surfaces:

- **Google Docs** for the written pulse
- **Gmail** for a draft email to yourself (or an alias)

Credentials and REST wiring must not be handled directly (see [Integrations](#integrations-google-docs--gmail-via-mcp)).

**Course track:** AI Workflows, Agents and Evals

## End-to-End Flow ("done" looks like)

1. Pull recent Play Store reviews for the product (within the constraints below).
   - Source: <https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en_IN>
   - **Scope note:** the original brief mentions both App Store and Play Store. The **Apple App Store is out of scope for now**; only Google Play reviews are used. It can be added later as a second review source.
2. Cluster reviews into a small set of themes and distill a one-page weekly note.
3. Put the note where stakeholders can read it (Google Docs).
4. Create a draft email to yourself (or an alias) that contains or links to the pulse (Gmail).

## Deliverables

**Weekly one-page pulse** must include:

- **Top themes**: what people are talking about most
- **Real user quotes**: verbatim snippets from reviews, no invented wording
- **Three action ideas**: concrete next steps grounded in the themes

**Finally:** a draft email to yourself containing the weekly note (or a clear pointer to it).

## Who This Helps

| Audience | Why |
| --- | --- |
| Product / Growth | Prioritize fixes and improvements from real signals |
| Support | Align messaging with what users are actually saying |
| Leadership | One-page health check without drowning in raw reviews |

## What You Must Build

1. **Import reviews** from roughly the last **8-12 weeks** (fields such as rating, title, text, date, whatever the export provides).
2. **Group reviews into at most 5 themes** (examples: onboarding, KYC, payments, statements, withdrawals; pick what fits the product).
3. **Generate a weekly one-page note** with:
   - Top 3 themes (a subset of the themes, as appropriate)
   - 3 user quotes
   - 3 action ideas
4. **Draft an email** with the note to yourself or an alias.

## Integrations: Google Docs & Gmail via MCP

- Use **MCP (Model Context Protocol) servers** for Google Docs and Gmail, e.g. creating or updating the pulse document and creating the draft message.
- Do **not** integrate Google APIs directly: no bespoke OAuth client + REST client code as the primary integration path.
- MCP servers expose tools the agent or app calls. This keeps Docs and Gmail consistent with the course tooling and avoids duplicating auth and HTTP plumbing.
- Choose whichever MCP servers or connectors the environment provides for Docs and Gmail. The requirement is **MCP-first**, not "call Google APIs manually."

## Key Constraints

| Area | Constraint |
| --- | --- |
| Reviews | Public review exports only. No scraping behind store logins or ToS-violating automation. |
| Themes | Maximum **5** themes for clustering; the written pulse highlights the **top 3**. |
| Length | Keep the note scannable and **≤ 250 words** where applicable. |
| Privacy | **No PII** in any artifact: no usernames, emails, device IDs, or other identifiable reviewer data. Quotes must be anonymous / stripped as needed. |
