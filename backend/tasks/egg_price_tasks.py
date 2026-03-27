
"""
Scheduled tasks for fetching egg price data from external websites.
These tasks should be run daily to update egg price information.
"""
import logging
from datetime import datetime
from typing import Dict, Optional
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from database import SessionLocal
from models.egg_price import EggPrice as EggPriceModel

logger = logging.getLogger(__name__)

def fetch_egg_price_from_kisandeals() -> Optional[Dict[str, str]]:
    """
    Fetch egg price data from kisandeals.com website.

    Returns:
        Dict containing egg price information or None if fetch fails
    """
    url = "https://www.kisandeals.com/egg-rate/TAMIL-NADU/NAMAKKAL"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Using response.text (decoded string) instead of response.content (bytes)
        # allows 'requests' to handle character encoding detection automatically.
        soup = BeautifulSoup(response.text, "html.parser")

        # Find the market summary table
        market_summary_table = soup.find("div", id="market-summary-tables")
        table = None
        
        if market_summary_table:
            table = market_summary_table.find("table")
            
        # Fallback: If the specific div is missing, search for any table containing the price data
        if not table:
            for t in soup.find_all("table"):
                if "Single Egg Rate" in t.get_text():
                    table = t
                    break
        
        if not table:
            logger.error("Could not find market-summary-tables or any relevant price table")
            return None

        rows = table.find_all("tr")
        price_data = {}

        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                price_data[label] = value

        return price_data

    except requests.RequestException as e:
        logger.error(f"Error fetching egg price from kisandeals: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing egg price data: {e}")
        return None


def update_daily_egg_price():
    """
    Fetch latest egg price and update database.
    This should be called daily (e.g., via cron job or scheduled task).

    Returns:
        Dict containing the fetched price data or None if failed
    """
    price_data = fetch_egg_price_from_kisandeals()
    if not price_data:
        logger.warning("Failed to fetch egg price data")
        return None

    db = SessionLocal()
    try:
        today = datetime.now().date()

        # Check if there's already a price for today
        existing_price = db.query(EggPriceModel).filter(
            EggPriceModel.price_date == today
        ).first()

        if existing_price:
            # Update existing record
            existing_price.single_egg_rate = price_data.get("Single Egg Rate")
            existing_price.dozen_eggs_rate = price_data.get("Dozen Eggs Rate")
            existing_price.hundred_eggs_rate = price_data.get("100 Eggs Rate")
            existing_price.average_market_price = price_data.get("Average Market Price")
            existing_price.best_market_price = price_data.get("Best Market Price")
            existing_price.lowest_market_price = price_data.get("Lowest Market Price")
            existing_price.best_price_market = price_data.get("Best Price Market")
            existing_price.lowest_price_market = price_data.get("Lowest Price Market")
            existing_price.updated_at = datetime.now()

            logger.info(f"Updated egg price for {today}")
        else:
            # Create new record
            new_price = EggPriceModel(
                price_date=today,
                single_egg_rate=price_data.get("Single Egg Rate"),
                dozen_eggs_rate=price_data.get("Dozen Eggs Rate"),
                hundred_eggs_rate=price_data.get("100 Eggs Rate"),
                average_market_price=price_data.get("Average Market Price"),
                best_market_price=price_data.get("Best Market Price"),
                lowest_market_price=price_data.get("Lowest Market Price"),
                best_price_market=price_data.get("Best Price Market"),
                lowest_price_market=price_data.get("Lowest Price Market"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(new_price)
            logger.info(f"Created new egg price record for {today}")

        db.commit()
        return price_data

    except Exception as e:
        logger.error(f"Error updating egg price in database: {e}")
        db.rollback()
        return None
    finally:
        db.close()


if __name__ == "__main__":
    # Run the task
    print(f"[{datetime.now()}] Starting egg price update task")
    result = update_daily_egg_price()
    if result:
        print(f"[{datetime.now()}] Egg price update completed successfully")
    else:
        print(f"[{datetime.now()}] Egg price update failed")
