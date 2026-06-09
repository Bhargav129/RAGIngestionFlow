import asyncio
import json
import io
import pika
import time
import httpx
import os
import zipfile
import aiofiles

from zipfile import BadZipFile
from pathlib import Path
from src.repositories.file_operation_repo import FileOperationRepo
from src.logger import BASIC_LOGGING_CONFIG



logging.config.dictConfig(BASIC_LOGGING_CONFIG)
logger = logging.getLogger('my_app')


# Initialize RabbitMQ blocking connection
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.queue_declare(queue='pdf_downloader', durable=True,  arguments={'x-queue-type': 'quorum'})

file_name = Path("symbols.json")
file_repo = FileOperationRepo(file_name)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

current_dir_path = os.path.dirname(os.path.abspath(os.curdir))
if not os.path.exists(annual_reports_path := os.path.join(current_dir_path, "AnnualReports")):
    logger.info("AnnualReports directory not found, creating directory")
    os.makedirs(annual_reports_path, exist_ok=True)


async def pdf_downloader(ticker_json, links, session, tickers_list):
    try:
        ticker = ticker_json.get("ticker_symbol")
        target_ticker_obj = next((t for t in tickers_list if t.get("ticker_symbol") == ticker), None)
        if not target_ticker_obj:
            logger.info(f"Ticker {ticker} not found in symbols array.")
            return
        yearwise_status = target_ticker_obj.get("status", {})
        ticker_path = os.path.join(annual_reports_path, ticker)
        os.makedirs(ticker_path, exist_ok=True)

        for ticker_data in links:
            download_status = "success"
            from_year = ticker_data.get("fromyear")
            to_year = ticker_data.get("toyear")
            url_path = ticker_data.get("url")

            if yearwise_status.get(from_year) == "pending":
                file_path = Path("{}_{}_{}.pdf".format(ticker, from_year, to_year))
                annual_report_filepath = ticker_path / file_path
                resp = await session.get(url_path)
                resp.raise_for_status()
                logger.info("Status {} for url  {}".format(resp.status_code, url_path))
                if resp.status_code == 200:
                    content = resp.read()
                    try:
                        if ".zip" in url_path:
                            with zipfile.ZipFile(io.BytesIO(content)) as zip_ref:
                                for zip_info in zip_ref.infolist():
                                    file_size = zip_info.file_size / 1024
                                    if not (zip_info.filename.startswith("BRR_SR_") or int(file_size) < 500):
                                        with zip_ref.open(zip_info.filename) as source:
                                            file_bytes = source.read()
                                        if file_bytes:
                                            async with aiofiles.open(annual_report_filepath, "wb") as file:
                                                await file.write(file_bytes)
                                                logger.info("Data written into file for zip file")
                                        else:
                                            download_status = "pending"
                                            logger.info("I didn't found content for zip file so update status to pending")
                        else:
                            async with aiofiles.open(annual_report_filepath, "wb") as file:
                                if not content:
                                    download_status = "pending"
                                    logger.info("I didn't found content so update status to pending")
                                else:
                                    await file.write(content)
                                    logger.info("Data written into file")
                    except BadZipFile as e:
                        download_status = "failed"
                        logger.error("Issue with zipfile {}".format(e))
                    except Exception as e:
                        download_status = "failed"
                        logger.error("Getting Exception: {}".format(e))
                yearwise_status[from_year] = download_status

    except Exception as e:
        logger.error("Getting exception in pdf_downloader {}".format(e))


async def worker_orchestration(ticker_json, links):
    tickers = file_repo.file_reader("r")
    try:
        async with httpx.AsyncClient(headers=HEADERS, http2=True) as worker_session:
            await pdf_downloader(ticker_json, links, worker_session, tickers)
        #channel.basic_publish(exchange='direct_exchange', routing_key='extractor_loader', body=json.dumps(ticker_json))
    except Exception as e:
        logger.error("Exception in worker_orchestration {}".format(e))
    finally:
        file_repo.file_writer("w", tickers)
        print("@@@@@@@@@@@ File updated on disk successfully.")

#TODO  Retry file downloading and add to Dead letter Queue

def callback(ch, method, properties, body):
    json_body = json.loads(body.decode('utf-8'))
    ticker_json = json_body.get("data")
    links = json_body.get("links")
    logger.info("@@@@@@@@@@@@@@@  file_downloader consumer pull the data....")
    asyncio.run(worker_orchestration(ticker_json, links))
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='pdf_downloader', on_message_callback=callback)

logger.info("file downloader worker active and listening to RabbitMQ...")
channel.start_consuming()
