"""
Reusable cleaning pipeline for hospital_patients_real_world.csv.

Built and validated across a documented audit process — see
docs/project1_build_documentation.md in this repo for the full
step-by-step reasoning behind each function.

Design principle: flag data problems explicitly rather than silently
dropping or imputing them. This dataset shows no reliable statistical
relationship between fields, so guessing at missing/bad values would
fabricate data rather than recover it.
"""
import pandas as pd

# Conditions that shouldn't realistically appear in infants (Age == 0).
# Domain-knowledge rule, not statistically derived from the data itself.
ADULT_ONLY_CONDITIONS = {
    'Type 2 Diabetes', 'Osteoarthritis', 'Myocardial Infarction',
    'Hypertension', 'Atrial Fibrillation', 'Chronic Kidney Disease'
}


def audit_report(df: pd.DataFrame) -> dict:
    """Quantify known data quality issues. Returns a dict summary."""
    report = {}

    report['missing_counts'] = df[['Age', 'Gender', 'Diagnosis']].isnull().sum().to_dict()
    missing_mask = df[['Age', 'Gender', 'Diagnosis']].isnull()
    report['rows_missing_all_three'] = int((missing_mask.sum(axis=1) == 3).sum())

    non_null_dx = df['Diagnosis'].dropna()
    report['diagnosis_raw_categories'] = non_null_dx.nunique()
    report['diagnosis_normalized_categories'] = non_null_dx.str.strip().str.title().nunique()

    admit = pd.to_datetime(df['AdmissionDate'])
    discharge = pd.to_datetime(df['DischargeDate'])
    los = (discharge - admit).dt.days
    report['negative_los_count'] = int((los < 0).sum())
    report['negative_los_values'] = sorted(los[los < 0].unique().tolist())

    report['duplicate_rows'] = int(df.duplicated().sum())
    report['duplicate_patient_ids'] = int(df['PatientID'].duplicated().sum())

    return report


def normalize_diagnosis(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize Diagnosis casing/whitespace. Preserves NaN."""
    df = df.copy()
    df['Diagnosis'] = df['Diagnosis'].str.strip().str.title()
    return df


def flag_missingness(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add explicit missingness flags for Age, Gender, Diagnosis rather than
    imputing — this dataset shows no reliable correlation to impute from,
    so filling values would fabricate data rather than recover it.
    """
    df = df.copy()
    for col in ['Age', 'Gender', 'Diagnosis']:
        df[f'{col}_missing'] = df[col].isnull()

    df['missing_field_count'] = df[
        ['Age_missing', 'Gender_missing', 'Diagnosis_missing']
    ].sum(axis=1)
    return df


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

    swap_mask = los == -5  # exact signature validated against the healthy LOS range

    df['LOS_was_swapped'] = swap_mask
    df.loc[swap_mask, ['AdmissionDate', 'DischargeDate']] = \
        df.loc[swap_mask, ['DischargeDate', 'AdmissionDate']].values

    return df


def flag_implausible_age_diagnosis(df: pd.DataFrame) -> pd.DataFrame:
    """Flag Age == 0 rows paired with adult-only diagnoses."""
    df = df.copy()
    df['implausible_age_diagnosis'] = (
        (df['Age'] == 0) & (df['Diagnosis'].isin(ADULT_ONLY_CONDITIONS))
    )
    return df


def clean_hospital_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Full cleaning pipeline for hospital_patients_real_world.csv.

    Steps:
      1. Normalize Diagnosis casing (28 -> 14 categories)
      2. Flag (not impute) missing Age/Gender/Diagnosis
      3. Fix the validated AdmissionDate/DischargeDate swap bug (LOS == -5)
      4. Recompute LOS from corrected dates
      5. Flag implausible Age==0 + adult-only-diagnosis pairs

    Returns a cleaned dataframe with original columns preserved plus
    quality flags (*_missing, LOS_was_swapped, implausible_age_diagnosis).
    Nothing is silently dropped or imputed — flags let downstream users
    decide what to exclude for their specific analysis.
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


def run_pipeline_tests(clean_df: pd.DataFrame) -> None:
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


if __name__ == '__main__':
    raw = pd.read_csv('data/hospital_patients_real_world.csv')
    cleaned = clean_hospital_data(raw)
    print(scorecard(raw, cleaned).to_string(index=False))
    run_pipeline_tests(cleaned)
    cleaned.to_csv('data/hospital_patients_cleaned.csv', index=False)
