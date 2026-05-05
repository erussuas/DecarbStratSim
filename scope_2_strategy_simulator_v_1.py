import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Scope 2 Strategy Simulator",
    page_icon="⚡",
    layout="wide"
)

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def calculate_baseline(annual_mwh, electricity_price_per_mwh, emissions_factor_tco2e_per_mwh):
    annual_cost = annual_mwh * electricity_price_per_mwh
    annual_emissions = annual_mwh * emissions_factor_tco2e_per_mwh
    return annual_cost, annual_emissions


def calculate_target_gap(baseline_emissions, reduction_target_pct):
    target_emissions = baseline_emissions * (1 - reduction_target_pct / 100)
    required_reduction = baseline_emissions - target_emissions
    return target_emissions, required_reduction


def format_currency(value):
    return f"${value:,.0f}"


def format_emissions(value):
    return f"{value:,.0f} tCO₂e"


# ------------------------------------------------------------
# App header
# ------------------------------------------------------------

st.title("⚡ Scope 2 Strategy Simulator")
st.caption("Manual-input MVP | No API | Executive decision support for electricity emissions strategy")

st.markdown(
    """
    This first version helps estimate a company's current Scope 2 electricity footprint, 
    define a reduction target, and quantify the emissions gap that must be solved through 
    efficiency, renewable procurement, EACs/RECs, PPAs, or other interventions.
    """
)

# ------------------------------------------------------------
# Sidebar inputs
# ------------------------------------------------------------

st.sidebar.header("Company / Portfolio Inputs")

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

emissions_factor = st.sidebar.number_input(
    "Emissions factor (tCO₂e/MWh)",
    min_value=0.0,
    value=0.40,
    step=0.01,
    format="%.3f"
)

st.sidebar.header("Target Inputs")

reduction_target_pct = st.sidebar.slider(
    "Scope 2 reduction target (%)",
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
    options=["Cost reduction required", "Cost neutral preferred", "Moderate premium acceptable", "Strategic investment acceptable"],
    index=1
)

# ------------------------------------------------------------
# Core calculations
# ------------------------------------------------------------

annual_cost, baseline_emissions = calculate_baseline(
    annual_mwh,
    electricity_price,
    emissions_factor
)

target_emissions, required_reduction = calculate_target_gap(
    baseline_emissions,
    reduction_target_pct
)

remaining_pct_of_baseline = 100 - reduction_target_pct

# ------------------------------------------------------------
# KPI cards
# ------------------------------------------------------------

st.subheader(f"Baseline and Target Summary — {company_name}")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Annual electricity use", f"{annual_mwh:,.0f} MWh")

with col2:
    st.metric("Annual electricity cost", format_currency(annual_cost))

with col3:
    st.metric("Current Scope 2 emissions", format_emissions(baseline_emissions))

with col4:
    st.metric("Required reduction", format_emissions(required_reduction))

# ------------------------------------------------------------
# Target chart data
# ------------------------------------------------------------

st.subheader("Emissions Target Gap")

chart_data = pd.DataFrame({
    "Category": ["Current emissions", f"Target emissions by {target_year}", "Required reduction"],
    "tCO2e": [baseline_emissions, target_emissions, required_reduction]
})

st.bar_chart(chart_data.set_index("Category"))

# ------------------------------------------------------------
# Executive interpretation
# ------------------------------------------------------------

st.subheader("Executive Interpretation")

if reduction_target_pct == 0:
    target_message = "No emissions reduction target has been selected yet."
elif reduction_target_pct <= 25:
    target_message = "This is a moderate target that may be achievable through efficiency, EACs/RECs, and selective renewable procurement."
elif reduction_target_pct <= 60:
    target_message = "This is a meaningful target that likely requires a portfolio strategy combining efficiency, market instruments, and renewable procurement."
else:
    target_message = "This is an aggressive target that likely requires significant renewable procurement, careful risk management, and strong executive sponsorship."

st.markdown(f"""
**{company_name} currently consumes approximately {annual_mwh:,.0f} MWh of electricity per year**, representing an estimated annual Scope 2 footprint of **{format_emissions(baseline_emissions)}** and an annual electricity cost of approximately **{format_currency(annual_cost)}**.

To achieve a **{reduction_target_pct}% Scope 2 reduction by {target_year}**, the company would need to reduce or address approximately **{format_emissions(required_reduction)}** annually, leaving a target footprint of **{format_emissions(target_emissions)}**.

**Initial read:** {target_message}

**Decision posture selected:** Risk preference is **{risk_preference}** and budget posture is **{budget_preference}**.
""")

# ------------------------------------------------------------
# Early decision guidance - simple rules only
# ------------------------------------------------------------

st.subheader("Initial Strategic Guidance")

recommendations = []

if budget_preference in ["Cost reduction required", "Cost neutral preferred"]:
    recommendations.append("Prioritize efficiency and load reduction first, because these can reduce both emissions and operating cost.")
    recommendations.append("Use EACs/RECs selectively to close near-term target gaps, but avoid over-reliance if credibility is important.")
else:
    recommendations.append("Consider a broader portfolio including onsite solar, PPAs/VPPAs, and strategic EAC/REC procurement.")

if risk_preference == "Low":
    recommendations.append("Limit exposure to long-term market instruments unless pricing, volume, and settlement risks are clearly understood.")
elif risk_preference == "Medium":
    recommendations.append("Evaluate a balanced mix of efficiency, EACs/RECs, and contracted renewable procurement.")
else:
    recommendations.append("A more aggressive renewable procurement strategy may be acceptable, including PPAs or VPPAs where market conditions are favorable.")

if reduction_target_pct >= 50:
    recommendations.append("A target of 50% or more likely requires more than certificates alone; leadership should evaluate durable procurement and operational measures.")

for rec in recommendations:
    st.markdown(f"- {rec}")

# ------------------------------------------------------------
# Placeholder for next build step
# ------------------------------------------------------------

st.divider()
st.info("Next build step: add a decarbonization lever library for efficiency, onsite solar, EACs/RECs, and PPAs/VPPAs, then compare scenarios.")
