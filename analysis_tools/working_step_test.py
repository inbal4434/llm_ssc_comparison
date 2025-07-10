#!/usr/bin/env python3
"""
Working test script to run the real configure_search_space_step with actual LLM calls.

This script compares outputs with and without additional AWS services data.
"""

import sys
import os
import json
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Set, List
from uuid import uuid4
from unittest.mock import Mock, AsyncMock

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_env_file():
    """Load environment variables from .env file"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
        print("✅ Loaded environment variables from .env file")
    else:
        print("⚠️ No .env file found in sandbox directory")


# Load environment first
load_env_file()

# Fix database URL to use async driver before any imports
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = (
        "postgresql+asyncpg://postgres:cloudculate123@localhost:5432/taura_dev"
    )
elif not os.environ["DATABASE_URL"].startswith("postgresql+asyncpg://"):
    # Replace postgresql:// with postgresql+asyncpg://
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"].replace(
        "postgresql://", "postgresql+asyncpg://"
    )

# Disable schema discovery for IBU-only testing
os.environ["DISABLE_SCHEMA_DISCOVERY"] = "true"

# Also set the cloud data database URL (for schema discovery) - only if database is available
if "CLOUD_DATA_DATABASE_URL_SYNC" not in os.environ:
    os.environ["CLOUD_DATA_DATABASE_URL_SYNC"] = os.environ["DATABASE_URL"]

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import the step we want to test
from solution_optimizer.pipeline.steps.configure_search_space_step import (
    ConfigureSearchSpaceStep,
)


def load_mock_data():
    """Load mock data from JSON files"""
    sandbox_dir = Path(__file__).parent

    # Load architectures set
    with open(sandbox_dir / "db_architectures_set.json", "r") as f:
        architectures_set_data = json.load(f)

    # Load abstract system architecture
    with open(sandbox_dir / "db_abstract_system_architectures.json", "r") as f:
        abstract_system_data = json.load(f)

    return architectures_set_data, abstract_system_data


def load_aws_services_data():
    """Load AWS services data for additional context (DISABLED - focusing on IBU data only)"""
    logger.info("AWS services data loading disabled - focusing on IBU data only")
    return None


def load_scraped_calculator_data():
    """Load scraped AWS calculator data for enhanced service configuration"""
    sandbox_dir = Path(__file__).parent

    # Look for the toggle_aware_analysis.json file
    scraped_data_paths = [
        sandbox_dir / "toggle_aware_analysis.json",
        Path("toggle_aware_analysis.json"),
        sandbox_dir / "../toggle_aware_analysis.json",
        Path("../toggle_aware_analysis.json"),
        sandbox_dir / "../independent_billable_units/toggle_aware_analysis.json",
        Path("../independent_billable_units/toggle_aware_analysis.json"),
    ]

    scraped_file_path = None
    for path in scraped_data_paths:
        if path.exists():
            scraped_file_path = path
            break

    if not scraped_file_path:
        logger.info(
            "Scraped calculator data file (toggle_aware_analysis.json) not found, continuing without scraped data"
        )
        return {
            "available": False,
            "reason": "Scraped calculator data file not found",
            "services_data": {},
            "total_services": 0,
        }

    try:
        with open(scraped_file_path, "r") as f:
            scraped_data = json.load(f)

        # Count services with actual scraped data
        valid_services = {
            service: data
            for service, data in scraped_data.items()
            if isinstance(data, dict) and "discovered_ibus" in data
        }

        total_services = len(valid_services)

        logger.info(
            f"Loaded scraped calculator data: {total_services} services analyzed"
        )

        return {
            "available": True,
            "services_data": valid_services,
            "total_services": total_services,
            "source_file": str(scraped_file_path),
        }

    except Exception as e:
        logger.warning(f"Error loading scraped calculator data: {e}")
        return {
            "available": False,
            "reason": f"Error loading scraped data: {e}",
            "services_data": {},
            "total_services": 0,
        }


def load_ibu_data():
    """Load IBU (Independent Billable Units) data for enhanced service configuration - CSV ONLY"""
    sandbox_dir = Path(__file__).parent

    # Focus ONLY on CSV format - the attached ibu_mapping_dataframe.csv file
    csv_paths = [
        sandbox_dir / "ibu_mapping_dataframe.csv",
        Path("ibu_mapping_dataframe.csv"),
        sandbox_dir / "../independent_billable_units/ibu_mapping_dataframe.csv",
        Path("../independent_billable_units/ibu_mapping_dataframe.csv"),
    ]

    ibu_file_path = None
    for path in csv_paths:
        if path.exists():
            ibu_file_path = path
            break

    if not ibu_file_path:
        logger.info(
            "IBU mapping file not found (neither JSON nor CSV format), continuing without IBU data"
        )
        return {
            "available": False,
            "reason": "IBU mapping file not found",
            "service_ibu_mappings": {},
            "total_services": 0,
            "total_ibus": 0,
        }

    try:
        # Load IBU data using pandas if available, otherwise manual parsing
        try:
            import pandas as pd

            ibu_df = pd.read_csv(ibu_file_path)

            # Convert to service -> IBU -> attributes mapping
            service_ibu_mappings = {}
            for _, row in ibu_df.iterrows():
                service = row["service"]
                ibu = row["ibu"]
                attribute = row["attribute"]

                if service not in service_ibu_mappings:
                    service_ibu_mappings[service] = {}
                if ibu not in service_ibu_mappings[service]:
                    service_ibu_mappings[service][ibu] = []
                service_ibu_mappings[service][ibu].append(attribute)

            total_services = len(service_ibu_mappings)
            total_ibus = sum(len(ibus) for ibus in service_ibu_mappings.values())

            logger.info(
                f"Loaded IBU data: {total_services} services, {total_ibus} IBUs"
            )

            return {
                "available": True,
                "service_ibu_mappings": service_ibu_mappings,
                "total_services": total_services,
                "total_ibus": total_ibus,
            }

        except ImportError:
            logger.warning("Pandas not available for IBU data loading")
            # Fallback: try to manually parse CSV
            service_ibu_mappings = {}
            total_lines = 0

            with open(ibu_file_path, "r") as f:
                lines = f.readlines()
                if len(lines) > 1:  # Skip header
                    for line in lines[1:]:
                        parts = line.strip().split(",")
                        if len(parts) >= 3:
                            service, ibu, attribute = parts[0], parts[1], parts[2]
                            if service not in service_ibu_mappings:
                                service_ibu_mappings[service] = {}
                            if ibu not in service_ibu_mappings[service]:
                                service_ibu_mappings[service][ibu] = []
                            service_ibu_mappings[service][ibu].append(attribute)
                            total_lines += 1

            total_services = len(service_ibu_mappings)
            total_ibus = sum(len(ibus) for ibus in service_ibu_mappings.values())

            logger.info(
                f"Manually parsed IBU data: {total_services} services, {total_ibus} IBUs from {total_lines} entries"
            )

            return {
                "available": True,
                "service_ibu_mappings": service_ibu_mappings,
                "total_services": total_services,
                "total_ibus": total_ibus,
            }

    except Exception as e:
        logger.warning(f"Error loading IBU data: {e}")
        return {
            "available": False,
            "reason": f"Error loading IBU data: {e}",
            "service_ibu_mappings": {},
            "total_services": 0,
            "total_ibus": 0,
        }


def format_ibu_context(service_codename: str, ibu_data: Dict[str, Any]) -> str:
    """Format IBU data for inclusion in LLM context"""
    if not ibu_data.get("available", False):
        return f"IBU Data: Not available ({ibu_data.get('reason', 'Unknown reason')})"

    service_ibu_mappings = ibu_data.get("service_ibu_mappings", {})
    data_format = ibu_data.get("format", "csv")

    # Check for exact service match first
    service_ibus = service_ibu_mappings.get(service_codename)

    # If no exact match, try partial matches (e.g., "Amazon EC2" for "AmazonEC2")
    if not service_ibus:
        for service_name, ibus in service_ibu_mappings.items():
            if (
                service_codename.lower() in service_name.lower()
                or service_name.lower() in service_codename.lower()
            ):
                service_ibus = ibus
                logger.info(
                    f"Using IBU data from '{service_name}' for service '{service_codename}'"
                )
                break

    if not service_ibus:
        # Show available services for context
        available_services = list(service_ibu_mappings.keys())[
            :5
        ]  # First 5 for brevity
        return f"""IBU Data Available: Yes ({ibu_data['total_services']} services, {ibu_data['total_ibus']} IBUs total)
