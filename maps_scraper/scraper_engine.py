import json
import os
import re
from idlelib.debugobj import AtomicObjectTreeItem
from itertools import product
from pathlib import Path
import pandas as pd
from playwright.sync_api import sync_playwright
from time import sleep
from bs4 import BeautifulSoup
import config
COOKIE_FILE = "cookies.json"
adv_links = []


def save_cookies(context):
    """Save cookies to a file."""
    cookies = context.cookies()
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f)
    print("Cookies saved!")


def load_cookies(context):
    """Load cookies from a file if it exists."""
    file_path = Path(COOKIE_FILE)
    if file_path.exists():
        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)
            context.add_cookies(cookies)
        print("Cookies loaded!")
    else:
        print("No cookies found. Starting fresh session.")


def slow_scroll(page, step=300, delay=1):
    """
    Scrolls the page slowly in small increments with a delay.

    Parameters:
    - page: Playwright page object
    - step: Number of pixels to scroll per step
    - delay: Time delay between scrolls (in seconds)
    """
    total_height = page.evaluate("document.body.scrollHeight")
    current_position = 0

    while current_position < total_height:
        # Scroll by step size
        page.evaluate(f"window.scrollBy(0, {step})")
        current_position += step
        print(f"Scrolled to: {current_position}px")

        # Wait for content to load
        sleep(delay)

        # Recalculate height in case content has loaded and expanded the page
        total_height = page.evaluate("document.body.scrollHeight")

    print("Reached the bottom of the page!")


def get_all_links(html_content):
    links_list = []
    # Parse the HTML using Beautiful Soup
    soup = BeautifulSoup(html_content, 'html.parser')
    # print(soup.prettify())
    containers = soup.find_all('div', class_="css-5wh65g")
    for container in containers:
        link = container.find('a').get('href')
        links_list.append(link)
    return links_list


def browser_context(keyword=config.KEYWORD, city=config.JAKARTA):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        # Create a new browser context
        context = browser.new_context()

        # Create a new page and navigate to the site
        page = context.new_page()
        page.set_default_navigation_timeout(60000)  # Set navigation timeout
        page.goto(f"https://www.google.co.id/maps/search/{keyword}/{city}")
        # RESULT CONTAINER
        sleep(2)
        result_container = page.locator("//div[@role='feed']")

        # Scroll the container incrementally
        previous_height = 0
        n = 0
        while True:
            n += 1
            print('scroll :', n)

            # Get the current scroll height
            current_height = result_container.evaluate("element => element.scrollHeight")

            # Scroll down
            result_container.evaluate("element => element.scrollBy(0, 1600)")
            sleep(1)
            # Wait for new content to load
            page.wait_for_timeout(10000)
            # Check if height has changed
            if current_height == previous_height:
                print("No more results to load.")
                break
            else:
                previous_height = current_height

        result_container = page.locator("//div[@role='feed']")
        # scraping process
        final_data = []


        advertisements = result_container.locator("//a[@class='hfpxzc']")
        advertisement_containers = result_container.inner_html()
        soup = BeautifulSoup(advertisement_containers, 'html.parser')
        num_containers = len(soup.find_all('a', class_='hfpxzc'))
        print('container number: ', num_containers)
        for i in range(num_containers):
            container = advertisements.nth(i)
            title = container.get_attribute('aria-label')
            sleep(1)
            container.click()
            sleep(1)
            container.click()
            try:
                result_container.evaluate("element => element.scrollBy(0, 600)")
            except Exception as e:
                print("error:  ", e)
            page.wait_for_selector(f"//div[@aria-label='{title}']", timeout=60000)
            popup_window = page.locator(f"//div[@aria-label='{title}']").inner_html()

            soup = BeautifulSoup(popup_window, 'html.parser')
            print(soup.prettify())
            all_info = soup.find_all('div', class_="rogA2c")
            raw_info = []

            try:
                link = soup.find('a', class_="CsEnBe")['href']
                raw_info.append(link)
            except Exception as e:
                link = ''
                print('error: ', e )

            for info in all_info:
                raw_info.append(info.text.replace("-", "").replace("(021) ", "021").replace("https://wa.me/62", "0").replace("http://wa.me/62", "0"))


            # Regex pattern to match addresses
            address_pattern = r'(?:[A-Za-z0-9\s]+(?:,|No:?\s?[A-Za-z0-9]+)?\s?)?(Jl\.|Jalan)\s[A-Za-z0-9\s.,/-]+(?:,\s?[A-Za-z\s.,/-]+)+'
            phone_pattern = r'(?:\(?0\d{2,3}\)?[-\s]?)?\d{3,4}[-\s]?\d{3,4}'

            # Extract info from the raw info
            try:
                address = [item for item in raw_info if re.search(address_pattern, item)][0]
            except IndexError:
                address = ""

            try:
                phone_number = [item for item in raw_info if re.search(phone_pattern, item)][0]
            except IndexError:
                phone_number = ""

            data = {
                'title': title,
                'phone number': phone_number,
                'link': link,
                'address': address
            }
            print("title: ", title)
            final_data.append(data)
            df = pd.DataFrame(final_data)
            # Export the DataFrame to a CSV file
            df.to_csv(f"bandung_{keyword.replace("+", "_")}.csv", index=False)

            print("CSV file has been created.")





def get_all_fields(html_content, link):
    data = {}
    soup = BeautifulSoup(html_content, 'html.parser')
    try:
        title = soup.find('h1', {'data-testid': 'lblPDPDetailProductName'}).text
    except AttributeError:
        title = ''
    try:
        rating = soup.find('span', {'data-testid': 'lblPDPDetailProductRatingNumber'}).text
    except AttributeError:
        rating = ''

    try:
        rating_counter = soup.find('span', {'data-testid': 'lblPDPDetailProductRatingCounter'}).text.replace("(",
                                                                                                             "").replace(
            ")", "").replace('rating', '').strip()
    except AttributeError:
        rating_counter = ''
    price = soup.find('div', {'data-testid': 'lblPDPDetailProductPrice'}).text
    try:
        sold = soup.find('p', {'data-testid': 'lblPDPDetailProductSoldCounter'}).text.replace("Terjual", "").replace(
            'rb+', "000").replace(" ", "").replace("+", "").replace("barangberhasilterjual", '')
    except AttributeError:
        sold = ''
    description = soup.find('div', {'data-testid': 'lblPDPDescriptionProduk'}).text.strip().replace("\n", " ")
    try:
        shop_name = soup.find('a', {'data-testid': 'llbPDPFooterShopName'}).text
    except AttributeError:
        shop_name = ''
    try:
        store_location = soup.find('h2', class_='css-1pd07ge-unf-heading e1qvo2ff2').text.replace('Dikirim dari',
                                                                                                  '').strip()
    except AttributeError:
        store_location = ''
    data['title'] = title
    data['rating'] = rating
    data['price'] = price
    data['rating counter'] = rating_counter
    data['sold'] = sold
    data['description'] = description
    data['shop name'] = shop_name
    data['url'] = link
    data['store location'] = store_location

    print('title: ', title)
    print('shop name: ', shop_name)
    print('rating: ', rating)
    print('rating counter: ', rating_counter)
    print('price: ', price)
    print('sold: ', sold)
    print('description: ', description)
    print('send from: ', store_location)
    return data

