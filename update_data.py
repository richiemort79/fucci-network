#!/usr/bin/env python3
"""
update_data.py — Regenerate index.html from fresh Scopus exports.

Usage:
    python update_data.py

Input files expected in data/:
    fucci2a.csv       Scopus export for Mort et al. 2014 (Cell Cycle)
    arl13b.csv        Scopus export for Ford, Mort et al. 2018 (Dev Cell)
    multistage.csv    Scopus export for Yates, Ford & Mort 2017 (Bull Math Biol)

Optional (to preserve manual mouse-use verification):
    data/verification.csv   Previously exported verified paper list
                            (must contain columns: doi, verification_status,
                             verification_note, verification_category)

Output:
    index.html        Updated interactive network (GDPR-safe, no distribution data)

Requires: pandas
    pip install pandas

What this script does:
    - Parses Scopus CSV exports and extracts title, authors, journal, year,
      institution (first-listed affiliation), country, DOI, citation count
    - Classifies each paper's funders from the Funding Details field
    - Classifies each paper's research field from title/abstract/keywords
    - Flags papers with collaborator co-authors (non-independent)
    - Looks up journal impact factors and flags high-impact journals (IF > 10)
    - Merges verification status from a previous run (if data/verification.csv exists)

What this script does NOT do:
    - Mouse-use verification — this requires manual methods-section review.
      Preserve your verified data by keeping data/verification.csv up to date.
    - Distribution data (RIKEN/EMMA) — excluded intentionally for GDPR.
"""

import json
import re
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas is required: pip install pandas")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR  = Path("data")
TEMPLATE  = Path("template.html")
OUTPUT    = Path("index.html")

SOURCE_FILES = {
    "fucci2a": DATA_DIR / "fucci2a.csv",
    "arl13b":  DATA_DIR / "arl13b.csv",
    "markov":  DATA_DIR / "multistage.csv",
}

VERIFICATION_CSV = DATA_DIR / "verification.csv"

# Close collaborator author set — papers co-authored by these people are flagged
# as non-independent. Update if the collaborator circle changes.
COLLAB_NAMES = {
    "mort r.l.", "ford m.j.", "yates c.a.",
    "sakaue-sawano a.", "miyawaki a."
}

# Journal impact factors (JCR/Clarivate 2023/2024). Update annually.
# Papers in journals with IF > IF_THRESHOLD are flagged as high-impact.
IF_THRESHOLD = 10.0
JOURNAL_IF = {
    "nature": 50.5,
    "science": 44.7,
    "cell": 45.5,
    "nature communications": 15.7,
    "nature communications ": 15.7,
    "nature cell biology": 16.6,
    "nature reviews genetics": 41.4,
    "nature reviews nephrology": 33.3,
    "nature structural and molecular biology": 12.8,
    "cell stem cell": 19.8,
    "molecular cell": 16.6,
    "cancer cell": 38.6,
    "cancer discovery": 28.2,
    "developmental cell": 10.7,
    "circulation research": 16.2,
    "journal of clinical investigation": 13.3,
    "science advances": 11.7,
    "science advances ": 11.7,
    "science translational medicine": 15.8,
    "neuron": 14.0,
    "blood": 20.3,
    "trends in cell biology": 13.6,
    "advanced science": 14.3,
    "cancer research": 11.2,
    "kidney international": 11.1,
    "genome medicine": 10.3,
    "cardiovascular research": 10.5,
    "seminars in cancer biology": 10.5,
    "annual review of biochemistry": 11.4,
    "journal of the american society of nephrology": 9.6,
    "embo journal": 9.4,
    "molecular systems biology": 8.1,
    "proceedings of the national academy of sciences of the united states of america": 9.1,
    "elife": 6.4,
    "current biology": 7.3,
    "journal of cell biology": 6.1,
    "plos biology": 5.5,
    "cell reports": 7.5,
    "physical review x": 15.7,
}

# ---------------------------------------------------------------------------
# Helpers: extract institution and country from Scopus affiliation strings
# ---------------------------------------------------------------------------

