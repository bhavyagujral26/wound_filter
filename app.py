import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Wound Care Dashboard", layout="wide")

st.title("🏥 Wound Care Dashboard")
st.write("Upload the three Excel exports")

# =====================================================
# CLEAN HEADERS
# =====================================================

def clean(df):
    df.columns = (
        df.columns
        .str.replace("\u00A0"," ", regex=False)
        .str.strip()
    )
    return df


# =====================================================
# NORMALIZE MRN COLUMN
# =====================================================

def normalize_mrn(df):

    aliases = ["mrn","medical record","record number","chart"]

    for col in df.columns:
        if any(a in col.lower() for a in aliases):
            return df.rename(columns={col:"MRN"})

    raise Exception("No MRN column found")


# =====================================================
# UPLOADS
# =====================================================

census_file = st.file_uploader("Upload Census", type=["xlsx"])
roster_file = st.file_uploader("Upload Roster", type=["xlsx"])
schedule_file = st.file_uploader("Upload Schedule", type=["xlsx"])

# =====================================================
# LOAD DATA IMMEDIATELY AFTER UPLOAD
# =====================================================

if census_file and roster_file and schedule_file:

    census = normalize_mrn(clean(pd.read_excel(census_file)))
    roster = normalize_mrn(clean(pd.read_excel(roster_file)))
    schedule = normalize_mrn(clean(pd.read_excel(schedule_file)))

    # -------------------------------------------------
    # COLUMN PICKERS UI
    # -------------------------------------------------

    st.header("Choose columns to include")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Schedule columns")
        sched_cols = st.multiselect(
            "Pick schedule columns",
            schedule.columns.tolist(),
            default=schedule.columns.tolist()
        )

    with col2:
        st.subheader("Census columns")
        census_cols = st.multiselect(
            "Pick census columns",
            census.columns.tolist(),
            default=census.columns.tolist()
        )

    with col3:
        st.subheader("Roster columns")
        roster_cols = st.multiselect(
            "Pick roster columns",
            roster.columns.tolist(),
            default=roster.columns.tolist()
        )

    # =====================================================
    # PROCESS BUTTON
    # =====================================================

    if st.button("Generate Wound Dashboard"):

        with st.spinner("Processing..."):

            # --------------------------
            # FILTER WOUND FROM CENSUS
            # --------------------------
            census["PDGM Grouping"] = census["PDGM Grouping"].astype(str)

            mrn_pdgm = set(
                census[
                    census["PDGM Grouping"].str.contains("WOUND", case=False, na=False)
                ]["MRN"].astype(str)
            )

            # --------------------------
            # FILTER WOUND FROM ROSTER
            # --------------------------
            roster["Patient Flags"] = roster["Patient Flags"].astype(str)

            mrn_flags = set(
                roster[
                    roster["Patient Flags"].str.contains("WOUND CARE", case=False, na=False)
                ]["MRN"].astype(str)
            )

            target_mrns = mrn_pdgm | mrn_flags

            st.success(f"Found {len(target_mrns)} wound patients")

            # --------------------------
            # FILTER SCHEDULE
            # --------------------------
            schedule["MRN"] = schedule["MRN"].astype(str)
            filtered = schedule[schedule["MRN"].isin(target_mrns)]

            # --------------------------
            # PREP FOR MERGE
            # --------------------------
            census["MRN"] = census["MRN"].astype(str)
            roster["MRN"] = roster["MRN"].astype(str)

            census = census.drop_duplicates("MRN")
            roster = roster.drop_duplicates("MRN")

            # --------------------------
            # MERGE
            # --------------------------
            merged = filtered.merge(census, on="MRN", how="left", suffixes=("","_census"))
            merged = merged.merge(roster, on="MRN", how="left", suffixes=("","_roster"))

            # --------------------------
            # SORT
            # --------------------------
            if "Target Date" in merged.columns:
                merged = merged.sort_values(by=["MRN","Target Date"])
            else:
                merged = merged.sort_values(by=["MRN"])

            # --------------------------
            # APPLY USER COLUMN CHOICES
            # --------------------------
            chosen = set(sched_cols + census_cols + roster_cols)

            final_cols = [c for c in merged.columns if c in chosen]

            merged = merged[final_cols]

            # --------------------------
            # SHOW TABLE
            # --------------------------
            st.subheader("Preview")
            st.dataframe(merged, use_container_width=True)

            # --------------------------
            # DOWNLOAD
            # --------------------------
            buf = BytesIO()
            merged.to_excel(buf, index=False)
            buf.seek(0)

            st.download_button(
                "⬇ Download Excel",
                data=buf,
                file_name="WoundCare_Dashboard.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
