# PythonDeadlin.es

- Status: Recommended next
- Official/source URL(s): [`jesperdramsch/python-deadlines`](https://github.com/jesperdramsch/python-deadlines)
- Interface: [`_data/conferences.yml`](https://raw.githubusercontent.com/jesperdramsch/python-deadlines/main/_data/conferences.yml)
- Verification: 2026-11-11

## Data and access

The maintained, public, unauthenticated YAML contains `conference`, `year`, event `link`, `cfp_link`, `cfp` timestamp, optional `timezone`, free-text `place`, event `start`/`end`, and comma-separated `sub` topics. The repository is MIT-licensed and describes itself as an independently maintained fork of ai-deadlines. The 2026-11-11 snapshot had 75 records, ten current/future deadlines, and nine of those with a CFP link; these are dated counts, not guaranteed future yield.

## Caveats

Require an actionable `cfp_link`; do not invent one for rows such as the snapshot's PyCon Côte d’Ivoire. Filter `cfp`, not merely event dates. Missing timezone must remain unknown—do not import AoE defaults from sibling projects. `place` is not a structured country field. **Python Community Leadership Summit and PyTexas intentionally share a Pretalx CFP URL while remaining distinct events**; URL-only merging would be wrong.

## Integration guidance

Select `cfp >= cutoff`, map `link`→`event_url`, `cfp_link`→`cfp_url`, `conference`→name, and start/place fields conservatively. Split and trim `sub`; preserve source deadline precision during parsing before deriving the note's date-only close. Dedupe by normalized name plus close date, then rely on the writer's compatible-name gate for cross-path URL matches—not a raw shared-URL rule. Leave country blank unless independently established. Proposed ownership is below TechConf Spain and above AgentConfs/confs.tech; measure post-dedupe unique speaking notes against the complete tracker before promotion.

## Evidence

- [Maintained YAML](https://raw.githubusercontent.com/jesperdramsch/python-deadlines/main/_data/conferences.yml) — current rows, fields, and shared-Pretalx example.
- [Project README](https://raw.githubusercontent.com/jesperdramsch/python-deadlines/main/README.md) — contribution model and fork status.
- [MIT license](https://raw.githubusercontent.com/jesperdramsch/python-deadlines/main/LICENSE) — reuse terms.
