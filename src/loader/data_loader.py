from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client import models
from FlagEmbedding import BGEM3FlagModel, FlagReranker
from dotenv import load_dotenv
from src.logger import BASIC_LOGGING_CONFIG

import uuid
import os

logging.config.dictConfig(BASIC_LOGGING_CONFIG)
logger = logging.getLogger('my_app')

load_dotenv()

model = BGEM3FlagModel('BAAI/bge-m3',  use_fp16=True)

BATCH_SIZE = 10

def embeddings(docs):
        embedded_data = [doc.page_content for doc in docs] if isinstance(docs, list) else [docs]
        final_embeddings = model.encode(embedded_data,
                                batch_size=12,
                                max_length=1092,
                                return_dense=True,
                                return_sparse=True)

        dense_vec = final_embeddings['dense_vecs']
        sparse_vec = final_embeddings['lexical_weights']


        return dense_vec, sparse_vec


def sparse_embeddings(docs):
    embedded_data = [doc.page_content for doc in docs] if isinstance(docs, list) else [docs]
    sparse_vec = model.encode(embedded_data, return_dense=False, return_sparse=True, return_colbert_vecs=False)['lexical_weights']

    sparse_indices = []
    sparse_values = []

    for token_id, weight in sparse_vec.items():
        sparse_indices.append(int(token_id) if str(token_id).isdigit() else token_id)
        sparse_values.append(float(weight))

    return sparse_indices, sparse_values

client = QdrantClient(
    url= os.getenv('QDRANT_URL'),
    api_key= os.getenv('QDRANT_APIKEY'),
)

collection_name = "annual_reports_rag"

#TODO Avoid duplicate embedding store

def embedding_storer(docs):

    dense_embeds, sparse_embeds = embeddings(docs)

    points = []

    for doc, dense_vec, sparse_vec in zip(docs, dense_embeds, sparse_embeds):

        sparse_indices = []
        sparse_values = []

        for token_id, weight in sparse_vec.items():
            sparse_indices.append(int(token_id) if str(token_id).isdigit() else token_id)
            sparse_values.append(float(weight))

        point = models.PointStruct(id=uuid.uuid4().hex,
                                   vector={
                                       "dense": dense_vec.tolist(),
                                       "sparse": models.SparseVector(indices=sparse_indices,values=sparse_values)
                                   },
                                   payload={
                                       **doc.metadata,
                                        "text":doc.page_content
                                   }
                                   )
        points.append(point)

    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": models.VectorParams(
                    distance=models.Distance.COSINE,
                    size=1024,
                ),
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams()
            }
        )
        client.create_payload_index(
            collection_name=collection_name,
            field_name="ticker",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

        client.create_payload_index(
            collection_name=collection_name,
            field_name="fiscal_year",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    for  idx in range(0, len(points), BATCH_SIZE):
        client.upsert(
            collection_name=collection_name,
            points = points[idx:idx + BATCH_SIZE],
        )