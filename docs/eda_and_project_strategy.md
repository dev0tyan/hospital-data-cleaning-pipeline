# Hospital Patient Dataset — Exploratory Data Analysis & Project Strategy Report

**Dataset:** `hospital_patients_real_world.csv`
**Records:** 5,000 patient encounters | **Fields:** 7 | **Hospitals:** 90
**Analyst:** Senior Data Science Review
**Date:** July 23, 2026

---

## 1. Dataset Overview

| Column | Type | Description | Non-null |
|---|---|---|---|
| PatientID | string | Unique encounter ID (`PN-XXXXXXX`) | 5,000 (100%) |
| Age | float | Patient age in years (0–95) | 4,650 (93%) |
| Gender | string | Female / Male / Other / Unknown | 4,650 (93%) |
| Diagnosis | string | One of 14 conditions (free-text, mixed case) | 4,650 (93%) |
| AdmissionDate | date | 2023-05-11 to 2026-02-12 | 5,000 (100%) |
| DischargeDate | date | 2023-05-12 to 2026-02-14 | 5,000 (100%) |
| HospitalID | string | 90 unique facilities (`HOSP-XX`) | 5,000 (100%) |

No duplicate rows or duplicate `PatientID` values exist — each row is a distinct encounter.

---

## 2. Data Quality Assessment

| Issue | Scope | Detail |
|---|---|---|
| **Missing values** | 350 rows (7%) | Age, Gender, and Diagnosis are missing together in nearly the same 350 rows (348 of them missing all three at once), suggesting a single dropped upstream field-group rather than three independent issues — consistent with a Missing-Completely-At-Random (MCAR) intake gap. |
| **Inconsistent categorical casing** | 321 records (6.9% of non-null diagnoses) | Diagnosis appears twice per condition — a Title Case version (e.g., "Cholelithiasis") and a duplicate ALL-CAPS version (e.g., "CHOLELITHIASIS"). This effectively doubles the category cardinality (28 raw values → 14 true conditions) and will silently break any groupby, model encoding, or filter unless normalized. |
| **Invalid negative length-of-stay** | 150 records (3%) | Discharge date precedes admission date. Notably, **every single one** of these is exactly **−5 days**, not a spread of small negative values — a strong signature of a systematic upstream bug (e.g., a swapped date pair or an off-by-one batch import error) rather than random data entry noise. |
| **Clinically implausible age–diagnosis pairs** | 52 records (1.1% of non-null age) | All Age = 0 records — infants — are paired with adult-only conditions such as Type 2 Diabetes, Osteoarthritis, and Myocardial Infarction. This is not clinically plausible and indicates random/synthetic field assignment rather than genuine linkage between age and diagnosis. |
| **"Unknown"/"Other" as valid Gender categories** | 1,163 "Unknown" + 1,223 "Other" (51% combined) | Over half of records fall outside binary Female/Male, which is unusually high for real-world EHR data and should be treated deliberately (not silently dropped) in any downstream analysis. |

**No outliers requiring treatment** were found in Age (bounded 0–95, no negative or >120 values) or LOS aside from the systematic −5 issue above.

---

## 3. Summary Statistics & Distributions

- **Age:** Mean 47.4, median 47, range 0–95, std 27.9. The histogram is essentially **flat/uniform** across the full range rather than showing the typical real-world hospital age skew toward older adults.
- **Gender:** Near-equal split across Female (23.1%), Male (22.2%), Other (24.5%), Unknown (23.3%) — statistically uniform, not reflective of typical population gender distributions.
- **Diagnosis:** 14 conditions, each roughly 275–345 records (excluding casing duplicates) — a **balanced/uniform class distribution**, atypical of real hospitals where common conditions (e.g., UTI, hypertension) usually dominate volume.
- **Length of Stay (valid records):** Uniform across 1–10 days (mean 5.4, std ~2.6), with **no long tail** — real LOS data is almost always right-skewed (most stays short, a few very long). This flat distribution is another synthetic-data signature.
- **Admissions over time:** ~150 admissions/month consistently from May 2023 to January 2026 (Feb 2026 is a partial month), with **no seasonality, trend, or weekday/weekend effect**.
- **HospitalID:** 90 facilities, each with 40–72 patients (mean 55.6) — evenly distributed, no dominant "hub" hospitals.

---

## 4. Key Patterns, Correlations & Insights

| Relationship tested | Finding |
|---|---|
| Age vs. LOS | r = −0.02 (no correlation) |
| LOS by Diagnosis | Range 5.27–5.74 days across all 14 conditions — clinically implausible near-equality (e.g., Osteoarthritis and Myocardial Infarction should differ substantially in real care) |
| Age by Diagnosis | Range 44.1–49.6 years across all conditions — no meaningful separation |
| Gender by Diagnosis | Roughly even counts across all four gender categories for every diagnosis |
| Admissions by month/hospital | No seasonal, cyclical, or facility-driven variation |

