#!/usr/bin/env python3
"""
Tabular Architecture Comparison Tool
====================================
Creates individual tables for each architecture with attribute-level comparison.
Each row represents: Service | Component | Attribute | Baseline_Values | Enhanced_Values | etc.
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class AttributeComparisonRow:
    """Structure for each attribute-level row in the detailed comparison"""

    service_name: str
    component_name: str
    attribute_name: str
    baseline_values: str
    enhanced_values: str
    baseline_constraint: str
    enhanced_constraint: str
    baseline_unit: str
    enhanced_unit: str
    status: str  # Same, Modified, Baseline_Only, Enhanced_Only
    baseline_reasoning: str
    enhanced_reasoning: str


@dataclass
class TabularComparisonRow:
    """Structure for each row in the tabular comparison"""

    architecture_id: str
    services_same: int  # 1 or 0
    components_same: int  # 1 or 0
    attributes_same: int  # 1 or 0
    configurations_same: int  # 1 or 0

    # Complete lists for both baseline and enhanced
    services_baseline_all: str
    services_enhanced_all: str
    components_baseline_all: str
    components_enhanced_all: str
    attributes_baseline_all: str
    attributes_enhanced_all: str
    configurations_baseline_all: str
    configurations_enhanced_all: str

    # Separate difference columns
    services_baseline_only: str
    services_enhanced_only: str
    components_baseline_only: str
    components_enhanced_only: str
    attributes_baseline_only: str
    attributes_enhanced_only: str
    configurations_baseline_only: str
    configurations_enhanced_only: str

    reasoning_description: str


class TabularArchitectureComparator:
    """Creates individual architecture tables with attribute-level comparison"""

    def __init__(
        self,
        baseline_file: Path,
        enhanced_file: Path,
        baseline_reasoning_file: Path,
        enhanced_reasoning_file: Path,
    ):
        self.baseline_data = self._load_json(baseline_file)
        self.enhanced_data = self._load_json(enhanced_file)
        self.baseline_reasoning = self._load_json(baseline_reasoning_file)
        self.enhanced_reasoning = self._load_json(enhanced_reasoning_file)

        # Create reasoning lookup tables
        self.baseline_reasoning_lookup = self._create_reasoning_lookup(
            self.baseline_reasoning
        )
        self.enhanced_reasoning_lookup = self._create_reasoning_lookup(
            self.enhanced_reasoning
        )

    def _load_json(self, file_path: Path) -> Dict:
        """Load JSON file with error handling"""
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return {}

    def _create_reasoning_lookup(self, reasoning_data: Dict) -> Dict:
        """Create lookup table for reasoning by service name"""
        lookup = {}
        for reasoning_obj in reasoning_data.get("reasoning_objects", []):
            service_name = reasoning_obj.get("service_codename")
            if service_name:
                lookup[service_name] = reasoning_obj
        return lookup

    def _get_service_reasoning(self, service_name: str, reasoning_lookup: Dict) -> str:
        """Extract relevant reasoning information for a service"""
        reasoning_obj = reasoning_lookup.get(service_name, {})
        if not reasoning_obj:
            return "No reasoning available"

        # Extract key reasoning information
        reasoning_parts = []

        # Service understanding
        service_understanding = reasoning_obj.get("service_understanding", "")
        if service_understanding:
            reasoning_parts.append(f"Service purpose: {service_understanding[:200]}...")

        # Attribute selection rationale
        attr_rationale = reasoning_obj.get("attribute_selection_rationale", "")
        if attr_rationale:
            reasoning_parts.append(f"Attribute selection: {attr_rationale[:200]}...")

        # Critical attributes reasoning
        critical_attrs = reasoning_obj.get("critical_attributes_reasoning", "")
        if critical_attrs:
            reasoning_parts.append(f"Critical attributes: {critical_attrs[:200]}...")

        # Alternatives considered
        alternatives = reasoning_obj.get("alternatives_considered", [])
        if alternatives and len(alternatives) > 0:
            alt_text = (
                str(alternatives[0])
                if isinstance(alternatives[0], str)
                else str(alternatives[0])
            )
            reasoning_parts.append(f"Alternatives: {alt_text[:200]}...")

        if reasoning_parts:
            return " | ".join(reasoning_parts)
        else:
            return "No specific reasoning details available"

    def _get_attribute_specific_reasoning(
        self, service_name: str, attribute_name: str, reasoning_lookup: Dict
    ) -> str:
        """Extract attribute-specific reasoning information"""
        reasoning_obj = reasoning_lookup.get(service_name, {})
        if not reasoning_obj:
            return "No reasoning available"

        # Look for attribute-specific mentions in reasoning
        attribute_reasoning = []

        # Check critical attributes reasoning for this specific attribute
        critical_attrs = reasoning_obj.get("critical_attributes_reasoning", "")
        if critical_attrs and attribute_name.lower() in critical_attrs.lower():
            # Extract the sentence or paragraph mentioning this attribute
            sentences = critical_attrs.split(". ")
            for sentence in sentences:
                if attribute_name.lower() in sentence.lower():
                    attribute_reasoning.append(f"Critical: {sentence[:150]}...")
                    break

        # Check attribute selection rationale for this specific attribute
        attr_rationale = reasoning_obj.get("attribute_selection_rationale", "")
        if attr_rationale and attribute_name.lower() in attr_rationale.lower():
            sentences = attr_rationale.split(". ")
            for sentence in sentences:
                if attribute_name.lower() in sentence.lower():
                    attribute_reasoning.append(f"Selection: {sentence[:150]}...")
                    break

        # Check service understanding for attribute context
        service_understanding = reasoning_obj.get("service_understanding", "")
        if (
            service_understanding
            and attribute_name.lower() in service_understanding.lower()
        ):
            sentences = service_understanding.split(". ")
            for sentence in sentences:
                if attribute_name.lower() in sentence.lower():
                    attribute_reasoning.append(f"Context: {sentence[:150]}...")
                    break

        if attribute_reasoning:
            return " | ".join(attribute_reasoning)
        else:
            # Fallback to general service reasoning if no attribute-specific info found
            return self._get_service_reasoning(service_name, reasoning_lookup)

    def create_individual_architecture_tables(
        self, output_dir: Path
    ) -> Dict[str, pd.DataFrame]:
        """Create individual detailed tables for each architecture"""
        baseline_archs = {
            arch["architecture_id"]: arch
            for arch in self.baseline_data.get("architectures", [])
        }
        enhanced_archs = {
            arch["architecture_id"]: arch
            for arch in self.enhanced_data.get("architectures", [])
        }

        all_arch_ids = sorted(set(baseline_archs.keys()) | set(enhanced_archs.keys()))

        print(f"🔍 Creating individual tables for {len(all_arch_ids)} architectures...")

        architecture_tables = {}

        for arch_id in all_arch_ids:
            print(f"  📋 Processing {arch_id}")
            baseline_arch = baseline_archs.get(arch_id)
            enhanced_arch = enhanced_archs.get(arch_id)

            # Create detailed table for this architecture
            df = self._create_architecture_detailed_table(
                arch_id, baseline_arch, enhanced_arch
            )
            architecture_tables[arch_id] = df

            # Save individual CSV file
            output_file = output_dir / f"{arch_id}_detailed_comparison.csv"
            df.to_csv(output_file, index=False)
            print(f"    ✅ Saved: {output_file}")

        return architecture_tables

    def _create_architecture_detailed_table(
        self, arch_id: str, baseline_arch: Optional[Dict], enhanced_arch: Optional[Dict]
    ) -> pd.DataFrame:
        """Create detailed attribute-level comparison table for a single architecture"""

        comparison_rows = []

        # Extract architecture structures
        baseline_structure = (
            self._extract_architecture_structure(baseline_arch)
            if baseline_arch
            else {"services": {}}
        )
        enhanced_structure = (
            self._extract_architecture_structure(enhanced_arch)
            if enhanced_arch
            else {"services": {}}
        )

        # Get all services from both architectures
        all_services = set(baseline_structure["services"].keys()) | set(
            enhanced_structure["services"].keys()
        )

        for service_name in sorted(all_services):
            baseline_service = baseline_structure["services"].get(service_name, {})
            enhanced_service = enhanced_structure["services"].get(service_name, {})

            # Get all components from both baseline and enhanced for this service
            baseline_components = (
                baseline_service.get("components", {}) if baseline_service else {}
            )
            enhanced_components = (
                enhanced_service.get("components", {}) if enhanced_service else {}
            )
            all_components = set(baseline_components.keys()) | set(
                enhanced_components.keys()
            )

            for component_name in sorted(all_components):
                baseline_component = (
                    baseline_components.get(component_name, {})
                    if baseline_components
                    else {}
                )
                enhanced_component = (
                    enhanced_components.get(component_name, {})
                    if enhanced_components
                    else {}
                )

                # Get all attributes from both baseline and enhanced for this component
                baseline_attributes = (
                    baseline_component.get("attributes_search_space", [])
                    if baseline_component
                    else []
                )
                enhanced_attributes = (
                    enhanced_component.get("attributes_search_space", [])
                    if enhanced_component
                    else []
                )

                # Create lookup for attributes by name
                baseline_attr_lookup = {
                    attr.get("attribute_codename", "unknown"): attr
                    for attr in baseline_attributes
                }
                enhanced_attr_lookup = {
                    attr.get("attribute_codename", "unknown"): attr
                    for attr in enhanced_attributes
                }

                all_attr_names = set(baseline_attr_lookup.keys()) | set(
                    enhanced_attr_lookup.keys()
                )

                for attr_name in sorted(all_attr_names):
                    baseline_attr = baseline_attr_lookup.get(attr_name)
                    enhanced_attr = enhanced_attr_lookup.get(attr_name)

                    # Determine status and values
                    if baseline_attr and enhanced_attr:
                        # Attribute exists in both
                        baseline_values = str(
                            baseline_attr.get("attribute_values", "-")
                        )
                        enhanced_values = str(
                            enhanced_attr.get("attribute_values", "-")
                        )
                        baseline_constraint = str(
                            baseline_attr.get("attribute_constraint_expr", "-")
                        )
                        enhanced_constraint = str(
                            enhanced_attr.get("attribute_constraint_expr", "-")
                        )
                        baseline_unit = str(baseline_attr.get("attribute_unit", "-"))
                        enhanced_unit = str(enhanced_attr.get("attribute_unit", "-"))

                        # Determine if same or modified
                        if (
                            baseline_values == enhanced_values
                            and baseline_constraint == enhanced_constraint
                            and baseline_unit == enhanced_unit
                        ):
                            status = "Same"
                        else:
                            status = "Modified"

                    elif baseline_attr:
                        # Attribute exists only in baseline
                        baseline_values = str(
                            baseline_attr.get("attribute_values", "-")
                        )
                        enhanced_values = "-"
                        baseline_constraint = str(
                            baseline_attr.get("attribute_constraint_expr", "-")
                        )
                        enhanced_constraint = "-"
                        baseline_unit = str(baseline_attr.get("attribute_unit", "-"))
                        enhanced_unit = "-"
                        status = "Baseline_Only"

                    else:
                        # Attribute exists only in enhanced
                        baseline_values = "-"
                        enhanced_values = str(
                            enhanced_attr.get("attribute_values", "-")
                            if enhanced_attr
                            else "-"
                        )
                        baseline_constraint = "-"
                        enhanced_constraint = str(
                            enhanced_attr.get("attribute_constraint_expr", "-")
                            if enhanced_attr
                            else "-"
                        )
                        baseline_unit = "-"
                        enhanced_unit = str(
                            enhanced_attr.get("attribute_unit", "-")
                            if enhanced_attr
                            else "-"
                        )
                        status = "Enhanced_Only"

                    # Get attribute-specific reasoning
                    baseline_reasoning = self._get_attribute_specific_reasoning(
                        service_name, attr_name, self.baseline_reasoning_lookup
                    )
                    enhanced_reasoning = self._get_attribute_specific_reasoning(
                        service_name, attr_name, self.enhanced_reasoning_lookup
                    )

                    # Create row
                    row = AttributeComparisonRow(
                        service_name=service_name,
                        component_name=component_name,
                        attribute_name=attr_name,
                        baseline_values=baseline_values,
                        enhanced_values=enhanced_values,
                        baseline_constraint=baseline_constraint,
                        enhanced_constraint=enhanced_constraint,
                        baseline_unit=baseline_unit,
                        enhanced_unit=enhanced_unit,
                        status=status,
                        baseline_reasoning=baseline_reasoning,
                        enhanced_reasoning=enhanced_reasoning,
                    )
                    comparison_rows.append(row)

        # Convert to DataFrame
        df_data = []
        for row in comparison_rows:
            df_data.append(
                {
                    "Service": row.service_name,
                    "Component": row.component_name,
                    "Attribute": row.attribute_name,
                    "Baseline_Values": row.baseline_values,
                    "Enhanced_Values": row.enhanced_values,
                    "Baseline_Constraint": row.baseline_constraint,
                    "Enhanced_Constraint": row.enhanced_constraint,
                    "Baseline_Unit": row.baseline_unit,
                    "Enhanced_Unit": row.enhanced_unit,
                    "Status": row.status,
                    "Baseline_Reasoning": row.baseline_reasoning,
                    "Enhanced_Reasoning": row.enhanced_reasoning,
                }
            )

        df = pd.DataFrame(df_data)

        # Add summary statistics
        total_attributes = len(df)
        same_count = len(df[df["Status"] == "Same"])
        modified_count = len(df[df["Status"] == "Modified"])
        baseline_only_count = len(df[df["Status"] == "Baseline_Only"])
        enhanced_only_count = len(df[df["Status"] == "Enhanced_Only"])

        print(f"    📊 {arch_id}: {total_attributes} attributes total")
        print(f"       Same: {same_count}, Modified: {modified_count}")
        print(
            f"       Baseline_Only: {baseline_only_count}, Enhanced_Only: {enhanced_only_count}"
        )

        return df

    def compare_all_architectures_tabular(self) -> List[TabularComparisonRow]:
        """Generate tabular comparison data"""
        baseline_archs = {
            arch["architecture_id"]: arch
            for arch in self.baseline_data.get("architectures", [])
        }
        enhanced_archs = {
            arch["architecture_id"]: arch
            for arch in self.enhanced_data.get("architectures", [])
        }

        all_arch_ids = sorted(set(baseline_archs.keys()) | set(enhanced_archs.keys()))

        print(
            f"🔍 Creating tabular comparison for {len(all_arch_ids)} architectures..."
        )

        comparison_rows = []

        for arch_id in all_arch_ids:
            print(f"  📋 Processing {arch_id}")
            baseline_arch = baseline_archs.get(arch_id)
            enhanced_arch = enhanced_archs.get(arch_id)

            row = self._create_comparison_row(arch_id, baseline_arch, enhanced_arch)
            comparison_rows.append(row)

        return comparison_rows

    def _create_comparison_row(
        self, arch_id: str, baseline_arch: Optional[Dict], enhanced_arch: Optional[Dict]
    ) -> TabularComparisonRow:
        """Create a single row of tabular comparison"""

        # Handle missing architectures
        if not baseline_arch:
            enhanced_structure = (
                self._extract_architecture_structure(enhanced_arch)
                if enhanced_arch
                else {"services": {}}
            )
            return TabularComparisonRow(
                architecture_id=arch_id,
                services_same=0,
                components_same=0,
                attributes_same=0,
                configurations_same=0,
                services_baseline_all="",
                services_enhanced_all=self._get_all_services_list(enhanced_structure),
                components_baseline_all="",
                components_enhanced_all=self._get_all_components_list(
                    enhanced_structure
                ),
                attributes_baseline_all="",
                attributes_enhanced_all=self._get_all_attributes_list(
                    enhanced_structure
                ),
                configurations_baseline_all="",
                configurations_enhanced_all=self._get_all_configurations_list(
                    enhanced_structure
                ),
                services_baseline_only="",
                services_enhanced_only=self._get_all_services_list(enhanced_structure),
                components_baseline_only="",
                components_enhanced_only=self._get_all_components_list(
                    enhanced_structure
                ),
                attributes_baseline_only="",
                attributes_enhanced_only=self._get_all_attributes_list(
                    enhanced_structure
                ),
                configurations_baseline_only="",
                configurations_enhanced_only=self._get_all_configurations_list(
                    enhanced_structure
                ),
                reasoning_description="Architecture exists only in enhanced dataset",
            )

        if not enhanced_arch:
            baseline_structure = (
                self._extract_architecture_structure(baseline_arch)
                if baseline_arch
                else {"services": {}}
            )
            return TabularComparisonRow(
                architecture_id=arch_id,
                services_same=0,
                components_same=0,
                attributes_same=0,
                configurations_same=0,
                services_baseline_all=self._get_all_services_list(baseline_structure),
                services_enhanced_all="",
                components_baseline_all=self._get_all_components_list(
                    baseline_structure
                ),
                components_enhanced_all="",
                attributes_baseline_all=self._get_all_attributes_list(
                    baseline_structure
                ),
                attributes_enhanced_all="",
                configurations_baseline_all=self._get_all_configurations_list(
                    baseline_structure
                ),
                configurations_enhanced_all="",
                services_baseline_only=self._get_all_services_list(baseline_structure),
                services_enhanced_only="",
                components_baseline_only=self._get_all_components_list(
                    baseline_structure
                ),
                components_enhanced_only="",
                attributes_baseline_only=self._get_all_attributes_list(
                    baseline_structure
                ),
                attributes_enhanced_only="",
                configurations_baseline_only=self._get_all_configurations_list(
                    baseline_structure
                ),
                configurations_enhanced_only="",
                reasoning_description="Architecture exists only in baseline dataset",
            )

        # Extract architecture structures
        baseline_structure = self._extract_architecture_structure(baseline_arch)
        enhanced_structure = self._extract_architecture_structure(enhanced_arch)

        # Compare at each level
        services_comparison = self._compare_services_level(
            baseline_structure, enhanced_structure
        )
        components_comparison = self._compare_components_level(
            baseline_structure, enhanced_structure
        )
        attributes_comparison = self._compare_attributes_level(
            baseline_structure, enhanced_structure
        )
        configurations_comparison = self._compare_configurations_level(
            baseline_structure, enhanced_structure
        )

        # Get reasoning description
        reasoning_desc = self._get_reasoning_description(
            baseline_structure, enhanced_structure
        )

        return TabularComparisonRow(
            architecture_id=arch_id,
            services_same=1 if services_comparison["same"] else 0,
            components_same=1 if components_comparison["same"] else 0,
            attributes_same=1 if attributes_comparison["same"] else 0,
            configurations_same=1 if configurations_comparison["same"] else 0,
            services_baseline_all=self._get_all_services_list(baseline_structure),
            services_enhanced_all=self._get_all_services_list(enhanced_structure),
            components_baseline_all=self._get_all_components_list(baseline_structure),
            components_enhanced_all=self._get_all_components_list(enhanced_structure),
            attributes_baseline_all=self._get_all_attributes_list(baseline_structure),
            attributes_enhanced_all=self._get_all_attributes_list(enhanced_structure),
            configurations_baseline_all=self._get_all_configurations_list(
                baseline_structure
            ),
            configurations_enhanced_all=self._get_all_configurations_list(
                enhanced_structure
            ),
            services_baseline_only=services_comparison["baseline_only"],
            services_enhanced_only=services_comparison["enhanced_only"],
            components_baseline_only=components_comparison["baseline_only"],
            components_enhanced_only=components_comparison["enhanced_only"],
            attributes_baseline_only=attributes_comparison["baseline_only"],
            attributes_enhanced_only=attributes_comparison["enhanced_only"],
            configurations_baseline_only=configurations_comparison["baseline_only"],
            configurations_enhanced_only=configurations_comparison["enhanced_only"],
            reasoning_description=reasoning_desc,
        )

    def _extract_architecture_structure(self, arch_data: Dict) -> Dict:
        """Extract clean architecture structure for comparison"""
        if not arch_data:
            return {"services": {}}

        services = {}
        for component in arch_data.get("components_search_space", []):
            component_id = component.get("component_id", "")
            service_space = component.get("service_search_space", {})
            service_codename = service_space.get("service_codename", "Unknown")

            if service_codename not in services:
                services[service_codename] = {
                    "service_codename": service_codename,
                    "select_attributes": service_space.get(
                        "service_select_attributes", []
                    ),
                    "components": {},
                }

            # Add component details
            for service_component in service_space.get(
                "service_components_search_spaces", []
            ):
                comp_name = service_component.get(
                    "service_component_codename", "Unknown"
                )
                full_comp_name = f"{component_id}_{comp_name}"

                services[service_codename]["components"][full_comp_name] = {
                    "component_id": component_id,
                    "service_component_codename": comp_name,
                    "attributes_search_space": service_component.get(
                        "attributes_search_space", []
                    ),
                    "number_of_instances": service_component.get(
                        "number_of_instances", 1
                    ),
                    "service_component_sort": service_component.get(
                        "service_component_sort", []
                    ),
                }

        return {"services": services}

    def _compare_services_level(
        self, baseline_structure: Dict, enhanced_structure: Dict
    ) -> Dict:
        """Compare at services level"""
        baseline_services = set(baseline_structure["services"].keys())
        enhanced_services = set(enhanced_structure["services"].keys())

        same = baseline_services == enhanced_services
        baseline_only = baseline_services - enhanced_services
        enhanced_only = enhanced_services - baseline_services

        return {
            "same": same,
            "baseline_only": "; ".join(sorted(baseline_only)) if baseline_only else "",
            "enhanced_only": "; ".join(sorted(enhanced_only)) if enhanced_only else "",
        }

    def _compare_components_level(
        self, baseline_structure: Dict, enhanced_structure: Dict
    ) -> Dict:
        """Compare at components level"""
        baseline_components = {}
        enhanced_components = {}

        # Flatten all components across services
        for service_name, service_data in baseline_structure["services"].items():
            for comp_name, comp_data in service_data["components"].items():
                baseline_components[f"{service_name}::{comp_name}"] = comp_data

        for service_name, service_data in enhanced_structure["services"].items():
            for comp_name, comp_data in service_data["components"].items():
                enhanced_components[f"{service_name}::{comp_name}"] = comp_data

        baseline_comp_keys = set(baseline_components.keys())
        enhanced_comp_keys = set(enhanced_components.keys())

        same = baseline_comp_keys == enhanced_comp_keys
        baseline_only = baseline_comp_keys - enhanced_comp_keys
        enhanced_only = enhanced_comp_keys - baseline_comp_keys

        return {
            "same": same,
            "baseline_only": "; ".join(sorted(baseline_only)) if baseline_only else "",
            "enhanced_only": "; ".join(sorted(enhanced_only)) if enhanced_only else "",
        }

    def _compare_attributes_level(
        self, baseline_structure: Dict, enhanced_structure: Dict
    ) -> Dict:
        """Compare at attributes level"""
        baseline_attrs = self._get_all_attributes(baseline_structure)
        enhanced_attrs = self._get_all_attributes(enhanced_structure)

        same = baseline_attrs == enhanced_attrs
        baseline_only = {}
        enhanced_only = {}

        if not same:
            # Compare each component's attributes
            all_comp_keys = set(baseline_attrs.keys()) | set(enhanced_attrs.keys())
            for comp_key in all_comp_keys:
                baseline_comp_attrs = baseline_attrs.get(comp_key, {})
                enhanced_comp_attrs = enhanced_attrs.get(comp_key, {})

                if baseline_comp_attrs != enhanced_comp_attrs:
                    baseline_attr_names = set(baseline_comp_attrs.keys())
                    enhanced_attr_names = set(enhanced_comp_attrs.keys())

                    if baseline_attr_names != enhanced_attr_names:
                        baseline_only[comp_key] = (
                            baseline_attr_names - enhanced_attr_names
                        )
                        enhanced_only[comp_key] = (
                            enhanced_attr_names - baseline_attr_names
                        )

        return {
            "same": same,
            "baseline_only": (
                "; ".join(
                    [f"{k}: {', '.join(sorted(v))}" for k, v in baseline_only.items()]
                )
                if baseline_only
                else ""
            ),
            "enhanced_only": (
                "; ".join(
                    [f"{k}: {', '.join(sorted(v))}" for k, v in enhanced_only.items()]
                )
                if enhanced_only
                else ""
            ),
        }

    def _compare_configurations_level(
        self, baseline_structure: Dict, enhanced_structure: Dict
    ) -> Dict:
        """Compare at configurations level (attribute values, constraints, etc.)"""
        baseline_configs = self._get_all_configurations(baseline_structure)
        enhanced_configs = self._get_all_configurations(enhanced_structure)

        same = baseline_configs == enhanced_configs
        baseline_output = []
        enhanced_output = []

        # Group components by service for easier matching
        baseline_by_service = {}
        enhanced_by_service = {}

        # Parse baseline components by service
        for comp_key, comp_config in baseline_configs.items():
            if "::" in comp_key:
                service_name, comp_name = comp_key.split("::", 1)
                if service_name not in baseline_by_service:
                    baseline_by_service[service_name] = {}
                baseline_by_service[service_name][comp_name] = comp_config

        # Parse enhanced components by service
        for comp_key, comp_config in enhanced_configs.items():
            if "::" in comp_key:
                service_name, comp_name = comp_key.split("::", 1)
                if service_name not in enhanced_by_service:
                    enhanced_by_service[service_name] = {}
                enhanced_by_service[service_name][comp_name] = comp_config

        # Get all services from both datasets
        all_services = set(baseline_by_service.keys()) | set(enhanced_by_service.keys())

        for service_name in all_services:
            baseline_service_comps = baseline_by_service.get(service_name, {})
            enhanced_service_comps = enhanced_by_service.get(service_name, {})

            # Find components that exist in both baseline and enhanced (IDENTICAL names)
            baseline_comp_names = set(baseline_service_comps.keys())
            enhanced_comp_names = set(enhanced_service_comps.keys())

            # Components only in baseline
            baseline_only_comps = baseline_comp_names - enhanced_comp_names
            for comp_name in baseline_only_comps:
                baseline_output.append(
                    f"{service_name}::{comp_name}: Component only in baseline"
                )

            # Components only in enhanced
            enhanced_only_comps = enhanced_comp_names - baseline_comp_names
            for comp_name in enhanced_only_comps:
                enhanced_output.append(
                    f"{service_name}::{comp_name}: Component only in enhanced"
                )

            # IDENTICAL components (same name in both datasets)
            identical_components = baseline_comp_names & enhanced_comp_names

            for comp_name in identical_components:
                baseline_comp = baseline_service_comps[comp_name]
                enhanced_comp = enhanced_service_comps[comp_name]

                baseline_comp_diffs = []
                enhanced_comp_diffs = []

                # Compare basic configurations (instances, sort)
                baseline_instances = baseline_comp.get("instances")
                enhanced_instances = enhanced_comp.get("instances")
                if baseline_instances != enhanced_instances:
                    baseline_comp_diffs.append(f"instances: {baseline_instances}")
                    enhanced_comp_diffs.append(f"instances: {enhanced_instances}")

                baseline_sort = baseline_comp.get("sort", [])
                enhanced_sort = enhanced_comp.get("sort", [])
                if baseline_sort != enhanced_sort:
                    baseline_sort_str = ",".join([str(item) for item in baseline_sort])
                    enhanced_sort_str = ",".join([str(item) for item in enhanced_sort])
                    baseline_comp_diffs.append(f"sort: {baseline_sort_str}")
                    enhanced_comp_diffs.append(f"sort: {enhanced_sort_str}")

                # Get attributes from both baseline and enhanced for this component
                baseline_attrs = baseline_comp.get("attributes", {})
                enhanced_attrs = enhanced_comp.get("attributes", {})

                baseline_attr_names = set(baseline_attrs.keys())
                enhanced_attr_names = set(enhanced_attrs.keys())

                # Find COMMON attributes (attributes that exist in BOTH baseline and enhanced)
                common_attr_names = baseline_attr_names & enhanced_attr_names

                # For each common attribute, compare its configuration
                for attr_name in sorted(common_attr_names):
                    baseline_attr = baseline_attrs[attr_name]
                    enhanced_attr = enhanced_attrs[attr_name]

                    # Always show configuration details for common attributes
                    baseline_attr_details = []
                    enhanced_attr_details = []

                    # Show values (always)
                    baseline_values = baseline_attr.get("values", "N/A")
                    enhanced_values = enhanced_attr.get("values", "N/A")
                    baseline_attr_details.append(f"values={baseline_values}")
                    enhanced_attr_details.append(f"values={enhanced_values}")

                    # Show constraints (always)
                    baseline_constraint = baseline_attr.get("constraint", "N/A")
                    enhanced_constraint = enhanced_attr.get("constraint", "N/A")
                    baseline_attr_details.append(f"constraint={baseline_constraint}")
                    enhanced_attr_details.append(f"constraint={enhanced_constraint}")

                    # Show units (always)
                    baseline_unit = baseline_attr.get("unit", "N/A")
                    enhanced_unit = enhanced_attr.get("unit", "N/A")
                    baseline_attr_details.append(f"unit={baseline_unit}")
                    enhanced_attr_details.append(f"unit={enhanced_unit}")

                    # Add to component details (always, not just when different)
                    baseline_comp_diffs.append(
                        f"{attr_name}: {', '.join(baseline_attr_details)}"
                    )
                    enhanced_comp_diffs.append(
                        f"{attr_name}: {', '.join(enhanced_attr_details)}"
                    )

                # Handle attributes that exist only in baseline or enhanced
                baseline_only_attrs = baseline_attr_names - enhanced_attr_names
                enhanced_only_attrs = enhanced_attr_names - baseline_attr_names

                if baseline_only_attrs:
                    attr_list = ", ".join(sorted(baseline_only_attrs))
                    baseline_comp_diffs.append(
                        f"Attributes only in baseline: {attr_list}"
                    )

                if enhanced_only_attrs:
                    attr_list = ", ".join(sorted(enhanced_only_attrs))
                    enhanced_comp_diffs.append(
                        f"Attributes only in enhanced: {attr_list}"
                    )

                # Add this component's configurations to the overall output (always, not just when different)
                if baseline_comp_diffs:
                    comp_diff_str = "; ".join(baseline_comp_diffs)
                    baseline_output.append(
                        f"{service_name}::{comp_name}: {comp_diff_str}"
                    )

                if enhanced_comp_diffs:
                    comp_diff_str = "; ".join(enhanced_comp_diffs)
                    enhanced_output.append(
                        f"{service_name}::{comp_name}: {comp_diff_str}"
                    )

        return {
            "same": same,
            "baseline_only": "; ".join(baseline_output) if baseline_output else "",
            "enhanced_only": "; ".join(enhanced_output) if enhanced_output else "",
        }

    def _group_components_by_service(self, configs: Dict) -> Dict:
        """Group components by service name for better matching"""
        by_service = {}
        for comp_key, comp_config in configs.items():
            if "::" in comp_key:
                service_name, comp_name = comp_key.split("::", 1)
                if service_name not in by_service:
                    by_service[service_name] = {}
                by_service[service_name][comp_name] = comp_config
        return by_service

    def _find_similar_components(
        self, baseline_comps: set, enhanced_comps: set
    ) -> List[Tuple[str, str]]:
        """Find similar component names between baseline and enhanced"""
        matches = []
        used_enhanced = set()

        for baseline_comp in baseline_comps:
            best_match = None
            best_score = 0

            # Extract the core component type (remove numbers, prefixes)
            baseline_core = self._extract_component_core(baseline_comp)

            for enhanced_comp in enhanced_comps:
                if enhanced_comp in used_enhanced:
                    continue

                enhanced_core = self._extract_component_core(enhanced_comp)

                # Calculate similarity score
                score = self._calculate_similarity(baseline_core, enhanced_core)

                if score > best_score and score > 0.6:  # Threshold for similarity
                    best_match = enhanced_comp
                    best_score = score

            if best_match:
                matches.append((baseline_comp, best_match))
                used_enhanced.add(best_match)

        return matches

    def _extract_component_core(self, comp_name: str) -> str:
        """Extract core component type from name (remove prefixes, numbers)"""
        # Remove common prefixes like 'ds-1_', 'ecs-1_', etc.
        import re

        core = re.sub(r"^[a-z]+-\d+_", "", comp_name)
        # Remove common suffixes and normalize
        core = re.sub(
            r"(DataTransfer|DataSync|TaskExecution|Task|Execution|Data|Transfer)",
            "DataSync",
            core,
        )
        core = re.sub(r"(CPU|Memory|OS|License)", "Compute", core)
        return core.lower()

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings"""
        if str1 == str2:
            return 1.0

        # Check for common substrings
        common_parts = 0
        for part in str1.split():
            if part in str2:
                common_parts += 1

        max_parts = max(len(str1.split()), len(str2.split()))
        if max_parts == 0:
            return 0.0

        return common_parts / max_parts

    def _compare_component_configs(
        self, baseline_comp: Dict, enhanced_comp: Dict
    ) -> Tuple[List[str], List[str]]:
        """Compare configurations between two matched components"""
        baseline_diffs = []
        enhanced_diffs = []

        # Compare instances
        baseline_instances = baseline_comp.get("instances")
        enhanced_instances = enhanced_comp.get("instances")
        if baseline_instances != enhanced_instances:
            baseline_diffs.append(f"instances: {baseline_instances}")
            enhanced_diffs.append(f"instances: {enhanced_instances}")

        # Compare sort configuration
        baseline_sort = baseline_comp.get("sort", [])
        enhanced_sort = enhanced_comp.get("sort", [])
        if baseline_sort != enhanced_sort:
            baseline_sort_str = ",".join([str(item) for item in baseline_sort])
            enhanced_sort_str = ",".join([str(item) for item in enhanced_sort])
            baseline_diffs.append(f"sort: {baseline_sort_str}")
            enhanced_diffs.append(f"sort: {enhanced_sort_str}")

        # Compare attribute configurations
        baseline_attrs = baseline_comp.get("attributes", {})
        enhanced_attrs = enhanced_comp.get("attributes", {})

        # Find common attributes
        baseline_attr_names = set(baseline_attrs.keys())
        enhanced_attr_names = set(enhanced_attrs.keys())
        common_attrs = baseline_attr_names & enhanced_attr_names

        # Compare common attributes
        for attr_name in sorted(common_attrs):
            baseline_attr = baseline_attrs[attr_name]
            enhanced_attr = enhanced_attrs[attr_name]

            if baseline_attr != enhanced_attr:
                baseline_attr_config = []
                enhanced_attr_config = []

                if baseline_attr.get("values") != enhanced_attr.get("values"):
                    baseline_attr_config.append(
                        f"values={baseline_attr.get('values', 'N/A')}"
                    )
                    enhanced_attr_config.append(
                        f"values={enhanced_attr.get('values', 'N/A')}"
                    )

                if baseline_attr.get("constraint") != enhanced_attr.get("constraint"):
                    baseline_attr_config.append(
                        f"constraint={baseline_attr.get('constraint', 'N/A')}"
                    )
                    enhanced_attr_config.append(
                        f"constraint={enhanced_attr.get('constraint', 'N/A')}"
                    )

                if baseline_attr.get("unit") != enhanced_attr.get("unit"):
                    baseline_attr_config.append(
                        f"unit={baseline_attr.get('unit', 'N/A')}"
                    )
                    enhanced_attr_config.append(
                        f"unit={enhanced_attr.get('unit', 'N/A')}"
                    )

                if baseline_attr_config and enhanced_attr_config:
                    baseline_diffs.append(
                        f"{attr_name}: {', '.join(baseline_attr_config)}"
                    )
                    enhanced_diffs.append(
                        f"{attr_name}: {', '.join(enhanced_attr_config)}"
                    )

        # Handle attributes that exist only in one dataset
        baseline_only_attrs = baseline_attr_names - enhanced_attr_names
        enhanced_only_attrs = enhanced_attr_names - baseline_attr_names

        if baseline_only_attrs:
            baseline_diffs.append(
                f"Attributes only in baseline: {', '.join(sorted(baseline_only_attrs))}"
            )

        if enhanced_only_attrs:
            enhanced_diffs.append(
                f"Attributes only in enhanced: {', '.join(sorted(enhanced_only_attrs))}"
            )

        return baseline_diffs, enhanced_diffs

    def _get_all_attributes(self, structure: Dict) -> Dict:
        """Extract all attributes for comparison"""
        attributes = {}

        for service_name, service_data in structure["services"].items():
            for comp_name, comp_data in service_data["components"].items():
                comp_key = f"{service_name}::{comp_name}"
                attributes[comp_key] = {}

                for attr in comp_data.get("attributes_search_space", []):
                    attr_name = attr.get("attribute_codename", "unknown")
                    attributes[comp_key][attr_name] = {
                        "codename": attr_name,
                        "exists": True,
                    }

        return attributes

    def _get_all_configurations(self, structure: Dict) -> Dict:
        """Extract all configurations for detailed comparison"""
        configurations = {}

        for service_name, service_data in structure["services"].items():
            for comp_name, comp_data in service_data["components"].items():
                comp_key = f"{service_name}::{comp_name}"
                configurations[comp_key] = {
                    "instances": comp_data.get("number_of_instances"),
                    "sort": comp_data.get("service_component_sort", []),
                    "attributes": {},
                }

                for attr in comp_data.get("attributes_search_space", []):
                    attr_name = attr.get("attribute_codename", "unknown")
                    configurations[comp_key]["attributes"][attr_name] = {
                        "values": attr.get("attribute_values"),
                        "constraint": attr.get("attribute_constraint_expr"),
                        "unit": attr.get("attribute_unit"),
                    }

        return configurations

    def _get_all_services_list(self, structure: Dict) -> str:
        """Get a comma-separated list of all services in the architecture"""
        return "; ".join(sorted(structure["services"].keys()))

    def _get_all_components_list(self, structure: Dict) -> str:
        """Get a comma-separated list of all components in the architecture"""
        all_components = []
        for service_name, service_data in structure["services"].items():
            for comp_name, comp_data in service_data["components"].items():
                all_components.append(f"{service_name}::{comp_name}")
        return "; ".join(sorted(all_components))

    def _get_all_attributes_list(self, structure: Dict) -> str:
        """Get a comma-separated list of all attributes in the architecture"""
        all_attributes = []
        for service_name, service_data in structure["services"].items():
            for comp_name, comp_data in service_data["components"].items():
                for attr in comp_data.get("attributes_search_space", []):
                    attr_name = attr.get("attribute_codename", "unknown")
                    all_attributes.append(f"{service_name}::{comp_name}::{attr_name}")
        return "; ".join(sorted(all_attributes))

    def _get_all_configurations_list(self, structure: Dict) -> str:
        """Get a comma-separated list of all configurations in the architecture"""
        all_configs = []
        for service_name, service_data in structure["services"].items():
            for comp_name, comp_data in service_data["components"].items():
                comp_key = f"{service_name}::{comp_name}"
                if comp_data.get("number_of_instances") is not None:
                    all_configs.append(
                        f"{comp_key}:instances={comp_data['number_of_instances']}"
                    )
                if comp_data.get("service_component_sort"):
                    sort_items = comp_data["service_component_sort"]
                    # Convert sort items to strings (they might be dicts)
                    sort_str = ",".join([str(item) for item in sort_items])
                    all_configs.append(f"{comp_key}:sort={sort_str}")
                for attr in comp_data.get("attributes_search_space", []):
                    attr_name = attr.get("attribute_codename", "unknown")
                    attr_values = attr.get("attribute_values", [])
                    all_configs.append(f"{comp_key}:{attr_name}={attr_values}")
        return "; ".join(sorted(all_configs))

    def _get_reasoning_description(
        self, baseline_structure: Dict, enhanced_structure: Dict
    ) -> str:
        """Generate reasoning description from reasoning files with specific insights about why choices were made"""
        descriptions = []

        # Get service names from both structures
        baseline_services = set(baseline_structure["services"].keys())
        enhanced_services = set(enhanced_structure["services"].keys())
        all_services = baseline_services | enhanced_services

        for service_name in all_services:
            baseline_reasoning = self.baseline_reasoning_lookup.get(service_name, {})
            enhanced_reasoning = self.enhanced_reasoning_lookup.get(service_name, {})

            # Extract specific decision rationales
            baseline_attr_rationale = baseline_reasoning.get(
                "attribute_selection_rationale", ""
            )
            enhanced_attr_rationale = enhanced_reasoning.get(
                "attribute_selection_rationale", ""
            )

            baseline_critical_attrs = baseline_reasoning.get(
                "critical_attributes_reasoning", ""
            )
            enhanced_critical_attrs = enhanced_reasoning.get(
                "critical_attributes_reasoning", ""
            )

            baseline_alternatives = baseline_reasoning.get(
                "alternatives_considered", []
            )
            enhanced_alternatives = enhanced_reasoning.get(
                "alternatives_considered", []
            )

            # If service exists in both, compare decision rationales
            if service_name in baseline_services and service_name in enhanced_services:
                insights = []

                # Compare attribute selection rationale
                if baseline_attr_rationale != enhanced_attr_rationale:
                    if enhanced_attr_rationale:
                        # Extract key insight from enhanced rationale
                        key_insight = self._extract_key_insight(
                            enhanced_attr_rationale, "Enhanced reasoning"
                        )
                        if key_insight:
                            insights.append(f"Attribute selection: {key_insight}")

                # Compare critical attributes reasoning
                if baseline_critical_attrs != enhanced_critical_attrs:
                    if enhanced_critical_attrs:
                        key_insight = self._extract_key_insight(
                            enhanced_critical_attrs, "Critical attributes"
                        )
                        if key_insight:
                            insights.append(f"Critical attributes: {key_insight}")

                # Compare alternatives considered
                if baseline_alternatives != enhanced_alternatives:
                    if enhanced_alternatives and len(enhanced_alternatives) > 0:
                        # Get the first alternative reasoning
                        alt_reasoning = (
                            enhanced_alternatives[0]
                            if isinstance(enhanced_alternatives[0], str)
                            else str(enhanced_alternatives[0])
                        )
                        key_insight = self._extract_key_insight(
                            alt_reasoning, "Alternative considered"
                        )
                        if key_insight:
                            insights.append(f"Design choice: {key_insight}")

                if insights:
                    descriptions.append(f"{service_name}: {'; '.join(insights)}")

            # If service exists only in one dataset, provide reasoning for why it was included
            elif (
                service_name in enhanced_services
                and service_name not in baseline_services
            ):
                enhanced_understanding = enhanced_reasoning.get(
                    "service_understanding", ""
                )
                if enhanced_understanding:
                    key_insight = self._extract_key_insight(
                        enhanced_understanding, "Service purpose"
                    )
                    if key_insight:
                        descriptions.append(
                            f"{service_name} (Enhanced only): {key_insight}"
                        )

                # Also include why this service was chosen
                if enhanced_attr_rationale:
                    choice_insight = self._extract_key_insight(
                        enhanced_attr_rationale, "Selection rationale"
                    )
                    if choice_insight:
                        descriptions.append(
                            f"{service_name} selection reasoning: {choice_insight}"
                        )

            elif (
                service_name in baseline_services
                and service_name not in enhanced_services
            ):
                baseline_understanding = baseline_reasoning.get(
                    "service_understanding", ""
                )
                if baseline_understanding:
                    key_insight = self._extract_key_insight(
                        baseline_understanding, "Service purpose"
                    )
                    if key_insight:
                        descriptions.append(
                            f"{service_name} (Baseline only): {key_insight}"
                        )

        # If no differences found, provide insights from common services about their configuration choices
        if not descriptions:
            common_services = baseline_services & enhanced_services
            for service_name in list(common_services)[
                :2
            ]:  # Get insights from first 2 services
                reasoning = self.enhanced_reasoning_lookup.get(
                    service_name, {}
                ) or self.baseline_reasoning_lookup.get(service_name, {})

                # Get insights about why specific configurations were chosen
                attr_rationale = reasoning.get("attribute_selection_rationale", "")
                critical_attrs = reasoning.get("critical_attributes_reasoning", "")

                if attr_rationale:
                    key_insight = self._extract_key_insight(
                        attr_rationale, "Configuration rationale"
                    )
                    if key_insight:
                        descriptions.append(f"{service_name}: {key_insight}")
                elif critical_attrs:
                    key_insight = self._extract_key_insight(
                        critical_attrs, "Critical reasoning"
                    )
                    if key_insight:
                        descriptions.append(f"{service_name}: {key_insight}")

        return (
            "; ".join(descriptions)
            if descriptions
            else "No specific reasoning insights available"
        )

    def _extract_key_insight(self, text: str, context: str) -> str:
        """Extract key insight from reasoning text"""
        if not text:
            return ""

        # Clean up the text
        text = text.strip()

        # Look for key phrases that indicate decision rationale
        key_phrases = [
            "because",
            "due to",
            "in order to",
            "to ensure",
            "chosen to",
            "selected to",
            "prioritized",
            "optimized for",
            "designed for",
            "configured for",
            "focused on",
            "enables",
            "allows",
            "provides",
            "ensures",
            "guarantees",
            "supports",
        ]

        sentences = text.split(". ")

        # Find sentences with key decision-making phrases
        key_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if any(phrase in sentence.lower() for phrase in key_phrases):
                # Clean up the sentence
                if sentence and not sentence.endswith("."):
                    sentence += "."
                key_sentences.append(sentence)

        # If we found key sentences, use the first one (usually most important)
        if key_sentences:
            return key_sentences[0][:150] + (
                "..." if len(key_sentences[0]) > 150 else ""
            )

        # Otherwise, take the first meaningful sentence
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 30:  # Avoid very short sentences
                return sentence[:150] + ("..." if len(sentence) > 150 else "")

        # Fallback to first part of text
        return text[:150] + ("..." if len(text) > 150 else "")

    def export_tabular_comparison(self, output_file: Path) -> pd.DataFrame:
        """Export tabular comparison to CSV"""
        comparison_rows = self.compare_all_architectures_tabular()

        # Convert to DataFrame
        df_data = []
        for row in comparison_rows:
            df_data.append(
                {
                    "Architecture": row.architecture_id,
                    "Services_Same": row.services_same,
                    "Components_Same": row.components_same,
                    "Attributes_Same": row.attributes_same,
                    "Configurations_Same": row.configurations_same,
                    "Services_Baseline_All": row.services_baseline_all,
                    "Services_Enhanced_All": row.services_enhanced_all,
                    "Components_Baseline_All": row.components_baseline_all,
                    "Components_Enhanced_All": row.components_enhanced_all,
                    "Attributes_Baseline_All": row.attributes_baseline_all,
                    "Attributes_Enhanced_All": row.attributes_enhanced_all,
                    "Configurations_Baseline_All": row.configurations_baseline_all,
                    "Configurations_Enhanced_All": row.configurations_enhanced_all,
                    "Services_Baseline_Only": row.services_baseline_only,
                    "Services_Enhanced_Only": row.services_enhanced_only,
                    "Components_Baseline_Only": row.components_baseline_only,
                    "Components_Enhanced_Only": row.components_enhanced_only,
                    "Attributes_Baseline_Only": row.attributes_baseline_only,
                    "Attributes_Enhanced_Only": row.attributes_enhanced_only,
                    "Configurations_Baseline_Only": row.configurations_baseline_only,
                    "Configurations_Enhanced_Only": row.configurations_enhanced_only,
                    "Reasoning_Description": row.reasoning_description,
                }
            )

        df = pd.DataFrame(df_data)

        # Save to CSV
        df.to_csv(output_file, index=False)
        print(f"✅ Tabular comparison exported to: {output_file}")

        # Print summary stats
        total_archs = len(df)
        services_same_count = df["Services_Same"].sum()
        components_same_count = df["Components_Same"].sum()
        attributes_same_count = df["Attributes_Same"].sum()
        configurations_same_count = df["Configurations_Same"].sum()

        print(f"\n📊 Summary Statistics:")
        print(f"   Total Architectures: {total_archs}")
        print(
            f"   Services Same: {services_same_count}/{total_archs} ({services_same_count/total_archs*100:.1f}%)"
        )
        print(
            f"   Components Same: {components_same_count}/{total_archs} ({components_same_count/total_archs*100:.1f}%)"
        )
        print(
            f"   Attributes Same: {attributes_same_count}/{total_archs} ({attributes_same_count/total_archs*100:.1f}%)"
        )
        print(
            f"   Configurations Same: {configurations_same_count}/{total_archs} ({configurations_same_count/total_archs*100:.1f}%)"
        )

        return df


