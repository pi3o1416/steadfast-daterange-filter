"""
Main
"""
import time
import random
import datetime
import logging
import os
import pickle
import requests
from bs4 import BeautifulSoup
import pandas as pd

from steadfast.dt import Status
from steadfast.exceptions import ValidationError


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.DEBUG)

DATE_FORMAT = "%Y-%m-%d"
CACHE_FILE_NAME = "cache.pkl"

URLS = {
    Status.ALL: "https://steadfast.com.bd/user/consignment/status/all",
    Status.APPROVAL_PENDING: "https://steadfast.com.bd/user/consignment/status/approval",
    Status.CANCELLED: "https://steadfast.com.bd/user/consignment/status/cancelled",
    Status.DELEVERED: "https://steadfast.com.bd/user/consignment/status/delivered",
    Status.IN_REVIEW: "https://steadfast.com.bd/user/consignment/status/in-review",
    Status.PARTLY_DELIVERED: "https://steadfast.com.bd/user/consignment/status/partial",
    Status.PENDING: "https://steadfast.com.bd/user/consignment/status/pending",
    Status.PICK_N_DROP: "https://steadfast.com.bd/user/consignment/status/pick-n-drop",
}


def main():
    """
    Main Function
    """
    cookie = input("Enter Cookie: ")
    start_date = input("Start Date: ")
    end_date = input("End Date: ")
    status = input("Status: ")

    validated_data = validate_request(cookie, start_date, end_date, status)
    scraped_data = scrap_data(validated_data=validated_data)
    filtered_data = filter_scraped_data(scraped_data, validated_data)
    df = pd.DataFrame(filtered_data)
    df.to_excel(f"reports/{validated_data['start_date'].strftime(DATE_FORMAT)}_{validated_data['end_date'].strftime(DATE_FORMAT)}_{validated_data['status']}.xlsx", index=False, engine="openpyxl")


def filter_scraped_data(scraped_data, validated_data):
    filtered_data = []
    for data in scraped_data:
        if data["Date"] <= validated_data["start_date"] and data["Date"] >= validated_data["end_date"]:
            filtered_data.append(data)
    return filtered_data



def validate_request(cookie, start_date, end_date, status):
    """
    Validate Request Data
    """
    cache = load_cache()
    validated_data = {}
    validated_data["cookie"] = validate_cookie(cookie, cache)
    validated_data["start_date"] = validate_start_date(start_date)
    validated_data["end_date"] = validate_end_date(end_date, validated_data["start_date"])
    validated_data["status"] = validate_status(status)
    update_cache(validated_data)

    return validated_data


def load_cache():
    """Load previous request data"""
    if not os.path.exists(CACHE_FILE_NAME):
        return None

    with open("cache.pkl", "rb") as file:
        cache = pickle.load(file)
    return cache


def update_cache(validated_data):
    """Update previous request data"""
    with open("cache.pkl", "wb") as file:
        pickle.dump(validated_data, file)


def validate_cookie(cookie, cache=None):
    """Validate cookie"""
    if cookie:
        return cookie
    LOGGER.warning("No Cookie given in stdio, Retrieving cookie from cache")
    if cache and cache["cookie"] is not None:
        return cache["cookie"]

    LOGGER.error("No cookie found in stdio/cache")
    raise ValidationError("No cookie found in stdio/cache")


def validate_start_date(start_date: str | None):
    """Validate start date"""
    if not start_date:
        LOGGER.warning("Start Date autometically set to current time as nothing provided")
        return datetime.datetime.now()

    try:
        return datetime.datetime.strptime(start_date, DATE_FORMAT)
    except ValueError as exc:
        LOGGER.error(f"Invalid date format. Use this format: {DATE_FORMAT}")
        raise ValidationError("Invalid date format.") from exc


def validate_end_date(end_date, start_date):
    """Validate end date"""
    if not end_date:
        LOGGER.warning("End date autometically set to 7 days after start_date as nothing provided")
        return start_date - datetime.timedelta(days=7)

    try:
        return datetime.datetime.strptime(end_date, DATE_FORMAT)
    except ValueError as exc:
        LOGGER.error(f"Invalid date format. Use this format: {DATE_FORMAT}")
        raise ValidationError("Invalid date format.") from exc


def validate_status(status):
    """Validate status"""
    if not status:
        return Status.ALL

    try:
        return Status(status)
    except ValueError as exc:
        LOGGER.warning("Invalid status, just copy the header from table and use as status")
        raise ValidationError("Invalid status value") from exc


def scrap_data(validated_data, page=1):
    """
    Recursive function to extract data from steadfast
    """
    LOGGER.info(f"Extracting from page {page}")
    url = URLS[validated_data["status"]]
    params = {"page": page}

    response = requests.get(
        url=url,
        params=params,
        headers={
            "Cookie": validated_data["cookie"]
        },
        timeout= 10
    )
    page_data = parsed_data_from_html(response.text)

    if len(page_data) == 0:
        return []

    if page_data[-1]['Date'] < validated_data["end_date"]:
        return page_data
    time.sleep(0.2 + round(random.uniform(0.1, 0.2), 2))

    return page_data + scrap_data(validated_data, page+1)


def parsed_data_from_html(html_content):
    """Extract table data from html"""
    soup = BeautifulSoup(html_content, "html.parser")
    table_rows = soup.select('.tbody .tbody-row')
    parsed_data = []
    for row in table_rows:
        raw_datetime = parse_datetime(row)
        steadfast_id = parse_steadfast_id(row)
        customer_name = parse_customer_name(row)
        payment = parse_payment(row)
        charge = parse_charge(row)
        status = parse_status(row)
        detail = parse_detail(row)

        row_data = {
            'Date': formatted_datetime(raw_datetime),
            'Id': steadfast_id,
            'Customer Name': customer_name,
            'Payment': payment,
            'Charge': charge,
            'Status': status[0] if isinstance(status, tuple) else status,
            'Details': detail
        }
        parsed_data.append(row_data)
    return parsed_data


def parse_datetime(row):
    """parse datetime"""
    return row.select_one('.cell_1').get_text(strip=True).replace('Date', '')


def parse_steadfast_id(row):
    """parse steadfast id"""
    try:
        return row.select_one('.cell_2 a').get_text(strip=True)
    except AttributeError:
        return ""


def parse_customer_name(row):
    """parse customer name"""
    try:
        return row.select_one('.cell_3').get_text(strip=True).replace('Name', '')
    except AttributeError:
        return ""


def parse_payment(row):
    """parse payment"""
    try:
        return row.select_one('.cell_4').get_text(strip=True).replace('Payment', '')
    except AttributeError:
        return ""


def parse_charge(row):
    """parse charge"""
    try:
        return row.select_one('.cell_5').get_text(strip=True).replace('Charge', '')
    except AttributeError:
        return ""


def parse_status(row):
    """parse status"""
    try:
        return row.select_one('.cell_6 label').get_text(strip=True)
    except AttributeError:
        return ""


def parse_detail(row):
    """parse detail"""
    try:
        return row.select_one('.cell_7 a').get('href', '')
    except AttributeError:
        return ""


def formatted_datetime(raw_datetime):
    """Format raw datetime"""
    return datetime.datetime.strptime(raw_datetime, "%B %d, %Y %I:%M %p")


if __name__ == "__main__":
    main()