Service-Specific IBUs: None found for '{service_codename}'
Available Services (sample): {', '.join(available_services)}{'...' if len(service_ibu_mappings) > 5 else ''}

⚠️  CRITICAL: NOT ALL SERVICES HAVE IBUs IN THE DATASET!
This service '{service_codename}' was NOT found in the IBU mapping, which means:
1. This service may have a single billing component (all attributes billed together)
2. The service was not included in the IBU analysis dataset
3. The service name format differs between systems
4. The service may be too new or rarely used to be analyzed

IBU Analysis: Proceed with standard attribute grouping. Do not force IBU-specific considerations.
Focus on logical attribute groupings based on functionality rather than billing boundaries."""

    # Handle different data formats
    if data_format == "json":
        # JSON format: service -> [ibu_names]
        if isinstance(service_ibus, list):
            ibu_names = service_ibus
            return f"""IBU Data Available: Yes ({ibu_data['total_services']} services, {ibu_data['total_ibus']} IBUs total)

✅ SPECIAL: This service HAS IBU data! (Many services do not)
Service-Specific IBUs for '{service_codename}':
  IBU Names: {', '.join(ibu_names)}

IBU Analysis: This service has {len(ibu_names)} Independent Billable Units: {', '.join(ibu_names)}
Each IBU represents a separate billing component. When configuring search spaces:
- Group attributes that belong to the same IBU for coherent cost analysis  
- Consider which IBUs are most cost-critical for typical workloads
- Understand how different IBUs scale and interact with each other

⚠️  IMPORTANT: This service is SPECIAL - most services do NOT have detailed IBU mappings in the dataset!
Use this IBU information as valuable billing boundary guidance."""
    else:
        # CSV format: service -> {ibu_name: [attributes]}
        ibu_details = []
        for ibu_name, attributes in service_ibus.items():
            ibu_details.append(
                f"""
  IBU: {ibu_name}
    Attributes ({len(attributes)}): {', '.join(attributes[:8])}{'...' if len(attributes) > 8 else ''}"""
            )

        return f"""IBU Data Available: Yes ({ibu_data['total_services']} services, {ibu_data['total_ibus']} IBUs total)

✅ SPECIAL: This service HAS IBU data! (Many services do not)
Service-Specific IBUs for '{service_codename}':
{chr(10).join(ibu_details)}

IBU Analysis: This service has {len(service_ibus)} Independent Billable Units. Each IBU represents a separate billing component. When configuring search spaces, consider that attributes within the same IBU are typically billed together and should be configured as coherent units.

⚠️  IMPORTANT: This service is SPECIAL - most services do NOT have detailed IBU mappings in the dataset!
Use this IBU information as valuable billing boundary guidance."""

    return f"""IBU Data Available: Yes but format unclear
