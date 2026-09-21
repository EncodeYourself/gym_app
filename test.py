'''for table in tables:
        # Convert table name to URL-friendly format
        page_name = table.replace("_", " ").title()
        # Create a button for each table
        if st.button(f"📋 {page_name}", key=table, use_container_width=True):
            # Navigate to the corresponding page
            # Streamlit pages are named with numbers: 1_Table_Name.py
            page_file = f"pages/{tables.index(table) + 1}_{table}.py"
            st.switch_page(page_file)'''

x = {1: 'lol'}
print(str(1))

"""
timetable = create_timetable(pl.DataFrame([]))

st.title("Class Schedule")


# Convert to DataFrame
header = timetable[0]
data_rows = timetable[1:]
timetable_df = pl.DataFrame(data_rows, schema=header)

# Display the table - it will now use full width
st.dataframe(
    timetable_df,
    column_config={
        "Time": st.column_config.TextColumn("Time", width=50),
        **{day: st.column_config.TextColumn(day, width='medium', ) for day in header[1:]}
    },
    hide_index=True,
    use_container_width=True,
    height=len(timetable_df) * 35 + 38
)
"""