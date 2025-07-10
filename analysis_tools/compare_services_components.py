#!/usr/bin/env python3
import json
import os
from typing import Set, List, Dict, Tuple


def extract_service_names(aws_services_file: str) -> Set[str]:
    """Extract unique service names from AWS services JSON file."""
    with open(aws_services_file, "r") as file:
        data = json.load(file)

    service_names = set()
    for service_key, service_data in data.items():
        if isinstance(service_data, dict) and "service_name" in service_data:
            service_name = service_data["service_name"]
            service_names.add(service_name)

    return service_names


def extract_component_types(architectures_file: str) -> Set[str]:
    """Extract unique component types from architectures JSON file."""
    with open(architectures_file, "r") as file:
        data = json.load(file)

    component_types = set()
    for architecture in data.get("architectures", []):
        for component in architecture.get("components", []):
            component_type = component.get("component_type")
            if component_type:
                component_types.add(component_type)

    return component_types


def normalize_string(text: str) -> str:
    """Normalize string by removing spaces and converting to lowercase."""
    return text.lower().replace(" ", "").replace("-", "").replace("_", "")


def find_matches(
    service_names: Set[str], component_types: Set[str]
) -> Dict[str, List[str]]:
    """Find matches between service names and component types (case-insensitive, space-insensitive)."""
    matches = {
        "exact_matches": [],
        "service_contains_component": [],
        "component_contains_service": [],
        "partial_matches": [],
    }

    # Create normalized mappings for case-insensitive and space-insensitive comparison
    service_normalized_to_original = {normalize_string(s): s for s in service_names}
    component_normalized_to_original = {normalize_string(c): c for c in component_types}

    # Find exact matches (normalized)
    service_names_normalized = set(service_normalized_to_original.keys())
    component_types_normalized = set(component_normalized_to_original.keys())
    exact_matches_normalized = service_names_normalized.intersection(
        component_types_normalized
    )

    for match_normalized in exact_matches_normalized:
        original_service = service_normalized_to_original[match_normalized]
        original_component = component_normalized_to_original[match_normalized]
        matches["exact_matches"].append(f"{original_service} = {original_component}")

    # Find partial matches (normalized)
    for service in service_names:
        for component in component_types:
            service_normalized = normalize_string(service)
            component_normalized = normalize_string(component)

            if service_normalized == component_normalized:
                continue  # Already found as exact match

            # Check if service name contains component type
            if component_normalized in service_normalized:
                matches["service_contains_component"].append(f"{service} ⊃ {component}")

            # Check if component type contains service name
            elif service_normalized in component_normalized:
                matches["component_contains_service"].append(f"{component} ⊃ {service}")

            # Check for other partial matches (common words, etc.)
            service_words = set(service.lower().split())
            component_words = set(component.lower().split())
            common_words = service_words.intersection(component_words)
            if common_words and len(common_words) > 0:
                # Filter out only very common words (keep "aws", "amazon" for AWS services)
                significant_words = common_words - {
                    "the",
                    "and",
                    "of",
                    "for",
                    "in",
                    "on",
                    "at",
                    "to",
                    "a",
                    "an",
                    "is",
                    "with",
                    "by",
                    "or",
                }
                if significant_words:
                    matches["partial_matches"].append(
                        f"{service} ≈ {component} (common: {', '.join(significant_words)})"
                    )

    return matches