**Headline insight:** across every dimension tested, the data behaves like **independently, randomly generated fields** rather than a system with real clinical cause-and-effect. This isn't a criticism of the dataset's usefulness — it's a critical scoping fact that should shape which projects are worth pursuing and how their results should be framed (see Section 7).

---

## 5. Strengths, Limitations & Domain Opportunities

**Strengths**
- Clean relational structure, realistic-looking schema (patient/hospital/diagnosis/dates) that mirrors real EHR admission tables
- Sufficient volume (5,000 rows, 90 facilities, 34-month span) for meaningful aggregation and pipeline testing
- Deliberately-seeded data quality issues (missingness, casing, bad dates, implausible values) make it well-suited for **data cleaning and governance practice**
- Multi-hospital structure supports benchmarking-style analysis

**Limitations**
- No real statistical signal between demographics, diagnosis, and outcomes (LOS) — limits the ceiling of any predictive model built on it
- No clinical severity, vitals, labs, comorbidities, or cost/billing fields
- No outcome variables (readmission, mortality, discharge disposition)
- Single diagnosis per encounter, free text rather than coded (e.g., ICD-10)
- No patient-level linkage across multiple visits (each ID is a one-off encounter), so readmission/utilization-over-time analysis isn't possible as-is

**Domain opportunities**
- Strong candidate as a **template/sandbox dataset** for building a production-grade hospital analytics pipeline that could later be pointed at real EHR data
- Good foundation for **data governance and quality-monitoring tooling** demos
- Useful as a **benchmarking testbed** if paired with public real-world epidemiological base rates (e.g., WHO/DOH disease prevalence data) to validate synthetic realism

---

## 6. Ethical & Data Privacy Considerations

- Although the data is very likely **synthetic** (see Section 4), it should still be **handled under the same governance discipline as real Protected Health Information (PHI)** — this reinforces good habits and avoids risk if a similar pipeline is later pointed at real patient records.
- If any part of this analysis is extended to real hospital data, it would fall under HIPAA (if US-linked) or the Philippine **Data Privacy Act of 2012**, requiring de-identification, access controls, and a documented legal basis for processing health data.
- Diagnosis-based segmentation, even on synthetic IDs, can create stigmatizing groupings (e.g., "Diabetes cohort") — any dashboard or report should default to aggregate reporting and avoid exposing individual-level diagnosis with identifiers.
- The "Other"/"Unknown" Gender categories (51% of records) should be preserved and reported transparently, not silently collapsed into a binary — doing so would misrepresent over half the dataset.
- **Assumption flag:** this report assumes the dataset is synthetic based on its statistical flatness; if it later turns out to represent real patients, the privacy considerations above become mandatory rather than precautionary.

---

## 7. Recommended Projects

### Project 1 — Data Quality & ETL Cleaning Pipeline
**Objective:** Build a reusable, automated pipeline that standardizes diagnosis casing, resolves the MCAR missingness block, flags/corrects the systematic −5-day LOS bug, and validates age–diagnosis plausibility.
**Value:** Every other project depends on clean inputs; this is the foundation and highest-leverage first step.
**Techniques:** Pandas transformations, regex/string normalization, rule-based validation (e.g., Great Expectations or Pandera schemas), unit testing.
**Deliverables:** Reusable Python cleaning module, data quality scorecard report, documented data dictionary.
**Complexity:** Beginner–Intermediate | **Skills:** Python, pandas, data validation frameworks.
**Impact & scalability:** Directly reusable as an ingestion template for real EHR data; the validation rules scale naturally to streaming/batch pipelines.

### Project 2 — Interactive Hospital Operations Dashboard
**Objective:** A descriptive BI dashboard covering admission volume trends, LOS distribution, diagnosis mix, and hospital-level comparisons, filterable by date range, facility, and demographics.
**Value:** Gives administrators immediate operational visibility with no modeling risk — fast, low-cost win.
**Techniques:** Time-series resampling, groupby aggregation, interactive visualization.
**Deliverables:** Streamlit/Plotly Dash (or Power BI/Tableau) dashboard; a short methodology write-up.
**Complexity:** Beginner–Intermediate | **Skills:** Streamlit/Dash or BI tooling, SQL, visualization design.
**Impact & scalability:** Extends naturally to a multi-facility network monitoring tool if refreshed on a live data feed.

### Project 3 — Multi-Hospital Benchmarking & Resource Utilization Report
**Objective:** Compare admission volumes, average LOS, and diagnosis mix across all 90 hospitals to surface high/low-volume facilities and LOS-management outliers.
**Value:** Supports resource allocation and capacity-planning conversations at the network level.
**Techniques:** Groupby aggregation, ranking/scorecards, ANOVA or Kruskal-Wallis test for cross-hospital LOS differences.
**Deliverables:** Facility benchmarking report/dashboard with ranked scorecards.
**Complexity:** Beginner–Intermediate | **Skills:** pandas, basic inferential statistics, visualization.
**Impact & scalability:** Immediately actionable for network administrators; scales well once real capacity/cost/staffing data is layered in.

