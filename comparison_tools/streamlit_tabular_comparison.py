#!/usr/bin/env python3
"""
Streamlit Individual Architecture Tables Comparison Dashboard
============================================================
Displays individual architecture tables with global insights and detailed filtering.
Run with: streamlit run comparison_tools/streamlit_tabular_comparison.py
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict
import numpy as np
import os


@st.cache_data
def load_all_architecture_tables():
    """Load all individual architecture tables"""
    comparison_dir = Path("comparison_output")
    architecture_tables = {}
    failed_files = []
    all_files = list(comparison_dir.glob("*_detailed_comparison.csv"))

    for csv_file in all_files:
        arch_id = csv_file.stem.replace("_detailed_comparison", "")
        try:
            df = pd.read_csv(csv_file)
            architecture_tables[arch_id] = df
        except Exception as e:
            failed_files.append(f"{csv_file.name} ({e})")

    loaded_count = len(architecture_tables)
    total_count = len(all_files)
    if loaded_count == total_count:
        st.success(
            f"✅ Loaded {loaded_count} out of {total_count} architecture tables."
        )
    else:
        st.warning(f"⚠️ Loaded {loaded_count} out of {total_count} architecture tables.")
        if failed_files:
            st.error("Failed to load: " + ", ".join(failed_files))

    return architecture_tables


def create_global_summary_metrics(architecture_tables):
    """Create global summary metrics across all architectures"""
    total_architectures = len(architecture_tables)

    # Calculate global statistics
    total_attributes = sum(len(df) for df in architecture_tables.values())
    total_modified = sum(
        len(df[df["Status"] == "Modified"]) for df in architecture_tables.values()
    )
    total_same = sum(
        len(df[df["Status"] == "Same"]) for df in architecture_tables.values()
    )
    total_baseline_only = sum(
        len(df[df["Status"] == "Baseline_Only"]) for df in architecture_tables.values()
    )
    total_enhanced_only = sum(
        len(df[df["Status"] == "Enhanced_Only"]) for df in architecture_tables.values()
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Architectures", total_architectures)

    with col2:
        st.metric("Total Attributes", total_attributes)

    with col3:
        st.metric("Modified Attributes", total_modified)

    with col4:
        st.metric("Same Attributes", total_same)

    with col5:
        change_rate = (
            (total_modified + total_baseline_only + total_enhanced_only)
            / total_attributes
            * 100
            if total_attributes > 0
            else 0
        )
        st.metric("Change Rate", f"{change_rate:.1f}%")


def create_global_insights_charts(architecture_tables):
    """Create global insights charts"""

    # Prepare data for charts
    service_changes = defaultdict(int)
    component_changes = defaultdict(int)
    status_distribution = defaultdict(int)
    arch_change_counts = {}

    for arch_id, df in architecture_tables.items():
        # Count changes by service
        for service in df["Service"].unique():
            service_df = df[df["Service"] == service]
            if len(service_df[service_df["Status"] != "Same"]) > 0:
                service_changes[service] += 1

        # Count changes by component
        for component in df["Component"].unique():
            component_df = df[df["Component"] == component]
            if len(component_df[component_df["Status"] != "Same"]) > 0:
                component_changes[component] += 1

        # Count by status
        for status in df["Status"].unique():
            status_distribution[status] += len(df[df["Status"] == status])

        # Count total changes per architecture
        arch_change_counts[arch_id] = len(df[df["Status"] != "Same"])

    col1, col2 = st.columns(2)

    with col1:
        # Service change frequency
        if service_changes:
            service_df = pd.DataFrame.from_records(
                list(service_changes.items()),
                columns=["Service", "Architectures_Changed"],
            )
            service_df = service_df.sort_values("Architectures_Changed", ascending=True)

            fig = px.bar(
                service_df,
                x="Architectures_Changed",
                y="Service",
                orientation="h",
                title="Services Changed Across Architectures",
                color="Architectures_Changed",
                color_continuous_scale="Reds",
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Status distribution
        if status_distribution:
            status_df = pd.DataFrame.from_records(
                list(status_distribution.items()), columns=["Status", "Count"]
            )

            fig = px.pie(
                status_df,
                values="Count",
                names="Status",
                title="Global Status Distribution",
                color_discrete_map={
                    "Same": "#2E8B57",
                    "Modified": "#FF6B6B",
                    "Baseline_Only": "#FFA500",
                    "Enhanced_Only": "#4ECDC4",
                },
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

    # Architecture change frequency
    if arch_change_counts:
        arch_df = pd.DataFrame.from_records(
            list(arch_change_counts.items()), columns=["Architecture", "Changes"]
        )
        arch_df = arch_df.sort_values("Changes", ascending=False)

        fig = px.bar(
            arch_df,
            x="Architecture",
            y="Changes",
            title="Number of Changes per Architecture",
            color="Changes",
            color_continuous_scale="Reds",
        )
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)


def show_architecture_details(selected_arch, df):
    """Show detailed view for selected architecture"""

    # Summary metrics for selected architecture
    total_attributes = len(df)
    same_count = len(df[df["Status"] == "Same"])
    modified_count = len(df[df["Status"] == "Modified"])
    baseline_only_count = len(df[df["Status"] == "Baseline_Only"])
    enhanced_only_count = len(df[df["Status"] == "Enhanced_Only"])

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Attributes", total_attributes)

    with col2:
        st.metric("Same", same_count, delta=f"{same_count/total_attributes*100:.1f}%")

    with col3:
        st.metric(
            "Modified",
            modified_count,
            delta=f"{modified_count/total_attributes*100:.1f}%",
        )

    with col4:
        st.metric("Baseline Only", baseline_only_count)

    with col5:
        st.metric("Enhanced Only", enhanced_only_count)

    # Filters
    st.subheader("🔍 Filters")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        status_filter = st.multiselect(
            "Status", df["Status"].unique(), default=df["Status"].unique()
        )

    with col2:
        service_filter = st.multiselect(
            "Service", df["Service"].unique(), default=df["Service"].unique()
        )

    with col3:
        component_filter = st.multiselect(
            "Component", df["Component"].unique(), default=df["Component"].unique()
        )

    with col4:
        attribute_filter = st.multiselect(
            "Attribute", df["Attribute"].unique(), default=df["Attribute"].unique()
        )

    # Apply filters
    filtered_df = df[
        (df["Status"].isin(status_filter))
        & (df["Service"].isin(service_filter))
        & (df["Component"].isin(component_filter))
        & (df["Attribute"].isin(attribute_filter))
    ]

    st.write(f"Showing {len(filtered_df)} of {len(df)} attributes")

    # Architecture-specific insights
    st.subheader("💡 Architecture Insights")

    col1, col2 = st.columns(2)

    with col1:
        # Service breakdown
        service_stats = (
            df.groupby("Service")
            .agg({"Status": lambda x: (x != "Same").sum()})
            .reset_index()
        )
        service_stats.columns = ["Service", "Changes"]

        if len(service_stats) > 0:
            fig = px.bar(
                service_stats,
                x="Service",
                y="Changes",
                title=f"Changes by Service in {selected_arch}",
                color="Changes",
                color_continuous_scale="Reds",
            )
            fig.update_layout(height=300, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Status breakdown
        status_stats = df["Status"].value_counts()

        fig = px.pie(
            values=status_stats.values,
            names=status_stats.index,
            title=f"Status Distribution in {selected_arch}",
            color_discrete_map={
                "Same": "#2E8B57",
                "Modified": "#FF6B6B",
                "Baseline_Only": "#FFA500",
                "Enhanced_Only": "#4ECDC4",
            },
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    # Key insights text
    st.subheader("🔍 Key Insights")

    # Most changed service
    if len(service_stats) > 0:
        most_changed_service = service_stats.loc[service_stats["Changes"].idxmax()]
        st.info(
            f"**{most_changed_service['Service']}** has the most changes ({most_changed_service['Changes']} attributes)"
        )

    # Most changed component
    component_stats = (
        df.groupby("Component")
        .agg({"Status": lambda x: (x != "Same").sum()})
        .reset_index()
    )
    component_stats.columns = ["Component", "Changes"]

    if len(component_stats) > 0:
        most_changed_component = component_stats.loc[
            component_stats["Changes"].idxmax()
        ]
        st.info(
            f"**{most_changed_component['Component']}** component has the most changes ({most_changed_component['Changes']} attributes)"
        )

    # Change rate
    change_rate = (
        (modified_count + baseline_only_count + enhanced_only_count)
        / total_attributes
        * 100
    )
    if change_rate > 50:
        st.warning(f"This architecture has a **high change rate** ({change_rate:.1f}%)")
    elif change_rate > 20:
        st.info(
            f"This architecture has a **moderate change rate** ({change_rate:.1f}%)"
        )
    else:
        st.success(f"This architecture has a **low change rate** ({change_rate:.1f}%)")

    # Display filtered table
    st.subheader("📋 Detailed Comparison Table")

    # Style the dataframe
    def style_status(val):
        if val == "Same":
            return "background-color: #d4edda; color: #155724"
        elif val == "Modified":
            return "background-color: #f8d7da; color: #721c24"
        elif val == "Baseline_Only":
            return "background-color: #fff3cd; color: #856404"
        elif val == "Enhanced_Only":
            return "background-color: #d1ecf1; color: #0c5460"
        return ""

    styled_df = filtered_df.style.map(style_status, subset=["Status"])
    st.dataframe(styled_df, use_container_width=True)

    # Export options
    st.subheader("📤 Export Options")
    col1, col2 = st.columns(2)

    with col1:
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="Download Filtered Data (CSV)",
            data=csv,
            file_name=f"{selected_arch}_filtered_comparison.csv",
            mime="text/csv",
        )

    with col2:
        csv_full = df.to_csv(index=False)
        st.download_button(
            label="Download Full Data (CSV)",
            data=csv_full,
            file_name=f"{selected_arch}_full_comparison.csv",
            mime="text/csv",
        )


def main():
    """Main Streamlit application"""

    st.set_page_config(
        page_title="Individual Architecture Comparison Dashboard",
        page_icon="🏗️",
        layout="wide",
    )

    st.title("🏗️ Individual Architecture Comparison Dashboard")
    st.markdown("**Detailed comparison of baseline vs enhanced cloud architectures**")

    # Load all architecture tables
    with st.spinner("Loading architecture tables..."):
        architecture_tables = load_all_architecture_tables()

    if not architecture_tables:
        st.error(
            "No architecture tables found. Please run the comparison script first."
        )
        st.info(
            "Expected files: *_detailed_comparison.csv (e.g., data-sync-and-processing-architecture-3_detailed_comparison.csv)"
        )
        return

    # Create tabs
    tab1, tab2 = st.tabs(["🌍 Global Insights", "🏗️ Architecture Details"])

    with tab1:
        st.header("🌍 Global Insights Across All Architectures")

        # Global summary metrics
        create_global_summary_metrics(architecture_tables)
        st.markdown("---")

        # Global insights charts
        create_global_insights_charts(architecture_tables)

        # Additional insights
        st.subheader("💡 Cross-Architecture Patterns")

        # Find most commonly changed services
        service_change_counts = defaultdict(int)
        for df in architecture_tables.values():
            for service in df["Service"].unique():
                service_df = df[df["Service"] == service]
                if len(service_df[service_df["Status"] != "Same"]) > 0:
                    service_change_counts[service] += 1

        if service_change_counts:
            most_changed_service = max(
                service_change_counts.items(), key=lambda x: x[1]
            )
            st.info(
                f"**{most_changed_service[0]}** is the most commonly changed service (modified in {most_changed_service[1]}/{len(architecture_tables)} architectures)"
            )

        # Find architectures with most changes
        arch_change_counts = {}
        for arch_id, df in architecture_tables.items():
            arch_change_counts[arch_id] = len(df[df["Status"] != "Same"])

        if arch_change_counts:
            most_changed_arch = max(arch_change_counts.items(), key=lambda x: x[1])
            least_changed_arch = min(arch_change_counts.items(), key=lambda x: x[1])

            col1, col2 = st.columns(2)
            with col1:
                st.warning(
                    f"**{most_changed_arch[0]}** has the most changes ({most_changed_arch[1]} attributes)"
                )
            with col2:
                st.success(
                    f"**{least_changed_arch[0]}** has the fewest changes ({least_changed_arch[1]} attributes)"
                )

    with tab2:
        st.header("🏗️ Individual Architecture Details")

        # Architecture selector
        architecture_options = sorted(architecture_tables.keys())
        selected_arch = st.selectbox("Select Architecture:", architecture_options)

        if selected_arch:
            df = architecture_tables[selected_arch]
            show_architecture_details(selected_arch, df)

    # Footer
    st.markdown("---")
    st.markdown(
        "**Legend:** Same = Identical | Modified = Different values | "
        "Baseline_Only = Exists only in baseline | Enhanced_Only = Exists only in enhanced"
    )


if __name__ == "__main__":
    main()
