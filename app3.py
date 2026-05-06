import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="Scope 2 / Energy Baseline Strategy Simulator",
    page_icon="⚡",
    layout="wide"
)

# ============================================================
# Constants and configuration
# ============================================================

SUPPORTED_COMMODITIES = ["electricity", "natural_gas"]
SUPPORTED_CHARGE_TYPES = ["bundled", "delivery", "supply", "unknown"]

COLUMN_ALIASES = {
    "site_name": [
        "site", "site_name", "facility", "facility_name", "location", "location_name",
        "building", "plant", "property", "service_location"
    ],
    "state": [
        "state", "province", "region", "service_state", "site_state", "jurisdiction"
    ],
    "commodity": [
        "commodity", "fuel", "energy_type", "service_type", "utility_type", "resource",
        "meter_type"
    ],
    "usage": [
        "usage", "annual_usage", "consumption", "quantity", "annual_quantity",
        "annual_mwh", "mwh", "annual_mmbtu", "mmbtu", "kwh", "therms",
        "quantity_for_emissions", "quantity emissions", "usage_quantity", "energy_quantity"
    ],
    "unit": [
        "unit", "uom", "units", "usage_unit", "quantity_unit", "quantity_uom",
        "quantity_uom_for_emissions", "uom_for_emissions"
    ],
    "annual_cost": [
        "cost", "annual_cost", "spend", "annual_spend", "amount", "total_cost",
        "total_amount", "charges", "utility_cost"
    ],
    "emissions_factor": [
        "emissions_factor", "emission_factor", "ef", "tco2e_per_unit",
        "kgco2e_per_unit", "co2e_factor", "emissions_intensity"
    ],
    "charge_type": [
        "charge_type", "charge_category", "bill_component", "delivery_supply",
        "utility_component", "component", "rate_component", "line_item_type"
    ],
    "account_number": [
        "account", "account_number", "utility_account", "account_id", "customer_account"
    ],
    "meter_number": [
        "meter", "meter_number", "meter_id", "service_meter", "meter_identifier"
    ],
    "period_start": [
        "period_start", "bill_start", "start_date", "from_date", "service_start"
    ],
    "period_end": [
        "period_end", "bill_end", "end_date", "to_date", "service_end"
    ],
    "year": [
        "year", "calendar_year", "calendar_hierarchy_year", "calendar hierarchy - year"
    ],
    "month": [
        "month", "calendar_month", "calendar_hierarchy_month", "calendar hierarchy - month"
    ]
}

REQUIRED_CANONICAL_COLUMNS = [
    "site_name", "state", "commodity", "usage", "unit", "annual_cost", "emissions_factor"
]

OPTIONAL_CANONICAL_COLUMNS = [
    "charge_type", "account_number", "meter_number", "period_start", "period_end", "year", "month"
]

ALL_CANONICAL_COLUMNS = REQUIRED_CANONICAL_COLUMNS + OPTIONAL_CANONICAL_COLUMNS

US_STATE_ABBREVIATIONS = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY"
}

# ============================================================
# Helper functions
# ============================================================

def normalize_header(value):
    return str(value).strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")


def infer_column_mapping(columns):
    normalized_columns = {normalize_header(col): col for col in columns}
    mapping = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        match = None
        for alias in aliases:
            normalized_alias = normalize_header(alias)
            if normalized_alias in normalized_columns:
                match = normalized_columns[normalized_alias]
                break
        mapping[canonical] = match

    return mapping


def read_excel_smart(uploaded_file):
    """
    Reads Excel files where the real table may not start on row 1.
    Many BI exports include an 'Applied filters' note above the actual headers.
    This function scans the first rows and chooses the most likely header row.
    """
    preview = pd.read_excel(uploaded_file, header=None, engine="openpyxl")
    uploaded_file.seek(0)

    best_header_row = 0
    best_score = -1

    for idx in range(min(20, len(preview))):
        row = preview.iloc[idx]
        non_null_count = row.notna().sum()
        text_values = [str(v).lower() for v in row.dropna().tolist()]
        joined = " ".join(text_values)

        keyword_score = sum(
            keyword in joined
            for keyword in [
                "site", "state", "resource", "commodity", "scope", "quantity",
                "emissions", "emission", "year", "month", "mwh", "mmbtu", "usage"
            ]
        )

        score = non_null_count + (keyword_score * 2)
        if non_null_count >= 2 and score > best_score:
            best_score = score
            best_header_row = idx

    df = pd.read_excel(uploaded_file, header=best_header_row, engine="openpyxl")
    uploaded_file.seek(0)
    return df, best_header_row, preview