def main():
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Use absolute paths based on script location
    aws_services_file = os.path.join(script_dir, "aws_services_dynamic.json")
    architectures_file = os.path.join(script_dir, "db_architectures_set.json")

    try:
        print("🔍 Comparing AWS Service Names with Architecture Component Types")
        print("=" * 70)

        # Extract data
        print("📊 Extracting data...")
        service_names = extract_service_names(aws_services_file)
        component_types = extract_component_types(architectures_file)

        print(f"  - Found {len(service_names)} unique service names")
        print(f"  - Found {len(component_types)} unique component types")

        # Find matches
        print("\n🔍 Finding matches...")
        matches = find_matches(service_names, component_types)

        # Display results
        print("\n📋 RESULTS:")
        print("=" * 50)

        if matches["exact_matches"]:
            print(f"\n✅ EXACT MATCHES ({len(matches['exact_matches'])}):")
            print("-" * 30)
            for match in sorted(matches["exact_matches"]):
                print(f"  • {match}")

        if matches["service_contains_component"]:
            print(
                f"\n🔍 SERVICE NAMES CONTAINING COMPONENT TYPES ({len(matches['service_contains_component'])}):"
            )
            print("-" * 30)
            for match in sorted(matches["service_contains_component"]):
                print(f"  • {match}")

        if matches["component_contains_service"]:
            print(
                f"\n🔍 COMPONENT TYPES CONTAINING SERVICE NAMES ({len(matches['component_contains_service'])}):"
            )
            print("-" * 30)
            for match in sorted(matches["component_contains_service"]):
                print(f"  • {match}")

        if matches["partial_matches"]:
            print(f"\n🔍 PARTIAL MATCHES ({len(matches['partial_matches'])}):")
            print("-" * 30)
            for match in sorted(set(matches["partial_matches"])):  # Remove duplicates
                print(f"  • {match}")

        # Find unmatched items
        matched_services = set()
        matched_components = set()

        # Collect all matched service names and component types
        for match_list in matches.values():
            for match in match_list:
                if " = " in match:  # Exact match
                    service_part, component_part = match.split(" = ")
                    matched_services.add(service_part)
                    matched_components.add(component_part)
                elif " ⊃ " in match:  # Containment match
                    parts = match.split(" ⊃ ")
                    matched_services.add(
                        parts[0] if parts[0] in service_names else parts[1]
                    )
                    matched_components.add(
                        parts[1] if parts[1] in component_types else parts[0]
                    )
                elif " ≈ " in match:  # Partial match
                    parts = match.split(" ≈ ")[
                        0:2
                    ]  # Take first two parts before (common:...)
                    if len(parts) >= 2:
                        matched_services.add(
                            parts[0] if parts[0] in service_names else parts[1]
                        )
                        matched_components.add(
                            parts[1] if parts[1] in component_types else parts[0]
                        )

        unmatched_services = service_names - matched_services
        unmatched_components = component_types - matched_components

        # Show unmatched items
        if unmatched_services:
            print(f"\n❌ UNMATCHED SERVICE NAMES ({len(unmatched_services)}):")
            print("-" * 40)
            for service in sorted(unmatched_services):
                print(f"  • {service}")

        if unmatched_components:
            print(f"\n❌ UNMATCHED COMPONENT TYPES ({len(unmatched_components)}):")
            print("-" * 40)
            for component in sorted(unmatched_components):
                print(f"  • {component}")

        # Summary
        total_matches = (
            len(matches["exact_matches"])
            + len(matches["service_contains_component"])
            + len(matches["component_contains_service"])
            + len(set(matches["partial_matches"]))
        )

        print(f"\n📊 SUMMARY:")
        print("-" * 20)
        print(f"  - Total service names: {len(service_names)}")
        print(f"  - Total component types: {len(component_types)}")
        print(f"  - Exact matches: {len(matches['exact_matches'])}")
        print(f"  - Partial matches: {total_matches - len(matches['exact_matches'])}")
        print(f"  - Total relationships found: {total_matches}")
        print(f"  - Unmatched services: {len(unmatched_services)}")
        print(f"  - Unmatched components: {len(unmatched_components)}")

        if not any(matches.values()):
            print("\n❌ No matches found between service names and component types")

        # Show unique service names and component types for reference
        print(f"\n📝 ALL SERVICE NAMES ({len(service_names)}):")
        print("-" * 30)
        for service in sorted(service_names):
            print(f"  • {service}")

        print(f"\n🏗️  ALL COMPONENT TYPES ({len(component_types)}):")
        print("-" * 30)
        for component in sorted(component_types):
            print(f"  • {component}")

    except FileNotFoundError as e:
        print(f"Error: Could not find file - {e}")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
