#!/usr/bin/env python
"""
Extract all <a> elements that share the same parent as links to URLs in the summarized_urls.json file.

Usage:
    python extract_siblings.py <page_url> [json_file]

Example:
    python extract_siblings.py https://www.nav.no/soknader test/summaries/summarized_urls.json
"""

import sys
import json
import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin


async def fetch_url(url: str) -> str:
    """Fetch HTML content from a URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        sys.exit(1)


def load_json_urls(json_file: str) -> set:
    """Load URLs from the JSON file."""
    try:
        with open(json_file, "r") as f:
            data = json.load(f)
            # Extract just the URLs (keys from the JSON)
            return set(data.keys())
    except Exception as e:
        print(f"Error loading JSON file {json_file}: {str(e)}")
        sys.exit(1)


def extract_sibling_links(html: str, page_url: str, json_urls: set) -> list[dict]:
    """
    Find all <a> elements that share a parent container with links to URLs in json_urls.
    Walks up the DOM tree to find the best parent that contains both navigation links and action buttons.

    Args:
        html: HTML content to parse
        page_url: The page URL (for resolving relative links)
        json_urls: Set of URLs from the JSON file

    Returns:
        List of dictionaries with parent info and all link children
    """
    soup = BeautifulSoup(html, "lxml")
    results = []
    processed_sections = set()

    # Find all <a> tags
    all_links = soup.find_all("a")

    for link in all_links:
        href = link.get("href", "")
        if not href:
            continue

        # Resolve relative URLs
        absolute_url = urljoin(page_url, href)
        
        # Check if this link points to a URL in the JSON
        if absolute_url in json_urls or href in json_urls:
            # Walk up the tree to find a good parent container
            # We want to find a parent that likely contains both this link and related action buttons
            current = link.parent
            best_parent = None
            max_levels = 10
            
            # Walk up to find a parent with sufficient links or content
            for level in range(max_levels):
                if current is None:
                    break
                
                # Get all <a> tags in this parent
                all_a_tags = current.find_all("a")
                
                # If this parent has multiple links (3+), it's probably a good container
                # This ensures we get the button, the standalone link, and possibly the copyLink
                if len(all_a_tags) >= 3:
                    best_parent = current
                    break
                
                # Also check if we've reached a major container element
                classes = current.get("class", [])
                class_str = " ".join(classes) if classes else ""
                
                # Look for content container patterns
                if any(pattern in class_str for pattern in [
                    "expansioncard__content-inner",
                    "OversiktListPanel",
                    "navds-expansioncard__content"
                ]):
                    # This looks like a content container
                    if len(all_a_tags) >= 2:  # At least link + button or more
                        best_parent = current
                        break
                
                current = current.parent
            
            # If we didn't find a multi-link parent, use the direct parent
            if best_parent is None:
                best_parent = link.parent
            
            # Use id of parent to avoid processing the same parent multiple times
            parent_id = id(best_parent)
            
            if parent_id not in processed_sections:
                processed_sections.add(parent_id)
                
                # Get ALL <a> elements in this parent (recursively), excluding copyLink anchors
                all_sibling_links = []
                for sibling in best_parent.find_all("a"):
                    # Skip the copyLink anchors
                    if "copyLink_copyLink" in sibling.get("class", []):
                        continue
                    
                    sibling_href = sibling.get("href", "")
                    sibling_text = sibling.get_text(strip=True)
                    if sibling_href:
                        sibling_absolute = urljoin(page_url, sibling_href)
                        all_sibling_links.append({
                            "text": sibling_text,
                            "href": sibling_href,
                            "absolute_url": sibling_absolute,
                            "is_json_url": sibling_absolute in json_urls or sibling_href in json_urls,
                            "classes": sibling.get("class", [])
                        })

                if all_sibling_links:
                    results.append({
                        "parent_tag": best_parent.name,
                        "parent_classes": best_parent.get("class", []),
                        "matched_link": {
                            "text": link.get_text(strip=True),
                            "href": href,
                            "absolute_url": absolute_url
                        },
                        "all_links": all_sibling_links
                    })

    return results


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python extract_siblings.py <page_url> [json_file]")
        print("Example: python extract_siblings.py https://www.nav.no/soknader test/summaries/summarized_urls.json")
        sys.exit(1)

    page_url = sys.argv[1]
    json_file = sys.argv[2] if len(sys.argv) > 2 else "test/summaries/summarized_urls.json"

    print(f"Loading URLs from {json_file}...")
    json_urls = load_json_urls(json_file)
    print(f"Loaded {len(json_urls)} URLs from JSON file\n")

    print(f"Fetching {page_url}...")
    html = await fetch_url(page_url)

    print("Extracting sibling links...\n")
    results = extract_sibling_links(html, page_url, json_urls)

    if results:
        print(f"Found {len(results)} parent element(s) containing links to JSON URLs:\n")
        
        for i, result in enumerate(results, 1):
            print(f"{'='*80}")
            print(f"Parent #{i}: <{result['parent_tag']}> with classes: {result['parent_classes']}")
            print(f"Matched link: [{result['matched_link']['text']}]({result['matched_link']['absolute_url']})")
            print(f"\nAll <a> elements in this parent ({len(result['all_links'])} total):")
            print(f"{'-'*80}")
            
            for j, link in enumerate(result['all_links'], 1):
                is_json = "✓ (in JSON)" if link['is_json_url'] else ""
                print(f"  {j}. [{link['text']}]")
                print(f"     href: {link['href']}")
                print(f"     absolute: {link['absolute_url']} {is_json}")
                print(f"     classes: {link['classes']}")
            print()
    else:
        print("No parent elements found containing links to JSON URLs.")


if __name__ == "__main__":
    asyncio.run(main())