def parse_filter_context(preview_df):
    """
    Extracts useful context from BI-export filter text when data columns are missing.
    Example: 'Resource is Electricity' or 'Quantity UOM For Emissions is MWh'.
    """
    context = {
        "commodity": None,
        "unit": None,
        "country": None,
        "customer_name": None,
    }

    text_chunks = []
    for value in preview_df.head(10).values.flatten().tolist():
        if pd.notna(value):
            text_chunks.append(str(value))
    full_text = "\n".join(text_chunks)
    lower_text = full_text.lower()

    if "resource is electricity" in lower_text or "electricity" in lower_text:
        context["commodity"] = "electricity"
    elif "resource is natural gas" in lower_text or "natural gas" in lower_text:
        context["commodity"] = "natural_gas"

    if "quantity uom for emissions is mwh" in lower_text or " mwh" in lower_text:
        context["unit"] = "MWh"
    elif "quantity uom for emissions is mmbtu" in lower_text or "mmbtu" in lower_text:
        context["unit"] = "MMBtu"
    elif "therm" in lower_text:
        context["unit"] = "therms"

    for line in full_text.splitlines():
        line_lower = line.lower().strip()
        if line_lower.startswith("country name is"):
            context["country"] = line.split(" is ", 1)[-1].strip()
        if line_lower.startswith("customer name is"):
            context["customer_name"] = line.split(" is ", 1)[-1].strip()

    return context


def normalize_state(value):
    if pd.isna(value):
        return "Unknown"
    value_str = str(value).strip()
    if len(value_str) == 2:
        return value_str.upper()
    return US_STATE_ABBREVIATIONS.get(value_str.lower(), value_str.upper())


def normalize_commodity(value):
    if pd.isna(value):
        return "unknown"
    value_str = str(value).strip().lower().replace(" ", "_").replace("-", "_")

    electricity_terms = ["electric", "electricity", "power", "kwh", "mwh", "elec"]
    gas_terms = ["natural_gas", "gas", "ng", "therm", "therms", "mmbtu"]

    if value_str in electricity_terms or any(term == value_str for term in electricity_terms):
        return "electricity"
    if value_str in gas_terms or any(term == value_str for term in gas_terms):
        return "natural_gas"
    if "electric" in value_str or "power" in value_str:
        return "electricity"
    if "gas" in value_str or "therm" in value_str:
        return "natural_gas"
    return value_str


def normalize_charge_type(value):
    if pd.isna(value):
        return "unknown"
    value_str = str(value).strip().lower().replace(" ", "_").replace("-", "_")

    if any(term in value_str for term in ["bundled", "full_service", "combined", "total"]):
        return "bundled"
    if any(term in value_str for term in ["delivery", "distribution", "transmission", "td", "t&d", "wires"]):
        return "delivery"
    if any(term in value_str for term in ["supply", "generation", "commodity", "energy_supplier"]):
        return "supply"
    return "unknown"


def normalize_unit(value, commodity):
    if pd.isna(value):
        return "MWh" if commodity == "electricity" else "MMBtu"
    value_str = str(value).strip().lower()
    if value_str in ["kwh", "kilowatt_hour", "kilowatt-hours"]:
        return "kWh"
    if value_str in ["mwh", "megawatt_hour", "megawatt-hours"]:
        return "MWh"
    if value_str in ["therm", "therms"]:
        return "therms"
    if value_str in ["mmbtu", "mm_btu", "dekatherm", "dth"]:
        return "MMBtu"
    return str(value).strip()


