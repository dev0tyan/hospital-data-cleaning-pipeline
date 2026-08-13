# Project 1: Hospital Data Cleaning Pipeline — Build Documentation

This document walks through every step of building the cleaning pipeline for
`hospital_patients_real_world.csv`, explaining what each piece of code does,
why it was written that way, and what the results at each stage revealed.
It's meant to be read alongside the notebook — each section maps to one step
in the build.

**Design principle used throughout:** flag data problems explicitly rather
than silently dropping or imputing them. This dataset showed no reliable
statistical relationships between fields (confirmed in the EDA), so guessing
at missing/bad values would fabricate data rather than recover it. Every
function below either **fixes a provably systematic bug** or **flags an
issue for a downstream user to decide on** — nothing is silently discarded.

---

## Step 1 — Setup + Baseline Audit

### Code: Load the data
```python
import pandas as pd
import numpy as np

df = pd.read_csv('/kaggle/input/YOUR-DATASET-FOLDER/hospital_patients_real_world.csv')

print(df.shape)
df.head()
```
**What it does:** Imports pandas/numpy and loads the raw CSV into a DataFrame.
`df.shape` confirms row/column counts (5,000 rows × 7 columns) and `.head()`
gives a quick visual sanity check that columns loaded correctly and nothing
got mis-parsed (e.g., dates as strings instead of numbers, etc.).

### Code: `audit_report()` function
```python
def audit_report(df: pd.DataFrame) -> dict:
    """Quantify known data quality issues. Returns a dict summary."""
    report = {}

    # Missingness
    report['missing_counts'] = df[['Age', 'Gender', 'Diagnosis']].isnull().sum().to_dict()
    missing_mask = df[['Age', 'Gender', 'Diagnosis']].isnull()
    report['rows_missing_all_three'] = int((missing_mask.sum(axis=1) == 3).sum())

    # Diagnosis casing duplicates
    non_null_dx = df['Diagnosis'].dropna()
    report['diagnosis_raw_categories'] = non_null_dx.nunique()
    report['diagnosis_normalized_categories'] = non_null_dx.str.strip().str.title().nunique()

    # LOS validity
    admit = pd.to_datetime(df['AdmissionDate'])
    discharge = pd.to_datetime(df['DischargeDate'])
    los = (discharge - admit).dt.days
    report['negative_los_count'] = int((los < 0).sum())
    report['negative_los_values'] = sorted(los[los < 0].unique().tolist())

    # Duplicates
    report['duplicate_rows'] = int(df.duplicated().sum())
    report['duplicate_patient_ids'] = int(df['PatientID'].duplicated().sum())

    return report

baseline = audit_report(df)
for k, v in baseline.items():
    print(f"{k}: {v}")
```

**What it does, piece by piece:**

| Line(s) | Purpose |
|---|---|
| `df[['Age','Gender','Diagnosis']].isnull().sum()` | Counts nulls per column — gives the raw missingness numbers (350 each). |
| `missing_mask.sum(axis=1) == 3` | Sums `True`/`False` across the row (axis=1) to see how many of the three columns are null *for that row*, then counts how many rows hit all three. This is the first pass at understanding whether missingness is clustered or scattered. |
| `non_null_dx.nunique()` vs `.str.strip().str.title().nunique()` | Compares category count before and after normalizing whitespace/case — the gap between these two numbers (28 vs 14) is what reveals the casing-duplication bug. |
| `(discharge - admit).dt.days` | Computes Length of Stay in days by subtracting two datetime columns; `.dt.days` extracts the day count from the resulting `Timedelta`. |
| `los[los < 0].unique()` | Pulls the distinct negative LOS values — this is what revealed **every single one was exactly −5**, the key clue that pointed to a systematic bug rather than random noise. |
| `df.duplicated()` / `df['PatientID'].duplicated()` | Standard duplicate-row and duplicate-key checks. |

**Purpose of building this as a function (not just inline cells):** it lets
us call `audit_report()` again later on the *cleaned* data and compare
before/after side-by-side — this becomes the scorecard in Step 6.

**Result obtained:**
```
missing_counts: {'Age': 350, 'Gender': 350, 'Diagnosis': 350}
rows_missing_all_three: 2
diagnosis_raw_categories: 28
diagnosis_normalized_categories: 14
negative_los_count: 150
negative_los_values: [-5]
duplicate_rows: 0
duplicate_patient_ids: 0
```
The `rows_missing_all_three: 2` result was the important surprise here — it
disproved the initial hypothesis (from the earlier EDA) that the 350 missing
values formed one shared block. That single number changed the entire
strategy for Step 3.

