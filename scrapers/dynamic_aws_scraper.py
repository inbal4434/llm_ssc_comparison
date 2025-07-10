#!/usr/bin/env python3
"""
Dynamic AWS Pricing Calculator Scraper
=====================================
General-purpose scraper that automatically detects and handles dynamic interactions
on any AWS pricing calculator page. Systematically tests interactive elements to
discover hidden content, changing options, and dynamic configurations.
"""

import json
import asyncio
import time
import os
import re
from playwright.async_api import async_playwright
from typing import Dict, List, Any, Optional

OUTPUT_JSON = "scraper_output_arch_set_services.json"
UNSCRAPED_SERVICES_JSON = "unscraped_aws_services.json"
DISCOVERED_SERVICES_JSON = "discovered_aws_services.json"


class GeneralDynamicAWSExtractor:
    """General-purpose extractor for dynamic AWS service configurations."""

    def __init__(self, page):
        self.page = page
        self.interaction_log = []
        self.content_snapshots = {}

    async def extract_service_config(self, service_name: str) -> Dict[str, Any]:
        """Extract complete dynamic service configuration data."""

        service_data = {
            "service_name": service_name,
            "service_description": "",
            "interactive_elements": {},
            "configuration_states": {},
            "global_settings": {},
            "extraction_metadata": {
                "interactive_elements_found": 0,
                "successful_interactions": 0,
                "configuration_states_captured": 0,
                "content_changes_detected": 0,
            },
        }

        try:
            print(f"🔍 Extracting dynamic config for: {service_name}")

            # Get service description
            service_data["service_description"] = (
                await self._extract_service_description()
            )

            # Capture initial global settings
            service_data["global_settings"] = await self._extract_global_settings()

            # Take initial content snapshot
            initial_content = await self._capture_content_snapshot("initial")
            self.content_snapshots["initial"] = initial_content

            # Detect all interactive elements
            interactive_elements = await self._detect_all_interactive_elements()
            service_data["extraction_metadata"]["interactive_elements_found"] = len(
                interactive_elements
            )

            print(f"📋 Found {len(interactive_elements)} interactive elements")

            # Debug: Show "Show calculations" elements specifically
            show_calc_elements = [
                e
                for e in interactive_elements
                if "show calculations" in e.get("name", "").lower()
            ]
            if show_calc_elements:
                print(
                    f"   🎯 Found {len(show_calc_elements)} 'Show calculations' elements:"
                )
                for elem in show_calc_elements:
                    print(f"      - {elem.get('name', 'Unknown')}")
            else:
                print(f"   ⚠️ No 'Show calculations' elements detected")

            # Process each interactive element systematically
            for i, element_info in enumerate(interactive_elements):
                print(
                    f"  🔄 Testing element {i+1}/{len(interactive_elements)}: {element_info['name']}"
                )

                interaction_result = await self._test_element_interaction(element_info)

                if interaction_result["successful"]:
                    service_data["interactive_elements"][
                        element_info["name"]
                    ] = interaction_result
                    service_data["extraction_metadata"]["successful_interactions"] += 1

                    if interaction_result.get("content_changed", False):
                        service_data["extraction_metadata"][
                            "content_changes_detected"
                        ] += 1

            # Discover different configuration states
            configuration_states = await self._discover_configuration_states(
                interactive_elements
            )
            service_data["configuration_states"] = configuration_states
            service_data["extraction_metadata"]["configuration_states_captured"] = len(
                configuration_states
            )

        except Exception as e:
            print(f"❌ Error extracting service config: {e}")

        return service_data

    async def _extract_service_description(self) -> str:
        """Extract the main service description."""
        description_selectors = [
            'div:has-text("provides") p',
            'div:has-text("service") p',
            'div:has-text("AWS") p',
            '[class*="description"] p',
            'p[class*="description"]',
            ".service-description",
        ]

        for selector in description_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                for elem in elements:
                    text = await elem.text_content()
                    if text and len(text) > 5 and len(text) < 500 and "AWS" in text:
                        return text.strip()
            except:
                continue
        return ""

    async def _extract_global_settings(self) -> Dict[str, Any]:
        """Extract global settings like region dropdowns."""
        global_settings = {"dropdowns": {}, "other_controls": {}}

        try:
            # Find all select elements
            selects = await self.page.query_selector_all("select")
            for select in selects:
                label = await self._get_element_label(select)
                if label:
                    options = await self._extract_select_options(select)
                    global_settings["dropdowns"][label] = {
                        "options": options,
                        "type": "select",
                    }

            # Find other global control elements
            other_controls = await self.page.query_selector_all(
                'input[type="radio"], input[type="checkbox"], button[role="switch"]'
            )

            for control in other_controls:
                label = await self._get_element_label(control)
                if label and await self._is_global_control(control, label):
                    control_type = await control.get_attribute(
                        "type"
                    ) or await control.evaluate("el => el.tagName.toLowerCase()")
                    global_settings["other_controls"][label] = {
                        "type": control_type,
                        "checked": await self._is_element_checked(control),
                    }

        except Exception as e:
            print(f"⚠️ Error extracting global settings: {e}")

        return global_settings

    async def _is_global_control(self, element, label: str) -> bool:
        """Determine if this is a global control vs service-specific."""
        label_lower = label.lower()
        global_keywords = ["region", "location", "currency", "language", "timezone"]
        return any(keyword in label_lower for keyword in global_keywords)

    async def _detect_all_interactive_elements(self) -> List[Dict[str, Any]]:
        """Detect all potentially interactive elements on the page."""
        interactive_elements = []

        # Define all types of interactive elements to look for
        element_selectors = {
            "checkboxes": 'input[type="checkbox"]',
            "radio_buttons": 'input[type="radio"]',
            "select_dropdowns": "select",
            "custom_dropdowns": 'button[aria-haspopup], [role="combobox"], button[class*="select"]',
            "toggles": 'button[role="switch"], button[aria-pressed]',
            "tabs": '[role="tab"], button[class*="tab"], .tab',
            "accordions": '[aria-expanded], button[class*="expand"], button[class*="collapse"], [class*="accordion"], [class*="collaps"], summary, details > summary, button[aria-controls], [role="button"][aria-controls], div[class*="toggle"], div[class*="dropdown"], span[class*="expand"], span[class*="toggle"]',
            "custom_buttons": 'button:not([type="submit"]):not([class*="primary"]):not([class*="cancel"])',
        }

        try:
            for element_type, selector in element_selectors.items():
                elements = await self.page.query_selector_all(selector)

                for element in elements:
                    # Skip if element is not visible
                    if not await element.is_visible():
                        continue

                    # Get element info
                    element_info = await self._analyze_interactive_element(
                        element, element_type
                    )

                    if element_info and self._is_valid_interactive_element(
                        element_info
                    ):
                        interactive_elements.append(element_info)

            # Additional detection for text-based elements like "Show calculations"
            text_selectors = [
                'text="Show calculations"',
                "text=/Show calculations/",
                'text="Show Details"',
                "text=/Show Details/",
                '*:has-text("Show calculations")',
                '*:has-text("Show Details")',
            ]

            for text_selector in text_selectors:
                try:
                    text_elements = await self.page.query_selector_all(text_selector)
                    for element in text_elements:
                        if await element.is_visible():
                            element_info = await self._analyze_interactive_element(
                                element, "accordions"
                            )
                            if element_info and self._is_valid_interactive_element(
                                element_info
                            ):
                                interactive_elements.append(element_info)
                except Exception as e:
                    # Some text selectors might not work in all contexts
                    continue

        except Exception as e:
            print(f"⚠️ Error detecting interactive elements: {e}")

        # Remove duplicates based on element position and text
        unique_elements = []
        seen_signatures = set()

        for element in interactive_elements:
            signature = f"{element.get('name', '')}-{element.get('type', '')}-{element.get('position', '')}"
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_elements.append(element)

        return unique_elements

    async def _analyze_interactive_element(
        self, element, element_type: str
    ) -> Optional[Dict[str, Any]]:
        """Analyze an interactive element to get its properties."""
        try:
            # Get element position for uniqueness
            bounding_box = await element.bounding_box()
            position = (
                f"{int(bounding_box['x'])},{int(bounding_box['y'])}"
                if bounding_box
                else "unknown"
            )

            # Get element name/label
            name = await self._get_element_label(element)
            if not name:
                name = await self._get_element_context(element)

            if not name:
                return None

            # Get current state
            current_state = await self._get_element_state(element, element_type)

            element_info = {
                "name": name.strip(),
                "type": element_type,
                "element_type": await element.evaluate(
                    "el => el.tagName.toLowerCase()"
                ),
                "position": position,
                "current_state": current_state,
                "element": element,  # Keep reference for interaction
            }

            return element_info

        except Exception as e:
            print(f"      ⚠️ Error analyzing element: {e}")
            return None

    async def _get_element_state(self, element, element_type: str) -> Dict[str, Any]:
        """Get the current state of an element."""
        state = {}

        try:
            if element_type in ["checkboxes", "radio_buttons", "toggles"]:
                state["checked"] = await self._is_element_checked(element)

            if element_type in ["select_dropdowns", "custom_dropdowns"]:
                if element_type == "select_dropdowns":
                    options = await self._extract_select_options(element)
                    selected_option = await element.evaluate("el => el.value")
                    state["options"] = options
                    state["selected"] = selected_option
                else:
                    # For custom dropdowns, get the displayed text
                    state["displayed_text"] = await element.text_content()

            if element_type == "tabs":
                state["active"] = await element.get_attribute("aria-selected") == "true"

            if element_type == "accordions":
                state["expanded"] = (
                    await element.get_attribute("aria-expanded") == "true"
                )

        except Exception as e:
            print(f"        ⚠️ Error getting element state: {e}")

        return state

    def _is_valid_interactive_element(self, element_info: Dict[str, Any]) -> bool:
        """Check if this element is worth testing for interactions."""
        name = element_info.get("name", "").lower()

        # Always include "Show calculations" and "Show details" elements
        if "show calculations" in name or "show details" in name:
            return True

        # Skip obvious UI noise
        skip_patterns = [
            "cookie",
            "privacy",
            "terms",
            "accept",
            "decline",
            "cancel",
            "save",
            "apply",
            "learn more",
            "contact",
            "feedback",
            "language",
            "help",
            "documentation",
        ]

        for pattern in skip_patterns:
            if pattern in name:
                return False

        # Must have a meaningful name
        return len(name) > 2 and len(name) < 150

    async def _test_element_interaction(
        self, element_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test interacting with an element and capture what changes."""
        interaction_result = {
            "element_name": element_info["name"],
            "element_type": element_info["type"],
            "successful": False,
            "content_changed": False,
            "changes_detected": [],
            "new_content": {},
            "error": None,
        }

        try:
            element = element_info["element"]

            # Take snapshot before interaction
            content_before = await self._capture_content_snapshot(
                f"before_{element_info['name']}"
            )

            # Perform the interaction based on element type
            await self._perform_interaction(element, element_info["type"])

            # Wait for potential content changes
            await self.page.wait_for_timeout(2000)

            # Take snapshot after interaction
            content_after = await self._capture_content_snapshot(
                f"after_{element_info['name']}"
            )

            # Compare snapshots
            changes = self._compare_content_snapshots(content_before, content_after)

            if changes:
                interaction_result["successful"] = True
                interaction_result["content_changed"] = True
                interaction_result["changes_detected"] = changes
                interaction_result["new_content"] = content_after

                print(
                    f"    ✅ Interaction successful - {len(changes)} changes detected"
                )
            else:
                interaction_result["successful"] = (
                    True  # Interaction worked, just no content changes
                )
                print(f"    ℹ️  Interaction completed - no content changes detected")

        except Exception as e:
            interaction_result["error"] = str(e)
            print(f"    ❌ Interaction failed: {e}")

        return interaction_result

    async def _perform_interaction(self, element, element_type: str):
        """Perform the appropriate interaction for an element type."""
        try:
            if element_type in [
                "checkboxes",
                "radio_buttons",
                "toggles",
                "tabs",
                "accordions",
                "custom_buttons",
            ]:
                await element.click()

            elif element_type == "select_dropdowns":
                # For select dropdowns, try to open and see all options
                await element.focus()
                await element.click()
                await self.page.wait_for_timeout(500)

            elif element_type == "custom_dropdowns":
                # For custom dropdowns, click to open
                await element.click()
                await self.page.wait_for_timeout(1000)
                # Try to close by clicking elsewhere or pressing escape
                await self.page.keyboard.press("Escape")

        except Exception as e:
            print(f"      ⚠️ Error performing interaction: {e}")
            raise

    async def _capture_content_snapshot(self, snapshot_name: str) -> Dict[str, Any]:
        """Capture a snapshot of current page content."""
        snapshot = {
            "name": snapshot_name,
            "timestamp": time.time(),
            "form_fields": [],
            "visible_text": "",
            "dropdowns": {},
            "sections": [],
        }

        try:
            # Capture form fields
            form_elements = await self.page.query_selector_all(
                "input, select, textarea"
            )
            for element in form_elements:
                if await element.is_visible():
                    field_info = await self._extract_form_attribute(element)
                    if field_info:
                        snapshot["form_fields"].append(field_info)

            # Capture visible text content
            body_text = await self.page.evaluate("() => document.body.innerText")
            snapshot["visible_text"] = (
                body_text[:1000] if body_text else ""
            )  # Limit to first 1000 chars

            # Capture dropdown states
            selects = await self.page.query_selector_all("select")
            for select in selects:
                if await select.is_visible():
                    label = await self._get_element_label(select)
                    if label:
                        options = await self._extract_select_options(select)
                        current_value = await select.evaluate("el => el.value")
                        snapshot["dropdowns"][label] = {
                            "options": options,
                            "current_value": current_value,
                        }

            # Capture section headers
            headers = await self.page.query_selector_all("h1, h2, h3, h4")
            for header in headers:
                if await header.is_visible():
                    text = await header.text_content()
                    if text and len(text.strip()) > 3:
                        snapshot["sections"].append(text.strip())

        except Exception as e:
            print(f"        ⚠️ Error capturing content snapshot: {e}")

        return snapshot

    def _compare_content_snapshots(
        self, before: Dict[str, Any], after: Dict[str, Any]
    ) -> List[str]:
        """Compare two content snapshots and return detected changes."""
        changes = []

        try:
            # Compare form fields
            before_fields = {
                f.get("name", ""): f for f in before.get("form_fields", [])
            }
            after_fields = {f.get("name", ""): f for f in after.get("form_fields", [])}

            # New fields appeared
            new_fields = set(after_fields.keys()) - set(before_fields.keys())
            if new_fields:
                changes.append(f"New form fields appeared: {list(new_fields)}")

            # Fields disappeared
            removed_fields = set(before_fields.keys()) - set(after_fields.keys())
            if removed_fields:
                changes.append(f"Form fields removed: {list(removed_fields)}")

            # Compare dropdown options
            before_dropdowns = before.get("dropdowns", {})
            after_dropdowns = after.get("dropdowns", {})

            for dropdown_name in after_dropdowns:
                if dropdown_name in before_dropdowns:
                    before_options = [
                        opt.get("text", "")
                        for opt in before_dropdowns[dropdown_name].get("options", [])
                    ]
                    after_options = [
                        opt.get("text", "")
                        for opt in after_dropdowns[dropdown_name].get("options", [])
                    ]

                    if before_options != after_options:
                        changes.append(f"Dropdown '{dropdown_name}' options changed")
                else:
                    changes.append(f"New dropdown appeared: '{dropdown_name}'")

            # Compare sections
            before_sections = set(before.get("sections", []))
            after_sections = set(after.get("sections", []))

            new_sections = after_sections - before_sections
            if new_sections:
                changes.append(f"New sections appeared: {list(new_sections)}")

            # Compare text content length (rough indicator of content changes)
            before_text_len = len(before.get("visible_text", ""))
            after_text_len = len(after.get("visible_text", ""))

            if abs(after_text_len - before_text_len) > 100:  # Significant text change
                changes.append(
                    f"Significant text content change (before: {before_text_len} chars, after: {after_text_len} chars)"
                )

        except Exception as e:
            print(f"        ⚠️ Error comparing snapshots: {e}")

        return changes

    async def _discover_configuration_states(
        self, interactive_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Discover different configuration states by testing combinations."""
        configuration_states = {}

        try:
            # Test some combinations of interactive elements
            print(f"  🔍 Discovering configuration states...")

            # Single element states
            for element in interactive_elements[
                :10
            ]:  # Limit to avoid too many combinations
                if element.get("type") in ["checkboxes", "radio_buttons", "toggles"]:
                    state_name = f"only_{element['name']}"

                    # Reset all elements first
                    await self._reset_all_elements(interactive_elements)

                    # Activate only this element
                    try:
                        await element["element"].click()
                        await self.page.wait_for_timeout(1000)

                        # Capture this configuration state
                        config_snapshot = await self._capture_content_snapshot(
                            state_name
                        )
                        configuration_states[state_name] = config_snapshot

                    except Exception as e:
                        print(f"    ⚠️ Error testing state {state_name}: {e}")

        except Exception as e:
            print(f"  ⚠️ Error discovering configuration states: {e}")

        return configuration_states

    async def _reset_all_elements(self, interactive_elements: List[Dict[str, Any]]):
        """Reset all interactive elements to their default state."""
        try:
            for element in interactive_elements:
                if element.get("type") in ["checkboxes", "toggles"]:
                    # If currently checked, uncheck it
                    if element.get("current_state", {}).get("checked", False):
                        await element["element"].click()
                        await self.page.wait_for_timeout(200)
        except Exception as e:
            print(f"    ⚠️ Error resetting elements: {e}")

    # Helper methods (reused and enhanced from previous version)
    async def _get_element_label(self, element) -> str:
        """Get the best label for an element."""
        try:
            # Try multiple methods to get element label
            methods = [
                # Direct label association
                lambda: self._get_direct_label(element),
                # ARIA label
                lambda: element.get_attribute("aria-label"),
                # Placeholder text
                lambda: element.get_attribute("placeholder"),
                # Nearby text
                lambda: self._get_nearby_text(element),
                # Parent container text (limited)
                lambda: self._get_parent_text(element),
            ]

            for method in methods:
                try:
                    label = await method()
                    if label and len(label.strip()) > 2 and len(label.strip()) < 150:
                        return label.strip()
                except:
                    continue

        except Exception as e:
            pass

        return ""

    async def _get_direct_label(self, element) -> str:
        """Get directly associated label."""
        element_id = await element.get_attribute("id")
        if element_id:
            label_elem = await self.page.query_selector(f'label[for="{element_id}"]')
            if label_elem:
                return await label_elem.text_content()
        return ""

    async def _get_nearby_text(self, element) -> str:
        """Get text near an element."""
        try:
            # Look in closest container
            parent = await element.evaluate_handle(
                "el => el.closest('div, fieldset, section, li')"
            )
            if parent:
                text = await parent.evaluate("el => el.textContent")
                if text and len(text.strip()) < 200:
                    return text.strip()
        except:
            pass
        return ""

    async def _get_parent_text(self, element) -> str:
        """Get limited parent text."""
        try:
            parent_text = await element.evaluate(
                "el => el.parentElement?.textContent?.substring(0, 100)"
            )
            return parent_text.strip() if parent_text else ""
        except:
            return ""

    async def _get_element_context(self, element) -> str:
        """Get contextual information about an element."""
        try:
            # Get text from siblings or nearby elements
            context = await element.evaluate(
                """el => {
                    // Try to get text from previous/next siblings
                    const prev = el.previousElementSibling?.textContent?.trim();
                    const next = el.nextElementSibling?.textContent?.trim();
                    
                    if (prev && prev.length < 100) return prev;
                    if (next && next.length < 100) return next;
                    
                    // Try parent's first text node
                    const parentText = el.parentElement?.childNodes[0]?.textContent?.trim();
                    if (parentText && parentText.length < 100) return parentText;
                    
                    return '';
                }"""
            )
            return context if context else ""
        except:
            return ""

    async def _is_element_checked(self, element) -> bool:
        """Check if an element is currently checked/selected."""
        try:
            # For standard inputs
            checked = await element.get_attribute("checked")
            if checked is not None:
                return checked == "true" or checked == ""

            # For ARIA elements
            aria_checked = await element.get_attribute("aria-checked")
            if aria_checked:
                return aria_checked == "true"

            # For buttons with pressed state
            aria_pressed = await element.get_attribute("aria-pressed")
            if aria_pressed:
                return aria_pressed == "true"

            # For select elements, check if something is selected
            if await element.evaluate("el => el.tagName.toLowerCase()") == "select":
                selected_value = await element.evaluate("el => el.value")
                return bool(selected_value)

            return False
        except:
            return False

    async def _extract_select_options(self, select_element) -> List[Dict[str, str]]:
        """Extract options from a select element."""
        options = []
        try:
            option_elements = await select_element.query_selector_all("option")
            for option in option_elements:
                text = await option.text_content()
                value = await option.get_attribute("value")
                if text and text.strip():
                    options.append(
                        {"text": text.strip(), "value": value or text.strip()}
                    )
        except:
            pass
        return options

    async def _extract_form_attribute(self, element) -> Optional[Dict[str, Any]]:
        """Extract clean attribute data from a form element."""
        try:
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            element_type = await element.get_attribute("type") or tag_name

            label = await self._get_element_label(element)
            if not label:
                return None

            value = await element.get_attribute("value") or ""

            options = []
            if tag_name == "select":
                options = await self._extract_select_options(element)

            attribute = {
                "name": label,
                "type": element_type,
                "default_value": value,
                "required": await element.get_attribute("required") is not None,
                "options": options,
            }

            return attribute

        except Exception as e:
            return None


def get_real_service_id(service_name: str) -> Optional[str]:
    """Map discovered service names to real AWS service IDs from the static list."""

    # Load the static service list to get real IDs
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        static_file = os.path.join(script_dir, "aws_services_from_debug.json")

        if os.path.exists(static_file):
            with open(static_file, "r") as f:
                static_services = json.load(f)

            # Create a mapping from normalized names to IDs
            name_to_id = {}
            for service in static_services:
                static_name = service.get("name", "").strip()
                service_id = service.get("id", "")

                if static_name and service_id:
                    # Normalize both names for comparison
                    normalized_static = re.sub(r"[^a-zA-Z0-9]", "", static_name.lower())
                    name_to_id[normalized_static] = service_id

            # Normalize the input service name
            normalized_input = re.sub(r"[^a-zA-Z0-9]", "", service_name.lower())

            # Try exact match first
            if normalized_input in name_to_id:
                return name_to_id[normalized_input]

            # Try partial matches
            for static_normalized, service_id in name_to_id.items():
                if (
                    static_normalized in normalized_input
                    or normalized_input in static_normalized
                ):
                    # Check if it's a reasonable match (not too different in length)
                    if abs(len(static_normalized) - len(normalized_input)) <= 5:
                        return service_id

    except Exception as e:
        print(f"⚠️ Error loading static service list: {e}")

    return None


async def discover_aws_services(page) -> List[Dict[str, str]]:
    """Discover all AWS services from the Add Service page."""
    services = []

    try:
        print("🔍 Discovering services from AWS Calculator Add Service page...")

        # Navigate to the Add Service page
        await page.goto(
            "https://calculator.aws/#/addService", wait_until="domcontentloaded"
        )
        await page.wait_for_timeout(5000)  # Wait for page to load

        # Debug: Check page content
        page_title = await page.title()
        print(f"📄 Page title: {page_title}")

        # Try to find the main services grid/container first
        services_container = None
        container_selectors = [
            ".awsui-grid[data-testid]",
            '[data-testid*="service"]',
            ".services-grid",
            ".service-list",
            "main .awsui-grid",
            '[class*="grid"]',
        ]

        for selector in container_selectors:
            try:
                container = await page.query_selector(selector)
                if container:
                    services_container = container
                    print(f"✅ Found services container with selector: {selector}")
                    break
            except:
                continue

        if not services_container:
            print("⚠️ No specific services container found, searching entire page")
            services_container = await page.query_selector("body")

        # Look for individual service items within the container
        service_items = []
        if services_container:
            # Try multiple selectors to find service cards
            item_selectors = [
                'div:has(button:text("Configure"))',
                "[data-testid]:has(button)",
                ".awsui-grid-item:has(button)",
                "article:has(button)",
                'div[class*="card"]:has(button)',
                'div:has(a[href*="createCalculator"])',
                'div:has(a:text("Configure"))',
            ]

            for selector in item_selectors:
                try:
                    items = await services_container.query_selector_all(selector)
                    if items:
                        print(f"🔍 Found {len(items)} items with selector: {selector}")
                        service_items = items
                        break
                except:
                    continue

        if not service_items:
            print("❌ Could not find service items with Configure buttons")
            # Fallback: try to find all elements with Configure text
            service_items = await page.query_selector_all('*:text("Configure")')
            print(
                f"🔄 Fallback: found {len(service_items)} elements with 'Configure' text"
            )

        print(f"🎯 Processing {len(service_items)} potential service items...")

        # Process each service item
        for i, item in enumerate(
            service_items[:200]
        ):  # Limit to prevent infinite processing
            try:
                # Skip if this is obviously not a service card
                item_text = await item.text_content()
                if not item_text:
                    continue

                # Skip items that are clearly page elements, not services
                skip_patterns = [
                    "AWS services (",
                    "Search by location",
                    "Search all services",
                    "Choose a location",
                    "Choose a Region",
                    "Find Service",
                    "Cancel",
                    "aws services (",
                    "154)",
                    "177)",
                ]

                should_skip = False
                for pattern in skip_patterns:
                    if pattern.lower() in item_text.lower():
                        should_skip = True
                        break

                if should_skip:
                    continue

                # Find the Configure button/link
                configure_element = None

                # Look for Configure button or link within this item
                configure_selectors = [
                    'button:text("Configure")',
                    'a:text("Configure")',
                    'button[aria-label*="Configure"]',
                    'a[href*="createCalculator"]',
                ]

                for selector in configure_selectors:
                    try:
                        configure_element = await item.query_selector(selector)
                        if configure_element:
                            break
                    except:
                        continue

                if not configure_element:
                    # If the item itself is a Configure button/link
                    try:
                        tag_name = await item.evaluate("el => el.tagName.toLowerCase()")
                        if tag_name in ["button", "a"]:
                            element_text = await item.text_content()
                            if element_text and "Configure" in element_text:
                                configure_element = item
                    except:
                        pass

                if not configure_element:
                    continue

                # Extract service name - look for the actual service title
                service_name = ""

                # Method 1: Look for headings near the Configure button
                headings = await item.query_selector_all(
                    'h1, h2, h3, h4, h5, h6, [role="heading"]'
                )
                for heading in headings:
                    heading_text = await heading.text_content()
                    if (
                        heading_text
                        and len(heading_text.strip()) > 3
                        and len(heading_text.strip()) < 100
                        and "Configure" not in heading_text
                        and "Product page" not in heading_text
                    ):
                        service_name = heading_text.strip()
                        break

                # Method 2: Look for bold/strong text that might be service names
                if not service_name:
                    bold_elements = await item.query_selector_all(
                        'strong, b, [class*="title"], [class*="name"]'
                    )
                    for bold in bold_elements:
                        bold_text = await bold.text_content()
                        if (
                            bold_text
                            and len(bold_text.strip()) > 3
                            and len(bold_text.strip()) < 100
                            and "Configure" not in bold_text
                            and "Product page" not in bold_text
                            and (
                                bold_text.strip().startswith("Amazon")
                                or bold_text.strip().startswith("AWS")
                            )
                        ):
                            service_name = bold_text.strip()
                            break

                # Method 3: Look for first line of text that looks like a service name
                if not service_name:
                    lines = [
                        line.strip() for line in item_text.split("\n") if line.strip()
                    ]
                    for line in lines:
                        if (
                            len(line) > 10
                            and len(line) < 80
                            and ("Amazon" in line or "AWS" in line)
                            and "Configure" not in line
                            and "Product page" not in line
                            and not line.endswith(".")
                        ):  # Service names don't end with periods
                            service_name = line
                            break

                # Method 4: Try to parse the combined text more intelligently
                if not service_name and item_text:
                    # Look for patterns like "AWS ServiceNameAWS ServiceName description..."
                    # or "Amazon ServiceNameAmazon ServiceName description..."
                    patterns = [
                        r"^(Amazon [A-Za-z0-9\s\-\.]+?)Amazon ",  # Amazon service followed by Amazon
                        r"^(AWS [A-Za-z0-9\s\-\.]+?)AWS ",  # AWS service followed by AWS
                        r"^(Amazon [A-Za-z0-9\s\-\.]+?)(?:Amazon|AWS|\s[A-Z])",  # Amazon service followed by Amazon/AWS/capital
                        r"^(AWS [A-Za-z0-9\s\-\.]+?)(?:Amazon|AWS|\s[A-Z])",  # AWS service followed by Amazon/AWS/capital
                        r"^(Amazon [A-Za-z0-9\s\-\.]{5,50}?)(?:\s+[a-z])",  # Amazon service followed by lowercase
                        r"^(AWS [A-Za-z0-9\s\-\.]{5,50}?)(?:\s+[a-z])",  # AWS service followed by lowercase
                        r"^(Amazon [A-Za-z0-9\s\-\.]{5,40})",  # Fallback Amazon
                        r"^(AWS [A-Za-z0-9\s\-\.]{5,40})",  # Fallback AWS
                    ]

                    clean_text = item_text.replace("\n", " ").replace("\t", " ")
                    clean_text = re.sub(r"\s+", " ", clean_text).strip()

                    for pattern in patterns:
                        match = re.search(pattern, clean_text)
                        if match:
                            candidate_name = match.group(1).strip()
                            # Clean up common issues
                            candidate_name = re.sub(
                                r"\s+(is|provides|offers|minimizes|helps).*$",
                                "",
                                candidate_name,
                                flags=re.IGNORECASE,
                            )
                            candidate_name = re.sub(
                                r"With$", "", candidate_name
                            )  # Remove trailing "With"
                            candidate_name = candidate_name.strip()

                            if len(candidate_name) > 5 and len(candidate_name) < 80:
                                service_name = candidate_name
                                break

                if not service_name:
                    if i < 10:  # Debug first 10
                        print(
                            f"  ❌ No service name found for item {i}: {item_text[:100]}..."
                        )
                    continue

                # IMPROVED URL EXTRACTION - Prioritize real service IDs
                service_url = ""

                # FIRST: Try to get real service ID from static mapping
                real_service_id = get_real_service_id(service_name)
                if real_service_id:
                    service_url = (
                        f"https://calculator.aws/#/createCalculator/{real_service_id}"
                    )
                    if i < 10:  # Debug first 10
                        print(
                            f"  🔗 Mapped URL for {service_name}: {service_url} (using real ID: {real_service_id})"
                        )
                else:
                    # SECOND: Try to extract URL from the page
                    # Method 1: Check href attribute directly
                    href = await configure_element.get_attribute("href")
                    if href:
                        if href.startswith("http"):
                            service_url = href
                        elif href.startswith("#/"):
                            service_url = f"https://calculator.aws{href}"
                        if i < 10:  # Debug first 10
                            print(
                                f"  🔗 Found href for {service_name}: {href} -> {service_url}"
                            )

                    # Method 2: Check onclick attribute for service ID
                    if not service_url:
                        onclick = await configure_element.get_attribute("onclick")
                        if onclick and "createCalculator" in onclick:
                            # Look for patterns like navigate('/createCalculator/bedrock')
                            match = re.search(
                                r'createCalculator/([^"\')\s,/]+)', onclick
                            )
                            if match:
                                service_id = match.group(1)
                                service_url = f"https://calculator.aws/#/createCalculator/{service_id}"
                                if i < 10:  # Debug first 10
                                    print(
                                        f"  🔗 Found onclick for {service_name}: {onclick} -> service_id: {service_id}"
                                    )

                    # Method 3: Look for data attributes that might contain the service ID
                    if not service_url:
                        data_attrs = [
                            "data-url",
                            "data-href",
                            "data-link",
                            "data-service-url",
                            "data-service-id",
                        ]
                        for attr in data_attrs:
                            attr_value = await configure_element.get_attribute(attr)
                            if attr_value:
                                if attr_value.startswith("http"):
                                    service_url = attr_value
                                elif attr_value.startswith("#/"):
                                    service_url = f"https://calculator.aws{attr_value}"
                                elif "/" not in attr_value:  # Looks like a service ID
                                    service_url = f"https://calculator.aws/#/createCalculator/{attr_value}"
                                if i < 10:  # Debug first 10
                                    print(
                                        f"  🔗 Found {attr} for {service_name}: {attr_value} -> {service_url}"
                                    )
                                break

                    # LAST RESORT: Generate URL (but mark as potentially non-working)
                    if not service_url:
                        service_id = service_name.lower()
                        service_id = service_id.replace("amazon ", "").replace(
                            "aws ", ""
                        )
                        service_id = re.sub(r"[^a-zA-Z0-9]", "", service_id)
                        if len(service_id) > 2:
                            service_url = f"https://calculator.aws/#/createCalculator/{service_id}"
                            if i < 10:  # Debug first 10
                                print(
                                    f"  🔗 Generated URL for {service_name}: {service_url} (WARNING: May not work)"
                                )

                if service_name and service_url:
                    # Clean up the service name
                    service_name = re.sub(r"\s+", " ", service_name).strip()

                    # Final validation - make sure this looks like a real service
                    if (
                        len(service_name) > 5
                        and len(service_name) < 100
                        and ("Amazon" in service_name or "AWS" in service_name)
                    ):

                        services.append({"name": service_name, "url": service_url})
                        print(f"  ✅ Found: {service_name}")

            except Exception as e:
                if i < 5:  # Only log errors for first few items
                    print(f"  ⚠️ Error processing item {i}: {e}")
                continue

        # Remove duplicates
        unique_services = []
        seen_names = set()
        for service in services:
            if service["name"] not in seen_names:
                seen_names.add(service["name"])
                unique_services.append(service)

        services = unique_services
        print(f"🎯 Discovered {len(services)} unique AWS services")

        # Save discovered services for future use
        with open(DISCOVERED_SERVICES_JSON, "w", encoding="utf-8") as f:
            json.dump(services, f, indent=2, ensure_ascii=False)

        print(f"💾 Saved discovered services to: {DISCOVERED_SERVICES_JSON}")

    except Exception as e:
        print(f"❌ Error discovering services: {e}")
        # Fallback to some known services
        services = [
            {
                "name": "Amazon Bedrock",
                "url": "https://calculator.aws/#/createCalculator/bedrock",
            },
            {
                "name": "Amazon RDS",
                "url": "https://calculator.aws/#/createCalculator/RDS",
            },
            {
                "name": "Amazon EC2",
                "url": "https://calculator.aws/#/createCalculator/EC2",
            },
        ]
        print(f"🔄 Using fallback services: {len(services)} services")

    return services


async def test_service_url(page, service_url: str) -> bool:
    """Test if a service URL actually leads to a service configuration page."""
    try:
        await page.goto(service_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        current_url = page.url

        # Check if we were redirected to the wrong page
        if current_url == "https://calculator.aws/#/addService":
            return False

        # Check if we're on a service configuration page
        if "/createCalculator/" not in current_url:
            return False

        # Check for service configuration elements
        form_fields = await page.query_selector_all("input, select, textarea")

        # A real service config page should have some form fields
        return len(form_fields) >= 3

    except Exception:
        return False


def load_existing_scraped_data() -> Dict[str, Any]:
    """Load existing scraped data if it exists."""
    try:
        if os.path.exists(OUTPUT_JSON):
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading existing scraped data: {e}")
    return {}


def save_service_data(service_name: str, service_data: Dict[str, Any]):
    """Save a single service's data to the main data file."""
    try:
        # Load existing data
        all_data = load_existing_scraped_data()

        # Add new service data
        all_data[service_name] = service_data

        # Save updated data
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Saved {service_name} data to {OUTPUT_JSON}")

    except Exception as e:
        print(f"❌ Error saving service data for {service_name}: {e}")


def load_unscraped_services() -> List[Dict[str, str]]:
    """Load the list of services that haven't been scraped yet."""
    try:
        if os.path.exists(UNSCRAPED_SERVICES_JSON):
            with open(UNSCRAPED_SERVICES_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading unscraped services: {e}")
    return []


def save_unscraped_services(services: List[Dict[str, str]]):
    """Save the list of services that haven't been scraped yet."""
    try:
        with open(UNSCRAPED_SERVICES_JSON, "w", encoding="utf-8") as f:
            json.dump(services, f, indent=2, ensure_ascii=False)
        print(f"💾 Updated unscraped services list: {len(services)} remaining")
    except Exception as e:
        print(f"❌ Error saving unscraped services: {e}")


def remove_service_from_unscraped(service_name: str):
    """Remove a service from the unscraped services list after successful scraping."""
    try:
        unscraped = load_unscraped_services()
        original_count = len(unscraped)

        # Remove the service from the list
        unscraped = [s for s in unscraped if s.get("name") != service_name]

        if len(unscraped) < original_count:
            save_unscraped_services(unscraped)
            print(f"✅ Removed {service_name} from unscraped list")
        else:
            print(f"⚠️ Service {service_name} not found in unscraped list")

    except Exception as e:
        print(f"❌ Error removing service from unscraped list: {e}")


def get_services_to_process() -> List[Dict[str, str]]:
    """Get the list of services to process, checking for existing unscraped list first."""
    # First, check if we have an existing unscraped services list
    unscraped_services = load_unscraped_services()

    if unscraped_services:
        print(
            f"📋 Found existing unscraped services list with {len(unscraped_services)} services"
        )

        # Check which services have already been scraped
        scraped_data = load_existing_scraped_data()
        scraped_service_names = set(scraped_data.keys())

        # Filter out already scraped services
        remaining_unscraped = [
            s for s in unscraped_services if s.get("name") not in scraped_service_names
        ]

        if len(remaining_unscraped) != len(unscraped_services):
            print(
                f"🔄 Filtered out {len(unscraped_services) - len(remaining_unscraped)} already scraped services"
            )
            save_unscraped_services(remaining_unscraped)

        if remaining_unscraped:
            return remaining_unscraped
        else:
            print("✅ All services from unscraped list have been processed!")
            return []

    # If no unscraped list exists, we need to discover services
    print("🔍 No existing unscraped services list found, will discover services first")
    return []


def get_target_services() -> List[Dict[str, str]]:
    """Get the specific list of architecture set services."""
    target_services = [
        {
            "name": "AWS DataSync",
            "url": "https://calculator.aws/#/createCalculator/DataSync",
            "component_type": "AWSDataSync",
        },
        {
            "name": "AWS Direct Connect",
            "url": "https://calculator.aws/#/createCalculator/DirectConnect",
            "component_type": "AWSDirectConnect",
        },
        {
            "name": "Amazon EventBridge",
            "url": "https://calculator.aws/#/createCalculator/EventBridge",
            "component_type": "AWSEvents",
        },
        {
            "name": "AWS Lambda",
            "url": "https://calculator.aws/#/createCalculator/Lambda",
            "component_type": "AWSLambda",
        },
        {
            "name": "AWS Storage Gateway",
            "url": "https://calculator.aws/#/createCalculator/StorageGateway",
            "component_type": "AWSStorageGateway",
        },
        {
            "name": "AWS Systems Manager",
            "url": "https://calculator.aws/#/createCalculator/SystemsManager",
            "component_type": "AWSSystemsManager",
        },
        {
            "name": "AWS Transfer Family",
            "url": "https://calculator.aws/#/createCalculator/TransferFamily",
            "component_type": "AWSTransfer",
        },
        {
            "name": "Amazon EC2",
            "url": "https://calculator.aws/#/createCalculator/EC2",
            "component_type": "AmazonEC2",
        },
        {
            "name": "Amazon ECS",
            "url": "https://calculator.aws/#/createCalculator/ECS",
            "component_type": "AmazonECS",
        },
        {
            "name": "Amazon EKS",
            "url": "https://calculator.aws/#/createCalculator/EKS",
            "component_type": "AmazonEKS",
        },
        {
            "name": "Amazon S3",
            "url": "https://calculator.aws/#/createCalculator/S3",
            "component_type": "AmazonS3",
        },
    ]

    print(
        f"🎯 Using architecture set services list with {len(target_services)} specific services"
    )
    return target_services


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True
        )  # Set to True for headless mode
        context = await browser.new_context()
        page = await context.new_page()

        # Use target services instead of discovering
        print("🎯 Using predefined target services list")
        target_services = get_target_services()

        # Filter out any services that were already scraped
        existing_scraped_data = load_existing_scraped_data()
        scraped_service_names = set(existing_scraped_data.keys())

        unscraped_services = [
            s for s in target_services if s.get("name") not in scraped_service_names
        ]

        if len(unscraped_services) != len(target_services):
            print(
                f"🔄 Filtered out {len(target_services) - len(unscraped_services)} already scraped services"
            )

        # Save the list of services to be scraped
        save_unscraped_services(unscraped_services)
        services_to_process = unscraped_services

        print(f"🚀 Starting Targeted AWS Service Scraper")
        print("=" * 60)
        print(f"🔍 Will scrape {len(services_to_process)} specific services")

        # Load existing scraped data to avoid duplication
        scraped_count = len(existing_scraped_data)
        print(f"📊 Already scraped: {scraped_count} services")

        for i, service in enumerate(services_to_process):
            print(
                f"\n➡️  [{i+1}/{len(services_to_process)}] Scraping: {service['name']} ({service.get('component_type', 'N/A')})"
            )

            # Check if this service was already scraped
            if service["name"] in existing_scraped_data:
                print(f"    ⏭️  Already scraped - skipping")
                remove_service_from_unscraped(service["name"])
                continue

            try:
                # Navigate to service page
                await page.goto(service["url"], wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)  # Wait for page to fully load

                # Verify we're on the right page
                current_url = page.url
                if current_url == "https://calculator.aws/#/addService":
                    print(f"    ❌ URL redirected to service selection page - skipping")
                    remove_service_from_unscraped(service["name"])
                    continue

                # Extract dynamic service data
                extractor = GeneralDynamicAWSExtractor(page)
                service_data = await extractor.extract_service_config(service["name"])

                # Add component type to service data
                service_data["component_type"] = service.get("component_type", "")

                # Save immediately after successful extraction
                save_service_data(service["name"], service_data)

                # Remove from unscraped list
                remove_service_from_unscraped(service["name"])

                metadata = service_data["extraction_metadata"]
                print(f"✅ Extraction complete!")
                print(
                    f"   📊 Interactive elements: {metadata['interactive_elements_found']}"
                )
                print(
                    f"   📊 Successful interactions: {metadata['successful_interactions']}"
                )
                print(
                    f"   📊 Content changes detected: {metadata['content_changes_detected']}"
                )
                print(
                    f"   📊 Configuration states: {metadata['configuration_states_captured']}"
                )

                scraped_count += 1

            except Exception as e:
                print(f"❌ Error scraping {service['name']}: {e}")
                print(f"   ⚠️  Service remains in unscraped list for retry")
                continue

        print(f"\n✅ Targeted scraping session complete!")
        print(f"📁 Data saved incrementally to: {OUTPUT_JSON}")
        print(
            f"📊 Total services scraped this session: {scraped_count - len(existing_scraped_data)}"
        )
        print(f"📊 Total services scraped overall: {scraped_count}")

        # Check remaining unscraped services
        remaining_unscraped = load_unscraped_services()
        if remaining_unscraped:
            print(f"📋 {len(remaining_unscraped)} services remain unscraped")
            print(f"💡 Run the script again to continue scraping remaining services")
        else:
            print(f"🎉 All target services have been scraped!")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