def convert_usage_to_standard_unit(row):
    usage = row["usage"]
    unit = row["unit"]
    commodity = row["commodity"]

    if pd.isna(usage):
        return np.nan, unit

    if commodity == "electricity":
        if unit == "kWh":
            return usage / 1000, "MWh"
        return usage, "MWh"

    if commodity == "natural_gas":
        if unit == "therms":
            return usage / 10, "MMBtu"
        return usage, "MMBtu"

    return usage, unit


def standardize_uploaded_data(raw_df, mapping, fallback_context=None, fallback_emissions_factors=None):
    df = pd.DataFrame()

    for canonical in ALL_CANONICAL_COLUMNS:
        source_col = mapping.get(canonical)
        if source_col and source_col in raw_df.columns:
            df[canonical] = raw_df[source_col]
        else:
            df[canonical] = np.nan

    fallback_context = fallback_context or {}
    fallback_emissions_factors = fallback_emissions_factors or {}

    fallback_site = fallback_context.get("customer_name") or "Portfolio"
    fallback_commodity = fallback_context.get("commodity") or "electricity"
    fallback_unit = fallback_context.get("unit")

    df["site_name"] = df["site_name"].fillna(fallback_site).astype(str).str.strip()
    df["state"] = df["state"].fillna("US").apply(normalize_state)
    df["commodity"] = df["commodity"].fillna(fallback_commodity).apply(normalize_commodity)
    df["charge_type"] = df["charge_type"].apply(normalize_charge_type)

    df["usage"] = pd.to_numeric(df["usage"], errors="coerce")
    df["annual_cost"] = pd.to_numeric(df["annual_cost"], errors="coerce").fillna(0)
    df["emissions_factor"] = pd.to_numeric(df["emissions_factor"], errors="coerce")
    df["emissions_factor"] = df.apply(
        lambda row: fallback_emissions_factors.get(row["commodity"], np.nan)
        if pd.isna(row["emissions_factor"]) else row["emissions_factor"],
        axis=1
    )

    if fallback_unit:
        df["unit"] = df["unit"].fillna(fallback_unit)
    df["unit"] = df.apply(lambda row: normalize_unit(row["unit"], row["commodity"]), axis=1)

    converted = df.apply(convert_usage_to_standard_unit, axis=1, result_type="expand")
    df["standard_usage"] = converted[0]
    df["standard_unit"] = converted[1]

    df["period_start"] = pd.to_datetime(df["period_start"], errors="coerce")
    df["period_end"] = pd.to_datetime(df["period_end"], errors="coerce")

    # If explicit dates are missing but year/month columns exist, create a monthly period key later.
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["month"] = df["month"].astype(str).replace("nan", np.nan)

    return df


def select_consumption_records(df):
    working = df.copy()
    working["record_id"] = range(len(working))

    # Use billing-period fields when available; otherwise fallback to a portfolio-level annual grouping.
    working["period_key"] = np.where(
        working["period_start"].notna() | working["period_end"].notna(),
        working["period_start"].astype(str) + "_" + working["period_end"].astype(str),
        np.where(
            working["year"].notna() | working["month"].notna(),
            working["year"].astype(str) + "_" + working["month"].astype(str),
            "annual"
        )
    )

    working["account_key"] = working["account_number"].fillna("unknown_account").astype(str)
    working["meter_key"] = working["meter_number"].fillna("unknown_meter").astype(str)

    group_cols = ["site_name", "state", "commodity", "account_key", "meter_key", "period_key"]
    priority = {"bundled": 1, "delivery": 2, "supply": 3, "unknown": 4}
    working["selection_priority"] = working["charge_type"].map(priority).fillna(4)

    selected_ids = []
    audit_rows = []

    for group_key, group in working.groupby(group_cols, dropna=False):
        sorted_group = group.sort_values(["selection_priority", "record_id"])
        selected = sorted_group.iloc[0]
        selected_ids.append(selected["record_id"])

        charge_types_present = sorted(group["charge_type"].dropna().unique().tolist())
        usage_values = group["standard_usage"].dropna().unique().tolist()
        min_usage = np.nanmin(usage_values) if len(usage_values) > 0 else np.nan
        max_usage = np.nanmax(usage_values) if len(usage_values) > 0 else np.nan
        usage_variance_pct = 0
        if pd.notna(min_usage) and min_usage != 0 and pd.notna(max_usage):
            usage_variance_pct = ((max_usage - min_usage) / min_usage) * 100

        audit_rows.append({
            "site_name": group_key[0],
            "state": group_key[1],
            "commodity": group_key[2],
            "period_key": group_key[5],
            "records_in_group": len(group),
            "selected_charge_type": selected["charge_type"],
            "charge_types_present": ", ".join(charge_types_present),
            "excluded_records": len(group) - 1,
            "usage_variance_pct": usage_variance_pct,
            "review_flag": (
                len(group) > 1 or
                "unknown" in charge_types_present or
                usage_variance_pct > 5
            )
        })

    selected_df = working[working["record_id"].isin(selected_ids)].copy()
    excluded_df = working[~working["record_id"].isin(selected_ids)].copy()
    audit_df = pd.DataFrame(audit_rows)

    selected_df["emissions_tco2e"] = selected_df["standard_usage"] * selected_df["emissions_factor"]

    return selected_df, excluded_df, audit_df