def main():
    """Main execution function"""
    print("📊 Individual Architecture Tables Comparison")
    print("=" * 50)

    # File paths (use absolute paths from current script location)
    script_dir = Path(__file__).parent
    comparison_output_dir = script_dir.parent / "comparison_output"

    baseline_file = (
        comparison_output_dir / "baseline_db_architectures_set_search_space_output.json"
    )
    enhanced_file = (
        comparison_output_dir / "enhanced_db_architectures_set_search_space_output.json"
    )
    baseline_reasoning_file = (
        comparison_output_dir
        / "baseline_db_architectures_set_search_space_reasoning_output.json"
    )
    enhanced_reasoning_file = (
        comparison_output_dir
        / "enhanced_db_architectures_set_search_space_reasoning_output.json"
    )

    # Initialize comparator
    comparator = TabularArchitectureComparator(
        baseline_file, enhanced_file, baseline_reasoning_file, enhanced_reasoning_file
    )

    # Create individual architecture tables
    architecture_tables = comparator.create_individual_architecture_tables(
        comparison_output_dir
    )
    # to create one table for all architectures you can use:
    # comparison_rows = comparator.compare_all_architectures_tabular()
    # output_file = comparison_output_dir / "tabular_architecture_comparison_v8.csv"
    # df = comparator.export_tabular_comparison(output_file)

    print(f"\n🎉 Individual architecture tables complete!")
    print(f"   Output directory: {comparison_output_dir}")
    print(f"   Tables created: {len(architecture_tables)}")

    # Print summary for each architecture
    for arch_id, df in architecture_tables.items():
        total_attributes = len(df)
        same_count = len(df[df["Status"] == "Same"])
        modified_count = len(df[df["Status"] == "Modified"])
        baseline_only_count = len(df[df["Status"] == "Baseline_Only"])
        enhanced_only_count = len(df[df["Status"] == "Enhanced_Only"])

        print(f"   📊 {arch_id}: {total_attributes} attributes")
        print(f"      Same: {same_count}, Modified: {modified_count}")
        print(
            f"      Baseline_Only: {baseline_only_count}, Enhanced_Only: {enhanced_only_count}"
        )


if __name__ == "__main__":
    main()
