---
type: cfp
event_name:
event_date:
event_type: conference
location:
country:
cfp_close:
topics: []
benefits: []
languages: []
event_url:
cfp_url:
source: manual
shortlist: false
dismissed: false
submissions: []
curated_fields: []
created:
updated:
---

```
type:     cfp
source:   manual | developers.events | cfp.ninja | confs.tech   (manual = never overwritten by the pipeline)
event_date:   conference start date, YYYY-MM-DD (or leave empty / TBA)
event_type:   conference | summit | workshop | meetup | hackathon | webinar | other
cfp_close:    submission deadline, YYYY-MM-DD (or free text like "Early 2027")
country:  USA | UK | Online | <country name> | (empty)   (canonicalised on write)
topics:   [ai, agents, ...]
benefits: [travel, hotel, honorarium]   # add only when the organizer states it
languages: [english]                    # from developers.events tags; empty for other sources
submissions: ["[[my-talk]]", ...]       # wiki links, preserved across refreshes
curated_fields: [location, country]     # optional; source fields you own (kept on conflict)
created:  ISO timestamp of the note's first refresh (pipeline fills it)
updated:  ISO timestamp the source data last changed (pipeline fills it)
```

# {{title}}

## Notes

_Add notes here._
