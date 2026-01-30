"""Advanced visualization component with beautiful charts and popup support."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, Dict, List, Tuple, Any
import hashlib


# Beautiful color palettes
COLOR_PALETTES = {
    "default": ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe", "#43e97b", "#38f9d7"],
    "ocean": ["#0077b6", "#00b4d8", "#90e0ef", "#caf0f8", "#023e8a", "#03045e", "#48cae4", "#ade8f4"],
    "sunset": ["#ff6b6b", "#feca57", "#ff9ff3", "#54a0ff", "#5f27cd", "#00d2d3", "#ff9f43", "#ee5a24"],
    "forest": ["#2d6a4f", "#40916c", "#52b788", "#74c69d", "#95d5b2", "#b7e4c7", "#d8f3dc", "#1b4332"],
    "corporate": ["#1e3a5f", "#3d5a80", "#5c7da0", "#98c1d9", "#e0fbfc", "#ee6c4d", "#293241", "#3d5a80"],
}

# Chart type configurations
CHART_CONFIGS = {
    "bar": {"icon": "📊", "name": "Bar Chart", "min_rows": 2, "max_categories": 20},
    "horizontal_bar": {"icon": "📊", "name": "Horizontal Bar", "min_rows": 2, "max_categories": 30},
    "line": {"icon": "📈", "name": "Line Chart", "min_rows": 3, "max_categories": 100},
    "area": {"icon": "📉", "name": "Area Chart", "min_rows": 3, "max_categories": 100},
    "pie": {"icon": "🥧", "name": "Pie Chart", "min_rows": 2, "max_categories": 8},
    "donut": {"icon": "🍩", "name": "Donut Chart", "min_rows": 2, "max_categories": 8},
    "scatter": {"icon": "⚬", "name": "Scatter Plot", "min_rows": 5, "requires_two_numeric": True},
    "histogram": {"icon": "📊", "name": "Histogram", "min_rows": 10, "requires_numeric": True},
    "heatmap": {"icon": "🗺️", "name": "Heatmap", "min_rows": 4, "requires_pivot": True},
    "treemap": {"icon": "🌳", "name": "Treemap", "min_rows": 3, "max_categories": 30},
    "funnel": {"icon": "🔻", "name": "Funnel Chart", "min_rows": 3, "max_categories": 10},
    "table": {"icon": "📋", "name": "Data Table", "min_rows": 1},
}


_key_counts: Dict[str, int] = {}


def reset_key_counts():
    """Reset key counters. Call at the start of each Streamlit render cycle."""
    _key_counts.clear()


def get_unique_key(prefix: str, data: Any) -> str:
    """Generate a unique key based on data content, with collision avoidance."""
    data_str = str(data)[:1000]
    hash_val = hashlib.md5(data_str.encode()).hexdigest()[:8]
    base_key = f"{prefix}_{hash_val}"
    # Track how many times this base key has been requested in this render cycle
    _key_counts[base_key] = _key_counts.get(base_key, 0) + 1
    count = _key_counts[base_key]
    if count == 1:
        return base_key
    return f"{base_key}_{count}"


def analyze_data(df: pd.DataFrame) -> Dict:
    """Analyze DataFrame to determine best visualization options."""
    analysis = {
        "row_count": len(df),
        "col_count": len(df.columns),
        "numeric_cols": df.select_dtypes(include=["number"]).columns.tolist(),
        "categorical_cols": df.select_dtypes(include=["object", "category"]).columns.tolist(),
        "datetime_cols": df.select_dtypes(include=["datetime64"]).columns.tolist(),
        "has_dates": False,
        "suitable_charts": [],
        "recommended_chart": None,
        "x_col": None,
        "y_col": None,
    }

    # Check for date-like columns
    for col in analysis["categorical_cols"]:
        sample = df[col].iloc[0] if len(df) > 0 else ""
        if any(kw in str(col).lower() for kw in ["date", "time", "month", "year", "day"]):
            analysis["has_dates"] = True
            analysis["datetime_cols"].append(col)

    # Determine suitable charts
    num_cols = analysis["numeric_cols"]
    cat_cols = analysis["categorical_cols"]
    row_count = analysis["row_count"]

    # Always allow table
    analysis["suitable_charts"].append("table")

    if row_count >= 2:
        if cat_cols and num_cols:
            unique_cats = df[cat_cols[0]].nunique() if cat_cols else 0

            # Bar charts
            if unique_cats <= 20:
                analysis["suitable_charts"].extend(["bar", "horizontal_bar"])
                if unique_cats <= 8:
                    analysis["suitable_charts"].extend(["pie", "donut", "treemap"])
                if unique_cats <= 10:
                    analysis["suitable_charts"].append("funnel")

            # Line/Area for time-like data
            if analysis["has_dates"] or unique_cats <= 100:
                analysis["suitable_charts"].extend(["line", "area"])

        # Scatter requires 2 numeric
        if len(num_cols) >= 2 and row_count >= 5:
            analysis["suitable_charts"].append("scatter")

        # Histogram for numeric data
        if num_cols and row_count >= 10:
            analysis["suitable_charts"].append("histogram")

        # Heatmap for pivot-able data
        if len(cat_cols) >= 2 and num_cols and row_count >= 4:
            analysis["suitable_charts"].append("heatmap")

    # Remove duplicates while preserving order
    analysis["suitable_charts"] = list(dict.fromkeys(analysis["suitable_charts"]))

    # Determine recommended chart and columns
    if cat_cols and num_cols:
        analysis["x_col"] = cat_cols[0]
        analysis["y_col"] = num_cols[0]
        unique_x = df[cat_cols[0]].nunique()

        if analysis["has_dates"]:
            analysis["recommended_chart"] = "line"
        elif unique_x <= 6:
            analysis["recommended_chart"] = "bar"
        elif unique_x <= 15:
            analysis["recommended_chart"] = "horizontal_bar"
        else:
            analysis["recommended_chart"] = "table"
    elif len(num_cols) >= 2:
        analysis["x_col"] = num_cols[0]
        analysis["y_col"] = num_cols[1]
        analysis["recommended_chart"] = "scatter"
    else:
        analysis["recommended_chart"] = "table"

    return analysis


def create_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str = None,
    y_col: str = None,
    color_col: str = None,
    title: str = None,
    palette: str = "default",
    show_values: bool = True,
    height: int = 400,
) -> go.Figure:
    """Create a beautiful chart based on type and data."""
    colors = COLOR_PALETTES.get(palette, COLOR_PALETTES["default"])

    if not title:
        title = f"{y_col} by {x_col}" if x_col and y_col else "Data Visualization"

    # Common layout settings
    layout_common = dict(
        title=dict(text=title, font=dict(size=18, color="#333")),
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=60, r=40, t=60, b=60),
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_family="Inter"
        ),
    )

    fig = None

    if chart_type == "bar":
        fig = px.bar(
            df, x=x_col, y=y_col, color=color_col or x_col,
            color_discrete_sequence=colors,
            text=y_col if show_values else None
        )
        fig.update_traces(
            texttemplate='%{text:.2s}' if show_values else None,
            textposition='outside',
            marker_line_width=0,
        )
        fig.update_layout(showlegend=False if not color_col else True)

    elif chart_type == "horizontal_bar":
        fig = px.bar(
            df, x=y_col, y=x_col, color=color_col or x_col,
            orientation='h',
            color_discrete_sequence=colors,
            text=y_col if show_values else None
        )
        fig.update_traces(
            texttemplate='%{text:.2s}' if show_values else None,
            textposition='outside',
            marker_line_width=0,
        )
        fig.update_layout(showlegend=False if not color_col else True)

    elif chart_type == "line":
        fig = px.line(
            df.sort_values(x_col) if x_col else df,
            x=x_col, y=y_col, color=color_col,
            color_discrete_sequence=colors,
            markers=True
        )
        fig.update_traces(
            line=dict(width=3),
            marker=dict(size=8, line=dict(width=2, color='white'))
        )

    elif chart_type == "area":
        fig = px.area(
            df.sort_values(x_col) if x_col else df,
            x=x_col, y=y_col, color=color_col,
            color_discrete_sequence=colors
        )
        fig.update_traces(line=dict(width=2))

    elif chart_type == "pie":
        fig = px.pie(
            df, names=x_col, values=y_col,
            color_discrete_sequence=colors,
            hole=0
        )
        fig.update_traces(
            textposition='inside',
            textinfo='percent+label',
            marker=dict(line=dict(color='white', width=2))
        )

    elif chart_type == "donut":
        fig = px.pie(
            df, names=x_col, values=y_col,
            color_discrete_sequence=colors,
            hole=0.5
        )
        fig.update_traces(
            textposition='outside',
            textinfo='percent+label',
            marker=dict(line=dict(color='white', width=2))
        )
        # Add center text
        fig.add_annotation(
            text=f"<b>{df[y_col].sum():,.0f}</b><br>Total",
            x=0.5, y=0.5, font_size=16, showarrow=False
        )

    elif chart_type == "scatter":
        fig = px.scatter(
            df, x=x_col, y=y_col, color=color_col,
            color_discrete_sequence=colors,
            size_max=15
        )
        fig.update_traces(marker=dict(size=12, line=dict(width=1, color='white')))

    elif chart_type == "histogram":
        fig = px.histogram(
            df, x=y_col if y_col else x_col,
            color_discrete_sequence=colors,
            nbins=20
        )
        fig.update_traces(marker_line_width=1, marker_line_color="white")

    elif chart_type == "treemap":
        fig = px.treemap(
            df, path=[x_col], values=y_col,
            color_discrete_sequence=colors
        )

    elif chart_type == "funnel":
        fig = px.funnel(
            df, x=y_col, y=x_col,
            color_discrete_sequence=colors
        )

    elif chart_type == "heatmap":
        # Create pivot table for heatmap
        cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
        if len(cat_cols) >= 2:
            pivot = df.pivot_table(values=y_col, index=cat_cols[0], columns=cat_cols[1], aggfunc='sum', fill_value=0)
            fig = px.imshow(
                pivot,
                color_continuous_scale="Blues",
                aspect="auto"
            )

    if fig is None:
        # Fallback to bar chart
        fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=colors)

    # Apply common layout
    fig.update_layout(**layout_common)

    # Add grid styling
    fig.update_xaxes(
        showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)',
        showline=True, linewidth=1, linecolor='rgba(0,0,0,0.1)'
    )
    fig.update_yaxes(
        showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)',
        showline=True, linewidth=1, linecolor='rgba(0,0,0,0.1)'
    )

    return fig


def render_chart_selector(analysis: Dict, key_prefix: str) -> Tuple[str, str, str]:
    """Render chart type and column selectors."""
    suitable = analysis["suitable_charts"]

    # Create nice buttons for chart types
    st.markdown("**Select Chart Type:**")

    cols = st.columns(min(len(suitable), 6))
    selected_chart = analysis["recommended_chart"]

    for i, chart_type in enumerate(suitable[:6]):
        config = CHART_CONFIGS.get(chart_type, {})
        with cols[i % len(cols)]:
            is_recommended = chart_type == analysis["recommended_chart"]
            label = f"{config.get('icon', '📊')} {config.get('name', chart_type)}"
            if is_recommended:
                label += " ⭐"
            if st.button(label, key=f"{key_prefix}_btn_{chart_type}", width="stretch"):
                selected_chart = chart_type

    # If more than 6 charts, show dropdown
    if len(suitable) > 6:
        other_charts = suitable[6:]
        other_options = [f"{CHART_CONFIGS.get(c, {}).get('icon', '📊')} {CHART_CONFIGS.get(c, {}).get('name', c)}" for c in other_charts]
        selected_other = st.selectbox("More chart types:", [""] + other_options, key=f"{key_prefix}_more")
        if selected_other:
            idx = other_options.index(selected_other)
            selected_chart = other_charts[idx]

    # Column selectors
    x_col = analysis["x_col"]
    y_col = analysis["y_col"]

    if analysis["categorical_cols"] or analysis["numeric_cols"]:
        col1, col2 = st.columns(2)
        all_cols = analysis["categorical_cols"] + analysis["numeric_cols"]

        with col1:
            if analysis["categorical_cols"]:
                x_col = st.selectbox(
                    "Category/X-axis:",
                    analysis["categorical_cols"],
                    index=0 if analysis["x_col"] in analysis["categorical_cols"] else 0,
                    key=f"{key_prefix}_x"
                )

        with col2:
            if analysis["numeric_cols"]:
                y_col = st.selectbox(
                    "Value/Y-axis:",
                    analysis["numeric_cols"],
                    index=0,
                    key=f"{key_prefix}_y"
                )

    return selected_chart, x_col, y_col


def render_visualization(
    df: pd.DataFrame,
    title: str = None,
    key_prefix: str = "viz",
    show_selector: bool = True,
    default_expanded: bool = True,
    allow_download: bool = True,
) -> None:
    """Render complete visualization component with chart selection and popup."""

    if df is None or len(df) == 0:
        st.info("No data to visualize")
        return

    # Generate unique key
    unique_key = get_unique_key(key_prefix, df.to_dict())

    # Analyze data
    analysis = analyze_data(df)

    # If only 1 row or no suitable charts, just show table
    if len(df) == 1 or len(analysis["suitable_charts"]) <= 1:
        st.dataframe(df, width="stretch", hide_index=True)
        return

    with st.expander(f"📊 Visualization ({len(df)} rows)", expanded=default_expanded):

        # Chart type selector
        if show_selector:
            selected_chart, x_col, y_col = render_chart_selector(analysis, unique_key)
        else:
            selected_chart = analysis["recommended_chart"]
            x_col = analysis["x_col"]
            y_col = analysis["y_col"]

        # Display options
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            palette = st.selectbox(
                "Color theme:",
                list(COLOR_PALETTES.keys()),
                index=0,
                key=f"{unique_key}_palette"
            )
        with col2:
            chart_height = st.slider("Height:", 300, 600, 400, 50, key=f"{unique_key}_height")
        with col3:
            show_values = st.checkbox("Show values", value=True, key=f"{unique_key}_values")

        st.divider()

        # Render chart or table
        if selected_chart == "table":
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            try:
                fig = create_chart(
                    df,
                    chart_type=selected_chart,
                    x_col=x_col,
                    y_col=y_col,
                    title=title,
                    palette=palette,
                    show_values=show_values,
                    height=chart_height
                )

                # Configure for popup/fullscreen
                config = {
                    'displayModeBar': True,
                    'displaylogo': False,
                    'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'eraseshape'],
                    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                    'toImageButtonOptions': {
                        'format': 'png',
                        'filename': 'chart',
                        'height': 800,
                        'width': 1200,
                        'scale': 2
                    }
                }

                st.plotly_chart(fig, width="stretch", config=config)

                # Fullscreen / Enlarge button using modal
                render_fullscreen_button(fig, unique_key)

            except Exception as e:
                st.warning(f"Could not create {selected_chart} chart: {str(e)}")
                st.dataframe(df, width="stretch", hide_index=True)

        # Download options
        if allow_download:
            st.divider()
            col1, col2, col3 = st.columns(3)
            with col1:
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Download CSV",
                    csv,
                    f"data_{unique_key}.csv",
                    "text/csv",
                    key=f"{unique_key}_dl_csv",
                    width="stretch"
                )
            with col2:
                json_data = df.to_json(orient='records', indent=2)
                st.download_button(
                    "📥 Download JSON",
                    json_data,
                    f"data_{unique_key}.json",
                    "application/json",
                    key=f"{unique_key}_dl_json",
                    width="stretch"
                )
            with col3:
                if selected_chart != "table":
                    # Chart download handled by plotly toolbar
                    st.caption("💡 Use chart toolbar for image download")


def render_fullscreen_button(fig: go.Figure, key: str):
    """Render a fullscreen/enlarge button with modal dialog."""

    # Create an enlarged version of the chart
    if st.button("🔍 Enlarge Chart", key=f"{key}_enlarge", width="content"):
        st.session_state[f"{key}_fullscreen"] = True

    # Show modal if fullscreen is active
    if st.session_state.get(f"{key}_fullscreen", False):
        render_chart_modal(fig, key)


@st.dialog("📊 Chart View", width="large")
def render_chart_modal(fig: go.Figure, key: str):
    """Render chart in a modal/dialog for enlarged view."""

    # Make chart bigger
    fig_large = go.Figure(fig)
    fig_large.update_layout(height=600)

    config = {
        'displayModeBar': True,
        'displaylogo': False,
        'toImageButtonOptions': {
            'format': 'png',
            'filename': 'chart_enlarged',
            'height': 1200,
            'width': 1600,
            'scale': 2
        }
    }

    st.plotly_chart(fig_large, width="stretch", config=config)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Close", width="stretch"):
            st.session_state[f"{key}_fullscreen"] = False
            st.rerun()
    with col2:
        st.caption("💡 Use toolbar icons to download as PNG")


def suggest_visualizations(df: pd.DataFrame, query: str = "") -> List[Dict]:
    """Suggest appropriate visualizations based on data and query."""
    suggestions = []
    analysis = analyze_data(df)

    query_lower = query.lower()

    # Check query for visualization hints
    viz_keywords = {
        "trend": ["line", "area"],
        "over time": ["line", "area"],
        "compare": ["bar", "horizontal_bar"],
        "comparison": ["bar", "horizontal_bar"],
        "distribution": ["histogram", "pie", "donut"],
        "breakdown": ["pie", "donut", "treemap"],
        "proportion": ["pie", "donut"],
        "percentage": ["pie", "donut"],
        "correlation": ["scatter", "heatmap"],
        "relationship": ["scatter"],
        "top": ["bar", "horizontal_bar"],
        "ranking": ["horizontal_bar"],
        "composition": ["treemap", "pie"],
        "flow": ["funnel"],
        "stages": ["funnel"],
    }

    # Find matching keywords
    matched_charts = set()
    for keyword, charts in viz_keywords.items():
        if keyword in query_lower:
            matched_charts.update(charts)

    # Filter to suitable charts
    suitable = set(analysis["suitable_charts"])
    recommended = matched_charts & suitable if matched_charts else suitable

    # Build suggestions
    for chart_type in recommended:
        if chart_type == "table":
            continue
        config = CHART_CONFIGS.get(chart_type, {})
        suggestions.append({
            "type": chart_type,
            "icon": config.get("icon", "📊"),
            "name": config.get("name", chart_type),
            "reason": get_suggestion_reason(chart_type, analysis, query_lower),
            "recommended": chart_type == analysis["recommended_chart"]
        })

    # Sort: recommended first, then by suitability
    suggestions.sort(key=lambda x: (not x["recommended"], x["type"]))

    return suggestions[:5]  # Return top 5


def get_suggestion_reason(chart_type: str, analysis: Dict, query: str) -> str:
    """Get explanation for why a chart type is suggested."""
    reasons = {
        "bar": "Great for comparing values across categories",
        "horizontal_bar": "Perfect for ranking or when category names are long",
        "line": "Ideal for showing trends over time or sequences",
        "area": "Shows cumulative totals and trends",
        "pie": "Best for showing proportions of a whole (few categories)",
        "donut": "Modern pie chart with better readability",
        "scatter": "Reveals relationships between two numeric values",
        "histogram": "Shows distribution of numeric values",
        "heatmap": "Visualizes patterns across two categorical dimensions",
        "treemap": "Shows hierarchical proportions",
        "funnel": "Perfect for stage-based processes",
    }

    base_reason = reasons.get(chart_type, "Suitable for your data")

    # Add data-specific context
    if chart_type in ["pie", "donut"] and analysis.get("x_col"):
        unique = analysis.get("row_count", 0)
        if unique <= 5:
            base_reason += f" ({unique} categories)"

    if chart_type == "line" and analysis.get("has_dates"):
        base_reason += " (time-based data detected)"

    return base_reason


def render_chart_suggestions(df: pd.DataFrame, query: str = "", key_prefix: str = "suggest"):
    """Render chart suggestions with clickable options."""
    suggestions = suggest_visualizations(df, query)

    if not suggestions:
        return None

    st.markdown("**💡 Suggested visualizations:**")

    cols = st.columns(min(len(suggestions), 3))
    selected = None

    for i, sugg in enumerate(suggestions[:3]):
        with cols[i]:
            label = f"{sugg['icon']} {sugg['name']}"
            if sugg['recommended']:
                label += " ⭐"

            # Create a styled button with tooltip
            if st.button(
                label,
                key=f"{key_prefix}_{sugg['type']}",
                help=sugg['reason'],
                width="stretch"
            ):
                selected = sugg['type']

    # Show more suggestions if available
    if len(suggestions) > 3:
        with st.expander("More options"):
            for sugg in suggestions[3:]:
                st.markdown(f"{sugg['icon']} **{sugg['name']}**: {sugg['reason']}")

    return selected
