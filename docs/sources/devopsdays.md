# devopsdays

- Status: Recommended next
- Official/source URL(s): [devopsdays speaking calendar](https://devopsdays.org/speaking/), [`devopsdays/devopsdays-web`](https://github.com/devopsdays/devopsdays-web)
- Interface: official `data/events/<year>/<city>/main.yml` files, discoverable through the repository tree; [example Atlanta 2027 YAML](https://raw.githubusercontent.com/devopsdays/devopsdays-web/main/data/events/2027/atlanta/main.yml)
- Verification: 2026-11-11

## Data and access

Canonical per-event YAML carries event start/end dates, `cfp_date_start`, `cfp_date_end`, `cfp_link`, city, venue `location`, and `location_address`. Values may be ISO timestamps or legacy `YYYY-MM-DD`. The repository is Apache-2.0-licensed, with separate third-party assets under their stated licenses, and had a push on 2026-11-11. The speaking page listed exactly four open CFPs in that dated snapshot: Zurich, Atlanta, Raleigh, and Geneva. No official consolidated CFP JSON was verified.

## Caveats

**Country is not a structured field.** `location` is a venue, not a general city/country value; never copy it into country. Country needs a curated city mapping or must remain unknown. The speaking page is an open-CFP discovery view, not recently closed history. Avoid treating fixed `devops` topics as source-provided tags; if desired, they are pipeline defaults.

## Integration guidance

Use the speaking page for low-request discovery, then resolve only corresponding `main.yml` files for metadata. For open plus recently closed coverage, enumerate event YAML for the current and next year through the GitHub tree API and cache unchanged files. Filter on parsed `cfp_date_end`, require an actionable `cfp_link`, map event dates/city/venue carefully, and preserve date-only precision rather than inventing times. Apply normalized identity plus shared compatible-name URL dedupe against generic aggregators. Proposed ownership is immediately below `manual` and above developers.events **only because the adapter is restricted to this official series repository**; measure full-pipeline unique yield before implementation.

## Evidence

- [Speaking calendar](https://devopsdays.org/speaking/) — generated open-CFP index and dated snapshot.
- [Example event YAML](https://raw.githubusercontent.com/devopsdays/devopsdays-web/main/data/events/2027/atlanta/main.yml) — actual CFP, date, city, and venue fields.
- [Repository license](https://raw.githubusercontent.com/devopsdays/devopsdays-web/main/LICENSE) — Apache 2.0 terms.
