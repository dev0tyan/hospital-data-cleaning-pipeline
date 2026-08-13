# Hospital Patient Data Cleaning Pipeline

A reusable, tested Python pipeline that audits and fixes a 5,000-record hospital
admissions dataset — built and documented step by step, including a validated
root-cause fix for a systematic date-swap bug that produced impossible
negative-length hospital stays.

**Status:** Complete | **Language:** Python (pandas) | **Environment:** Kaggle Notebook

---

## Table of Contents
1. [Background and Overview](#1-background-and-overview)
2. [Data Structure Overview](#2-data-structure-overview)
3. [Executive Summary](#3-executive-summary)
4. [Insights Deep Dive](#4-insights-deep-dive)
5. [Recommendations](#5-recommendations)

---

## 1. Background and Overview

Hospital admissions data looks clean at a glance — no missing columns, no
obviously broken rows if you just skim it. This project started with a
5,000-record synthetic hospital admissions dataset and asked a simple
question: **is it actually trustworthy enough to build anything on top of?**

The answer was no — not without fixing it first. A full exploratory audit
surfaced four distinct data quality problems, each requiring a different kind
of fix: a categorical-encoding bug, a missingness pattern, a systematic
date-entry bug, and a set of clinically implausible records. Rather than
patch each one ad hoc, this project builds a single, reusable, **tested**
cleaning pipeline — the kind of foundation any downstream analytics,
dashboard, or modeling work should sit on.

**Goals of this project:**
- Quantify every data quality issue before fixing anything (audit first, fix second)
- Fix root causes where provable, not just symptoms
- Flag — never silently drop or guess — anything that can't be confidently fixed
- Leave a fully reproducible, unit-tested pipeline that downstream projects can import and trust

**Tools used:** Python, pandas, NumPy, Jupyter/Kaggle Notebooks

---

## 2. Data Structure Overview

The raw dataset is a single flat table of hospital admission encounters.

| Column | Type | Description |
|---|---|---|
| `PatientID` | string | Unique encounter identifier (`PN-XXXXXXX`) |
| `Age` | float | Patient age in years (0–95) |
| `Gender` | string | Female / Male / Other / Unknown |
| `Diagnosis` | string | One of 14 conditions (raw data had inconsistent casing) |
| `AdmissionDate` | date | Range: 2023-05-11 to 2026-02-12 |
| `DischargeDate` | date | Range: 2023-05-12 to 2026-02-14 |
| `HospitalID` | string | One of 90 facilities (`HOSP-XX`) |

**5,000 rows, 7 raw columns, 90 hospitals, ~34 months of admissions.**

The cleaned output adds 7 columns on top of the original 7 (14 total) —
these are audit/flag columns produced by the pipeline, not new source data:

| Added column | Purpose |
|---|---|
| `Age_missing`, `Gender_missing`, `Diagnosis_missing` | Per-field missingness flags |
| `missing_field_count` | Count of missing fields (0–3) per row |
| `LOS_was_swapped` | Flags the 150 rows corrected for the date-swap bug |
| `LOS` | Recomputed length of stay, in days |
| `implausible_age_diagnosis` | Flags clinically implausible Age=0 + adult-only-diagnosis pairs |

No data is deleted or imputed by the pipeline — every added column exists to
make a data quality issue **visible and queryable**, so downstream users can
decide for themselves how to handle it.

---

## 3. Executive Summary

An initial audit of the raw dataset found it was **not analysis-ready**,
despite having no missing columns and no obviously broken schema. Four
distinct issues were identified and addressed:

| Issue | Scope | Resolution |
|---|---|---|
| Duplicate diagnosis categories from inconsistent casing | 321 records (6.9% of non-null diagnoses) | Normalized 28 raw categories → true 14 |
| Missing Age / Gender / Diagnosis | 350 rows (7%), independently distributed across fields | Flagged explicitly, not imputed (no reliable signal to impute from) |
| Impossible negative length-of-stay | 150 records, all exactly −5 days | Root cause identified (Admission/Discharge dates swapped) and corrected |
| Clinically implausible age–diagnosis pairs | 21 of 52 infant (Age=0) records | Flagged for review, not deleted |

**The most consequential finding** was the negative length-of-stay bug. Rather
than assume the values needed to be made positive, a swap hypothesis was
tested first: reversing `AdmissionDate` and `DischargeDate` for the affected
150 rows produced a uniform, exactly 5-day stay — landing precisely inside
the healthy 1–10 day range seen across the rest of the dataset. That result
confirmed a genuine upstream data bug rather than 150 unrelated typos, and
justified fixing the root cause instead of masking the symptom.

The result is a single `clean_hospital_data()` function, backed by seven
automated tests, that deterministically reproduces this cleaning process on
any fresh copy of the raw file.

---

## 4. Insights Deep Dive

### 4.1 Diagnosis field was silently double-counting
`"Cholelithiasis"` and `"CHOLELITHIASIS"` were treated as two separate
categories by any groupby, filter, or chart — with no error raised. Any
prior report built on the raw `Diagnosis` column (e.g., "how many patients
had Condition X") would have been undercounted with no warning sign. Fixed
by normalizing case and whitespace, collapsing 28 raw values into the true
14 categories.

### 4.2 Missingness was independent, not clustered
An initial hypothesis assumed the 350 rows missing Age, Gender, and
Diagnosis formed one shared "dropped intake block." Testing this directly
disproved it: only 2 rows were missing all three fields. The actual
distribution (4,005 / 942 / 51 / 2 rows missing 0/1/2/3 fields) closely
matches what independent, per-field ~7% random missingness would produce.
This mattered because it changed the fix — instead of discarding a block of
rows, each field is flagged independently, preserving the two-thirds of
otherwise-valid data in partially-missing rows.

**Design decision:** values were flagged, not imputed. An EDA correlation
check found no reliable relationship between Age, Gender, Diagnosis, and any
other field (e.g., Age vs. Length of Stay: r ≈ −0.02) — meaning there was no
statistically sound basis to guess a missing value from the rest of the row.
In a healthcare-adjacent context, fabricating a plausible-looking but
invented data point was judged a higher risk than leaving it explicitly null.

### 4.3 The −5 day length-of-stay bug — root cause, not symptom
150 records (3% of the dataset) showed a discharge date before the admission
date — clinically impossible. Every single one of these was **exactly**
−5 days, not a spread of small negative values, which ruled out random data
entry error. Testing the hypothesis that `AdmissionDate` and `DischargeDate`
had been swapped for these rows: reversing them produced a uniform,
zero-variance **+5 day** stay for all 150 records — a result too precise to
be coincidence. The fix reversed the two date columns for exactly this
validated 150-row signature (not a blanket `< 0` fix), and left a permanent
`LOS_was_swapped` audit flag on every corrected row.

### 4.4 Clinically implausible age–diagnosis pairs
All 52 records with Age = 0 (infants) were cross-checked against a
domain-knowledge list of adult-only conditions (Type 2 Diabetes,
Osteoarthritis, Myocardial Infarction, Hypertension, Atrial Fibrillation,
Chronic Kidney Disease). 21 of the 52 matched an adult-only diagnosis and
were flagged; the remaining ~31 were paired with plausible pediatric-
compatible conditions (e.g., Asthma, Pneumonia, UTI) and correctly left
unflagged.

### 4.5 A broader signal: this dataset shows no real clinical correlation structure
Across every relationship tested — age vs. length of stay, diagnosis vs.
length of stay, diagnosis vs. age, gender vs. diagnosis — there was
essentially no meaningful correlation. Length-of-stay averages were nearly
identical (5.3–5.7 days) across all 14 diagnoses, and age/gender/diagnosis
were all close to uniformly distributed. This is a strong signature of
synthetic/simulated data rather than real clinical records, and it directly
shapes what kind of downstream project makes sense (see Recommendations).

---

## 5. Recommendations

1. **Treat this pipeline as the required first step for any further work on
   this dataset.** Every downstream project (dashboards, benchmarking,
   modeling) should consume `clean_hospital_data()`'s output, not the raw
   CSV — the four issues above will silently corrupt naive downstream
   analysis otherwise.

2. **Do not build predictive models expecting strong performance on this
   data as-is.** The lack of real correlation between demographics,
   diagnosis, and length of stay means a model trained on it will likely
   perform barely above a naive baseline. Any modeling project should be
   framed as a methodology/pipeline exercise, ready to plug in richer
   clinical features (severity scores, comorbidities, lab values) if this
   is ever paired with real clinical data.

3. **Prioritize descriptive and operational analytics next** — a dashboard
   (admissions trends, LOS distribution, diagnosis mix, hospital
   benchmarking) delivers immediate, low-risk value on top of the now-
   trustworthy data, with no modeling assumptions required.

4. **Extend the anomaly-flagging logic into an ongoing monitor.** The same
   rules used here (casing drift, implausible age/diagnosis pairs, LOS
   sanity checks) could run automatically on any future data refresh to
   catch new issues before they reach downstream reports.

5. **If this pipeline is ever pointed at real patient data**, apply the same
   governance discipline this project used as a baseline, but treat privacy
   requirements (e.g., HIPAA or the Philippine Data Privacy Act of 2012) as
   mandatory rather than precautionary — de-identification, access controls,
   and a documented legal basis for processing health data would all be
   required.

---

## Repository Structure

```
.
├── README.md
├── requirements.txt
├── src/
│   └── hospital_cleaning.py       # Reusable pipeline module
├── notebooks/
│   └── 01_eda_and_cleaning.ipynb  # Full build notebook (Kaggle export)
├── docs/
│   ├── eda_and_project_strategy.md
│   └── project1_build_documentation.md
└── data/
    └── sample/
        └── hospital_patients_sample.csv   # Small sample only — see note below
```

> **Data note:** this dataset is treated as synthetic based on its uniform,
> uncorrelated statistical structure (see Insight 4.5). It is still handled
> under standard data-privacy discipline as a matter of practice. Only a
> small sample is committed to this repo; the full raw and cleaned CSVs are
> intentionally excluded via `.gitignore`.

## Quickstart

```python
import pandas as pd
from src.hospital_cleaning import clean_hospital_data

raw_df = pd.read_csv('data/hospital_patients_real_world.csv')
clean_df = clean_hospital_data(raw_df)
```

## License

MIT — see `LICENSE`.