def format_currency(value):
    return f"${value:,.0f}"


def format_number(value, suffix=""):
    if pd.isna(value):
        return "N/A"
    return f"{value:,.0f}{suffix}"


def format_emissions(value):
    return f"{value:,.0f} tCO₂e"


def create_sample_dataset():
    return pd.DataFrame({
        "site_name": [
            "Dallas Plant", "Dallas Plant", "Phoenix DC", "Chicago Plant",
            "Chicago Plant", "Atlanta Warehouse", "Denver Office"
        ],
        "state": ["TX", "TX", "AZ", "IL", "IL", "GA", "CO"],
        "commodity": [
            "electricity", "electricity", "electricity", "natural_gas",
            "natural_gas", "electricity", "electricity"
        ],
        "usage": [20000, 20000, 12000, 60000, 60000, 8000, 3000],
        "unit": ["MWh", "MWh", "MWh", "MMBtu", "MMBtu", "MWh", "MWh"],
        "annual_cost": [1800000, 1750000, 1020000, 330000, 328000, 720000, 315000],
        "emissions_factor": [0.42, 0.42, 0.38, 0.053, 0.053, 0.39, 0.30],
        "charge_type": ["delivery", "supply", "bundled", "delivery", "supply", "bundled", "unknown"],
        "account_number": ["A-100", "A-100", "A-200", "A-300", "A-300", "A-400", "A-500"],
        "meter_number": ["M-1", "M-1", "M-2", "M-3", "M-3", "M-4", "M-5"],
        "period_start": ["2025-01-01"] * 7,
        "period_end": ["2025-12-31"] * 7,
    })


def build_manual_dataset(company_name, annual_mwh, electricity_price, electricity_ef, annual_mmbtu, gas_price, gas_ef):
    rows = []

    if annual_mwh > 0:
        rows.append({
            "site_name": f"{company_name} Portfolio",
            "state": "US",
            "commodity": "electricity",
            "usage": annual_mwh,
            "unit": "MWh",
            "annual_cost": annual_mwh * electricity_price,
            "emissions_factor": electricity_ef,
            "charge_type": "bundled",
            "account_number": "manual",
            "meter_number": "manual",
            "period_start": pd.NaT,
            "period_end": pd.NaT,
        })

    if annual_mmbtu > 0:
        rows.append({
            "site_name": f"{company_name} Portfolio",
            "state": "US",
            "commodity": "natural_gas",
            "usage": annual_mmbtu,
            "unit": "MMBtu",
            "annual_cost": annual_mmbtu * gas_price,
            "emissions_factor": gas_ef,
            "charge_type": "bundled",
            "account_number": "manual",
            "meter_number": "manual",
            "period_start": pd.NaT,
            "period_end": pd.NaT,
        })

    return pd.DataFrame(rows)


