import asyncio
from pyppeteer import launch

async def fetch_page_html(url):
    browser = await launch(
        headless=True,
        executablePath=r'C:\Program Files\Google\Chrome\Application\chrome.exe'  # Path to Chrome
    )
    page = await browser.newPage()

    # Set a realistic user-agent
    await page.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36")

    try:
        # Navigate to the page with a timeout to avoid indefinite waiting
        await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': 30000})  # Timeout set to 30 seconds
    except asyncio.TimeoutError:
        print(f"Timeout while fetching {url}")
    except Exception as e:
        print(f"Error fetching {url}: {e}")

    return page, browser

async def extract_content_from_xpath(page, xpath):
    # Use the XPath to find the content
    elements = await page.xpath(xpath)
    if elements:
        # Extract text content from the element using page.evaluate
        content = await page.evaluate('(element) => element.textContent', elements[0])
        return content.strip()
    return None

async def modify_iframe_padding(page, iframe_xpath, padding_value):
    # Use XPath to find the iframe
    iframe_elements = await page.xpath(iframe_xpath)
    if iframe_elements:
        iframe = iframe_elements[0]
        # Evaluate a script to modify the iframe padding
        await page.evaluate('(iframe, padding) => { iframe.style.padding = padding; }', iframe, padding_value)
        print(f"Iframe padding modified to {padding_value}")
    else:
        print("No iframe found at the specified XPath.")

async def main():
    url = "https://www.truepeoplesearch.com/find/address/w5861-clar-ken-rd_monroe-wi-53566"
    page, browser = await fetch_page_html(url)
    
    if page:
        print("Page fetched successfully!")

        # XPath you provided
        xpath = '/html/body/div[2]/div/div[2]/div[5]'

        # Extract content using XPath
        content = await extract_content_from_xpath(page, xpath)

        if content:
            print(f"Content extracted from XPath: {content}")
        else:
            print("No content found at the specified XPath.")

        # Modify iframe padding if needed
        iframe_xpath = '/html/body/iframe'  # Replace with the actual XPath to the iframe
        await modify_iframe_padding(page, iframe_xpath, '10px')
    else:
        print("Failed to fetch the page.")

    await browser.close()

asyncio.run(main())
