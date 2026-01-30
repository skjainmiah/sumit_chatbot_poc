"""SQL query and results display component with advanced visualization."""
import streamlit as st
import pandas as pd
from frontend.components.visualization import (
    render_visualization,
    suggest_visualizations,
    render_chart_suggestions,
    analyze_data,
    create_chart,
    get_unique_key,
)


def render_sql_results(sql_query: str = None, results: dict = None, query_text: str = ""):
    """Render SQL query and results with beautiful visualization."""
    if not sql_query and not results:
        return

    with st.expander("🔍 View SQL Query & Results", expanded=False):
        # Show SQL query with syntax highlighting
        if sql_query:
            st.markdown("**Generated SQL:**")
            st.code(sql_query, language="sql")

        # Show results
        if results:
            rows = results.get("rows", [])
            columns = results.get("columns", [])
            row_count = results.get("row_count", len(rows))

            if rows:
                # Create DataFrame
                if columns:
                    df = pd.DataFrame(rows, columns=columns)
                else:
                    df = pd.DataFrame(rows)

                st.markdown(f"**Results:** {row_count} row(s)")

                # Check if data is suitable for visualization
                analysis = analyze_data(df)

                if len(df) >= 2 and len(analysis["suitable_charts"]) > 1:
                    # Show chart suggestions if query suggests visualization
                    viz_keywords = ["show", "display", "chart", "graph", "plot", "visualize", "trend", "compare"]
                    should_suggest = any(kw in query_text.lower() for kw in viz_keywords)

                    if should_suggest or len(df) <= 20:
                        render_chart_suggestions(df, query_text, key_prefix=get_unique_key("sql", results))

                    # Render full visualization component
                    render_visualization(
                        df,
                        title=None,
                        key_prefix=get_unique_key("sqlviz", results),
                        show_selector=True,
                        default_expanded=len(df) <= 15,
                        allow_download=True
                    )
                else:
                    # Just show data table for simple results
                    st.dataframe(df, width="stretch", hide_index=True)

                    # Download button
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "📥 Download CSV",
                        csv,
                        "query_results.csv",
                        "text/csv",
                        key=get_unique_key("dl", results)
                    )

            elif row_count == 0:
                st.info("Query returned no results")


def render_quick_chart(df: pd.DataFrame, chart_type: str = None, key_prefix: str = "quick"):
    """Render a quick chart without the full selector UI."""
    if df is None or len(df) < 2:
        return

    analysis = analyze_data(df)

    if not chart_type:
        chart_type = analysis["recommended_chart"]

    if chart_type == "table":
        st.dataframe(df, width="stretch", hide_index=True)
        return

    try:
        fig = create_chart(
            df,
            chart_type=chart_type,
            x_col=analysis["x_col"],
            y_col=analysis["y_col"],
            height=350
        )

        config = {
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        }

        st.plotly_chart(fig, width="stretch", config=config)

    except Exception as e:
        st.dataframe(df, width="stretch", hide_index=True)


def render_auto_chart(df: pd.DataFrame):
    """Legacy function - redirects to render_quick_chart."""
    render_quick_chart(df)
