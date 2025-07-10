# 🔧 AWS IBU Scraper & LLM Configurator Project

**Independent Billable Units (IBU) extraction from AWS Calculator with enhanced LLM configuration testing**

## 📋 Project Overview

This consolidated project contains all essential files for scraping AWS pricing calculator data to extract Independent Billable Units (IBUs) and testing enhanced LLM configuration for cloud architecture generation.

## 📁 Project Structure

```
ibu_llm_configurator_project/
├── scrapers/                           # IBU Scraping Tools
│   ├── toggle_aware_ibu_scraper.py    # Most updated scraper
│   └── dynamic_aws_scraper.py         # Reliable alternative scraper
├── analysis_tools/                     # Analysis & LLM Testing
│   ├── compare_services_components.py  # Service coverage analysis
│   └── working_step_test.py           # LLM configurator test
├── comparison_tools/                   # Architecture Comparison
│   ├── compare_architectures_tabular.py
│   └── streamlit_tabular_comparison.py
├── prompts/                           # LLM Prompt Files
│   ├── baseline_prompts.yaml          # Standard LLM configurator prompts
│   └── enhanced_prompts.yaml          # IBU + calculator enhanced prompts
├── data/                              # Input Data
│   ├── db_architectures_set.json
│   ├── db_abstract_system_architectures.json
│   ├── aws_services_dynamic.json
│   ├── toggle_aware_analysis.json
│   └── ibu_mapping_dataframe.csv
├── comparison_output/                 # Results & Outputs
│   ├── tabular_architecture_comparison.csv
│   ├── enhanced_*_output.json
│   ├── baseline_*_output.json
│   └── *_reasoning_output.json
├── requirements.txt                   # Dependencies
└── README.md                         # This file
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd ibu_llm_configurator_project
pip install -r requirements.txt
```

### 2. Run IBU Scraper

```bash
# Option A: Most updated scraper (recommended)
cd scrapers
python toggle_aware_ibu_scraper.py

# Option B: Reliable alternative scraper
python dynamic_aws_scraper.py
```

### 3. Test LLM Configuration

```bash
cd ../analysis_tools
# Check service coverage gaps
python compare_services_components.py
```

### 4. Test Enhanced LLM Configuration

```bash
# Test enhanced LLM configuration with IBU context
python working_step_test.py
```

### 5. Compare Architectures

```bash
cd ../comparison_tools
python compare_architectures_tabular.py

# View interactive dashboard
streamlit run streamlit_tabular_comparison.py
```

---

## 🔧 Core Components

### 📊 IBU Scrapers (`scrapers/`)

#### **`toggle_aware_ibu_scraper.py`** ⭐

- **Most updated** scraper with advanced toggle detection
- Captures dynamic pricing options that affect IBU calculations
- Handles complex AWS calculator forms with JavaScript

#### **`dynamic_aws_scraper.py`**

- **Reliable alternative** scraper
- Stable fallback option if the updated scraper has issues
- Proven track record for consistent data extraction

### 🧪 Analysis Tools (`analysis_tools/`)

#### **`compare_services_components.py`** 🔍

- **Service Coverage Analysis**: Compares scraped services vs architecture requirements
- Uses `data/db_architectures_set.json` to identify coverage gaps
- Shows exact matches, partial matches, and missing services

#### **`working_step_test.py`** ⭐

- **Real LLM Zero-Shot Configurator**: Runs the actual `LLMSSCZeroShot` configurator from the Taura solution optimizer
- **Enhanced vs Baseline Comparison**: Tests enhanced prompts with IBU + scraped calculator data vs standard prompts
- **Production Integration**: Uses real taura pipeline (`ConfigureSearchSpaceStep`) with actual LLM API calls
- **Dual Database Usage**: Requires both `db_architectures_set.json` and `db_abstract_system_architectures.json`
- **IBU-Enhanced Decision Making**: Leverages IBU billing boundaries and scraped calculator interface data for superior attribute selection

### ⚖️ Comparison Tools (`comparison_tools/`)

#### **`compare_architectures_tabular.py`**

- Generates flat comparison tables with binary indicators (1/0)
- Shows differences in services, components, attributes, configurations
- Creates detailed difference analysis with reasoning explanations

#### **`streamlit_tabular_comparison.py`**

- Interactive Streamlit dashboard for exploring comparison results
- Filtering and search capabilities
- Visual analysis of architecture differences

---

## 📄 Data Files (`data/`)

### Input Data

- **`db_architectures_set.json`** - Architecture definitions for LLM configurator
- **`db_abstract_system_architectures.json`** - Abstract architecture database needed by LLM configurator
- **`aws_services_dynamic.json`** - Scraped IBU data from scrapers
- **`toggle_aware_analysis.json`** - IBU analysis results from toggle-aware scraper
- **`ibu_mapping_dataframe.csv`** - Structured IBU mapping data for enhanced LLM prompts

