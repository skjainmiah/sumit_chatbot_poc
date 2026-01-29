"""SQL query and results display component."""
import streamlit as st
import pandas as pd
import plotly.express as px


def render_sql_results(sql_query: str = None, results: dict = None):
    """Render SQL query and results with visualization."""
    if not sql_query and not results:
        return

    with st.expander("View SQL Query & Results", expanded=False):
        # Show SQL query with syntax highlighting
        if sql_query:
            st.subheader("Generated SQL")
            st.code(sql_query, language="sql")

        # Show results
        if results:
            st.subheader("Query Results")

            rows = results.get("rows", [])
            columns = results.get("columns", [])

            if rows and columns:
                # Create DataFrame
                df = pd.DataFrame(rows, columns=columns)

                # Display as table
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Show row count
                st.caption(f"{len(rows)} row(s) returned")

                # Auto-visualization for suitable data
                if len(df) > 1 and len(df) <= 50:
                    render_auto_chart(df)
            elif not rows:
                st.info("Query returned no results")


def render_auto_chart(df: pd.DataFrame):
    """Automatically create appropriate chart based on data."""
    # Skip if too few rows
    if len(df) < 2:
        return

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    non_numeric_cols = df.select_dtypes(exclude=["number"]).columns.tolist()

    # If we have a good category + numeric combo, show a chart
    if numeric_cols and non_numeric_cols:
        # Use first non-numeric as category, first numeric as value
        x_col = non_numeric_cols[0]
        y_col = numeric_cols[0]

        # Determine chart type based on data
        unique_x = df[x_col].nunique()

        if unique_x <= 10:
            # Bar chart for few categories
            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                title=f"{y_col} by {x_col}",
                color=x_col
            )
            st.plotly_chart(fig, use_container_width=True)
        elif unique_x <= 30:
            # Line chart for more categories (like dates)
            fig = px.line(
                df.sort_values(x_col),
                x=x_col,
                y=y_col,
                title=f"{y_col} over {x_col}",
                markers=True
            )
            st.plotly_chart(fig, use_container_width=True)

    # If we have multiple numeric columns, show summary stats
    elif len(numeric_cols) >= 2:
        st.caption("Numeric Summary")
        st.dataframe(df[numeric_cols].describe(), use_container_width=True)