def calculate_target_gap(baseline_emissions, reduction_target_pct):
    target_emissions = baseline_emissions * (1 - reduction_target_pct / 100)
    required_reduction = baseline_emissions - target_emissions
    return target_emissions, required_reduction

# ============================================================
# App header
# ============================================================

st.title("⚡ Energy & Emissions Baseline Strategy Simulator")
st.caption("V1.5 | US-focused baseline engine | Manual input + flexible upload | Commodity-aware | No API")

st.markdown(
    """
    This version creates a more realistic energy and emissions baseline by distinguishing electricity from natural gas,
    supporting state/site-level breakdowns, and applying a transparent usage-selection logic to reduce double-counting
    where delivery, supply, and bundled records coexist.
    """
)

# ============================================================
# Sidebar inputs
# ============================================================

st.sidebar.header("Input Mode")
input_mode = st.sidebar.radio(
    "Choose how to provide data",
    options=["Manual demo input", "Upload CSV/Excel", "Use sample dataset"],
    index=0
)

st.sidebar.header("Target Inputs")
reduction_target_pct = st.sidebar.slider(
    "Emissions reduction target (%)",
    min_value=0,
    max_value=100,
    value=50,
    step=5
)

target_year = st.sidebar.number_input(
    "Target year",
    min_value=2026,
    max_value=2050,
    value=2030,
    step=1
)

risk_preference = st.sidebar.selectbox(
    "Risk preference",
    options=["Low", "Medium", "High"],
    index=1
)

budget_preference = st.sidebar.selectbox(
    "Budget posture",
    options=[
        "Cost reduction required",
        "Cost neutral preferred",
        "Moderate premium acceptable",
        "Strategic investment acceptable"
    ],
    index=1
)

raw_df = None
company_name = "Example Company"

# ============================================================
# Data ingestion
# ============================================================

if input_mode == "Manual demo input":
    st.sidebar.header("Manual Portfolio Inputs")
    company_name = st.sidebar.text_input("Company name", value="Example Company")

    annual_mwh = st.sidebar.number_input(
        "Annual electricity consumption (MWh)",
        min_value=0.0,
        value=100000.0,
        step=1000.0
    )

    electricity_price = st.sidebar.number_input(
        "Average electricity price ($/MWh)",
        min_value=0.0,
        value=85.0,
        step=1.0
    )

    electricity_ef = st.sidebar.number_input(
        "Electricity emissions factor (tCO₂e/MWh)",
        min_value=0.0,
        value=0.40,
        step=0.01,
        format="%.3f"
    )

    annual_mmbtu = st.sidebar.number_input(
        "Annual natural gas consumption (MMBtu)",
        min_value=0.0,
        value=0.0,
        step=1000.0
    )

    gas_price = st.sidebar.number_input(
        "Average natural gas price ($/MMBtu)",
        min_value=0.0,
        value=5.50,
        step=0.10,
        format="%.2f"
    )

    gas_ef = st.sidebar.number_input(
        "Natural gas emissions factor (tCO₂e/MMBtu)",
        min_value=0.0,
        value=0.053,
        step=0.001,
        format="%.3f"
    )

    raw_df = build_manual_dataset(
        company_name,
        annual_mwh,
        electricity_price,
        electricity_ef,
        annual_mmbtu,
        gas_price,
        gas_ef
    )

elif input_mode == "Use sample dataset":
    company_name = "Sample US Portfolio"
    raw_df = create_sample_dataset()
    st.success("Loaded sample dataset with delivery/supply examples and electricity/natural gas records.")

else:
    st.subheader("Upload CSV or Excel File")
    uploaded_file = st.file_uploader(
        "Upload site-level or account-level annual energy data",
        type=["csv", "xlsx", "xls"]
    )

    if uploaded_file is not None:
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                raw_df = pd.read_csv(uploaded_file)
            else:
                raw_df, detected_header_row, preview_df = read_excel_smart(uploaded_file)
                filter_context = parse_filter_context(preview_df)
                st.info(f"Detected likely Excel header row: {detected_header_row + 1}.")
            st.success(f"Uploaded {uploaded_file.name} with {len(raw_df):,} rows and {len(raw_df.columns):,} columns.")
        except Exception as exc:
            st.error(f"Could not read file: {exc}")
            raw_df = None

