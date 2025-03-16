import asyncio
from playwright.async_api import async_playwright
from flask import Flask, request, jsonify
import re
from waitress import serve

app = Flask(__name__)

def run_async_scrape(url):
    """Run the async scraper in a synchronous function."""
    return asyncio.run(scrape_website(url))

async def scrape_website(url):
    """Scrapes structured property data asynchronously using Playwright."""
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True, executable_path="/usr/bin/firefox")
        page = await browser.new_page()

        try:
            await page.goto(url, timeout=15000)  # Load homepage
            
            # Step 1: Handle Rent Special Pop-Up
            rent_special = "N/A"
            popup = await page.query_selector('div[class*="popup"], div[class*="modal"], div[class*="overlay"]')
            if popup:
                rent_special_text = await popup.inner_text()
                if rent_special_text.strip():
                    rent_special = rent_special_text.strip()
                
                # Close pop-up
                close_button = await popup.query_selector('button[class*="close"], span[class*="close"], div[class*="close"]')
                if close_button:
                    await close_button.click()
                    await page.wait_for_timeout(2000)

            # Step 2: Scrape Property Name & Phone Number
            title = await page.title()

            phone_number = "N/A"
            page_content = await page.content()
            phone_match = re.search(r'\(\d{3}\) \d{3}-\d{4}', page_content)
            if phone_match:
                phone_number = phone_match.group(0)

            # Step 3: Scrape Address (Prioritize Footer)
            address = "N/A"
            footer_address = await page.query_selector("span.footer__text-line, div.footer-address, address")
            if footer_address:
                address = await footer_address.inner_text()
            else:
                all_text = await page.inner_text("body")
                address_match = re.search(r'\d{1,5} [\w\s]+, [\w\s]+, [A-Z]{2} \d{5}', all_text)
                if address_match:
                    address = address_match.group(0)
            address = address.strip() if address else "N/A"

            # Step 4: Scrape Images
            images = []
            image_elements = await page.query_selector_all("img")
            for img in image_elements:
                src = await img.get_attribute("src")
                if src and "logo" not in src.lower():
                    images.append(src)

            # Step 5: Scrape Amenities
            amenities = []
            amenity_elements = await page.query_selector_all("li")
            for amenity in amenity_elements:
                text = await amenity.inner_text()
                if text.strip():
                    amenities.append(text.strip())

            # Step 6: Scrape Property Overview
            property_overview = "N/A"
            paragraphs = await page.query_selector_all("p")
            full_text = [await para.inner_text() for para in paragraphs if (await para.inner_text()).strip()]
            if full_text:
                property_overview = " ".join(full_text[:5])  # Capture first 5 meaningful paragraphs

            # Step 7: Scrape "About Us" and "Neighborhood" Pages
            about_text = "N/A"
            neighborhood_text = "N/A"
            internal_links = await page.query_selector_all("a[href]")
            
            about_page = None
            neighborhood_page = None

            for link in internal_links:
                href = await link.get_attribute("href")
                if href:
                    if "about" in href.lower():
                        about_page = href
                    elif "neighborhood" in href.lower() or "location" in href.lower():
                        neighborhood_page = href

            if about_page:
                try:
                    await page.goto(about_page, timeout=10000)
                    about_paragraphs = await page.query_selector_all("p")
                    about_text = " ".join([await p.inner_text() for p in about_paragraphs if (await p.inner_text()).strip()][:5])
                except:
                    pass  

            if neighborhood_page:
                try:
                    await page.goto(neighborhood_page, timeout=10000)
                    neighborhood_paragraphs = await page.query_selector_all("p")
                    neighborhood_text = " ".join([await p.inner_text() for p in neighborhood_paragraphs if (await p.inner_text()).strip()][:5])
                except:
                    pass  

            # Step 8: Click "Floor Plans" Button to Navigate to Floor Plan Page
            floorplans_button = await page.query_selector("a[href*='/floor-plans/']")
            if floorplans_button:
                await floorplans_button.click()
                await page.wait_for_timeout(3000)  # Wait for floor plans page to load

            # Step 9: Get Floor Plan Category Links (Studio, One Bed, Two Bed)
            unit_links = await page.query_selector_all("div.quick_search a")
            unit_urls = [await link.get_attribute("href") for link in unit_links]

            all_rent_data = []

            for unit_url in unit_urls:
                await page.goto(unit_url, timeout=15000)
                await page.wait_for_timeout(3000)

                # Step 10: Scrape Rent Details for Each Available Unit
                unit_elements = await page.query_selector_all("div.fp_box")
                for unit in unit_elements:
                    unit_name = await unit.query_selector("h3.fp_num")
                    unit_title = await unit.query_selector("a.fp_title")
                    unit_details = await unit.query_selector("p")

                    unit_name = await unit_name.inner_text() if unit_name else "N/A"
                    unit_title = await unit_title.inner_text() if unit_title else "N/A"
                    unit_details_text = await unit_details.inner_text() if unit_details else "N/A"

                    # Extract Rent Price, Square Footage, Availability
                    rent_match = re.search(r"\$\d{1,4},\d{3}", unit_details_text)
                    size_match = re.search(r"\d{3,4} SF", unit_details_text)
                    availability_match = re.search(r"Available \d{2}/\d{2}/\d{4}", unit_details_text)

                    rent_price = rent_match.group(0) if rent_match else "N/A"
                    square_footage = size_match.group(0) if size_match else "N/A"
                    availability = availability_match.group(0) if availability_match else "N/A"

                    # Extract Floor Plan Image
                    floor_plan_image = "N/A"
                    image_tag = await unit.query_selector("a.fp_img img")
                    if image_tag:
                        floor_plan_image = await image_tag.get_attribute("src")

                    all_rent_data.append({
                        "unit_name": unit_name,
                        "unit_title": unit_title,
                        "square_footage": square_footage,
                        "rent_price": rent_price,
                        "availability": availability,
                        "floor_plan_image": floor_plan_image
                    })

            await browser.close()

            return {
                "property_name": title,
                "address": address,
                "phone_number": phone_number,
                "rent_specials": rent_special,
                "images": images,
                "amenities": amenities,
                "property_overview": property_overview,
                "about_us": about_text,
                "neighborhood": neighborhood_text,
                "units": all_rent_data
            }
        
        except Exception as e:
            error_message = str(e)
            await browser.close()
            return {"error": error_message}

@app.route("/scrape", methods=["POST"])
def scrape():
    """Handles API requests to scrape a given property website URL."""
    data = request.json
    if not data or "url" not in data:
        return jsonify({"error": "No URL provided"}), 400

    url = data["url"]
    result = run_async_scrape(url)
    return jsonify(result)

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5050)
