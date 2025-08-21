import streamlit as st
import pandas as pd
import sqlite3
import re
from io import BytesIO

# --- Page Configuration ---
st.set_page_config(page_title="GEDS Contact Finder", page_icon="🔎", layout="wide")

# --- Helper Functions ---
def create_acronym(name):
    if not isinstance(name, str): return ""
    stop_words = {'of', 'and', 'the', 'for', 'et', 'des', 'la', 'le'}
    name_no_parens = re.sub(r'\(.*\)', '', name).strip()
    return "".join(word[0].upper() for word in name_no_parens.split() if word.lower() not in stop_words)

@st.cache_data
def to_excel(df):
    """Encodes a DataFrame into a downloadable Excel file in memory."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Contacts')
    processed_data = output.getvalue()
    return processed_data

# --- Data Loading and Processing ---
@st.cache_data
def load_and_process_data(db_path):
    """Loads data and adds all necessary processed columns."""
    print("Connecting to database and processing data...")
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM contacts", conn)
    conn.close()

    # --- NEW: Define the role hierarchy directly in the app ---
    role_hierarchy = {
        "minister": "01 - Minister",
        "deputy minister": "02 - Deputy Minister",
        "assistant deputy minister": "03 - Associate/Assistant Deputy Minister",
        "associate assistant deputy minister": "04 - Associate Assistant Deputy Minister",
        "chief of staff": "04 - Chief of Staff",
        "chief/commissioner": "05 - Chief / President / Commissioner",
        "vice-president": "06 - Vice-President",
        "director general": "07 - Director General",
        "executive director": "08 - Executive Director",
        "director": "09 - Director",
        "manager": "10 - Manager",
        "principal/senior advisor": "11 - Senior Advisor",
        "senior policy professional": "12 - Senior Analyst",
        "scientist/researcher": "13 - Scientist / Researcher",
        "specialist/lead": "14 - Specialist / Lead",
        "governor": "15 - Governor",
        "secretary": "16 - Secretary",
        "executive assistant": "17 - Executive Assistant",
    }
      
    df['RoleDisplayName'] = df['CanonicalRole'].map(role_hierarchy).fillna(df['CanonicalRole'])
    df['Team'] = df['DepartmentPathEN'].apply(lambda path: path.split(' / ')[-1] if isinstance(path, str) and ' / ' in path else path)
    df['TeamParent'] = df['DepartmentPathEN'].apply(lambda path: path.split(' / ')[-2] if isinstance(path, str) and len(path.split(' / ')) > 1 else None)
    df['SearchableDepartment'] = df['TopLevelDepartmentEN'].apply(lambda name: f"{create_acronym(name)} - {name}" if create_acronym(name) else name)
    
    return df

# --- Main App Logic ---
df_master = load_and_process_data('master_contacts.db')

st.title("🔎 Government of Canada Contact Finder")
st.sidebar.header("Filter Contacts")

# --- Interactive Filters ---
departments = sorted(df_master['SearchableDepartment'].dropna().unique())
roles_for_display = sorted(df_master['RoleDisplayName'].dropna().unique())

selected_searchable_departments = st.sidebar.multiselect('1. Select Department(s)', options=departments)

df_filtered = df_master[df_master['SearchableDepartment'].isin(selected_searchable_departments)] if selected_searchable_departments else df_master.copy()

roles_in_filtered_df = sorted(df_filtered['RoleDisplayName'].dropna().unique())
selected_roles_display = st.sidebar.multiselect('2. Select Role(s)', options=roles_in_filtered_df)

if selected_roles_display:
    df_filtered = df_filtered[df_filtered['RoleDisplayName'].isin(selected_roles_display)]

st.sidebar.markdown("---")
st.sidebar.markdown("**Optional: Filter by Team**")
teams_in_filtered_df = sorted(df_filtered['Team'].dropna().unique())

teams_to_include = st.sidebar.multiselect('3a. Show ONLY these teams', options=teams_in_filtered_df)
if teams_to_include:
    df_filtered = df_filtered[df_filtered['Team'].isin(teams_to_include)]

teams_to_exclude = st.sidebar.multiselect('3b. HIDE these teams', options=teams_in_filtered_df)
if teams_to_exclude:
    df_filtered = df_filtered[~df_filtered['Team'].isin(teams_to_exclude)]

# --- Conditional Display Logic ---
st.markdown("---")

# Only show the results if the user has started filtering.
if selected_searchable_departments or selected_roles_display:
    st.header(f"Results: {len(df_filtered)} contacts found")
    display_cols = ['FullName', 'TitleEN', 'TopLevelDepartmentEN', 'TeamParent', 'Team', 'Email', 'IsActing']
    st.dataframe(df_filtered[display_cols])

    if not df_filtered.empty:
        download_cols = ['FullName', 'TitleEN', 'TopLevelDepartmentEN', 'TeamParent', 'Team', 'Email', 'IsActing', 'DepartmentPathEN']
        final_download_df = df_filtered[[col for col in download_cols if col in df_filtered.columns]]
        excel_data = to_excel(final_download_df)
        
        st.download_button(
            label="📥 Download Results as Excel",
            data=excel_data,
            file_name="filtered_contacts.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    # This is the default message shown before any filters are applied.
    st.info("ℹ️ Please select a Department or Role in the sidebar to begin your search.")
