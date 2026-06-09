# Financial RAG Ingestion Pipeline

This repository contains the ingestion pipeline for a Financial Retrieval-Augmented Generation (RAG) system. The pipeline processes financial annual reports, extracts and transforms document content, generates embeddings, and stores them in a vector database to enable efficient semantic retrieval for downstream RAG applications.

## Features

* Financial annual report ingestion
* Document parsing and preprocessing
* Text chunking and metadata extraction
* Embedding generation
* Vector database storage
* Asynchronous processing using RabbitMQ
* Scalable ingestion architecture

## Prerequisites

* Python 3.10+
* RabbitMQ Server
* Vector Database

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd <repository-name>
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install and start RabbitMQ:

RabbitMQ Installation Guide:
https://www.rabbitmq.com/docs/download

Ensure the RabbitMQ service is running before starting the application.

## Running the Application

Start the ingestion pipeline:

```bash
python -m src.main
```

## Workflow

1. Financial reports are received for processing.
2. Documents are parsed and cleaned.
3. Content is split into chunks.
4. Embeddings are generated for each chunk.
5. Embeddings and metadata are stored in the vector database.
6. The RAG application retrieves relevant information based on user queries.

## Project Purpose

This ingestion service serves as the backend data preparation layer for a Financial RAG application, enabling accurate and section-aware retrieval from annual reports.