# Common country suffixes that appear at the end of Scopus affiliation entries
COUNTRY_SUFFIXES = [
    "United States", "United Kingdom", "China", "Japan", "Germany", "France",
    "Italy", "Canada", "Australia", "Netherlands", "Sweden", "Denmark",
    "Finland", "Norway", "Spain", "Switzerland", "Belgium", "South Korea",
    "Republic of Korea", "Korea", "India", "Brazil", "Israel", "Singapore",
    "Austria", "Poland", "Czech Republic", "Portugal", "Greece", "Turkey",
    "Taiwan", "Russia", "Russian Federation", "Ireland", "New Zealand",
    "Argentina", "Mexico", "Hungary", "Romania", "Croatia", "Egypt",
    "South Africa", "Iran",
]

def extract_institution_country(affiliations_str):
    """Extract first-listed institution name and country from Scopus Affiliations field."""
    if not affiliations_str or pd.isna(affiliations_str):
        return "", ""
    first = str(affiliations_str).split(";")[0].strip()
    # Country is typically the last comma-separated element (possibly with a postcode)
    parts = [p.strip() for p in first.split(",")]
    country = ""
    for suffix in COUNTRY_SUFFIXES:
        if any(suffix.lower() in p.lower() for p in parts[-3:]):
            country = suffix
            break
    # Institution is the first element
    institution = parts[0] if parts else ""
    return institution, country

# ---------------------------------------------------------------------------
# Funder classifier
# ---------------------------------------------------------------------------

FUNDER_PATTERNS = [
    (r"national institutes of health|\bnih\b|national cancer institute|\bnci\b|national institute of general medical sciences|\bnigms\b|national heart,? lung,? and blood|\bnhlbi\b|national institute on aging|\bnia(?!\w)|national institute of child|\bnichd\b|national institute of diabetes|\bniddk\b|national institute of neurological|\bninds\b|national eye institute|\bnei\b|national human genome", "NIH (USA)"),
    (r"national science foundation|\bnsf\b(?!\w)", "NSF (USA)"),
    (r"wellcome trust|\bwellcome\b", "Wellcome Trust (UK)"),
    (r"medical research council|\bmrc\b(?!\w)", "MRC (UK)"),
    (r"biotechnology and biological sciences research council|\bbbsrc\b", "BBSRC (UK)"),
    (r"cancer research uk|\bcruk\b", "Cancer Research UK"),
    (r"engineering and physical sciences research council|\bepsrc\b", "EPSRC (UK)"),
    (r"european research council|\berc\b(?!\w)", "ERC (EU)"),
    (r"horizon 2020|h2020|european commission|european union.{0,15}(funding|grant)|marie.{0,10}curie", "EU / Horizon (EU)"),
    (r"national natural science foundation of china|\bnsfc\b", "NSFC (China)"),
    (r"china scholarship council|\bcsc\b(?!\w)", "China Scholarship Council"),
    (r"japan society for the promotion of science|\bjsps\b", "JSPS (Japan)"),
    (r"ministry of education, culture, sports, science|\bmext\b", "MEXT (Japan)"),
    (r"japan agency for medical research and development|\bamed\b", "AMED (Japan)"),
    (r"deutsche forschungsgemeinschaft|\bdfg\b", "DFG (Germany)"),
    (r"german federal ministry|bundesministerium", "BMBF (Germany)"),
    (r"canadian institutes of health research|\bcihr\b", "CIHR (Canada)"),
    (r"natural sciences and engineering research council|\bnserc\b", "NSERC (Canada)"),
    (r"australian research council|\barc\b(?!\w)", "ARC (Australia)"),
    (r"national health and medical research council|\bnhmrc\b", "NHMRC (Australia)"),
    (r"swedish research council|vetenskapsr", "Swedish Research Council"),
    (r"swiss national science foundation|\bsnsf\b", "SNSF (Switzerland)"),
    (r"agence nationale de la recherche|\banr\b(?!\w)", "ANR (France)"),
    (r"inserm", "INSERM (France)"),
    (r"netherlands organisation for scientific research|\bnwo\b", "NWO (Netherlands)"),
    (r"national research foundation of korea|\bnrf\b", "NRF (Korea)"),
    (r"ministry of science and technology", "MOST"),
    (r"european molecular biology organization|\bembo\b", "EMBO"),
    (r"howard hughes medical institute|\bhhmi\b", "HHMI (USA)"),
    (r"leukemia.{0,3}lymphoma society", "Leukemia & Lymphoma Society"),
    (r"american cancer society|\bacs\b(?!\w)", "American Cancer Society"),
    (r"damon runyon", "Damon Runyon Cancer Research Foundation"),
    (r"royal society", "Royal Society (UK)"),
    (r"academy of medical sciences", "Academy of Medical Sciences (UK)"),
    (r"\briken\b", "RIKEN (Japan)"),
    (r"howard hughes", "HHMI (USA)"),
]