if "filter_context" not in locals():
    filter_context = {}

# ============================================================
# Mapping workflow
# ============================================================

if raw_df is not None and len(raw_df) > 0:
    st.subheader("1. Data Preview and Column Mapping")

    with st.expander("Preview uploaded / source data", expanded=False):
        st.dataframe(raw_df.head(25), use_container_width=True)

    inferred_mapping = infer_column_mapping(raw_df.columns)
    available_columns = [None] + list(raw_df.columns)

    mapping = {}
    with st.expander("Column mapping — review and adjust as needed", expanded=(input_mode == "Upload CSV/Excel")):
        st.markdown(
            "The app attempts to identify common column names, but the user should confirm the mapping before relying on results."
        )

        cols = st.columns(2)
        for i, canonical in enumerate(ALL_CANONICAL_COLUMNS):
            with cols[i % 2]:
                default_col = inferred_mapping.get(canonical)
                default_index = available_columns.index(default_col) if default_col in available_columns else 0
                label = canonical.replace("_", " ").title()
                required_label = " *" if canonical in REQUIRED_CANONICAL_COLUMNS else ""
                mapping[canonical] = st.selectbox(
                    f"{label}{required_label}",
                    options=available_columns,
                    index=default_index,
                    key=f"map_{canonical}"
                )

    # In upload mode, some BI extracts may not include site/state/commodity/unit/EF columns.
    # The app allows safe defaults for those fields, while still requiring a usage/quantity column.
    hard_required = ["usage"]
    missing_required = [col for col in hard_required if mapping.get(col) is None]

    if missing_required:
        st.warning(
            "Please map the required fields before running the baseline: "
            + ", ".join(missing_required)
        )
        st.stop()

    st.sidebar.header("Fallbacks for Uploads")
    fallback_electricity_ef = st.sidebar.number_input(
        "Fallback electricity EF (tCO₂e/MWh)",
        min_value=0.0,
        value=0.40,
        step=0.01,
        format="%.3f"
    )
    fallback_gas_ef = st.sidebar.number_input(
        "Fallback natural gas EF (tCO₂e/MMBtu)",
        min_value=0.0,
        value=0.053,
        step=0.001,
        format="%.3f"
    )

    fallback_emissions_factors = {
        "electricity": fallback_electricity_ef,
        "natural_gas": fallback_gas_ef,
    }

    if filter_context:
        with st.expander("Detected context from file notes / filters", expanded=False):
            st.json(filter_context)

    standardized_df = standardize_uploaded_data(
        raw_df,
        mapping,
        fallback_context=filter_context,
        fallback_emissions_factors=fallback_emissions_factors
    )

    unsupported_commodities = sorted(
        [c for c in standardized_df["commodity"].dropna().unique().tolist() if c not in SUPPORTED_COMMODITIES]
    )
    if unsupported_commodities:
        st.warning(
            "Some commodities are not yet supported and will be excluded from calculations: "
            + ", ".join(unsupported_commodities)
        )

    standardized_df = standardized_df[standardized_df["commodity"].isin(SUPPORTED_COMMODITIES)].copy()
    standardized_df = standardized_df.dropna(subset=["standard_usage", "emissions_factor"])

    selected_df, excluded_df, audit_df = select_consumption_records(standardized_df)

    # ========================================================
    # Portfolio calculations
    # ========================================================

    total_cost = selected_df["annual_cost"].sum()
    total_emissions = selected_df["emissions_tco2e"].sum()
    target_emissions, required_reduction = calculate_target_gap(total_emissions, reduction_target_pct)

    electricity_df = selected_df[selected_df["commodity"] == "electricity"]
    gas_df = selected_df[selected_df["commodity"] == "natural_gas"]

    total_electricity_mwh = electricity_df["standard_usage"].sum()
    total_gas_mmbtu = gas_df["standard_usage"].sum()
    electricity_emissions = electricity_df["emissions_tco2e"].sum()
    gas_emissions = gas_df["emissions_tco2e"].sum()

    # ========================================================
    # KPI cards
    # ========================================================

    st.subheader("2. Portfolio Baseline Summary")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total emissions", format_emissions(total_emissions))
    with col2:
        st.metric("Total annual cost", format_currency(total_cost))
    with col3:
        st.metric("Electricity use", format_number(total_electricity_mwh, " MWh"))
    with col4:
        st.metric("Natural gas use", format_number(total_gas_mmbtu, " MMBtu"))

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Electricity emissions", format_emissions(electricity_emissions))
    with col6:
        st.metric("Natural gas emissions", format_emissions(gas_emissions))
    with col7:
        st.metric("Target emissions", format_emissions(target_emissions))
    with col8:
        st.metric("Required reduction", format_emissions(required_reduction))

    # ========================================================
    # Audit and usage selection transparency
    # ========================================================

    st.subheader("3. Usage Selection and Data Integrity Audit")

    audit_col1, audit_col2, audit_col3, audit_col4 = st.columns(4)
    with audit_col1:
        st.metric("Uploaded/source rows", f"{len(raw_df):,}")
    with audit_col2:
        st.metric("Rows used for emissions", f"{len(selected_df):,}")
    with audit_col3:
        st.metric("Rows excluded", f"{len(excluded_df):,}")
    with audit_col4:
        st.metric("Review flags", f"{int(audit_df['review_flag'].sum()) if len(audit_df) else 0:,}")

    st.markdown(
        """
        **Default usage-selection logic:** for each site/account/meter/commodity/period, the app selects one consumption record to avoid double counting. 
        The default hierarchy is **bundled → delivery → supply → unknown**. This is a practical data-integrity rule, not a direct GHG Protocol prescription.
        It is intended to create a consistent, non-duplicative representation of consumption.
        """
    )

    with st.expander("Audit table: selected usage and review flags", expanded=False):
        st.dataframe(audit_df, use_container_width=True)

    with st.expander("Rows used for emissions calculation", expanded=False):
        display_cols = [
            "site_name", "state", "commodity", "charge_type", "standard_usage", "standard_unit",
            "annual_cost", "emissions_factor", "emissions_tco2e", "account_number", "meter_number"
        ]
        st.dataframe(selected_df[display_cols], use_container_width=True)

    if len(excluded_df) > 0:
        with st.expander("Rows excluded to reduce double-counting risk", expanded=False):
            st.dataframe(excluded_df[display_cols], use_container_width=True)

    # ========================================================
    # Visual breakdowns
    # ========================================================

    st.subheader("4. Emissions Breakdown")

    by_commodity = selected_df.groupby("commodity", as_index=False).agg(
        emissions_tco2e=("emissions_tco2e", "sum"),
        annual_cost=("annual_cost", "sum"),
        records=("record_id", "count")
    ).sort_values("emissions_tco2e", ascending=False)

    by_state = selected_df.groupby(["state", "commodity"], as_index=False).agg(
        emissions_tco2e=("emissions_tco2e", "sum"),
        standard_usage=("standard_usage", "sum"),
        annual_cost=("annual_cost", "sum")
    )

    by_site = selected_df.groupby(["site_name", "state", "commodity"], as_index=False).agg(
        emissions_tco2e=("emissions_tco2e", "sum"),
        standard_usage=("standard_usage", "sum"),
        annual_cost=("annual_cost", "sum")
    ).sort_values("emissions_tco2e", ascending=False)

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("**Emissions by commodity**")
        st.bar_chart(by_commodity.set_index("commodity")[["emissions_tco2e"]])

    with chart_col2:
        st.markdown("**Target gap**")
        target_chart = pd.DataFrame({
            "Category": ["Current emissions", f"Target by {target_year}", "Required reduction"],
            "tCO2e": [total_emissions, target_emissions, required_reduction]
        })
        st.bar_chart(target_chart.set_index("Category"))

    st.markdown("**Emissions by state and commodity**")
    state_pivot = by_state.pivot_table(
        index="state",
        columns="commodity",
        values="emissions_tco2e",
        aggfunc="sum",
        fill_value=0
    )
    st.bar_chart(state_pivot)

    st.markdown("**Top emitting sites**")
    top_sites = by_site.head(15).copy()
    top_sites["site_state_commodity"] = (
        top_sites["site_name"] + " | " + top_sites["state"] + " | " + top_sites["commodity"]
    )
    st.bar_chart(top_sites.set_index("site_state_commodity")[["emissions_tco2e"]])

    # ========================================================
    # Tables
    # ========================================================

    st.subheader("5. Detailed Tables")

    tab1, tab2, tab3 = st.tabs(["By Commodity", "By State", "By Site"])

    with tab1:
        st.dataframe(by_commodity, use_container_width=True)

    with tab2:
        st.dataframe(by_state.sort_values("emissions_tco2e", ascending=False), use_container_width=True)

    with tab3:
        st.dataframe(by_site, use_container_width=True)

    # ========================================================
    # Rule-based executive interpretation
    # ========================================================

    st.subheader("6. Executive Interpretation")

    electricity_share = (electricity_emissions / total_emissions * 100) if total_emissions else 0
    gas_share = (gas_emissions / total_emissions * 100) if total_emissions else 0

    largest_state = None
    if len(by_state) > 0:
        state_total = by_state.groupby("state", as_index=False)["emissions_tco2e"].sum().sort_values(
            "emissions_tco2e", ascending=False
        )
        largest_state = state_total.iloc[0]

    largest_site = by_site.iloc[0] if len(by_site) > 0 else None

    st.markdown(f"""
    The current modeled portfolio baseline is **{format_emissions(total_emissions)}**, with an estimated annual energy cost of **{format_currency(total_cost)}**.

    To achieve a **{reduction_target_pct}% emissions reduction by {target_year}**, the company would need to reduce or address approximately **{format_emissions(required_reduction)}** annually.

    **Commodity exposure:** electricity represents approximately **{electricity_share:.1f}%** of modeled emissions, while natural gas represents approximately **{gas_share:.1f}%**.
    """)

    if largest_state is not None:
        st.markdown(
            f"**Geographic concentration:** {largest_state['state']} is the largest modeled state exposure, "
            f"representing **{format_emissions(largest_state['emissions_tco2e'])}**."
        )

    if largest_site is not None:
        st.markdown(
            f"**Site concentration:** {largest_site['site_name']} ({largest_site['state']}, {largest_site['commodity']}) "
            f"is the largest modeled site/commodity exposure, at **{format_emissions(largest_site['emissions_tco2e'])}**."
        )

    guidance = []
    if electricity_share >= 60:
        guidance.append("Electricity is the dominant emissions driver, so the next strategy layer should prioritize Scope 2 levers such as efficiency, renewable procurement, and EAC/REC strategy.")
    if gas_share >= 30:
        guidance.append("Natural gas is material enough to require a separate Scope 1 pathway, including thermal efficiency, process changes, and potential electrification screening.")
    if int(audit_df["review_flag"].sum()) > 0:
        guidance.append("Several records require review because the dataset contains duplicate-risk records, unknown charge types, or materially different usage values within the same group.")
    if budget_preference in ["Cost reduction required", "Cost neutral preferred"]:
        guidance.append("Given the selected budget posture, the first lever library should distinguish measures that reduce cost from measures that primarily reduce emissions or improve market-based accounting.")
    if risk_preference == "Low":
        guidance.append("Given the low-risk preference, future procurement levers should be modeled with strong attention to contract exposure, term length, settlement risk, and basis risk.")

    if guidance:
        st.markdown("**Initial guidance:**")
        for item in guidance:
            st.markdown(f"- {item}")

    st.divider()
    st.info(
        "Next build step: add the decarbonization lever library, now applied against this more granular baseline by commodity, state, and site."
    )

else:
    st.info("Choose manual input, upload a file, or load the sample dataset to begin.")
