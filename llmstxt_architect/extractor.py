"""
Content extraction utilities for web pages.
"""

import re

from bs4 import BeautifulSoup
from markdownify import markdownify


def bs4_extractor(html: str) -> str:
    """
    Extract content from HTML using BeautifulSoup.

    Args:
        html: The HTML content to extract from

    Returns:
        Extracted text content
    """
    soup = BeautifulSoup(html, "lxml")

    # Target the main article content for LangGraph documentation
    main_content = soup.find("article", class_="md-content__inner")

    # Get urls from application buttons, together with their title.
    for button in soup.find_all("a", class_="Button_button__8o_Gx SkjemadetaljerButton"):
        url = button.get("href")
        title = button.get_text(strip=True)
        if url and title:
            # Append the URL and title to the content
            main_content.append(f"\n\n[SOKNADSLINK: {title}]({url})\n\n")

    # If found, use that, otherwise fall back to the whole document
    content = main_content.get_text() if main_content else soup.text

    # Clean up whitespace
    content = re.sub(r"\n\n+", "\n\n", content).strip()

    return content


def default_extractor(html: str) -> str:
    """
    Extract content from HTML and convert to markdown.

    Falls back to plain text extraction if markdownify hits a recursion
    limit on deeply nested HTML (common on government/CMS sites).

    Args:
        html: The HTML content to extract from

    Returns:
        Markdown converted content
    """
    try:
        result = markdownify(html)
        return str(result)
    except RecursionError:
        return bs4_extractor(html)