def classify_funders(text):
    t = (text or "").lower()
    return sorted({label for pat, label in FUNDER_PATTERNS if re.search(pat, t)})

# ---------------------------------------------------------------------------
# Field classifier
# ---------------------------------------------------------------------------

FIELD_PATTERNS = [
    ("Cancer / oncology",                     r"\bcancer\b|\btumo[ur]r|carcinoma|oncogen|leukemia|lymphoma|melanoma|sarcoma|metasta"),
    ("Kidney / renal",                        r"\bkidney\b|\brenal\b|nephro"),
    ("Cardiovascular",                        r"\bcardiac\b|\bheart\b|cardiomyocyte|vascular|endotheli|angiogenesis|cardiovascular|atherosclero"),
    ("Neuroscience",                          r"\bneuron|\bbrain\b|neural|cortex|neurodevelop|\bglia|oligodendrocyte|astrocyte|synap"),
    ("Stem cell / regeneration",              r"stem cell|regenerat|organoid|pluripotent|\bipsc|reprogram"),
    ("Developmental biology",                 r"\bembryo|development(al)?\b|morphogenesis|organogenesis|gastrulation|limb bud"),
    ("Cilia / ciliopathy",                    r"\bcilia|ciliary|ciliopathy|flagell|centrosome|centriole|basal bod"),
    ("Immunology",                            r"\bimmune\b|immunolog|lymphocyte|macrophage|inflammat|\bt cell|\bb cell"),
    ("Skin / wound healing",                  r"\bskin\b|epiderm|dermal|wound heal|fibroblast"),
    ("Liver / hepatic",                       r"\bliver\b|hepatic|hepatocyte|cholangiocyte"),
    ("Mathematical / computational modeling", r"\bmodel(l)?ing\b|simulation|stochastic|markov|differential equation|computational|agent-based|in silico"),
    ("Microscopy / imaging methods",          r"live imaging|light sheet|microscop|image analysis|imaging technique"),
]

def classify_fields(text):
    t = (text or "").lower()
    hits = [label for label, pat in FIELD_PATTERNS if re.search(pat, t)]
    return hits if hits else ["General cell biology / other"]

# ---------------------------------------------------------------------------
# Parse one Scopus CSV
# ---------------------------------------------------------------------------

def norm_author(a):
    return a.strip().lower()

def get(row, col, default=""):
    val = row.get(col, default)
    return "" if pd.isna(val) else str(val)

def parse_csv(path):
    df = pd.read_csv(path)
    records = []
    for _, row in df.iterrows():
        authors_raw = get(row, "Authors")
        authors_list = [a.strip() for a in authors_raw.split(";") if a.strip()]
        author_names = {norm_author(a) for a in authors_list}
        has_collab = bool(author_names & COLLAB_NAMES)

        institution, country = extract_institution_country(get(row, "Affiliations"))

        journal = get(row, "Source title").strip()
        impact_factor = JOURNAL_IF.get(journal.lower())
        high_impact = bool(impact_factor and impact_factor > IF_THRESHOLD)

        full_text = " ".join([
            get(row, "Title"),
            get(row, "Abstract"),
            get(row, "Author Keywords"),
            get(row, "Index Keywords"),
        ])

        records.append({
            "title":                    get(row, "Title").strip(),
            "year":                     int(row["Year"]) if pd.notna(row.get("Year")) else None,
            "authors":                  authors_raw,
            "authors_list":             authors_list,
            "source":                   journal,
            "cited":                    int(row["Cited by"]) if pd.notna(row.get("Cited by")) else 0,
            "institution":              institution,
            "country":                  country,
            "doi":                      get(row, "DOI").strip(),
            "verification_status":      "unclassified",
            "verification_note":        "",
            "verification_category":    "",
            "journal_impact_factor":    impact_factor,
            "high_impact_journal":      high_impact,
            "funders":                  classify_funders(get(row, "Funding Details")),
            "has_collaborator_author":  has_collab,
            "collaborator_authors_found": sorted(author_names & COLLAB_NAMES),
            "fields":                   classify_fields(full_text),
        })
    return records

