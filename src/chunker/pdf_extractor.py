from pathlib import Path
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling_core.types.doc import DocItemLabel
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
from docling.document_converter import DocumentConverter, PdfFormatOption
from langchain_core.documents import Document
from src.repositories.file_operation_repo import FileOperationRepo
from docling.utils.profiling import settings
from src.logger import BASIC_LOGGING_CONFIG


import os
import re
import pymupdf
import time
import multiprocessing
import logging

logging.config.dictConfig(BASIC_LOGGING_CONFIG)

logger = logging.getLogger('my_app')


settings.debug.profile_pipeline_timings = True


MAX_CHARS = 2048

pdf_options = PdfPipelineOptions()

pdf_options.accelerator_options = AcceleratorOptions(
    num_threads=multiprocessing.cpu_count(),
    device=AcceleratorDevice.AUTO
)
pdf_options.do_ocr = False
pdf_options.generate_page_images = False
pdf_options.generate_picture_images = False

pdf_options.table_structure_options.mode = TableFormerMode.ACCURATE



doc_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options, backend=PyPdfiumDocumentBackend )
    }
)

file_name = Path("symbols.json")
file_repo = FileOperationRepo(file_name)

dir_path = os.path.dirname(os.path.abspath(os.curdir))

annual_reports_dir = os.path.join(dir_path, "AnnualReports")


def time_dec(func):
    def inner_func(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logger.info("Total time taken to extract pdf  and load data into DB {}".format(end - start))
        return result
    return inner_func


@time_dec
def extractor_loader(annual_report_dir_path):
    try:
        text_chunks = ""
        text_chunks_list = []
        table_chunks = []
        section_headers = "General"
        current_meta = None
        file_path = str(annual_report_dir_path)
        logger.info("@@@@@@@@@@@@@ file_path {}".format(file_path))
        annual_report = file_path.split("/")[-1].strip()
        ticker = annual_report.split("_")[0]
        fiscal_year = annual_report.split("_")[1]+ "-" + annual_report.split("_")[-1][:-4]
        logger.info("FiscalYear {} and ticker {}".format(fiscal_year, ticker))
        doc = pymupdf.open(file_path)
        total_pages = doc.page_count
        doc.close()
        logger.info("@@@@@@@@@@@@@ total pages are {}".format(total_pages))
        docs = doc_converter.convert(file_path)
        result = docs.document

        for item, level in result.iterate_items():
            page_no = item.prov[0].page_no
            #print("@@@@@@@@@@@@ current_page", page_no)
            # --- STRUCTURAL BREAKS (SECTION HEADERS & TABLES) ---
            if item.label in [DocItemLabel.SECTION_HEADER, DocItemLabel.TABLE]:
                # Flush existing accumulated text chunk before handling structural element
                if text_chunks.strip() and current_meta:
                    text_chunks_list.append((text_chunks.strip(), current_meta.copy()))

                # Completely clear state for the upcoming structural segment
                text_chunks = ""
                current_meta = None

                if item.label == DocItemLabel.SECTION_HEADER:
                    if not re.match(r'^\((rs|₹|rupees).*\)$', item.text.strip().lower()):
                        section_headers = item.text.strip()
                    continue

                if item.label == DocItemLabel.TABLE:
                    try:
                        table_md = item.export_to_markdown(doc=result)
                    except Exception:
                        table_md = item.export_to_markdown()

                    if table_md:
                        table_chunks.append({
                            "table": table_md.strip(),
                            "section": section_headers,
                            "page_no": page_no,
                            "ticker": ticker,
                            "fiscal_year": fiscal_year,
                            "chunk_type": "table"
                        })
                    continue

            if item.label in [DocItemLabel.TEXT, DocItemLabel.LIST_ITEM]:
                clean_text = item.text.strip()
                if not clean_text:
                    continue

                # FIXED: Safely check overflow based purely on existing text state
                if text_chunks and (len(text_chunks) + len(clean_text) + 1 > MAX_CHARS):
                    # Flush out the current chunk buffer
                    text_chunks_list.append((text_chunks.strip(), current_meta.copy()))

                    # Instantly seed a fresh chunk state using the new text element
                    text_chunks = clean_text
                    current_meta = {
                        "section": section_headers,
                        "page_start": page_no,
                        "page_end": page_no,
                        "ticker": ticker,
                        "fiscal_year": fiscal_year,
                        "chunk_type": "text"
                    }
                else:

                    text_chunks = f"{text_chunks} {clean_text}".strip()
                    if not current_meta:
                        current_meta = {
                            "section": section_headers,
                            "page_start": page_no,
                            "page_end": page_no,
                            "ticker": ticker,
                            "fiscal_year": fiscal_year,
                            "chunk_type": "text"
                        }
                    else:
                        current_meta["page_end"] = page_no

        if text_chunks.strip() and current_meta:
            text_chunks_list.append((text_chunks.strip(), current_meta.copy()))
        logger.info("Total text_chunks {} and table_chunks {}".format(len(text_chunks_list), len(table_chunks)))
        chunked_docs = [Document(page_content=data, metadata=meta) for data,meta in text_chunks_list]
        chunked_tables = [Document(page_content=table.get("table"), metadata={k:v for k,v in table.items() if k!="table"}) for table in table_chunks]
        return chunked_docs, chunked_tables
    except Exception as e:
        logger.error("Getting Exception as {}".format(e))
        return "", ""



if __name__ == "__main__":
    symbols_data = file_repo.file_reader("r")
    ticker_symbols = [symbol.get("ticker_symbol") for symbol in symbols_data]
    for tickers in ticker_symbols:
        path = os.path.join(annual_reports_dir, tickers)
        for file_path in Path(path).rglob('*.pdf'):
            chunked_docs,chunked_tables = extractor_loader(file_path)
            final_chunks = chunked_docs + chunked_tables
            # if len(final_chunks):
            #     embedding_storer(final_chunks)