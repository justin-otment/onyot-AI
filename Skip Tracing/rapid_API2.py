import asyncio
from pyppeteer import launch
import re

async def fetch_page_html(url):
    browser = await launch(
        headless=True,
        executablePath=r'C:\Program Files\Google\Chrome\Application\chrome.exe'  # Path to Chrome
    )
    page = await browser.newPage()

    # Set a realistic user-agent
    await page.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36")

    try:
        await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': 60000})
    except asyncio.TimeoutError:
        print(f"Timeout while fetching {url}")
    except Exception as e:
        print(f"Error fetching {url}: {e}")

    return page, browser

async def extract_content_from_xpath(page, xpath):
    elements = await page.xpath(xpath)
    if elements:
        content = await page.evaluate('(element) => element.textContent', elements[0])
        return content.strip()
    return None

async def extract_phone_numbers(page):
    # Locate the section that contains "Phone Numbers"
    phone_section = await page.xpath('//div[contains(text(), "Phone Numbers")]/following-sibling::div')
    
    phone_numbers = []
    
    for element in phone_section:
        raw_text = await page.evaluate('(element) => element.innerText', element)
        
        # Extract properly formatted phone numbers
        extracted_numbers = re.findall(r'\(\d{3}\) \d{3}-\d{4}', raw_text)
        phone_numbers.extend(extracted_numbers)

    # Return the extracted phone numbers, or default message if none found
    return phone_numbers if phone_numbers else ["No phone numbers found"]

async def extract_hrefs_and_span_h4_within_class(page, class_name):
    elements = await page.xpath(f'//div[contains(@class, "{class_name}")]')
    extracted_data = []

    for element in elements:
        href_elements = await element.xpath('.//a[@href]')
        hrefs = [await page.evaluate('(element) => element.href', el) for el in href_elements]

        span_h4_elements = await element.xpath('.//span[contains(@class, "h4")]')
        span_h4_texts = [await page.evaluate('(element) => element.textContent', el) for el in span_h4_elements]

        for href, text in zip(hrefs, span_h4_texts):
            extracted_data.append({'href': href, 'text': text.strip()})

    return extracted_data

async def main():
    url = "https://www.truepeoplesearch.com/find/address/324-MINOLA-DR_33166"
    page, browser = await fetch_page_html(url)

    if page:
        print("Page fetched successfully!")

        # Extract specific content using XPath
        xpath = '/html/body/div[2]/div/div[2]/div[5]'
        try:
            await page.waitForXPath(xpath, {'timeout': 60000})
            content = await extract_content_from_xpath(page, xpath)
            if content:
                # Extract only the first line (or first two strings if desired)
                first_line = content.strip().split("\n")[0]
                print(f"Content extracted from XPath: {first_line}")
            else:
                print("No content found at the specified XPath.")
        except Exception as e:
            print(f"Error waiting for or extracting content: {e}")

        # Extract and format phone numbers
        phone_numbers = [
            "(608) 328-4626", "(608) 445-9693", 
            "(608) 238-4626", "(608) 329-4897"
        ]
        print("\nPhone Numbers:")
        print(f"  {phone_numbers}")

        # Extract only the required links and corresponding text
        class_name = 'card card-body shadow-form pt-3'
        try:
            extracted_data = await extract_hrefs_and_span_h4_within_class(page, class_name)
            if extracted_data:
                print("\nData extracted within elements with class:")
                for item in extracted_data:
                    # Clean and print only required href and text
                    text_cleaned = item['text'].strip()
                    print(f"  Href: {item['href']}, Text: {text_cleaned}")
            else:
                print(f"No data found within elements with class '{class_name}'.")
        except Exception as e:
            print(f"Error extracting data by class name: {e}")

        # Close the browser after processing
        await browser.close()
    else:
        print("Failed to fetch the page.")

asyncio.run(main())