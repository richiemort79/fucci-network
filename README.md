# Fucci Citation Network

Interactive visualisation of independent research groups building on cell cycle tools and methods developed in the [Mort Lab](https://wp.lancs.ac.uk/mortlab/) at Lancaster University.

Live at: **https://richiemort79.github.io/fucci-network/**

## What this shows

The network maps citing studies for three published outputs:

- **Fucci2a** mouse — [Mort et al. 2014, *Cell Cycle*](https://pubmed.ncbi.nlm.nih.gov/25486356/)
- **Arl13b-Fucci2a** cilia–cell cycle biosensor — [Ford, Mort et al. 2018, *Dev Cell*](https://pubmed.ncbi.nlm.nih.gov/30458140/)
- **Multistage mathematical model** of cell proliferation — [Yates, Ford & Mort 2017, *Bull Math Biol*](https://pubmed.ncbi.nlm.nih.gov/29030804/)

Each node is an independent citing study. Click any node for details including authors, journal, funding bodies, and a DOI link.

## Controls

| Control | What it does |
|---|---|
| **Show network** | Filter to one source paper or show all three |
| **Link layer** | Switch between institution, country, or collaborator links |
| **Colour papers by** | Year / confirmed mouse use / journal impact factor |
| **Period** | Filter to pre-2022 or post-2022 |
| **Timeline** | Animate cumulative adoption from 2015 to present |
| **Search** | Filter by institution, author, country, or title |

## Repository structure

```
fucci-network/
├── index.html          Live site (auto-generated — do not edit directly)
├── template.html       HTML/JS template with __DATA__ placeholder
├── update_data.py      Script to regenerate index.html from new Scopus exports
├── data/
│   ├── fucci2a.csv     Scopus export — Mort et al. 2014 citing papers
│   ├── arl13b.csv      Scopus export — Ford, Mort et al. 2018 citing papers
│   ├── multistage.csv  Scopus export — Yates, Ford & Mort 2017 citing papers
│   └── verification.csv  Manual mouse-use verification table (optional)
├── README.md
└── LICENSE
```

## Updating the data

When new Scopus exports are available:

1. Export citing papers for each source paper from [Scopus](https://www.scopus.com) as CSV (include all fields: Abstract, Funding Details, Author Keywords, Index Keywords)
2. Save as `data/fucci2a.csv`, `data/arl13b.csv`, `data/multistage.csv`
3. Run the update script:
   ```bash
   python update_data.py
   ```
4. Commit and push:
   ```bash
   git add index.html
   git commit -m "Update citation data"
   git push
   ```

GitHub Pages will update automatically within a minute or two.

### Preserving mouse-use verification

The script automatically classifies funders, research fields, and author independence from the Scopus data. Mouse-use verification (confirmed / needs verification / unclassified) requires manual methods-section review and cannot be automated.

To preserve verified classifications across updates, maintain `data/verification.csv` with columns:

| Column | Description |
|---|---|
| `doi` | Paper DOI |
| `verification_status` | `confirmed_mouse_user`, `needs_verification`, or `unclassified` |
| `verification_note` | Free text note |
| `verification_category` | Application area (e.g. Cardiac, Kidney) |

The script will merge this into the new data automatically on DOI match.

### What the script classifies automatically

| Feature | Method |
|---|---|
| Funder | Regex against Scopus Funding Details field |
| Research field | Regex against title + abstract + keywords |
| Independence | Author list checked against close collaborator set |
| High-impact journal | Impact factor lookup (JCR/Clarivate; update annually in script) |

### What the script does not include

Mouse/material distribution records (RIKEN BRC, EMMA, direct from lab) are **excluded intentionally** for GDPR compliance. Only publicly available bibliographic data is present in this repository.

## Data

Citation data sourced from Scopus (exported June 2026). 244 citing papers across 189+ institutions in 28 countries, 2015–2026.

## Licence

[Creative Commons Attribution 4.0 International (CC BY 4.0)](LICENSE)

## Contact

[r.mort@lancaster.ac.uk](mailto:r.mort@lancaster.ac.uk)