### Prompt Files (`prompts/`)

- **`baseline_prompts.yaml`** - Standard LLM configurator prompts (8KB, 106 lines)
- **`enhanced_prompts.yaml`** - IBU + calculator enhanced prompts (20KB, 294 lines)

### Output Data (`comparison_output/`)

- **`tabular_architecture_comparison.csv`** - Binary comparison results
- **`enhanced_db_architectures_set_search_space_output.json`** - Enhanced architecture outputs
- **`baseline_db_architectures_set_search_space_output.json`** - Baseline architecture outputs
- **`enhanced_db_architectures_set_search_space_reasoning_output.json`** - Enhanced reasoning
- **`baseline_db_architectures_set_search_space_reasoning_output.json`** - Baseline reasoning

---

## 🔄 Complete Workflow

### Full Pipeline

```bash
# 1. Run IBU scraper
cd scrapers
python toggle_aware_ibu_scraper.py

# 2. Test service coverage and LLM configuration
cd ../analysis_tools
python compare_services_components.py
python working_step_test.py

# 3. Generate comparisons
cd ../comparison_tools
python compare_architectures_tabular.py

# 4. View results
streamlit run streamlit_tabular_comparison.py
```

### Data Flow

```
Scrapers → aws_services_dynamic.json → Analysis Tools → Enhanced LLM → Comparison Tools → Results
```

---

## 🎯 What This Project Accomplishes

### Problem Solved

- **IBU Data Gaps**: AWS Calculator has detailed pricing components not available elsewhere
- **LLM Context Enhancement**: Using real AWS pricing data improves architecture generation
- **Service Coverage**: Identifies which services need to be scraped for complete coverage

### Key Features

- **Toggle-Aware Scraping**: Captures dynamic pricing options and form interfaces
- **Real LLM Configurator**: Uses actual Taura production configurator (not mock)
- **Enhanced vs Baseline Prompts**: IBU billing boundary analysis + scraped calculator data vs standard AWS knowledge
- **IBU-First Prioritization**: PRIMARY/SECONDARY/TERTIARY attribute selection based on billing boundaries
- **Calculator Interface Mapping**: Maps scraped form elements to database schema columns
- **Gap Analysis**: Shows exactly which services are missing for complete coverage
- **Binary Comparison**: Clear 1/0 indicators for architecture differences
- **Interactive Analysis**: Streamlit dashboards for exploring results

---

## 🤖 LLM Prompt Enhancement Details

### **Enhanced vs Baseline Prompts**

The `working_step_test.py` compares two different LLM configurator approaches:

#### **🔵 Baseline Prompts** (`prompts/baseline_prompts.yaml`)

- **Standard AWS Knowledge**: Uses general AWS service understanding
- **Basic Prioritization**: Region → Payment → Core characteristics
- **Schema-Driven**: Relies on database schema discovery only
- **General Guidelines**: Standard attribute mapping rules
- **File Size**: 8KB (106 lines)

#### **🟢 Enhanced Prompts** (`prompts/enhanced_prompts.yaml`)

- **IBU Billing Boundary Analysis**: Uses actual Independent Billable Units data
- **Calculator Interface Mapping**: Leverages scraped AWS calculator form elements
- **IBU-First Prioritization**: PRIMARY (IBU attributes) → SECONDARY (multi-IBU) → TERTIARY (standard)
- **Cross-Service Relationships**: Analyzes service integration patterns
- **Form Element Intelligence**: Maps calculator dropdowns/inputs to schema columns
- **File Size**: 20KB (294 lines) - **2.5x larger with detailed IBU instructions**

### **Key Enhancement Differences**

| **Enhancement**                  | **Impact**                                                       |
| -------------------------------- | ---------------------------------------------------------------- |
| **IBU Attribute Mapping**        | Uses actual billing unit boundaries instead of guessing          |
| **Calculator Form Analysis**     | Maps real AWS interface elements to database columns             |
| **Billing-Aware Prioritization** | Focuses on cost-critical attributes first                        |
| **Cross-Service Intelligence**   | Understands how services integrate (EC2+RDS, Lambda+API Gateway) |
| **Enhanced Reasoning**           | Must explain IBU usage and calculator mapping decisions          |

### **Data Flow for Enhanced Prompts**

```
IBU Mapping CSV → Attribute Prioritization (PRIMARY/SECONDARY/TERTIARY)
     ↓
Scraped Calculator Data → Form Element to Schema Mapping
     ↓
Enhanced LLM Configurator → Superior Attribute Selection
     ↓
ServiceSearchSpace → More Cost-Optimized Results
```

---

## 🛠️ Prerequisites

- **Python 3.11+**
- **Chrome Browser** (for scraping)
- **LLM API Keys** (OpenAI, Anthropic, or OpenRouter for testing)

---