Service-Specific IBUs for '{service_codename}': {str(service_ibus)[:200]}{'...' if len(str(service_ibus)) > 200 else ''}

⚠️  Note: Not all services have IBUs in the data file."""


def format_scraped_calculator_context(
    service_codename: str, scraped_data: Dict[str, Any]
) -> str:
    """Format scraped calculator data for inclusion in LLM context"""
    if not scraped_data.get("available", False):
        return f"Scraped Calculator Data: Not available ({scraped_data.get('reason', 'Unknown reason')})"

    services_data = scraped_data.get("services_data", {})

    # Check for exact service match first
    service_calculator_data = services_data.get(service_codename)

    # If no exact match, try partial matches (e.g., "Amazon S3" for "AmazonS3")
    if not service_calculator_data:
        for service_name, calc_data in services_data.items():
            if (
                service_codename.lower() in service_name.lower()
                or service_name.lower() in service_codename.lower()
            ):
                service_calculator_data = calc_data
                logger.info(
                    f"Using scraped calculator data from '{service_name}' for service '{service_codename}'"
                )
                break

    if not service_calculator_data:
        # Show available services for context
        available_services = list(services_data.keys())[:5]  # First 5 for brevity
        return f"""Scraped Calculator Data Available: Yes ({scraped_data['total_services']} services analyzed)
Service-Specific Calculator Data: None found for '{service_codename}'
Available Services (sample): {', '.join(available_services)}{'...' if len(services_data) > 5 else ''}

⚠️  This service '{service_codename}' was NOT found in the scraped calculator dataset.
Proceed with standard attribute configuration without calculator insights."""

    # Extract key information from scraped calculator data
    discovered_ibus = service_calculator_data.get("discovered_ibus", {})
    ibu_mapping = service_calculator_data.get("ibu_mapping", [])

    # Format discovered IBUs
    ibu_sections = []
    for ibu_name, ibu_data in discovered_ibus.items():
        elements = ibu_data.get("elements", [])
        if elements:
            element_types = {}
            for element in elements:
                elem_type = element.get("type", "unknown")
                if elem_type not in element_types:
                    element_types[elem_type] = []
                element_types[elem_type].append(element.get("label", "unlabeled"))

            type_summary = []
            for elem_type, labels in element_types.items():
                type_summary.append(
                    f"{elem_type}: {', '.join(labels[:3])}{'...' if len(labels) > 3 else ''}"
                )

            ibu_sections.append(
                f"""
  IBU Section: {ibu_name}
    Elements ({len(elements)}): {' | '.join(type_summary)}"""
            )

    # Format final IBU mapping (service -> ibu -> attribute)
    ibu_mapping_summary = []
    mapped_services = {}
    for mapping in ibu_mapping:
        service = mapping.get("service", "Unknown")
        ibu = mapping.get("ibu", "Unknown")
        attribute = mapping.get("attribute", "Unknown")

        if service not in mapped_services:
            mapped_services[service] = {}
        if ibu not in mapped_services[service]:
            mapped_services[service][ibu] = []
        mapped_services[service][ibu].append(attribute)

    for service, ibus in mapped_services.items():
        for ibu, attributes in ibus.items():
            ibu_mapping_summary.append(
                f"""
  Final Mapping: {service} → {ibu}
    Attributes ({len(attributes)}): {', '.join(attributes[:5])}{'...' if len(attributes) > 5 else ''}"""
            )

    return f"""Scraped Calculator Data Available: Yes ({scraped_data['total_services']} services analyzed)

✅ SPECIAL: Calculator data found for '{service_codename}'!
Source: {scraped_data.get('source_file', 'Unknown')}

Calculator Page Structure:
{chr(10).join(ibu_sections) if ibu_sections else "  No IBU sections discovered"}

Final IBU Mappings:
{chr(10).join(ibu_mapping_summary) if ibu_mapping_summary else "  No final mappings available"}

Calculator Analysis: This service has actual AWS calculator page structure data available!
- Use the discovered form elements to understand user input patterns
- Map calculator field labels to database schema columns for precise targeting  
- Consider calculator section organization when grouping attributes
- Leverage element types (dropdown, input, checkbox) to understand attribute constraints

