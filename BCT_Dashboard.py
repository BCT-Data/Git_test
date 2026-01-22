import streamlit as st
import pandas as pd
import snowflake.snowpark as snowpark
import plotly.express as px

CREDIT_TO_USD = 3.0  # adjust if needed

st.markdown(
    "<h1 style='color:#1F409D; text-align:center; font-size: 2.5em;'>BCT - FinOps Dashboard</h1>",
    unsafe_allow_html=True
)

session = snowpark.Session.builder.getOrCreate()
current_role = session.sql("SELECT CURRENT_ROLE() AS ROLE").collect()[0]["ROLE"]
st.caption(f"Current Snowflake role: {current_role}")

# --- WAREHOUSE METERING (90 days) ---
query_wh = """
SELECT START_TIME::DATE AS DATE, WAREHOUSE_NAME, CREDITS_USED_COMPUTE
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE START_TIME >= DATEADD('day', -90, CURRENT_DATE())
ORDER BY START_TIME DESC
"""
df_wh = session.sql(query_wh).to_pandas()
df_wh["COST_USD"] = df_wh["CREDITS_USED_COMPUTE"] * CREDIT_TO_USD

# Aggregate by warehouse
wh_credits = (
    df_wh.groupby("WAREHOUSE_NAME", as_index=False)
         .agg({"CREDITS_USED_COMPUTE": "sum"})
)
wh_credits["COST_USD"] = wh_credits["CREDITS_USED_COMPUTE"] * CREDIT_TO_USD

# Aggregate by date
date_df = (
    df_wh.groupby("DATE", as_index=False)
         .agg({"CREDITS_USED_COMPUTE": "sum"})
)
date_df["COST_USD"] = date_df["CREDITS_USED_COMPUTE"] * CREDIT_TO_USD

# --- USER ATTRIBUTION (90 days) ---
query_user = """
SELECT USER_NAME, SUM(CREDITS_ATTRIBUTED_COMPUTE) AS TOTAL_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
WHERE START_TIME >= DATEADD('day', -90, CURRENT_DATE())
GROUP BY USER_NAME
ORDER BY TOTAL_CREDITS DESC
LIMIT 10
"""
df_user = session.sql(query_user).to_pandas()
df_user["TOTAL_COST_USD"] = df_user["TOTAL_CREDITS"] * CREDIT_TO_USD

# Debug counts (optional – remove later)
#st.write(f"Rows in df_wh: {len(df_wh)}")
#st.write(f"Rows in wh_credits: {len(wh_credits)}")
#st.write(f"Rows in date_df: {len(date_df)}")
#st.write(f"Rows in df_user: {len(df_user)}")

tab_titles = [
    "Overview",
    "Warehouse Consumption",
    "User Consumption",
    "Daily Trend",
    "Warehouse Share",
    "FinOps Recommendations",
]
tabs = st.tabs(tab_titles)

# --- Overview ---
with tabs[0]:
    st.markdown("## Overview")
    st.metric("Total Credits Used (90 days)", f"{df_wh['CREDITS_USED_COMPUTE'].sum():.2f}")
    st.metric("Total Cost (90 days)", f"${df_wh['COST_USD'].sum():,.2f}")
    if not wh_credits.empty:
        st.metric(
            "Top Consuming Warehouse",
            wh_credits.loc[wh_credits["CREDITS_USED_COMPUTE"].idxmax(), "WAREHOUSE_NAME"],
        )
    st.metric("Top User by Cost", df_user.iloc[0]["USER_NAME"] if not df_user.empty else "-")
    st.caption("Use the tabs to see breakdowns and recommendations.")