# ---------------------------------------------------------------------------
# Merge verification data from previous run
# ---------------------------------------------------------------------------

def merge_verification(papers, csv_path):
    """Overwrite verification fields for any DOI found in the verification CSV."""
    vdf = pd.read_csv(csv_path)
    required = {"doi", "verification_status"}
    if not required.issubset(set(vdf.columns)):
        print(f"  WARNING: {csv_path} missing columns {required - set(vdf.columns)} — skipping merge")
        return papers

    lookup = {}
    for _, row in vdf.iterrows():
        doi = str(row.get("doi", "") or "").strip().lower()
        if doi:
            lookup[doi] = {
                "verification_status":   str(row.get("verification_status", "unclassified") or "unclassified"),
                "verification_note":     str(row.get("verification_note", "") or ""),
                "verification_category": str(row.get("verification_category", "") or ""),
            }

    merged = 0
    for recs in papers.values():
        for r in recs:
            doi = r.get("doi", "").strip().lower()
            if doi in lookup:
                r.update(lookup[doi])
                merged += 1

    print(f"  Merged verification status for {merged} papers from {csv_path}")
    return papers

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    missing = [p for p in SOURCE_FILES.values() if not p.exists()]
    if missing:
        sys.exit(
            f"Missing input files: {', '.join(str(p) for p in missing)}\n"
            f"Place Scopus CSV exports in data/:\n"
            f"  data/fucci2a.csv\n  data/arl13b.csv\n  data/multistage.csv"
        )
    if not TEMPLATE.exists():
        sys.exit(f"Missing {TEMPLATE} — should contain a __DATA__ placeholder.")

    print("Parsing Scopus exports...")
    papers = {}
    for key, path in SOURCE_FILES.items():
        papers[key] = parse_csv(path)
        print(f"  {key}: {len(papers[key])} citing papers")

    if VERIFICATION_CSV.exists():
        print("Merging mouse-use verification data...")
        papers = merge_verification(papers, VERIFICATION_CSV)
    else:
        print(f"  No {VERIFICATION_CSV} found — all papers set to 'unclassified'.")
        print(f"  To preserve verification: export data/verification.csv with columns:")
        print(f"  doi, verification_status, verification_note, verification_category")

    all_recs = [r for recs in papers.values() for r in recs]
    total    = len(all_recs)
    n_indep  = sum(1 for r in all_recs if not r["has_collaborator_author"])
    n_hi_if  = sum(1 for r in all_recs if r["high_impact_journal"])
    n_fund   = len({f for r in all_recs for f in r["funders"]})
    n_conf   = sum(1 for r in all_recs if r["verification_status"] == "confirmed_mouse_user")
    countries = len({r["country"] for r in all_recs if r["country"]})
    insts     = len({r["institution"] for r in all_recs if r["institution"]})

    print(f"\nSummary:")
    print(f"  {total} citing papers")
    print(f"  {n_indep} ({100*n_indep//total}%) fully independent (no collaborator co-author)")
    print(f"  {n_hi_if} in journals with IF > {IF_THRESHOLD}")
    print(f"  {n_conf} confirmed mouse users")
    print(f"  {n_fund} distinct funding bodies identified")
    print(f"  {insts}+ institutions | {countries} countries")

    data_json = json.dumps(papers).replace("</script", "<\\/script")
    html      = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", data_json)
    OUTPUT.write_text(html, encoding="utf-8")

    print(f"\nWrote {OUTPUT} ({len(html)//1024} KB)")
    print("Commit and push to update the live site:")
    print("  git add index.html && git commit -m 'Update citation data' && git push")

if __name__ == "__main__":
    main()
