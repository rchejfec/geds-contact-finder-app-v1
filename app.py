import streamlit as st
import pandas as pd
import sqlite3
import re
from io import BytesIO

# --- Page Configuration ---
st.set_page_config(
    page_title="GEDS Contact Finder",
    page_icon="🔎",
    layout="wide"
)

# --- Helper Functions ---
def create_acronym(name):
    """Creates an acronym from a department name, ignoring common lowercase words."""
    if not isinstance(name, str):
        return ""
    # List of common words to ignore
    stop_words = {'of', 'and', 'the', 'for', 'et', 'des', 'la', 'le'}
    acronym = ""
    # Remove text in parentheses for cleaner acronyms
    name_no_parens = re.sub(r'\(.*\)', '', name).strip()
    words = name_no_parens.split()
    for word in words:
        if word.lower() not in stop_words:
            acronym += word[0].upper()
    return acronym

# --- Data Loading and Processing ---
@st.cache_data
def load_and_process_data(db_path):
    """
    Loads data from SQLite and performs all necessary pre-processing.
    This function is cached for performance.
    """
    print("Connecting to the database and processing data...")
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM contacts", conn)
    conn.close()

    # Create the new Team and TeamParent columns
    df['Team'] = df['DepartmentPathEN'].apply(lambda path: path.split(' / ')[-1] if isinstance(path, str) and ' / ' in path else path)
    df['TeamParent'] = df['DepartmentPathEN'].apply(lambda path: path.split(' / ')[-2] if isinstance(path, str) and len(path.split(' / ')) > 1 else None)
    
    # Create the searchable department name with acronym
    df['SearchableDepartment'] = df['TopLevelDepartmentEN'].apply(
        lambda name: f"{create_acronym(name)} - {name}" if create_acronym(name) else name
    )
    return df

# --- Main App Logic ---

# 1. Load and process the data
df_master = load_and_process_data('master_contacts.db')

# 2. Add a title and introduction
st.title("🔎 Government of Canada Contact Finder")
st.write(
    "Use the filters in the sidebar to narrow down the contact list. "
    "The results table will update automatically."
)

# 3. Sidebar for filters
st.sidebar.header("Filter Contacts")

# --- Interactive Filters ---
departments = sorted(df_master['SearchableDepartment'].dropna().unique())
roles = sorted(df_master['CanonicalRole'].dropna().unique())

# Filter 1: Department (Inclusion)
selected_searchable_departments = st.sidebar.multiselect(
    '1. Select Department(s)',
    options=departments,
    help="Start here. You can type to search by acronym or name."
)

# Filter the DataFrame based on the searchable department name
if selected_searchable_departments:
    df_filtered = df_master[df_master['SearchableDepartment'].isin(selected_searchable_departments)].copy()
else:
    df_filtered = df_master.copy()

# Filter 2: Role (Inclusion)
roles_in_filtered_df = sorted(df_filtered['CanonicalRole'].dropna().unique())
selected_roles = st.sidebar.multiselect(
    '2. Select Role(s)',
    options=roles_in_filtered_df
)

if selected_roles:
    df_filtered = df_filtered[df_filtered['CanonicalRole'].isin(selected_roles)]

# --- Dual Team Filters ---
st.sidebar.markdown("---")
st.sidebar.markdown("**Optional: Filter by Team**")

teams_in_filtered_df = sorted(df_filtered['Team'].dropna().unique())

# Filter 3a: Team (Inclusion)
teams_to_include = st.sidebar.multiselect(
    '3a. Show ONLY these teams',
    options=teams_in_filtered_df,
    help="Select one or more teams to narrow your results."
)

if teams_to_include:
    df_filtered = df_filtered[df_filtered['Team'].isin(teams_to_include)]

# Filter 3b: Team (Exclusion)
teams_to_exclude = st.sidebar.multiselect(
    '3b. HIDE these teams',
    options=teams_in_filtered_df,
    help="Use this to remove specific teams from your results."
)

if teams_to_exclude:
    df_filtered = df_filtered[~df_filtered['Team'].isin(teams_to_exclude)]

# --- Display the Results ---
st.markdown("---")
st.header(f"Results: {len(df_filtered)} contacts found")

display_cols = ['FullName', 'TitleEN', 'TopLevelDepartmentEN', 'TeamParent', 'Team', 'Email', 'IsActing']
st.dataframe(df_filtered[display_cols])

# --- Download Button ---
if not df_filtered.empty:
    output = BytesIO()
    download_cols = ['FullName', 'TitleEN', 'TitleFR', 'TopLevelDepartmentEN', 'TeamParent', 'Team', 'Email', 'IsActing', 'DepartmentPathEN']
    final_download_df = df_filtered[[col for col in download_cols if col in df_filtered.columns]]
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_download_df.to_excel(writer, index=False, sheet_name='Contacts')
    
    st.download_button(
        label="📥 Download Results as Excel",
        data=output.getvalue(),
        file_name="filtered_contacts.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )