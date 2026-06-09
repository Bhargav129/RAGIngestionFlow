import asyncio
import logging.config

import aiofiles
import httpx
import pika
import json
import os

from pathlib import Path
from datetime import datetime

from src.repositories.file_operation_repo import FileOperationRepo
from src.logger import BASIC_LOGGING_CONFIG

logging.config.dictConfig(BASIC_LOGGING_CONFIG)

logger = logging.getLogger('my_app')

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()


channel.exchange_declare(exchange='direct_exchange', exchange_type='direct')
channel.exchange_declare(exchange="dead_letter_exchange", exchange_type='direct')

channel.queue_declare(queue='fetch_pdf_links', durable=True,  arguments={'x-queue-type': 'quorum'})
channel.queue_declare(queue='pdf_downloader', durable=True,  arguments={'x-queue-type': 'quorum'})
channel.queue_declare(queue='dead_letter_queue', durable=True,  arguments={'x-queue-type': 'quorum'})

channel.queue_bind(exchange='direct_exchange', queue='pdf_downloader', routing_key='downloader')
channel.queue_bind(exchange='direct_exchange', queue='pdf_extractor_loader', routing_key='extractor_loader')
channel.queue_bind(exchange='dead_letter_exchange', queue='dead_letter_queue', routing_key='dead_letter')

dir_name = os.path.abspath(os.curdir)
file_name = os.path.join(dir_name, 'symbols.json')


file_repo = FileOperationRepo(file_name)


async def main(symbols):
    try:
        for idx, s in enumerate(symbols):
            body = json.dumps({"data": s})
            channel.basic_publish(exchange='', routing_key='fetch_pdf_links',
                                  body=body, properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent))

            logger.info("Data sent to the ftech_pdf_links Queue ...")

        connection.close()

    except Exception as e:
        logger.error("Getting Exception as {}".format(e))

if __name__ == "__main__":
    tickers = file_repo.file_reader("r")
    logger.info("Starting web scraper ...")
    asyncio.run(main(tickers))
