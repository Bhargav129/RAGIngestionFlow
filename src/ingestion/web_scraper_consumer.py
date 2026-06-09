from httpx_retries import RetryTransport, Retry
from datetime import datetime, timezone

import asyncio
import os
import httpx
import json
import pika
import logging

from src.logger import BASIC_LOGGING_CONFIG

logging.config.dictConfig(BASIC_LOGGING_CONFIG)

logger = logging.getLogger('my_app')



connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.queue_declare(queue='fetch_pdf_links', durable=True, arguments={'x-queue-type': 'quorum'})




NSE_API = "https://www.nseindia.com/api/annual-reports?index=equities&symbol={}"

NSE_HOMEPAGE = "https://www.nseindia.com/"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

BUFFER_YEARS = 5

current_year = datetime.now().year
fetch_years = current_year - BUFFER_YEARS
retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 502, 503, 504])
transport = RetryTransport(retry=retry)


async def fetch(symbol_json, session):
    try:
        symbol = symbol_json.get("ticker_symbol")
        url = NSE_API.format(symbol)
        resp = await session.get(url)
        resp.raise_for_status()
        if resp.status_code != 200:
            logger.error("FAILED:", symbol)
            return []
        data = resp.json()
        logger.info("Successfully fetch data from NSE API {}".format(symbol))
        pdfs = []
        for item in data.get("data", []):
            to_year = item.get("toYr")
            from_year = item.get("fromYr")
            if fetch_years <= int(from_year):
                pdfs.append({
                    "url": item.get("fileName"),
                    "fromyear": from_year,
                    "toyear": to_year
                })
        return pdfs
    except Exception as e:
        logger.error("@@@@@@@@@@@@ getting exception from NSE API {}".format(e))

async def homepage(session):
    try:
        resp = await session.get(NSE_HOMEPAGE)
        if resp.status_code != 200:
            resp.raise_for_status()
        logger.info("Successfully connect to the homepage")
    except Exception as e:
        logger.error("Failed to get the homepage", e)



async def fetch_link_process(json_data):
    try:
        async with httpx.AsyncClient(headers=HEADERS, http2=True, transport=transport) as session:
            await homepage(session)
            # TODO :  Implementation of index based
            pdfs = await fetch(json_data, session)
            body = {"data": json_data, "links": pdfs}
            channel.basic_publish(exchange='direct_exchange', routing_key='downloader', body=json.dumps(body))
    except Exception as e:
        logger.error("Getting exception as {}".format(e))
        symbol = json_data.get("ticker_symbol")
        url = NSE_API.format(symbol)
        try:
            source_queue = "fetch_pdf_links"
            exchange = "direct_exchange"
            routing_key = "downloader"

            body_data = {
                "source_queue": source_queue,
                "target_url": url,
                "exception_type": type(e).__name__,
                "exception_message": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "original_body": json_data,
                "exchange": exchange,
                "routing_key": routing_key
            }
            channel.basic_publish(exchange='dead_letter_exchange', routing_key='dead_letter', body=json.dumps(body_data))
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error("Getting Exception as {}".format(e))
    except KeyboardInterrupt as e:
        logger.warning("keyboard interrupt exception")


def fetch_link_callback(ch, method, properties, body):
    try:
        json_body = json.loads(body.decode('utf-8'))
        logger.info("consumer pull the data....")
        #print(("consumer pull the data...."))
        asyncio.run(fetch_link_process(json_body.get("data")))
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error("Getting Exception as {}".format(e))


channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='fetch_pdf_links', on_message_callback=fetch_link_callback)

logger.info("Web Scraper Worker active and listening to RabbitMQ...")
#print("Web Scraper Worker active and listening to RabbitMQ...")
channel.start_consuming()