⚠️  IMPORTANT: This scraped data represents the ACTUAL AWS calculator interface structure!
Use this information to make superior attribute selection decisions based on real user interaction patterns."""


async def create_real_schema_objects(arch_data, asa_data):
    """Create real schema objects from loaded data"""
    try:
        # Import the correct schemas
        from solution_optimizer.shared.schemas import (
            ArchitecturesSet,
            Architecture,
            Component,
            Connection,
            ArchitectureMetadata,
            AbstractSystemArchitecture,
            System,
            AbsComponent,
            AbsConnection,
        )

        # Convert architectures set data
        architectures_set = ArchitecturesSet.model_validate(arch_data)

        # Convert abstract system architecture data
        abstract_system_architecture = AbstractSystemArchitecture.model_validate(
            asa_data
        )

        logger.info(f"Successfully created schema objects:")
        logger.info(
            f"  - ArchitecturesSet with {len(architectures_set.architectures)} architectures"
        )
        logger.info(
            f"  - AbstractSystemArchitecture with {len(abstract_system_architecture.components)} components"
        )

        return architectures_set, abstract_system_architecture

    except Exception as e:
        logger.error(f"Failed to create real schema objects: {e}")
        raise


def save_results_to_json(result: Dict[str, Any], output_dir: Path, run_type: str):
    """Save the step results to JSON files for inspection"""
    try:
        output_dir.mkdir(exist_ok=True)

        for artifact_name, artifact_data in result.items():
            # Convert Pydantic models to dictionaries for JSON serialization
            if hasattr(artifact_data, "model_dump"):
                data_dict = artifact_data.model_dump()
            elif hasattr(artifact_data, "dict"):
                data_dict = artifact_data.dict()
            else:
                # Fallback for other types
                data_dict = artifact_data

            # Create filename with run type prefix
            filename = f"{run_type}_{artifact_name.lower()}_output.json"
            filepath = output_dir / filename

            # Save to JSON with pretty formatting
            with open(filepath, "w") as f:
                json.dump(data_dict, f, indent=2, default=str)

            logger.info(f"✅ Saved {artifact_name} to {filepath}")

            # Log summary of what was saved
            if isinstance(data_dict, dict):
                if "architectures" in data_dict:
                    logger.info(
                        f"   - Contains {len(data_dict['architectures'])} architecture search spaces"
                    )
                if "total_services_configured" in data_dict:
                    logger.info(
                        f"   - Configured {data_dict['total_services_configured']} services"
                    )
                if "reasoning_entries" in data_dict:
                    logger.info(
                        f"   - {len(data_dict['reasoning_entries'])} reasoning entries"
                    )

        logger.info(f"📁 All {run_type} results saved to: {output_dir}")

    except Exception as e:
        logger.error(f"Failed to save {run_type} results to JSON: {e}")


async def create_real_run_context():
    """Create real RunContext for testing"""
    from uuid import uuid4

    run_id = str(uuid4())

    # Simple context that provides what the step needs for testing
    # The configurator doesn't actually need database session for LLM calls
    class RealTestContext:
        def __init__(self, run_id: str, logger):
            self.run_id = run_id
            self.session = (
                None  # Steps will use real configurator, which doesn't need DB
            )
            self.logger = logger

    context = RealTestContext(run_id=run_id, logger=logger)
    return context


class EnhancedConfigureSearchSpaceStep:
    """Enhanced version of ConfigureSearchSpaceStep that uses IBU billing boundary data and scraped calculator data"""

    def __init__(
        self, ibu_data: Dict[str, Any], scraped_data: Optional[Dict[str, Any]] = None
    ):
        """Initialize with IBU billing boundary data and scraped calculator data"""
        from solution_optimizer.pipeline.steps.configure_search_space_step import (
            ConfigureSearchSpaceStep,
        )

        self.base_step = ConfigureSearchSpaceStep()
        self.ibu_data = ibu_data or {}
        self.scraped_data = scraped_data or {}

    async def execute(self, context, **loaded_input_artefacts):
        """Execute the step with enhanced additional_data_sources and enhanced prompts"""
        from solution_optimizer.shared.schemas import (
            ArtefactTable,
            ArchitecturesSet,
            AbstractSystemArchitecture,
            ArchitecturesSetSearchSpace,
            SearchSpaceReasoningCollection,
            QuestionnaireExtractedData,
        )
        from solution_optimizer.services.attributes_configuration.search_configurators.llm_zero_shot_configurator import (
            LLMSSCZeroShot,
        )

        context.logger.info(
            f"Starting enhanced step: {self.base_step.step_name} for run {context.run_id}"
        )

        architectures_set: Optional[ArchitecturesSet] = loaded_input_artefacts.get(
            ArtefactTable.DB_ARCHITECTURES_SET.value
        )
        abstract_system_architecture: Optional[AbstractSystemArchitecture] = (
            loaded_input_artefacts.get(
                ArtefactTable.DB_ABSTRACT_SYSTEM_ARCHITECTURE.value
            )
        )

        questionnaire_extracted_data: Optional[QuestionnaireExtractedData] = (
            loaded_input_artefacts.get(
                ArtefactTable.DB_QUESTIONNAIRE_EXTRACTED_DATA.value
            )
        )

        if not architectures_set:
            error_msg = f"Missing required input: ArchitecturesSet for step {self.base_step.step_name}."
            context.logger.error(error_msg)
            raise ValueError(error_msg)
        if not abstract_system_architecture:
            error_msg = f"Missing required input: AbstractSystemArchitecture for step {self.base_step.step_name}."
            context.logger.error(error_msg)
            raise ValueError(error_msg)

        if not architectures_set.architectures:
            context.logger.info(
                "ArchitecturesSet is empty. Skipping attribute search space configuration."
            )
            return {
                ArtefactTable.DB_ARCHITECTURES_SET_SEARCH_SPACE.name: ArchitecturesSetSearchSpace(
                    architectures=[]
                ),
                ArtefactTable.DB_ARCHITECTURES_SET_SEARCH_SPACE_REASONING.name: SearchSpaceReasoningCollection(
                    total_services_configured=0,
                    summary="No architectures to configure - empty ArchitecturesSet",
                ),
            }

        # Initialize additional_data_sources with IBU data and scraped calculator data
        additional_data_sources: Dict[str, Any] = {}

        # Add IBU data if available
        if self.ibu_data and self.ibu_data.get("available", False):
            additional_data_sources["ibu_data"] = self.ibu_data
            context.logger.info(
                f"🔧 Added IBU billing boundary data for {self.ibu_data['total_services']} services with {self.ibu_data['total_ibus']} IBUs to additional_data_sources"
            )
        else:
            context.logger.info("ℹ️ No IBU data available or IBU data not loaded")

        # Add scraped calculator data if available
        if self.scraped_data and self.scraped_data.get("available", False):
            additional_data_sources["scraped_data"] = self.scraped_data
            context.logger.info(
                f"🔧 Added scraped calculator data for {self.scraped_data['total_services']} services to additional_data_sources"
            )
        else:
            context.logger.info(
                "ℹ️ No scraped calculator data available or scraped data not loaded"
            )

        # Create enhanced LLM configurator that uses the new prompt file
        class EnhancedLLMConfigurator(LLMSSCZeroShot):
            """Enhanced LLM configurator that uses IBU billing boundary analysis prompts"""

            def __init__(self, service_codename: str):
                super().__init__(service_codename)

                # Load enhanced prompts directly
                enhanced_prompt_file = (
                    Path(__file__).parent.parent
                    / "solution_optimizer"
                    / "shared"
                    / "prompts"
                    / "solution_optimizer"
                    / "pipeline"
                    / "llm_search_space_configurator_enhanced_prompts.yaml"
                )

                self.enhanced_prompts = None
                if enhanced_prompt_file.exists():
                    import yaml

                    try:
                        with open(enhanced_prompt_file, "r") as f:
                            self.enhanced_prompts = yaml.safe_load(f)
                        context.logger.info(
                            f"✅ Enhanced prompts loaded from {enhanced_prompt_file}"
                        )
                    except Exception as e:
                        context.logger.warning(
                            f"❌ Failed to load enhanced prompts: {e}"
                        )
                        self.enhanced_prompts = None
                else:
                    context.logger.warning(
                        f"❌ Enhanced prompt file not found: {enhanced_prompt_file}"
                    )

                context.logger.info(
                    f"🔧 Enhanced configurator created for {service_codename} with {'IBU billing boundary analysis + scraped calculator prompts' if self.enhanced_prompts else 'fallback to standard prompts'}"
                )

            async def _generate_with_llm(self, context_data: Dict[str, Any]):
                """Override to add IBU context and use enhanced prompts (AWS services data removed)"""
                service_codename = context_data.get("service_codename", "")

                # Set AWS services as not available (focusing on IBU data only)
                context_data["aws_services_available"] = "No"
                context_data["scraped_materials_context"] = (
                    "AWS scraped materials disabled - focusing on IBU billing boundary data only"
                )

                # Add IBU data to context if available
                if additional_data_sources and "ibu_data" in additional_data_sources:
                    ibu_data = additional_data_sources["ibu_data"]

                    # Format IBU context for this specific service
                    ibu_context = format_ibu_context(service_codename, ibu_data)
                    context_data["ibu_context"] = ibu_context

                    context.logger.info(
                        f"🔧 Added IBU context for service '{service_codename}'"
                    )
                else:
                    context_data["ibu_context"] = "IBU Data: Not available"
                    context.logger.info("ℹ️ No IBU data available for LLM context")

                # Add scraped calculator data to context if available
                if (
                    additional_data_sources
                    and "scraped_data" in additional_data_sources
                ):
                    scraped_data = additional_data_sources["scraped_data"]

                    # Format scraped calculator context for this specific service
                    scraped_context = format_scraped_calculator_context(
                        service_codename, scraped_data
                    )
                    context_data["scraped_calculator_data"] = scraped_context

                    context.logger.info(
                        f"🔧 Added scraped calculator context for service '{service_codename}'"
                    )
                else:
                    context_data["scraped_calculator_data"] = (
                        "Scraped Calculator Data: Not available"
                    )
                    context.logger.info(
                        "ℹ️ No scraped calculator data available for LLM context"
                    )

                # Create enhanced additional context with both IBU and scraped data
                context_parts = []

                context_parts.append(
                    f"## IBU (INDEPENDENT BILLABLE UNITS) DATA:\n{context_data['ibu_context']}"
                )

                context_parts.append(
                    f"## SCRAPED AWS CALCULATOR DATA:\n{context_data['scraped_calculator_data']}"
                )

                context_parts.append(
                    f"""