# --- Warehouse Consumption ---
with tabs[1]:
    st.markdown("## Warehouse Consumption")
    if wh_credits.empty:
        st.warning("No warehouse consumption data available.")
    else:
        wc_sorted = wh_credits.sort_values("COST_USD", ascending=False)
        fig1 = px.bar(
            wc_sorted,
            x="WAREHOUSE_NAME",
            y="COST_USD",
            color="WAREHOUSE_NAME",
            title="Warehouse Cost (USD) in Last 90 Days",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig1.update_layout(xaxis_title="Warehouse", yaxis_title="Cost (USD)")
        st.plotly_chart(fig1, use_container_width=True)
        st.dataframe(
            wc_sorted.rename(
                columns={
                    "WAREHOUSE_NAME": "Warehouse",
                    "CREDITS_USED_COMPUTE": "Credits Used",
                    "COST_USD": "Cost (USD)",
                }
            )
        )

# --- User Consumption ---
with tabs[2]:
    st.markdown("## User Consumption")
    if df_user.empty:
        st.warning("No user consumption data available.")
    else:
        uu_sorted = df_user.sort_values("TOTAL_COST_USD", ascending=False)
        fig2 = px.bar(
            uu_sorted,
            x="USER_NAME",
            y="TOTAL_COST_USD",
            color="TOTAL_COST_USD",
            title="Top 10 Users by Cost (USD) in Last 90 Days",
            color_continuous_scale="Oranges",
        )
        fig2.update_layout(xaxis_title="User", yaxis_title="Cost (USD)")
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(
            uu_sorted.rename(
                columns={
                    "USER_NAME": "User",
                    "TOTAL_CREDITS": "Credits Used",
                    "TOTAL_COST_USD": "Cost (USD)",
                }
            )
        )

# --- Daily Trend ---
with tabs[3]:
    st.markdown("## Daily Cost Trend")
    if date_df.empty:
        st.warning("No daily cost data available.")
    else:
        dt_sorted = date_df.sort_values("DATE")
        fig3 = px.line(
            dt_sorted,
            x="DATE",
            y="COST_USD",
            title="Daily Cost Trend (USD) for Last 90 Days",
            color_discrete_sequence=["#2ECC71"],
            markers=True,
        )
        fig3.update_layout(xaxis_title="Date", yaxis_title="Cost (USD)")
        st.plotly_chart(fig3, use_container_width=True)
        st.dataframe(
            dt_sorted.rename(
                columns={
                    "DATE": "Date",
                    "CREDITS_USED_COMPUTE": "Credits Used",
                    "COST_USD": "Cost (USD)",
                }
            )
        )

# --- Warehouse Share ---
with tabs[4]:
    st.markdown("## Warehouse Share of Total Cost")
    if wh_credits.empty:
        st.warning("No warehouse data for share chart.")
    else:
        fig4 = px.pie(
            wh_credits,
            values="COST_USD",
            names="WAREHOUSE_NAME",
            title="Warehouse Cost Share (last 90 days, USD)",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig4.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig4, use_container_width=True)

# --- FinOps Recommendations ---

with tabs[5]:
    st.markdown("## AI-Driven Cost Optimization (Powered by Snowflake Cortex)")

    # User input inside the tab
    estimate_text = st.text_input(
        "Recommendations based on:",
        "realistic cost savings estimate"
    )

    # Prepare dataset summary for Cortex
    cost_summary_text = f"""
WAREHOUSE COSTS (wh_credits):
{wh_credits.to_string(index=False)}

USER COSTS (df_user):
{df_user.to_string(index=False)}

DAILY COST TRENDS (date_df):
{date_df.to_string(index=False)}
"""

    # Build Cortex prompt dynamically 
    prompt = f"""
You are a Senior Snowflake FinOps Architect specializing in Warehouse Cost Optimization.

Your task:
Analyze the 90-day cost dataset provided below and generate 8–12 *actionable, accurate, Snowflake-specific recommendations*.
For every recommendation, include a **${estimate_text}** based recommentations.

Input Dataset:
{cost_summary_text}
"""

    # Call Cortex and display recommendations
    try:
        cortex_query = f"""
        SELECT snowflake.cortex.complete(
            'mistral-large',
            $$ {prompt} $$
        ) AS RECOMMENDATION;
        """
        with st.spinner("Generating AI recommendations, please wait..."):
            cortex_df = session.sql(cortex_query).to_pandas()
            ai_output = cortex_df["RECOMMENDATION"][0]

        # Clean and display
        import re
        ai_output_fixed = re.sub(r'\.([A-Z])', r'. \1', ai_output)
        recs = ai_output_fixed.split("\n")
        html_list = "<ol>"
        for rec in recs:
            if rec.strip():
                rec_clean = re.sub(r'^\d+\.\s*', '', rec.strip())
                html_list += f"<li>{rec_clean}</li>"
        html_list += "</ol>"

        st.markdown(f"### Recommended Actions based on {estimate_text} (AI Generated)")
        st.markdown(html_list, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error while getting AI recommendations: {e}")

    st.info("These recommendations are generated by Snowflake Cortex based on the last 90 days of credit consumption and warehouse usage.")