### Project 4 — Diagnosis & Demographic Cohort Segmentation
**Objective:** Segment the patient population by diagnosis, age band, gender, and facility; statistically test associations between categorical variables; cluster cohorts for pattern discovery.
**Value:** Surfaces population-level utilization patterns useful for planning targeted health programs.
**Techniques:** Chi-square tests of independence, K-means/hierarchical clustering on encoded features, heatmap visualization.
**Deliverables:** Cohort segmentation report, cluster visualizations, statistical test summary.
**Complexity:** Intermediate | **Skills:** Applied statistics (hypothesis testing), scikit-learn clustering, seaborn/matplotlib.
**Impact & scalability:** Extends to real public-health surveillance work if paired with epidemiological base-rate data.

### Project 5 — Anomaly & Data-Integrity Monitoring System
**Objective:** Turn the quality issues found in Section 2 into an ongoing, automated monitor that flags negative LOS, casing drift, implausible age–diagnosis pairs, and missing-field bursts as new data arrives.
**Value:** Protects analytic trust in any downstream reporting; catches upstream pipeline bugs (like the −5-day issue) before they propagate.
**Techniques:** Rule-based validation plus statistical outlier detection (IQR, Isolation Forest) for continuous monitoring.
**Deliverables:** Anomaly detection module, alerting logic, audit log/report.
**Complexity:** Intermediate | **Skills:** Python, rule engines, optionally `scikit-learn` anomaly detection.
**Impact & scalability:** Designed to run on a schedule or in a streaming context; a natural companion to Project 1.

### Project 6 — Length-of-Stay Predictive Modeling (Methodology Demonstration)
**Objective:** Build a regression model (linear → gradient boosting) predicting LOS from age, gender, diagnosis, hospital, and admission timing, to support discharge planning and bed-capacity forecasting.
**Value:** If real signal-bearing clinical data (severity, comorbidities, vitals) is later available, this becomes directly operationally useful for capacity forecasting.
**Techniques:** Feature engineering (day-of-week, categorical encoding), train/test split, cross-validation, feature importance analysis.
**Deliverables:** Trained model, evaluation report, feature importance chart, optional lightweight prediction API (FastAPI/Flask).
**Complexity:** Intermediate–Advanced | **Skills:** scikit-learn/XGBoost, model evaluation, API serving.
**⚠️ Important caveat:** As shown in Section 4, this dataset currently carries almost no real correlation between LOS and the available features (r ≈ −0.02, near-identical LOS means across diagnoses). A model trained on it will likely perform barely above a naive baseline. **Recommend framing this project explicitly as a pipeline/methodology exercise**, built so it's ready to plug in richer features (severity scores, comorbidity counts, lab values) the moment such data becomes available, rather than presenting current-data results as clinically meaningful.
**Impact & scalability:** High long-term value once paired with genuine clinical signal; low standalone value on this dataset today.

---

## 8. Suggested Extensions (Additional Data Sources)

To unlock materially deeper insight, this dataset would benefit from:
- **ICD-10 coded diagnoses** instead of free text, for standardized severity/comorbidity grouping
- **Vitals and lab results** to explain LOS and severity variation
- **Cost/billing data** for financial impact analysis
- **Outcome fields** (readmission flag, discharge disposition, mortality) to support outcome-driven modeling
- **Patient-level longitudinal linkage** (repeat visits by the same person) to enable readmission and chronic-utilization analysis
- **Geocoded hospital locations** to support spatial/regional demand analysis

---

## 9. Key Assumptions Made

1. The 350 rows missing Age, Gender, and Diagnosis together are treated as a single MCAR intake gap, not three unrelated missingness mechanisms, based on the near-total overlap.
2. `PatientID` is treated as a unique **encounter** identifier rather than a unique **person** identifier, since there's no way to confirm whether the same individual appears under different IDs across visits.
3. The 150 records with exactly −5-day LOS are treated as a systematic date-swap/import bug rather than 150 independently occurring data entry typos, given the identical magnitude.
4. The dataset is assumed to be **synthetic/simulated**, based on the uniform distributions and absence of any real clinical correlation structure — this assumption directly shapes the caveats attached to Project 6 above.

---

## 10. Priority Recommendation

For a team with limited bandwidth, the suggested build order is:

1. **Project 1** (cleaning pipeline) — prerequisite for everything else
2. **Project 2** (operations dashboard) — fastest path to stakeholder-visible value
3. **Project 5** (anomaly monitoring) — low effort once Project 1 exists, protects data trust going forward
4. **Project 3 or 4** (benchmarking / cohort segmentation) — pick based on whether the driving business question is facility-level or population-level
5. **Project 6** (LOS prediction) — treat as a longer-horizon initiative, revisited once richer clinical variables are available