---

## Step 2 — Understand the Missingness Pattern

### Code
```python
missing_mask = df[['Age', 'Gender', 'Diagnosis']].isnull()
pattern_counts = missing_mask.sum(axis=1).value_counts().sort_index()
print(pattern_counts)
```
**What it does:** Same row-wise null count as before, but instead of just
checking "is it 3", `.value_counts()` shows the **full distribution** —
how many rows have 0, 1, 2, or 3 missing fields.

**Why this matters:** If the three columns were missing *independently* at
random (each with its own ~7% chance of being null), basic probability
predicts roughly 4,020 / 900 / 68 / 2 rows for the 0/1/2/3-missing buckets.
The actual result (4,005 / 942 / 51 / 2) is close enough to that expected
shape to confirm **independent random missingness** rather than one shared
outage — this is what justified flagging instead of block-dropping.

**Result obtained:**
```
0    4005
1     942
2      51
3      2
```

---

## Step 3 — Fix Diagnosis Casing

### Code
```python
def normalize_diagnosis(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize Diagnosis casing/whitespace. Preserves NaN."""
    df = df.copy()
    df['Diagnosis'] = df['Diagnosis'].str.strip().str.title()
    return df

df_clean = normalize_diagnosis(df)
```
**What it does:**
- `df.copy()` — makes a copy so the original `df` stays untouched (important
  for later before/after comparisons in the scorecard).
- `.str.strip()` — removes leading/trailing whitespace (defensive; guards
  against invisible formatting issues even though none were found here).
- `.str.title()` — converts to Title Case (`"CHOLELITHIASIS"` →
  `"Cholelithiasis"`, `"cholelithiasis"` → `"Cholelithiasis"`), collapsing
  case-variant duplicates into one canonical spelling.
- Because pandas string methods skip `NaN` automatically, the 350 missing
  diagnosis values stay `NaN` rather than becoming the string `"Nan"` — this
  was a deliberate check, not an accident.

**Result obtained:** 28 raw categories → 14 normalized categories, with
counts re-distributing cleanly (e.g., `Cholelithiasis` went from 338 to 363
after absorbing its 25 `CHOLELITHIASIS` duplicates).

---

## Step 4 — Flag (Not Impute) Missing Values

### Code
```python
def flag_missingness(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add explicit missingness flags for Age, Gender, Diagnosis rather than
    imputing — this dataset shows no reliable correlation to impute from,
    so filling values would fabricate data rather than recover it.
    """
    df = df.copy()
    for col in ['Age', 'Gender', 'Diagnosis']:
        df[f'{col}_missing'] = df[col].isnull()

    df['missing_field_count'] = df[['Age_missing', 'Gender_missing', 'Diagnosis_missing']].sum(axis=1)
    return df

df_clean = flag_missingness(df_clean)
```
**What it does:**
- Loops over the three at-risk columns and creates a companion boolean
  column (e.g., `Age_missing`) that's `True` wherever the original value is
  null. The original `Age`/`Gender`/`Diagnosis` values are **left untouched**
  — still `NaN` where they were `NaN`.
- `missing_field_count` sums the three boolean flags per row (booleans act
  as 1/0 in `.sum()`), giving a single number (0–3) for "how many of these
  three fields are missing on this row" — this is what let us pull up the
  two fully-empty rows on demand.

**Why flag instead of impute:** the EDA showed near-zero correlation between
these fields and anything else in the dataset (e.g., Age vs. LOS: r ≈ −0.02).
Without a real relationship to model, any imputed value (mean age, most
common diagnosis, etc.) would be a guess dressed up as data — risky in a
healthcare context. Explicit flags let each downstream project decide for
itself whether to exclude, impute, or ignore these rows based on its own
requirements.

**Result:** confirmed the two fully-null rows (`PN-8178896`, `PN-6739983`)
still had valid PatientID, dates, and HospitalID — only the three flagged
columns were empty, so nothing else about those rows needed to be discarded.

---

## Step 5 — Fix the LOS Swap Bug

