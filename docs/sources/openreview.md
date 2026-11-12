# OpenReview

- **Status:** Academic-only separate product; strongest structured academic candidate if needed later.
- **Official/source URL(s):** [OpenReview API v2](https://api2.openreview.net/invitations); [API guide](https://docs.openreview.net/getting-started/using-the-api); [invitation fields](https://docs.openreview.net/reference/api-v2/entities/invitation/fields).
- **Interface:** Documented v2 `GET /invitations`, plus `/groups` enrichment.
- **Verification:** Anonymous live query in the 2026-11-11 snapshot returned 192 current/future invitations.

## Data and access

Query `https://api2.openreview.net/invitations` with `invitee=~`, `type=note`, `minduedate`, `select=id,duedate,expdate,domain`, and `sort=duedate:asc`. Use `duedate` as the displayed deadline and retain `expdate` for the grace window. Enrich selected domains through `/groups`; group dates and locations may remain free text.

## Caveats

These are academic submission invitations, not developer talk CFPs. Anonymous reads succeeded even though the general guide describes account requirements. Anonymous `offset`/`after` pagination requires login, so do not assume that pagination route for overflow. The review established no anonymous rate limit.

## Integration guidance

Only build this after approval for a separate academic product. Use supported time bucketing if results overflow, retain both deadline fields, and enrich only selected groups rather than treating group prose as normalized event data.

[EasyChair Smart CFP](https://easychair.org/cfp) is a related, later single-page HTML option: the snapshot contained 1,152 linked rows, but blank deadlines and display-string fields require local filtering, and researchers did not verify every row was open.

## Evidence

The compact review recorded the dated 192-result query, anonymous pagination limits, free-text groups, and EasyChair constraints.
