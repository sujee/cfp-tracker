# Conference prestige list

A hand-curated ranking of conferences — edit the `ranking` cell (1 flagship, 2 major, 3 notable) then run:

```bash
python3 src/apply-prestige.py          # stamps `tier` on matching notes
python3 src/apply-prestige.py --check   # per-row match counts, writes nothing
```

Notes matching **no row** keep their hand-set tier (so you can rank a one-off directly).

`keywords` is a comma-separated list of alternatives — a row matches when any phrase appears in the `event_name` (case- and punctuation-insensitive; a trailing year may be glued on, e.g. `SREcon27`). Lowest tier wins when several rows match. Add per-edition keywords for non-year suffixes (`scale 24x`, not `scale`). Rows that list flagships no feed carries (re:Invent, Google I/O, NeurIPS, …) legitimately match nothing until one appears in a file named in `MANUAL_INPUT_FILES`; `--check` surfaces both those and typo'd keywords.

## Rankings

| conf name | ranking | keywords |
| :--- | :---: | :--- |
| FOSDEM | 1 | fosdem |
| KubeCon + CloudNativeCon | 1 | kubecon, cloudnativecon |
| SREcon (USENIX) | 1 | srecon |
| QCon | 1 | qcon |
| AI Engineer | 1 | ai engineer |
| JavaOne | 1 | javaone |
| Devoxx Belgium | 1 | devoxx belgium |
| AWS re:Invent | 1 | re invent |
| Google I/O | 1 | google i o |
| Google Cloud Next | 1 | cloud next |
| Microsoft Build | 1 | microsoft build |
| Apple WWDC | 1 | wwdc |
| GitHub Universe | 1 | github universe |
| PyCon US | 1 | pycon us |
| NeurIPS | 1 | neurips |
| ICML | 1 | icml |
| ICLR | 1 | iclr |
| USENIX ATC | 1 | usenix atc |
| OSDI | 1 | osdi |
| GOTO | 1 | goto |
| HumanX | 1 | humanx |
| AI Summit | 1 | ai summit |
| KotlinConf | 2 | kotlinconf |
| Craft Conference | 2 | craft conference |
| Devoxx | 2 | devoxx |
| GrafanaCON | 2 | grafanacon |
| OffensiveCon | 2 | offensivecon |
| Write the Docs | 2 | write the docs |
| AGNTCon + MCPCon | 2 | agntcon, mcpcon |
| DrupalCon | 2 | drupalcon |
| Percona Live | 2 | percona live |
| SCaLE | 2 | scale 24x, southern california linux expo |
| Jfokus | 2 | jfokus |
| TokioConf | 2 | tokioconf |
| Identiverse | 2 | identiverse |
| React Summit | 2 | react summit |
| JSNation | 2 | jsnation |
| PyTorch Day | 2 | pytorch day |
| SciPy | 2 | scipy |
| GopherCon | 2 | gophercon |
| Ubuntu Summit | 2 | ubuntu summit |
| ArgoCon | 2 | argocon |
| CiliumCon | 2 | ciliumcon |
| BackstageCon | 2 | backstagecon |
| FluxCon | 2 | fluxcon |
| OpenTofu Day | 2 | opentofu |
| Platform Engineering Day | 2 | platform engineering day |
| Observability Day | 2 | observability day |
| Open Source SecurityCon | 2 | open source securitycon |
| KeycloakCon | 2 | keycloakcon |
| NeoCloudCon | 2 | neocloudcon |
| Buildpacks Summit | 2 | buildpacks |
| Kubernetes on Edge Day | 2 | kubernetes on edge |
| SIGMOD | 2 | sigmod |
| VLDB | 2 | vldb |
| CVPR | 2 | cvpr |
| Voxxed Days | 3 | voxxed |
| Conf42 | 3 | conf42 |
| BSides | 3 | bsides |
| KCD (Kubernetes Community Day) | 3 | kcd |