### Code: Hypothesis test (before touching anything)
```python
admit = pd.to_datetime(df_clean['AdmissionDate'])
discharge = pd.to_datetime(df_clean['DischargeDate'])
los = (discharge - admit).dt.days

neg_mask = los < 0
swapped_los = (admit[neg_mask] - discharge[neg_mask]).dt.days

print("Current negative LOS stats:")
print(los[neg_mask].describe())
print()
print("If admit/discharge were swapped for these rows, LOS would be:")
print(swapped_los.describe())
```
**What it does:** Before writing any "fix," this tests a specific theory —
that for these 150 rows, `AdmissionDate` and `DischargeDate` were swapped at
the data source. `admit[neg_mask] - discharge[neg_mask]` computes what LOS
*would* be if the two columns were reversed, without actually changing the
data yet. `.describe()` shows the resulting distribution's shape.

**Why this step exists:** it's tempting to "fix" a negative number by just
taking its absolute value — but that's a guess, not a diagnosis. Testing the
swap hypothesis first proves *why* the bug happened, which matters because
a wrong assumption here could quietly corrupt 150 rows in a way that looks
plausible but isn't true.

**Result obtained:** the swapped LOS came out as **exactly 5.0 for all 150
rows, with zero variance** — landing right in the middle of the healthy 1–10
day range seen everywhere else in the dataset. That's about as strong a
confirmation as real-world data ever gives you, so the swap hypothesis was
accepted as fact rather than a guess.

### Code: Apply the fix
```python
def fix_los_swap(df: pd.DataFrame) -> pd.DataFrame:
    """
    Swap AdmissionDate/DischargeDate for rows where the swap produces
    exactly a +5 day LOS (validated hypothesis: source bug swapped these
    two columns for a subset of rows). Only touches rows matching this
    exact signature — doesn't guess on other negative values if any exist.
    """
    df = df.copy()
    admit = pd.to_datetime(df['AdmissionDate'])
    discharge = pd.to_datetime(df['DischargeDate'])
    los = (discharge - admit).dt.days

    swap_mask = los == -5  # exact signature we validated

    df['LOS_was_swapped'] = swap_mask
    df.loc[swap_mask, ['AdmissionDate', 'DischargeDate']] = \
        df.loc[swap_mask, ['DischargeDate', 'AdmissionDate']].values

    return df

df_clean = fix_los_swap(df_clean)
df_clean['AdmissionDate'] = pd.to_datetime(df_clean['AdmissionDate'])
df_clean['DischargeDate'] = pd.to_datetime(df_clean['DischargeDate'])
df_clean['LOS'] = (df_clean['DischargeDate'] - df_clean['AdmissionDate']).dt.days
```
**What it does:**
- `swap_mask = los == -5` — deliberately matches the **exact** validated
  signature (−5 days) rather than a general `los < 0` check. This is a
  safety choice: if some *other* negative value existed for a different
  reason (e.g., −1 day from a genuine typo), this code would leave it alone
  rather than blindly "fixing" it with an unproven assumption.
- `df.loc[swap_mask, ['AdmissionDate','DischargeDate']] = df.loc[swap_mask, ['DischargeDate','AdmissionDate']].values`
  — this is the actual swap. It selects the two columns in reversed order
  for just the flagged rows and assigns them back; using `.values` strips
  the column labels during assignment so pandas doesn't try to align them
  by name (which would cancel the swap out).
- `LOS_was_swapped` — a permanent audit trail flag, so anyone looking at the
  cleaned data later can see exactly which rows were altered and why,
  rather than the fix being invisible.
- The three lines after the function call **recompute LOS from the now-
  corrected dates** — the LOS column itself is derived, not stored, so it
  has to be rebuilt after the underlying dates change.

**Result obtained:** 150 rows swapped, 0 negative LOS remaining, and the
recomputed LOS distribution came back healthy (mean 5.45, range 1–10, no
negatives) — matching the rest of the dataset.

---

## Step 6 — Flag Implausible Age–Diagnosis Pairs

### Code
```python
ADULT_ONLY_CONDITIONS = {
    'Type 2 Diabetes', 'Osteoarthritis', 'Myocardial Infarction',
    'Hypertension', 'Atrial Fibrillation', 'Chronic Kidney Disease'
}

def flag_implausible_age_diagnosis(df: pd.DataFrame) -> pd.DataFrame:
    """Flag Age == 0 rows paired with adult-only diagnoses."""
    df = df.copy()
    df['implausible_age_diagnosis'] = (
        (df['Age'] == 0) & (df['Diagnosis'].isin(ADULT_ONLY_CONDITIONS))
    )
    return df

df_clean = flag_implausible_age_diagnosis(df_clean)
```
**What it does:**
- `ADULT_ONLY_CONDITIONS` is a hand-picked set of diagnoses that don't
  realistically occur in a newborn (Age = 0) — this is a **domain-knowledge
  rule**, not something derived statistically from the data itself.
