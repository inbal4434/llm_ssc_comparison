#!/usr/bin/env python3

import json
import asyncio
from typing import Dict, List, Any, Set
from playwright.async_api import async_playwright
import argparse
import csv
from datetime import datetime


class ToggleAwareIBUScraper:
    """Scraper that understands toggle-based IBU sections."""

    def __init__(self, page):
        self.page = page
        self.discovered_ibus = {}
        self.toggle_states = {}
        self.service_name = ""

    async def analyze_calculator_page(self, service_url: str) -> Dict[str, Any]:
        """Analyze calculator page with focus on toggle-based IBU discovery."""

        print(f"\n🔍 Analyzing {service_url.split('/')[-1]} calculator...")

        try:
            await self.page.goto(service_url, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(4000)  # Wait for full load

            # Extract service name
            self.service_name = await self._extract_service_name()
            print(f"   📋 Service: {self.service_name}")

            # Phase 1: Detect all toggle buttons that control IBU sections
            print("   🔘 Phase 1: Detecting toggle buttons...")
            await self._detect_ibu_toggle_buttons()

            # Phase 2: Test each toggle to discover IBU sections
            print("   🧪 Phase 2: Testing toggles to discover IBUs...")
            await self._test_toggle_combinations()

            # Phase 3: Map static sections (always visible)
            print("   📊 Phase 3: Mapping static IBU sections...")
            await self._map_static_ibu_sections()

            # Phase 4: Detect section-revealing toggles (like S3 storage class toggles)
            print("   🎯 Phase 4: Detecting section-revealing toggles...")
            await self._detect_section_revealing_toggles()

            # Phase 5: Generate final IBU mapping
            print("   📝 Phase 5: Generating IBU mapping...")
            ibu_mapping = await self._generate_comprehensive_ibu_mapping()

            return {
                "service_name": self.service_name,
                "discovered_ibus": self.discovered_ibus,
                "toggle_states": self.toggle_states,
                "ibu_mapping": ibu_mapping,
                "timestamp": datetime.now().timestamp(),
            }

        except Exception as e:
            print(f"❌ Error analyzing {service_url}: {e}")
            return {"error": str(e)}

    async def _extract_service_name(self) -> str:
        """Extract the actual service name from the page."""

        page_title = await self.page.title()

        # Clean up the service name
        if "Configure" in page_title:
            service_name = page_title.split("Configure ")[-1]
        else:
            service_name = page_title

        # Remove common suffixes
        service_name = service_name.replace(" pricing calculator", "").strip()

        return service_name

    async def _detect_ibu_toggle_buttons(self):
        """Detect toggle buttons that enable/disable entire IBU sections."""

        toggles = await self.page.evaluate(
            """
        () => {
            const toggles = [];
            
            function isCalculatorArea(element) {
                const rect = element.getBoundingClientRect();
                if (rect.x < -500 || rect.y < 0 || rect.width < 10 || rect.height < 10) {
                    return false;
                }
                
                // Skip navigation and header areas
                const skipSelectors = [
                    '.awsui_variant-top-navigation',
                    '.awsui_variant-secondary-navigation',
                    'nav', 'header', '.breadcrumb'
                ];
                
                for (const skipSelector of skipSelectors) {
                    if (element.closest(skipSelector)) {
                        return false;
                    }
                }
                
                return true;
            }
            
            // Look for feature toggle patterns commonly used in AWS calculators
            
            // 1. Checkboxes with feature names (like S3 storage classes)
            document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                if (!isCalculatorArea(checkbox)) return;
                
                const label = checkbox.closest('label') || 
                            document.querySelector(`label[for="${checkbox.id}"]`) ||
                            checkbox.parentElement;
                            
                if (label) {
                    const labelText = label.textContent.trim();
                    
                    // Patterns that suggest this enables an IBU section - GENERALIZED for all AWS services
                    const ibuPatterns = [
                        // Storage class patterns (S3, EBS, etc.)
                        /(Standard|Intelligent|Glacier|Express|Access|Infrequent|One Zone|Deep Archive)/i,
                        // Transfer patterns
                        /Data Transfer/i,
                        /Transfer Acceleration/i,
                        // Service class patterns
                        /(Storage|Database|Compute|Network|Instance) (Class|Type|Mode)/i,
                        // Enhancement patterns
                        /(Enhanced|Advanced|Premium|Professional|Enterprise) (Mode|Features|Edition)/i,
                        // Availability patterns
                        /(Multi-AZ|Cross-Region|Backup|Replication)/i,
                        // Performance patterns
                        /(Provisioned|Burstable|High Performance)/i,
                        // Architecture patterns
                        /(ARM|x86|Graviton)/i,
                        // Generic service features (broader matching)
                        /\b(enable|use|include)\s+\w+/i
                    ];
                    
                    const isIBUToggle = ibuPatterns.some(pattern => pattern.test(labelText));
                    
                    if (isIBUToggle && labelText.length > 5) {
                        toggles.push({
                            type: 'checkbox',
                            element: checkbox,
                            label: labelText,
                            checked: checkbox.checked,
                            id: checkbox.id || `toggle-${toggles.length}`,
                            position: checkbox.getBoundingClientRect()
                        });
                    }
                }
            });
            
            // 2. Toggle buttons (aria-pressed or specific classes)
            document.querySelectorAll('button[aria-pressed], .toggle-button, [class*="toggle"]').forEach(button => {
                if (!isCalculatorArea(button)) return;
                
                const text = button.textContent.trim();
                const pressed = button.getAttribute('aria-pressed') === 'true';
                
                if (text.length > 5 && text.length < 50) {
                    toggles.push({
                        type: 'toggle_button',
                        element: button,
                        label: text,
                        pressed: pressed,
                        id: button.id || `toggle-btn-${toggles.length}`,
                        position: button.getBoundingClientRect()
                    });
                }
            });
            
            // 3. Expandable sections (like collapsible feature groups)
            document.querySelectorAll('[role="button"][aria-expanded], .expandable-trigger').forEach(expander => {
                if (!isCalculatorArea(expander)) return;
                
                const text = expander.textContent.trim();
                const expanded = expander.getAttribute('aria-expanded') === 'true';
                
                // Look for section-like text
                if (text.match(/(feature|option|setting|configuration)/i) && text.length < 50) {
                    toggles.push({
                        type: 'expandable',
                        element: expander,
                        label: text,
                        expanded: expanded,
                        id: expander.id || `expander-${toggles.length}`,
                        position: expander.getBoundingClientRect()
                    });
                }
            });
            
            // Sort by position (top to bottom, left to right)
            return toggles.sort((a, b) => {
                if (Math.abs(a.position.y - b.position.y) < 50) {
                    return a.position.x - b.position.x;
                }
                return a.position.y - b.position.y;
            });
        }
        """
        )

        self.toggle_states = {
            toggle["id"]: {
                "type": toggle["type"],
                "label": toggle["label"],
                "initial_state": toggle.get(
                    "checked", toggle.get("pressed", toggle.get("expanded", False))
                ),
                "position": toggle["position"],
            }
            for toggle in toggles
        }

        print(f"   🔘 Found {len(toggles)} potential IBU toggles:")
        for toggle in toggles:
            state = toggle.get(
                "checked", toggle.get("pressed", toggle.get("expanded", "unknown"))
            )
            print(f"     • {toggle['label']} ({toggle['type']}) - {state}")

    async def _test_toggle_combinations(self):
        """Test each toggle to see what IBU sections it reveals."""

        for toggle_id, toggle_info in self.toggle_states.items():
            print(f"   🧪 Testing toggle: {toggle_info['label']}")

            try:
                # Find the toggle element
                toggle_element = await self._find_toggle_element(toggle_id, toggle_info)

                if not toggle_element:
                    print(f"     ❌ Could not find toggle element")
                    continue

                # Test both states: enabled and disabled
                await self._test_toggle_states(toggle_element, toggle_id, toggle_info)

            except Exception as e:
                print(f"     ❌ Error testing toggle: {e}")

    async def _find_toggle_element(self, toggle_id, toggle_info):
        """Find the toggle element using multiple strategies."""

        # Strategy 1: By ID
        if toggle_id.startswith("toggle-") or toggle_id.startswith("expander-"):
            # These are generated IDs, need to find by label
            pass
        else:
            element = await self.page.query_selector(f"#{toggle_id}")
            if element:
                return element

        # Strategy 2: By label text and type
        if toggle_info["type"] == "checkbox":
            checkboxes = await self.page.query_selector_all('input[type="checkbox"]')
            for checkbox in checkboxes:
                # Check label association
                checkbox_id = await checkbox.get_attribute("id")
                if checkbox_id:
                    label_element = await self.page.query_selector(
                        f'label[for="{checkbox_id}"]'
                    )
                    if label_element:
                        label_text = await label_element.text_content()
                        if toggle_info["label"] in label_text:
                            return checkbox

                # Check parent label
                parent = await checkbox.evaluate_handle('el => el.closest("label")')
                if parent:
                    parent_text = await parent.text_content()
                    if toggle_info["label"] in parent_text:
                        return checkbox

        elif toggle_info["type"] == "toggle_button":
            buttons = await self.page.query_selector_all("button[aria-pressed]")
            for button in buttons:
                button_text = await button.text_content()
                if toggle_info["label"] in button_text:
                    return button

        return None

    async def _test_toggle_states(self, toggle_element, toggle_id, toggle_info):
        """Test enabling and disabling a toggle to see what IBU sections appear/disappear."""

        # Capture initial page state
        initial_elements = await self._capture_page_elements()

        # Test enabling the toggle (if not already enabled)
        if not toggle_info["initial_state"]:
            print(f"     🔛 Enabling {toggle_info['label']}...")

            try:
                await toggle_element.click()
                await self.page.wait_for_timeout(3000)  # Wait for content to load

                # Capture new page state
                enabled_elements = await self._capture_page_elements()

                # Find new elements that appeared
                new_elements = self._find_new_elements(
                    initial_elements, enabled_elements
                )

                if new_elements:
                    ibu_name = self._generate_ibu_name(toggle_info["label"])
                    self.discovered_ibus[f"{ibu_name} (when enabled)"] = {
                        "trigger_toggle": toggle_info["label"],
                        "trigger_state": "enabled",
                        "elements": new_elements,
                        "element_count": len(new_elements),
                    }

                    print(
                        f"     ✅ Found {len(new_elements)} new elements when enabled"
                    )
                    for elem in new_elements[:3]:  # Show first 3
                        print(f"       - {elem['label']}")
                else:
                    print(f"     ➖ No new elements found when enabled")

            except Exception as e:
                print(f"     ❌ Error enabling toggle: {e}")

        # Test disabling the toggle (if currently enabled)
        current_state = await self._get_toggle_current_state(
            toggle_element, toggle_info["type"]
        )

        if current_state:
            print(f"     🔲 Disabling {toggle_info['label']}...")

            try:
                await toggle_element.click()
                await self.page.wait_for_timeout(2000)

                # Capture page state when disabled
                disabled_elements = await self._capture_page_elements()

                # Find elements that disappeared
                removed_elements = self._find_new_elements(
                    disabled_elements, initial_elements
                )

                if removed_elements:
                    print(
                        f"     ✅ Found {len(removed_elements)} elements that disappeared when disabled"
                    )

                # Re-enable for consistency (if it was initially enabled)
                if toggle_info["initial_state"]:
                    await toggle_element.click()
                    await self.page.wait_for_timeout(1000)

            except Exception as e:
                print(f"     ❌ Error disabling toggle: {e}")

    async def _get_toggle_current_state(self, toggle_element, toggle_type):
        """Get the current state of a toggle element."""

        if toggle_type == "checkbox":
            return await toggle_element.is_checked()
        elif toggle_type == "toggle_button":
            pressed = await toggle_element.get_attribute("aria-pressed")
            return pressed == "true"
        elif toggle_type == "expandable":
            expanded = await toggle_element.get_attribute("aria-expanded")
            return expanded == "true"

        return False

    async def _capture_page_elements(self):
        """Capture all calculator elements currently visible on the page."""

        return await self.page.evaluate(
            """
        () => {
            const elements = [];
            
            function isCalculatorArea(element) {
                const rect = element.getBoundingClientRect();
                if (rect.x < -500 || rect.y < 0 || rect.width < 10 || rect.height < 10) {
                    return false;
                }
                
                const skipSelectors = [
                    '.awsui_variant-top-navigation',
                    '.awsui_variant-secondary-navigation', 
                    'nav', 'header', '.breadcrumb'
                ];
                
                for (const skipSelector of skipSelectors) {
                    if (element.closest(skipSelector)) {
                        return false;
                    }
                }
                
                return true;
            }
            
            function getLabel(element) {
                // Try multiple label finding strategies
                const strategies = [
                    () => element.getAttribute('aria-label'),
                    () => {
                        if (element.id) {
                            const label = document.querySelector(`label[for="${element.id}"]`);
                            return label ? label.textContent.trim() : null;
                        }
                        return null;
                    },
                    () => element.getAttribute('placeholder'),
                    () => {
                        const parent = element.closest('.awsui-form-field, .form-field');
                        if (parent) {
                            const label = parent.querySelector('label, .awsui-form-field-label');
                            return label ? label.textContent.trim() : null;
                        }
                        return null;
                    },
                    () => {
                        if (element.tagName === 'BUTTON') {
                            return element.textContent.trim();
                        }
                        return null;
                    }
                ];
                
                for (const strategy of strategies) {
                    try {
                        const label = strategy();
                        if (label && label.length > 2 && !label.match(/^(Info:|Feedback)/)) {
                            return label;
                        }
                    } catch (e) {
                        continue;
                    }
                }
                
                return null;
            }
            
            // Capture inputs
            document.querySelectorAll('input[type="text"], input[type="number"], textarea').forEach(input => {
                if (input.offsetParent && isCalculatorArea(input)) {
                    const label = getLabel(input);
                    if (label) {
                        elements.push({
                            type: input.type || 'text',
                            label: label,
                            value: input.value,
                            id: input.id || `input-${elements.length}`,
                            position: input.getBoundingClientRect()
                        });
                    }
                }
            });
            
            // Capture selects and dropdowns
            document.querySelectorAll('select, button[class*="trigger"], [role="combobox"]').forEach(dropdown => {
                if (dropdown.offsetParent && isCalculatorArea(dropdown)) {
                    const label = getLabel(dropdown);
                    if (label) {
                        elements.push({
                            type: 'dropdown',
                            label: label,
                            id: dropdown.id || `dropdown-${elements.length}`,
                            position: dropdown.getBoundingClientRect()
                        });
                    }
                }
            });
            
            // Capture checkboxes (but exclude major IBU toggle checkboxes)
            document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                if (checkbox.offsetParent && isCalculatorArea(checkbox)) {
                    const label = getLabel(checkbox);
                    // Skip checkboxes that are major service feature toggles (these are handled separately)
                    const isMainFeatureToggle = label && (
                        /(Standard|Intelligent|Glacier|Express|Access|Infrequent|Deep Archive)/i.test(label) ||
                        /Data Transfer/i.test(label) ||
                        /Transfer Acceleration/i.test(label)
                    );
                    
                    if (label && !isMainFeatureToggle) {
                        elements.push({
                            type: 'checkbox',
                            label: label,
                            checked: checkbox.checked,
                            id: checkbox.id || `checkbox-${elements.length}`,
                            position: checkbox.getBoundingClientRect()
                        });
                    }
                }
            });
            
            return elements.sort((a, b) => {
                if (Math.abs(a.position.y - b.position.y) < 30) {
                    return a.position.x - b.position.x;
                }
                return a.position.y - b.position.y;
            });
        }
        """
        )

    def _find_new_elements(self, old_elements: List, new_elements: List) -> List:
        """Find elements that exist in new_elements but not in old_elements."""

        # Create a set of old element signatures for fast lookup
        old_signatures = set()
        for elem in old_elements:
            signature = (
                f"{elem['type']}:{elem['label']}:{elem.get('position', {}).get('y', 0)}"
            )
            old_signatures.add(signature)

        # Find new elements
        new_elements_found = []
        for elem in new_elements:
            signature = (
                f"{elem['type']}:{elem['label']}:{elem.get('position', {}).get('y', 0)}"
            )
            if signature not in old_signatures:
                new_elements_found.append(elem)

        return new_elements_found

    def _generate_ibu_name(self, toggle_label: str) -> str:
        """Generate a clean IBU name from toggle label."""

        # Clean up the label
        ibu_name = toggle_label.strip()

        # Remove common prefixes/suffixes
        ibu_name = (
            ibu_name.replace("Enable ", "").replace("Use ", "").replace("Include ", "")
        )

        # Handle service-specific patterns to avoid redundancy
        service_lower = self.service_name.lower()
        ibu_lower = ibu_name.lower()

        # Check if service name is already in the IBU name (avoid "Amazon S3 S3 Standard")
        if any(part.lower() in ibu_lower for part in self.service_name.split()):
            # Service name already present, just clean it up
            return ibu_name

        # For generic terms, add service name
        generic_terms = ["data transfer", "configuration", "settings", "options"]
        if any(term in ibu_lower for term in generic_terms):
            return f"{self.service_name} {ibu_name}"

        # For specific feature names, keep as-is (e.g., "S3 Standard", "Lambda ARM")
        return ibu_name

    async def _map_static_ibu_sections(self):
        """Map IBU sections that are always visible (not toggle-dependent)."""

        print("   📊 Mapping static sections...")

        # Look for clear section headers in the calculator
        static_sections = await self.page.evaluate(
            """
        () => {
            const sections = [];
            
            function isCalculatorArea(element) {
                const rect = element.getBoundingClientRect();
                return rect.x > -500 && rect.y > 0 && rect.width > 10 && rect.height > 10;
            }
            
            // Look for section headers
            document.querySelectorAll('h1, h2, h3, h4, .section-header, [class*="header"]').forEach(header => {
                if (!isCalculatorArea(header)) return;
                
                const text = header.textContent.trim();
                
                // AWS calculator section patterns - comprehensive detection
                const sectionPatterns = [
                    // Exact section headers
                    /^(Data Transfer feature?|Data Transfer|Service settings|Configuration|Pricing|Options)/i,
                    // Feature selection headers  
                    /^(Select .* features?|Choose .* options?|Select .* Storage classes)/i,
                    // Feature suffix patterns
                    /.*feature$/i,
                    // Settings patterns
                    /settings$/i,
                    // AWS-specific patterns
                    /^(Basic|Advanced|Enhanced) (Configuration|Settings)/i,
                    // Calculator specific headers
                    /^(Estimate|Calculate|Configure)/i
                ];
                
                const isSection = sectionPatterns.some(pattern => pattern.test(text));
                
                if (isSection && text.length > 3 && text.length < 80) {
                    sections.push({
                        title: text,
                        position: header.getBoundingClientRect(),
                        element_type: header.tagName.toLowerCase()
                    });
                }
            });
            
            return sections.sort((a, b) => a.position.y - b.position.y);
        }
        """
        )

        # For each static section, capture its elements
        for section in static_sections:
            section_title = section["title"]
            print(f"     📦 Found static section: {section_title}")

            # Capture elements in this section area
            section_elements = await self._capture_page_elements()

            # Filter elements that belong to this section using better logic
            section_y = section["position"]["y"]
            relevant_elements = []

            # Find the next section's Y position for better boundary detection
            next_section_y = section_y + 500  # default large boundary
            for other_section in static_sections:
                other_y = other_section["position"]["y"]
                if other_y > section_y and other_y < next_section_y:
                    next_section_y = other_y - 30  # 30px buffer

            for elem in section_elements:
                elem_y = elem.get("position", {}).get("y", 0)
                # Elements within the section boundaries
                if section_y <= elem_y <= next_section_y:
                    relevant_elements.append(elem)

            if relevant_elements:
                ibu_name = self._generate_ibu_name(section_title)
                self.discovered_ibus[f"{ibu_name} (static)"] = {
                    "type": "static_section",
                    "section_header": section_title,
                    "elements": relevant_elements,
                    "element_count": len(relevant_elements),
                }

                print(f"       ✅ Found {len(relevant_elements)} elements in section")

    async def _detect_section_revealing_toggles(self):
        """Detect toggles that reveal entire IBU sections when clicked (like S3 storage class toggles)."""

        print("   🎯 Looking for section-revealing toggles...")

        # Look for toggle areas that contain multiple feature toggles
        toggle_sections = await self.page.evaluate(
            """
        () => {
            const sections = [];
            
            function isCalculatorArea(element) {
                const rect = element.getBoundingClientRect();
                return rect.x > -500 && rect.y > 0 && rect.width > 10 && rect.height > 10;
            }
            
            // Look for containers that have multiple toggles (like S3 storage class section)
            const containers = document.querySelectorAll('[class*="select"], .feature-group, .options-group');
            
            containers.forEach(container => {
                if (!isCalculatorArea(container)) return;
                
                const toggles = container.querySelectorAll('input[type="checkbox"], button[aria-pressed]');
                
                if (toggles.length >= 3) { // Multiple toggles suggest this is a feature selection area
                    const containerText = container.textContent || '';
                    
                    // Look for text that suggests this controls IBU sections
                    if (containerText.match(/(storage class|select.*features|choose.*options)/i)) {
                        sections.push({
                            container: container,
                            toggle_count: toggles.length,
                            text_sample: containerText.substring(0, 100),
                            position: container.getBoundingClientRect()
                        });
                    }
                }
            });
            
            return sections;
        }
        """
        )

        for section in toggle_sections:
            print(
                f"     📦 Found toggle section with {section['toggle_count']} toggles"
            )
            print(f"       Sample text: {section['text_sample'][:50]}...")

            # Test each toggle in this section to see if it reveals an IBU section
            await self._test_toggle_section_effects(section)

    async def _test_toggle_section_effects(self, toggle_section):
        """Test toggles in a section to see which ones reveal IBU sections."""

        # Get all toggles in this section
        toggles_in_section = await self.page.evaluate(
            """
        (sectionData) => {
            const container = document.elementFromPoint(
                sectionData.position.x + sectionData.position.width/2,
                sectionData.position.y + sectionData.position.height/2
            );
            
            if (!container) return [];
            
            const parent = container.closest('[class*="select"], .feature-group, .options-group') || container;
            const toggles = parent.querySelectorAll('input[type="checkbox"], button[aria-pressed]');
            
            return Array.from(toggles).map(toggle => ({
                type: toggle.tagName.toLowerCase() === 'input' ? 'checkbox' : 'button',
                text: toggle.closest('label')?.textContent || toggle.textContent || 'Unknown',
                checked: toggle.checked || toggle.getAttribute('aria-pressed') === 'true',
                id: toggle.id || `section-toggle-${Math.random()}`
            }));
        }
        """,
            toggle_section,
        )

        # Test a few key toggles to see if they reveal sections
        for toggle_info in toggles_in_section[
            :3
        ]:  # Test first 3 to avoid too much clicking
            if not toggle_info["checked"]:
                print(f"     🧪 Testing toggle: {toggle_info['text'][:30]}")

                # Try to click this toggle and see if it reveals new content
                success = await self._try_click_toggle_by_text(toggle_info["text"])

                if success:
                    await self.page.wait_for_timeout(2000)  # Wait for content

                    # Capture new elements
                    new_elements = await self._capture_page_elements()

                    # See if new sections appeared
                    new_sections = await self._detect_new_sections()

                    if new_sections:
                        toggle_name = toggle_info["text"].strip()
                        ibu_name = self._generate_ibu_name(toggle_name)

                        self.discovered_ibus[f"{ibu_name}"] = {
                            "type": "toggle_revealed_section",
                            "trigger_toggle": toggle_name,
                            "sections": new_sections,
                            "element_count": len(new_sections.get("elements", [])),
                        }

                        print(f"     ✅ {toggle_name} revealed new IBU section!")

    async def _try_click_toggle_by_text(self, toggle_text: str) -> bool:
        """Try to click a toggle based on its text."""
        try:
            # Try multiple strategies to find and click the toggle
            selectors = [
                f'input[type="checkbox"]',
                f"button[aria-pressed]",
                f'[role="checkbox"]',
            ]

            for selector in selectors:
                elements = await self.page.query_selector_all(selector)
                for element in elements:
                    # Check if text matches
                    parent = await element.evaluate_handle(
                        'el => el.closest("label") || el.parentElement'
                    )
                    if parent:
                        parent_text = await parent.text_content()
                        if toggle_text.lower() in parent_text.lower():
                            await element.click()
                            return True

            return False
        except Exception as e:
            print(f"       ❌ Could not click toggle: {e}")
            return False

    async def _detect_new_sections(self):
        """Detect if new sections appeared after clicking a toggle."""

        # This is a simplified version - in practice you'd compare before/after page state
        current_sections = await self.page.evaluate(
            """
        () => {
            const sections = [];
            
            // Look for new form sections or content areas that appeared
            document.querySelectorAll('.form-section, .content-section, [class*="section"]').forEach(section => {
                const rect = section.getBoundingClientRect();
                if (rect.height > 50 && rect.width > 100) {
                    const inputs = section.querySelectorAll('input, select, button');
                    if (inputs.length > 0) {
                        sections.push({
                            element_count: inputs.length,
                            text_sample: section.textContent.substring(0, 50)
                        });
                    }
                }
            });
            
            return sections;
        }
        """
        )

        return {"elements": current_sections} if current_sections else None

    async def _generate_comprehensive_ibu_mapping(self) -> List[Dict[str, str]]:
        """Generate the final IBU mapping in CSV format."""

        ibu_mappings = []

        for ibu_name, ibu_data in self.discovered_ibus.items():
            # Clean up IBU name
            clean_ibu_name = ibu_name.replace(" (when enabled)", "").replace(
                " (static)", ""
            )

            # Add each element as an attribute
            for element in ibu_data.get("elements", []):
                attribute_name = element["label"]

                # Clean up attribute names - be more careful about prefixes
                attribute_lower = attribute_name.lower()

                if element["type"] == "dropdown":
                    # Only add prefix if it doesn't already have one
                    if not any(
                        prefix in attribute_lower
                        for prefix in ["choose", "select", "pick", "set"]
                    ):
                        attribute_name = f"Choose {attribute_name}"

                elif element["type"] == "checkbox":
                    # Only add Enable prefix if it doesn't have one
                    if not any(
                        prefix in attribute_lower
                        for prefix in ["enable", "disable", "use", "include"]
                    ):
                        attribute_name = f"Enable {attribute_name}"

                elif element["type"] in ["text", "number"]:
                    # Only add Enter prefix if needed
                    if not any(
                        prefix in attribute_lower
                        for prefix in ["enter", "specify", "set", "input"]
                    ):
                        # Check if it's already descriptive (has "amount", "number", etc.)
                        if not any(
                            desc in attribute_lower
                            for desc in [
                                "amount",
                                "number",
                                "quantity",
                                "size",
                                "value",
                            ]
                        ):
                            attribute_name = f"Enter {attribute_name}"

                # Final cleanup - remove redundant service names from attributes
                for service_part in self.service_name.split():
                    if (
                        service_part.lower() in attribute_name.lower()
                        and service_part.lower() not in ["aws", "amazon"]
                    ):
                        attribute_name = attribute_name.replace(
                            service_part, ""
                        ).strip()

                ibu_mappings.append(
                    {
                        "service": self.service_name,
                        "ibu": clean_ibu_name,
                        "attribute": attribute_name,
                    }
                )

        return ibu_mappings


async def analyze_with_toggle_awareness(
    service_urls: List[tuple], output_dir: str = "."
):
    """Analyze AWS calculator pages with toggle awareness."""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.set_viewport_size({"width": 1366, "height": 768})

        all_results = {}
        all_ibu_mappings = []

        for i, (service_name, url) in enumerate(service_urls, 1):
            print(f"\n{'='*60}")
            print(f"🎯 Analyzing {i}/{len(service_urls)}: {service_name}")
            print(f"{'='*60}")

            scraper = ToggleAwareIBUScraper(page)
            result = await scraper.analyze_calculator_page(url)

            if "error" not in result:
                all_results[service_name] = result
                all_ibu_mappings.extend(result.get("ibu_mapping", []))

                print(
                    f"✅ {service_name}: Found {len(result.get('discovered_ibus', {}))} IBU sections"
                )
                print(
                    f"   🔘 Toggle-controlled IBUs: {len([k for k in result.get('discovered_ibus', {}) if 'when enabled' in k])}"
                )
                print(
                    f"   📊 Static IBUs: {len([k for k in result.get('discovered_ibus', {}) if 'static' in k])}"
                )
            else:
                print(f"❌ {service_name}: {result['error']}")

        await browser.close()

        # Save results
        with open(f"{output_dir}/toggle_aware_analysis.json", "w") as f:
            json.dump(all_results, f, indent=2)

        with open(f"{output_dir}/toggle_aware_ibu_mapping.csv", "w", newline="") as f:
            if all_ibu_mappings:
                writer = csv.DictWriter(f, fieldnames=["service", "ibu", "attribute"])
                writer.writeheader()
                writer.writerows(all_ibu_mappings)

        print(f"\n🎉 Toggle-aware analysis complete!")
        print(f"📄 Detailed results: toggle_aware_analysis.json")
        print(f"📊 IBU mappings: toggle_aware_ibu_mapping.csv")
        print(f"🔢 Total IBU mappings: {len(all_ibu_mappings)}")


def main():
    parser = argparse.ArgumentParser(
        description="Toggle-Aware AWS Calculator IBU Scraper"
    )
    parser.add_argument(
        "--count", type=int, default=None, help="Number of services to analyze"
    )
    parser.add_argument("--output", default=".", help="Output directory")

    args = parser.parse_args()

    # Focus on services that have toggle-based IBUs
    services = [
        ("AWS DataSync", "https://calculator.aws/#/createCalculator/DataSync"),
        ("Amazon S3", "https://calculator.aws/#/createCalculator/S3"),
        ("AWS Lambda", "https://calculator.aws/#/createCalculator/Lambda"),
        ("Amazon RDS", "https://calculator.aws/#/createCalculator/RDS"),
    ]

    if args.count:
        services = services[: args.count]

    print(
        f"🚀 Starting toggle-aware analysis of {len(services)} AWS calculator pages..."
    )

    asyncio.run(analyze_with_toggle_awareness(services, args.output))


if __name__ == "__main__":
    main()
