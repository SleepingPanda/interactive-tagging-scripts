import time

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


def fetch_page_content(url):
    """Fetch page content using requests and return a BeautifulSoup object."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to retrieve the page: {e}"}


def extract_element_text(soup, tag, class_name, default="Not found", nested_tag=None):
    """Helper function to extract text from a BeautifulSoup object."""
    try:
        element = soup.find(tag, class_=class_name)
        if nested_tag:
            element = element.find(nested_tag)
        return element.get_text(strip=True) if element else default
    except AttributeError:
        return default


def get_manga_data(url, source):
    """Fetch manga data from a given source (viz, kodansha, yenpress)."""
    if source == "viz":
        soup = fetch_page_content(url)
        return get_viz_data(soup)
    elif source == "kodansha":
        return get_kodansha_data(url)
    elif source == "yenpress":
        soup = fetch_page_content(url)
        return get_yenpress_data(soup)
    else:
        return {"error": "Unsupported source"}


def get_viz_data(soup):
    """Extracts manga data from Viz website."""
    return {
        "title": extract_element_text(
            soup,
            "h2",
            "type-lg type-xl--md line-solid " "weight-bold mar-b-md mar-b-lg--md",
            "Title not found",
        ),
        "release_date": extract_element_text(
            soup, "div", "o_release-date", "Publication date not found"
        ).replace("Release", ""),
        "summary": extract_element_text(
            soup,
            "div",
            "g-6--lg pad-x-lg--lg mar-b-lg type-rg "
            "type-md--md line-caption text-spacing",
            "Summary not found",
            "p",
        ),
    }


def get_yenpress_data(soup):
    """Extracts manga data from Yen Press website."""
    return {
        "title": extract_element_text(
            soup,
            "h1",
            "heading title-52 bold white desktop-only fade-el",
            "Title not found",
        ),
        "release_date": extract_element_text(
            soup, "div", "detail-box", "Publication date not found", "span"
        ),
        "summary": extract_element_text(
            soup, "div", "content-heading-txt", "Summary not found", "p"
        ),
    }


def get_kodansha_data(url):
    options = Options()
    options.add_argument("--headless")
    service = Service()
    browser = webdriver.Firefox(service=service, options=options)
    try:
        browser.get(url)
        title = ""
        start_time = time.time()
        timeout = 20
        while time.time() - start_time < timeout:
            try:
                title_element = browser.find_element(
                    By.CSS_SELECTOR, "h1.product-title"
                )
                title = title_element.text
                if title:
                    break
            except NoSuchElementException:
                pass
            time.sleep(0.5)
        release_date = ""
        release_timeout = 20
        start_time = time.time()
        while time.time() - start_time < release_timeout:
            try:
                spans = browser.find_elements(
                    By.CLASS_NAME, "product-desktop-rating-table-title"
                )
                for i in range(len(spans)):
                    if "E-Book Release:" in spans[i].text:
                        if i + 1 < len(spans):
                            release_date = spans[i + 1].text
                        break
                if release_date:
                    break
            except NoSuchElementException:
                pass
            time.sleep(0.5)
        summary = ""
        summary_timeout = 20
        start_time = time.time()
        while time.time() - start_time < summary_timeout:
            try:
                summary_element = browser.find_element(
                    By.CLASS_NAME, "series-desktop-header-info-description"
                )
                summary = summary_element.text
                break
            except NoSuchElementException:
                pass
            time.sleep(0.5)
    except Exception as e:
        return {"error": f"An error occurred: {e}"}
    finally:
        browser.quit()
    return {"title": title, "release_date": release_date, "summary": summary}


viz_url = "https://viz.com/read/manga/jujutsu-kaisen-volume-23/product/7957/digital"
kodansha_url = "https://kodansha.us/product/in-spectre-2/"
yenpress_url = (
    "https://yenpress.com/titles/9781975392826-i-got-a-cheat-skill"
    "-in-another-world-and-became-unrivaled-in-the-real-world-too-vol-5-manga"
)
print("Viz Data:", get_manga_data(viz_url, "viz"))
print("Yen Press Data:", get_manga_data(yenpress_url, "yenpress"))
print("Kodansha Data:", get_manga_data(kodansha_url, "kodansha"))