- `(df['Age'] == 0) & (df['Diagnosis'].isin(ADULT_ONLY_CONDITIONS))` — a
  vectorized boolean condition: `True` only where *both* conditions hold.
  The `&` (not `and`) is required here because this operates element-wise
  across the whole column, not on a single value.
- Same flag-don't-delete pattern as before: the row stays in the dataset,
  just marked for review.

**Result obtained:** 21 rows flagged (out of 52 total Age = 0 records) — the
other ~31 infant records were paired with plausible pediatric conditions
(Asthma, Pneumonia, UTI, etc.) and correctly left unflagged.

---

## Step 7 — Full Pipeline + Before/After Scorecard

### Code: `clean_hospital_data()`
```python
def clean_hospital_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Full cleaning pipeline for hospital_patients_real_world.csv.
    Steps: normalize diagnosis casing -> flag missingness ->
    fix LOS swap bug -> recompute LOS -> flag implausible pairs.
    """
    df = raw_df.copy()
    df = normalize_diagnosis(df)
    df = flag_missingness(df)
    df = fix_los_swap(df)
    df['AdmissionDate'] = pd.to_datetime(df['AdmissionDate'])
    df['DischargeDate'] = pd.to_datetime(df['DischargeDate'])
    df['LOS'] = (df['DischargeDate'] - df['AdmissionDate']).dt.days
    df = flag_implausible_age_diagnosis(df)
    return df
```
**What it does:** Chains every function built so far into a single call.
Each function takes a DataFrame and returns a new one, so they compose
cleanly in sequence — this is the difference between "a notebook full of
cells that worked once" and an actual **reusable pipeline**: you can now run
`clean_hospital_data(df)` on any fresh copy of the raw file and get the same
result deterministically.

### Code: `scorecard()`
```python
def scorecard(raw_df: pd.DataFrame, clean_df: pd.DataFrame) -> pd.DataFrame:
    """Before/after comparison of key data quality metrics."""
    before = audit_report(raw_df)
    rows = [
        ('Rows', len(raw_df), len(clean_df)),
        ('Diagnosis categories (raw count)', before['diagnosis_raw_categories'],
            clean_df['Diagnosis'].dropna().nunique()),
        ('Negative LOS records', before['negative_los_count'],
            int((clean_df['LOS'] < 0).sum())),
        ('Rows with LOS swap corrected', '—', int(clean_df['LOS_was_swapped'].sum())),
        ('Rows flagged: missing Age', before['missing_counts']['Age'],
            int(clean_df['Age_missing'].sum())),
        ('Rows flagged: missing Gender', before['missing_counts']['Gender'],
            int(clean_df['Gender_missing'].sum())),
        ('Rows flagged: missing Diagnosis', before['missing_counts']['Diagnosis'],
            int(clean_df['Diagnosis_missing'].sum())),
        ('Rows flagged: implausible age/diagnosis', '—',
            int(clean_df['implausible_age_diagnosis'].sum())),
        ('Duplicate rows', before['duplicate_rows'], int(clean_df.duplicated().sum())),
    ]
    return pd.DataFrame(rows, columns=['Metric', 'Before', 'After'])

df_final = clean_hospital_data(df)
sc = scorecard(df, df_final)
print(sc.to_string(index=False))
```
**What it does:** Reuses the Step 1 `audit_report()` function on the
**original** raw `df` to get "before" numbers, then pulls matching "after"
numbers directly off the cleaned `df_final`. Packaging both into a small
DataFrame with `('Metric', 'Before', 'After')` rows makes the comparison
easy to read and easy to paste into a report.

**Why the missing-value counts stay identical before/after (350 → 350):**
this is intentional, not a bug — the pipeline never deletes or imputes those
rows, so the *presence* of missing data is unchanged. What changed is that
it's now **explicitly flagged and queryable** via `Age_missing`,
`Gender_missing`, `Diagnosis_missing` — the scorecard proves the flags are
tracking correctly, not that the missingness was "solved."

**Result obtained:**
```
Metric                                    Before   After
Rows                                        5000    5000
Diagnosis categories (raw count)              28      14
Negative LOS records                         150       0
Rows with LOS swap corrected                   —     150
Rows flagged: missing Age                    350     350
Rows flagged: missing Gender                 350     350
Rows flagged: missing Diagnosis              350     350
Rows flagged: implausible age/diagnosis        —      21
Duplicate rows                                 0       0
```

