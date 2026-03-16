"""Playwright tool for scraping JS-heavy sites."""

import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

def scrape_with_playwright(url: str) -> str:
    """Use this tool as a fallback when Meta Ad Library API or Firecrawl fail.
    Scrapes a given URL using Playwright. Ideal for JS-heavy sites, auth flows,
    or dynamic content (e.g., BigSpy, Google Ads Transparency).
    
    Args:
        url: The URL to scrape.
        
    Returns:
        The extracted inner text of the page.
    """
    logger.info(f"Scraping with Playwright: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=15000)
            
            # Keep it simple: grab body text. For a more robust solution, 
            # we could extract specific elements or handle auth states.
            content = page.evaluate("document.body.innerText")
            browser.close()
            
            # Cap return length so we don't blow up the context window
            return content[:15000]
    except Exception as e:
        logger.error(f"Playwright error on {url}: {e}")
        return f"Error scraping {url} with Playwright: {str(e)}"