## IMPORTANT CONTEXT NOTES:
- IBU data shows billing boundaries but NOT ALL SERVICES have IBUs in the dataset
- Scraped calculator data shows actual AWS interface structure for enhanced attribute mapping
- Focus on billing boundary insights when IBU data is available for a service
- Use scraped calculator form elements to map to database schema columns precisely
- Consider cost optimization implications from IBU billing perspective
- When no IBU data exists, use standard attribute grouping approaches
- When scraped data is available, prioritize calculator-informed attribute selection"""
                )

                context_data["additional_context"] = "\n\n".join(context_parts)

                # If we have enhanced prompts, use them
                if (
                    self.enhanced_prompts
                    and "zero_shot_generation" in self.enhanced_prompts
                ):
                    context.logger.info(
                        f"🔧 Using enhanced prompts with IBU + scraped calculator data for {context_data.get('service_codename', 'unknown')}"
                    )

                    # Get enhanced prompts
                    enhanced_config = self.enhanced_prompts["zero_shot_generation"]
                    system_prompt = enhanced_config.get("system_prompt", "")
                    user_prompt_template = enhanced_config.get(
                        "user_prompt_template", ""
                    )

                    # Format the user prompt with context data
                    try:
                        formatted_user_prompt = user_prompt_template.format(
                            **context_data
                        )
                    except KeyError as e:
                        context.logger.warning(
                            f"Missing template variable {e} in enhanced prompts, using partial formatting"
                        )
                        # Use safe substitute to avoid KeyError
                        from string import Template

                        template = Template(user_prompt_template)
                        formatted_user_prompt = template.safe_substitute(context_data)

                    # Call LLM with enhanced prompts
                    from solution_optimizer.shared.utils.llm_client import LLMClient
                    from solution_optimizer.shared.schemas import (
                        ServiceSearchSpaceWithReasoning,
                    )

                    llm_client = LLMClient()
                    result = await llm_client.generate_structured_output(
                        system_prompt=system_prompt,
                        user_prompt=formatted_user_prompt,
                        output_schema=ServiceSearchSpaceWithReasoning,
                    )

                    context.logger.info(
                        f"✅ Enhanced LLM configurator completed for {context_data.get('service_codename', 'unknown')} with IBU billing boundary context and enhanced prompts"
                    )

                    return result
                else:
                    # Fall back to parent implementation
                    context.logger.info(
                        f"⚠️ Using standard prompts for {context_data.get('service_codename', 'unknown')} (enhanced prompts not available)"
                    )
                    result = await super()._generate_with_llm(context_data)

                    context.logger.info(
                        f"✅ Standard LLM configurator completed for {context_data.get('service_codename', 'unknown')} with IBU billing boundary context"
                    )

                    return result

        # Handle GPU data as in the original step
        if questionnaire_extracted_data and questionnaire_extracted_data.processes:
            found_any_gpu_model = False
            for proc_name, proc_data in questionnaire_extracted_data.processes.items():
                if proc_data.extracted_ai_models:
                    context.logger.info(
                        f"Process '{proc_name}' contains {len(proc_data.extracted_ai_models)} structured AI models."
                    )
                    found_any_gpu_model = True
            if not found_any_gpu_model:
                context.logger.info(
                    "No structured AI/ML model data found in any process within QuestionnaireExtractedData."
                )

        # Create enhanced service registry that uses our enhanced configurators
        from solution_optimizer.services.attributes_configuration.comp_service_mapper import (
            ArchComponentServiceMapper,
            ServiceAttributesRegistry,
        )

        class EnhancedServiceRegistry(ServiceAttributesRegistry):
            """Enhanced registry that returns IBU billing boundary aware configurators"""

            def _get_default_configurator(self, service_codename: str):
                """Return enhanced LLM configurator with IBU billing boundary analysis"""
                context.logger.info(
                    f"🔧 Using enhanced LLM configurator with IBU billing boundary analysis for {service_codename}"
                )
                return EnhancedLLMConfigurator(service_codename)

        # Create mapper with enhanced registry
        enhanced_registry = EnhancedServiceRegistry()
        mapper = ArchComponentServiceMapper()

        # Replace the registry with our enhanced one
        mapper.registry = enhanced_registry

        context.logger.info(
            f"Inputs loaded. Using enhanced configurator with IBU billing boundary analysis for run {context.run_id} "
            f"with {len(architectures_set.architectures)} architectures and IBU data"
        )

        try:
            search_space_result, reasoning_collection = (
                await mapper.process_architectures(
                    architectures_set=architectures_set,
                    asa=abstract_system_architecture,
                    additional_data_sources=(
                        additional_data_sources if additional_data_sources else None
                    ),
                )
            )
        except Exception as e:
            error_msg = (
                f"Enhanced ArchComponentServiceMapper.process_architectures failed: {e}"
            )
            context.logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg)

        if not search_space_result or not isinstance(
            search_space_result, ArchitecturesSetSearchSpace
        ):
            error_msg = "Enhanced ArchComponentServiceMapper.process_architectures returned an invalid result or None."
            context.logger.error(error_msg)
            return {
                ArtefactTable.DB_ARCHITECTURES_SET_SEARCH_SPACE.name: ArchitecturesSetSearchSpace(
                    architectures=[]
                ),
                ArtefactTable.DB_ARCHITECTURES_SET_SEARCH_SPACE_REASONING.name: SearchSpaceReasoningCollection(
                    total_services_configured=0,
                    summary="Enhanced configuration failed - invalid result from mapper",
                ),
            }

        context.logger.info(
            f"✅ Enhanced configurator successfully configured attribute search space for {len(search_space_result.architectures)} architectures with IBU billing boundary analysis."
        )

        context.logger.info(
            f"📊 Collected {reasoning_collection.total_services_configured} enhanced reasoning objects with IBU billing boundary analysis."
        )

        return {
            ArtefactTable.DB_ARCHITECTURES_SET_SEARCH_SPACE.name: search_space_result,
            ArtefactTable.DB_ARCHITECTURES_SET_SEARCH_SPACE_REASONING.name: reasoning_collection,
        }


async def run_step_with_config(
    architectures_set,
    abstract_system_architecture,
    additional_data_sources: Optional[Dict[str, Any]],
    run_type: str,
):
    """Run the step with specific configuration"""
    from solution_optimizer.shared.schemas import ArtefactTable

    # Create the appropriate step instance
    if additional_data_sources and (
        "ibu_data" in additional_data_sources
        or "scraped_data" in additional_data_sources
    ):
        ibu_data = additional_data_sources.get("ibu_data", {})
        scraped_data = additional_data_sources.get("scraped_data", {})
        step = EnhancedConfigureSearchSpaceStep(
            ibu_data=ibu_data, scraped_data=scraped_data
        )

        enhancement_info = []
        if ibu_data and ibu_data.get("available", False):
            enhancement_info.append(
                f"IBU data ({ibu_data['total_services']} services, {ibu_data['total_ibus']} IBUs)"
            )
        if scraped_data and scraped_data.get("available", False):
            enhancement_info.append(
                f"scraped calculator data ({scraped_data['total_services']} services)"
            )

        enhancements = (
            " with " + " + ".join(enhancement_info) if enhancement_info else ""
        )
        logger.info(f"🚀 Using Enhanced step{enhancements} for {run_type}")
    else:
        from solution_optimizer.pipeline.steps.configure_search_space_step import (
            ConfigureSearchSpaceStep,
        )

        step = ConfigureSearchSpaceStep()
        logger.info(f"🚀 Using Standard step for {run_type}")

    # Create real test context
    context = await create_real_run_context()

    # Prepare input artifacts as the step expects them
    loaded_input_artefacts = {
        ArtefactTable.DB_ARCHITECTURES_SET.value: architectures_set,
        ArtefactTable.DB_ABSTRACT_SYSTEM_ARCHITECTURE.value: abstract_system_architecture,
        # No questionnaire data for this test
    }

    logger.info(f"🚀 Starting {run_type} step execution...")
    execution_start = time.time()

    # Execute the step - THIS WILL MAKE REAL LLM CALLS
    result = await step.execute(context, **loaded_input_artefacts)

    execution_time = time.time() - execution_start
    logger.info(f"✅ {run_type} execution completed in {execution_time:.2f} seconds")

    return result, execution_time


async def check_database_availability():
    """Check if database is available, if not use mock mode"""
    try:
        import asyncpg

        connection = await asyncpg.connect(os.environ["DATABASE_URL"])
        await connection.close()
        logger.info("✅ Database connection successful")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Database not available: {e}")
        logger.info("🔧 Continuing in mock mode (IBU data only)")
        # Set environment to use mock data
        os.environ["USE_MOCK_DATABASE"] = "true"
        return False


async def run_comparison_test():
    """Run comparison test with independent enhanced and baseline outputs"""

    # Check database availability
    db_available = await check_database_availability()
    if not db_available:
        logger.info("📊 Running in IBU-only mode without database schema discovery")

    # Load input files
    logger.info("Loading input files...")

    with open("db_architectures_set.json", "r") as f:
        architectures_set_data = json.load(f)

    with open("db_abstract_system_architectures.json", "r") as f:
        abstract_system_architecture_data = json.load(f)

    # Convert JSON data to proper Pydantic schema objects
    logger.info("Converting JSON data to schema objects...")
    architectures_set, abstract_system_architecture = await create_real_schema_objects(
        architectures_set_data, abstract_system_architecture_data
    )

    # Load IBU data and scraped calculator data (AWS services data disabled)
    ibu_data = load_ibu_data()
    scraped_data = load_scraped_calculator_data()

    logger.info(f"Loaded {len(architectures_set.architectures)} architectures")
    logger.info(
        "✅ AWS services data loading disabled - focusing on IBU + scraped calculator data"
    )

    if ibu_data.get("available", False):
        data_format = ibu_data.get("format", "csv")
        logger.info(
            f"✅ Loaded IBU data ({data_format} format): {ibu_data['total_services']} services, {ibu_data['total_ibus']} IBUs"
        )
        logger.info(
            "⚠️  CRITICAL: NOT ALL SERVICES have IBUs in the dataset! Only some services have billing boundary data."
        )
    else:
        logger.info(
            f"❌ IBU data not available: {ibu_data.get('reason', 'Unknown reason')}"
        )

    if scraped_data.get("available", False):
        logger.info(
            f"✅ Loaded scraped calculator data: {scraped_data['total_services']} services analyzed"
        )
        logger.info(f"Source: {scraped_data.get('source_file', 'Unknown')}")
    else:
        logger.info(
            f"❌ Scraped calculator data not available: {scraped_data.get('reason', 'Unknown reason')}"
        )

    # Log sample of IBU data being sent to LLM
    if ibu_data.get("available", False):
        logger.info("🔧 Sample IBU data that will be sent to LLM:")
        sample_ibu_services = list(ibu_data["service_ibu_mappings"].keys())[:3]
        for service in sample_ibu_services:
            ibus = ibu_data["service_ibu_mappings"][service]
            if isinstance(ibus, list):
                logger.info(f"  - {service}: {', '.join(ibus)}")
            else:
                logger.info(f"  - {service}: {len(ibus)} IBUs")

    # Create real test context
    context = await create_real_run_context()

    # Import the real ArtefactTable
    from solution_optimizer.shared.schemas import ArtefactTable

    # Create output directory
    output_dir = Path("comparison_output")
    output_dir.mkdir(exist_ok=True)

    # Test baseline version (no additional AWS data)
    logger.info("🚀 Running BASELINE configuration (standard prompts, no AWS data)...")
    baseline_step = ConfigureSearchSpaceStep()

    baseline_loaded_artifacts = {
        ArtefactTable.DB_ARCHITECTURES_SET.value: architectures_set,
        ArtefactTable.DB_ABSTRACT_SYSTEM_ARCHITECTURE.value: abstract_system_architecture,
    }

    baseline_result = await baseline_step.execute(context, **baseline_loaded_artifacts)
    baseline_search_space = baseline_result[
        ArtefactTable.DB_ARCHITECTURES_SET_SEARCH_SPACE.name
    ]

    # Test enhanced version (with IBU data, scraped calculator data, and enhanced prompts)
    logger.info(
        "🚀 Running ENHANCED configuration (enhanced prompts + IBU billing boundaries + scraped calculator data)..."
    )
    enhanced_step = EnhancedConfigureSearchSpaceStep(ibu_data, scraped_data)

    enhanced_result = await enhanced_step.execute(context, **baseline_loaded_artifacts)
    enhanced_search_space = enhanced_result[
        ArtefactTable.DB_ARCHITECTURES_SET_SEARCH_SPACE.name
    ]

    # Extract and log reasoning differences
    baseline_reasoning = baseline_result[
        ArtefactTable.DB_ARCHITECTURES_SET_SEARCH_SPACE_REASONING.name
    ]
    enhanced_reasoning = enhanced_result[
        ArtefactTable.DB_ARCHITECTURES_SET_SEARCH_SPACE_REASONING.name
    ]

    logger.info("📊 Reasoning Comparison:")
    if hasattr(baseline_reasoning, "reasoning_entries") and hasattr(
        enhanced_reasoning, "reasoning_entries"
    ):
        logger.info(
            f"  Baseline reasoning entries: {len(baseline_reasoning.reasoning_entries)}"
        )
        logger.info(
            f"  Enhanced reasoning entries: {len(enhanced_reasoning.reasoning_entries)}"
        )

        # Log sample reasoning to see the difference
        if enhanced_reasoning.reasoning_entries:
            sample_enhanced = enhanced_reasoning.reasoning_entries[0]
            if hasattr(sample_enhanced, "service_understanding"):
                logger.info(
                    f"  Enhanced service understanding sample: {sample_enhanced.service_understanding[:200]}..."
                )

    # Save both outputs independently (NO MERGING)
    logger.info("💾 Saving independent comparison outputs...")

    # Save baseline output
    with open(
        output_dir / "baseline_db_architectures_set_search_space_output.json", "w"
    ) as f:
        if hasattr(baseline_search_space, "dict"):
            json.dump(baseline_search_space.dict(), f, indent=2, default=str)
        else:
            json.dump(baseline_search_space, f, indent=2, default=str)

    # Save enhanced output (independent, no merging with baseline)
    with open(
        output_dir / "enhanced_db_architectures_set_search_space_output.json", "w"
    ) as f:
        if hasattr(enhanced_search_space, "dict"):
            json.dump(enhanced_search_space.dict(), f, indent=2, default=str)
        else:
            json.dump(enhanced_search_space, f, indent=2, default=str)

    # Save reasoning collections with enhanced analysis
    with open(
        output_dir / "baseline_db_architectures_set_search_space_reasoning_output.json",
        "w",
    ) as f:
        if hasattr(baseline_reasoning, "dict"):
            json.dump(baseline_reasoning.dict(), f, indent=2, default=str)
        else:
            json.dump(baseline_reasoning, f, indent=2, default=str)

    with open(
        output_dir / "enhanced_db_architectures_set_search_space_reasoning_output.json",
        "w",
    ) as f:
        if hasattr(enhanced_reasoning, "dict"):
            json.dump(enhanced_reasoning.dict(), f, indent=2, default=str)
        else:
            json.dump(enhanced_reasoning, f, indent=2, default=str)

    logger.info("✅ Independent comparison test completed successfully!")

    # Print summary with independent analysis
    baseline_count = count_attributes(baseline_search_space)
    enhanced_count = count_attributes(enhanced_search_space)

    logger.info("📈 INDEPENDENT RESULTS SUMMARY:")
    logger.info(f"  🔹 Baseline attributes (standard): {baseline_count}")
    logger.info(
        f"  🔹 Enhanced attributes (with IBU + scraped calculator data): {enhanced_count}"
    )
    logger.info(f"  🔹 Difference: {enhanced_count - baseline_count:+d} attributes")
    if ibu_data.get("available", False):
        logger.info(
            f"  🔹 IBU billing boundary data: {ibu_data['total_services']} services, {ibu_data['total_ibus']} IBUs (⚠️ NOT all services have IBUs!)"
        )
    else:
        logger.info(
            f"  🔹 IBU data: Not available ({ibu_data.get('reason', 'Unknown')})"
        )
    if scraped_data.get("available", False):
        logger.info(
            f"  🔹 Scraped calculator data: {scraped_data['total_services']} services analyzed"
        )
    else:
        logger.info(
            f"  🔹 Scraped calculator data: Not available ({scraped_data.get('reason', 'Unknown')})"
        )
    logger.info(f"  🔹 Enhanced prompts used: {'✅ Yes' if enhanced_step else '❌ No'}")
    logger.info(
        "  🔹 AWS scraped materials: Disabled (focusing on IBU + scraped calculator data only)"
    )

    # Analyze reasoning quality differences
    if (
        hasattr(enhanced_reasoning, "reasoning_entries")
        and enhanced_reasoning.reasoning_entries
    ):
        logger.info("🧠 ENHANCED REASONING QUALITY:")
        reasoning_with_relationships = 0
        for entry in enhanced_reasoning.reasoning_entries:
            if (
                hasattr(entry, "service_understanding")
                and "relationship" in entry.service_understanding.lower()
            ):
                reasoning_with_relationships += 1
        logger.info(
            f"  🔹 Reasoning entries with service relationships: {reasoning_with_relationships}"
        )
        logger.info(
            f"  🔹 Enhanced reasoning depth: {reasoning_with_relationships / len(enhanced_reasoning.reasoning_entries) * 100:.1f}%"
        )

    logger.info("💡 Both configurations ran independently - no merging applied!")
    logger.info(f"📁 Compare outputs in: {output_dir}")


def count_attributes(search_space_data) -> int:
    """Count total attributes in search space"""
    count = 0

    # Handle both Pydantic models and dicts
    if hasattr(search_space_data, "dict"):
        data = search_space_data.dict()
    else:
        data = search_space_data

    for arch in data.get("architectures", []):
        for component in arch.get("components_search_space", []):
            for service_component in component.get("service_search_space", {}).get(
                "service_components_search_spaces", []
            ):
                count += len(service_component.get("attributes_search_space", []))

    return count


# =============================================================================
# MERGE FUNCTIONS REMOVED FOR INDEPENDENT EXECUTION
# =============================================================================
#
# The following merge functions were removed to ensure the enhanced configuration
# runs completely independently from the baseline, as requested:
#
# - merge_enhanced_with_baseline()
# - merge_component_configs()
# - merge_attributes_search_space()
# - is_enhanced_attribute_better()
#
# This ensures a true comparison between:
# 1. Baseline: Standard prompts, no AWS services data
# 2. Enhanced: Enhanced prompts + AWS services relationship analysis
#
# Both configurations now run independently with no merging applied.
# =============================================================================


if __name__ == "__main__":
    asyncio.run(run_comparison_test())