---

## Step 8 — Unit Tests

### Code
```python
def run_pipeline_tests(clean_df: pd.DataFrame):
    """Sanity checks on the cleaned dataset. Raises AssertionError if any fail."""
    assert len(clean_df) == 5000, f"Expected 5000 rows, got {len(clean_df)}"

    dx = clean_df['Diagnosis'].dropna()
    assert dx.nunique() == 14, f"Expected 14 diagnosis categories, got {dx.nunique()}"
    assert (dx == dx.str.title()).all(), "Some diagnosis values aren't Title Case"

    assert (clean_df['LOS'] < 0).sum() == 0, "Negative LOS values still present"
    assert clean_df['LOS_was_swapped'].sum() == 150, "Unexpected LOS swap count"

    assert clean_df['Age_missing'].sum() == 350
    assert clean_df['Gender_missing'].sum() == 350
    assert clean_df['Diagnosis_missing'].sum() == 350

    assert clean_df['PatientID'].duplicated().sum() == 0

    implausible = clean_df[clean_df['implausible_age_diagnosis']]
    assert (implausible['Age'] == 0).all(), "Implausible flag applied to non-zero age"

    print("All pipeline tests passed ✅")

run_pipeline_tests(df_final)
```
**What it does:** Each `assert` re-checks one specific guarantee the
pipeline is supposed to provide — row count preserved, casing normalized,
no negative LOS, swap count matches the validated hypothesis, missingness
flags match the raw counts exactly, no duplicate keys introduced, and the
implausibility flag logic is internally consistent (it should never fire on
a non-zero age). If any single line fails, Python raises an `AssertionError`
naming exactly which guarantee broke — so if this pipeline is rerun later on
an updated export of the data, a silent regression (e.g., a new negative LOS
value slipping in) gets caught immediately instead of quietly breaking
downstream analysis.

**Why this matters for a reusable pipeline:** without these checks, this
would just be a script that happened to work once. With them, it becomes
something safe to rerun and hand off to Projects 2–6.

---

## Step 9 — Export

### Code
```python
df_final.to_csv('/kaggle/working/hospital_patients_cleaned.csv', index=False)
print("Cleaned CSV saved to /kaggle/working/hospital_patients_cleaned.csv")
print(f"Shape: {df_final.shape}")
```
**What it does:** Writes the fully cleaned DataFrame — original columns
plus all the audit flags (`Age_missing`, `LOS_was_swapped`,
`implausible_age_diagnosis`, etc.) — to a CSV in Kaggle's writable output
directory. `index=False` prevents pandas from adding an extra unnamed index
column to the file.

### Code: Module export
```python
%%writefile /kaggle/working/hospital_cleaning.py
"""
Reusable cleaning pipeline for hospital_patients_real_world.csv.
"""
import pandas as pd

ADULT_ONLY_CONDITIONS = {
    'Type 2 Diabetes', 'Osteoarthritis', 'Myocardial Infarction',
    'Hypertension', 'Atrial Fibrillation', 'Chronic Kidney Disease'
}

def normalize_diagnosis(df): ...
def flag_missingness(df): ...
def fix_los_swap(df): ...
def flag_implausible_age_diagnosis(df): ...
def clean_hospital_data(raw_df): ...
```
**What it does:** `%%writefile` is a Jupyter/Kaggle "cell magic" command —
when it's the first line of a cell, everything below it gets written to a
file on disk *instead of* being executed in the notebook. This turns the
five functions built across Steps 3–7 into a real, importable Python module
(`hospital_cleaning.py`), so Project 2 onward can do:

```python
from hospital_cleaning import clean_hospital_data
df = clean_hospital_data(pd.read_csv('hospital_patients_real_world.csv'))
```

instead of re-copying cells into every new notebook.

---

## Summary: What This Pipeline Guarantees

| Guarantee | How it's enforced |
|---|---|
| No rows silently dropped | Row count asserted at 5,000 in tests |
| Diagnosis categories consistent | Casing normalized, tested at exactly 14 |
| No negative LOS | Swap bug fixed based on validated hypothesis, tested at 0 remaining |
| Missingness never hidden | Explicit `*_missing` flag columns, counts preserved and tested |
| Implausible values never hidden | `implausible_age_diagnosis` flag, not deletion |
| Reproducible | Single `clean_hospital_data()` entry point, callable on any fresh raw load |
| Regression-safe | `run_pipeline_tests()` catches any future data drift or logic break |
