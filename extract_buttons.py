#!/usr/bin/env python
"""
Standalone script to extract button URLs from a web page.

Usage:
    python extract_buttons.py <URL>

Example:
    python extract_buttons.py https://www.nav.no/soknader
"""

import sys
import asyncio
import httpx
from bs4 import BeautifulSoup


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


def extract_buttons(html: str) -> list[dict]:
    """
    Extract buttons that share a parent element with a link.
    Finds parent elements containing both a URL link and a button with class 'Button_button__8o_Gx SkjemadetaljerButton_*'.

    Args:
        html: HTML content to parse

    Returns:
        List of dictionaries with 'title', 'button_url', and 'page_url' keys
    """
    soup = BeautifulSoup(html, "lxml")
    buttons_with_context = []

    # Find all <a> tags with role="button"
    button_links = soup.find_all("a", {"role": "button"})

    for button in button_links:
        # Check if it has both Button_button__8o_Gx and SkjemadetaljerButton classes
        classes = button.get("class", [])
        has_button_class = any("Button_button__8o_Gx" in cls for cls in classes)
        has_Skjemadetaljer_class = any("SkjemadetaljerButton" in cls for cls in classes)

        if has_button_class and has_Skjemadetaljer_class:
            button_url = button.get("href")
            # Get the text content from the span or button itself
            span = button.find("span", class_="navds-label")
            button_title = span.get_text(strip=True) if span else button.get_text(strip=True)

            if button_url and button_title:
                # Find the parent element and look for a sibling or nearby link
                parent = button.parent
                page_url = None
                
                # Search up the tree to find a parent that might contain a link
                current = button
                while current and current.parent:
                    current = current.parent
                    # Look for any <a> tags in this parent that are NOT the button itself
                    links = current.find_all("a", recursive=False)
                    for link in links:
                        if link != button and not link.get("role") == "button":
                            potential_url = link.get("href")
                            if potential_url:
                                page_url = potential_url
                                break
                    if page_url:
                        break

                buttons_with_context.append({
                    "title": button_title,
                    "button_url": button_url,
                    "page_url": page_url
                })

    return buttons_with_context


async def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python extract_buttons.py <URL>")
        print("Example: python extract_buttons.py https://www.nav.no/soknader")
        sys.exit(1)

    url = sys.argv[1]

    print(f"Fetching {url}...")
    html = await fetch_url(url)

    print("Extracting buttons...\n")
    buttons = extract_buttons(html)

    if buttons:
        print(f"Found {len(buttons)} button(s):\n")
        for i, button in enumerate(buttons, 1):
            print(f"{i}. Title: {button['title']}")
            print(f"   Button URL: {button['button_url']}")
            if button['page_url']:
                print(f"   Page URL:   {button['page_url']}")
            print()
    else:
        print("No buttons found.")


if __name__ == "__main__":
    asyncio.run(main())
