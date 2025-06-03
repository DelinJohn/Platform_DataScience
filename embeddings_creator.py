from google.cloud import storage
import os
from io import BytesIO
import PyPDF2
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from itertools import chain
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
import getpass
from fastapi import FastAPI
import logging

app = FastAPI()

# Setup logging
logging.basicConfig(level=logging.INFO)
logging.disable()
logger = logging.getLogger(__name__)

try:
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter API key for OpenAI: ")

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = '.json'

    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") is None:
        logger.warning("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")

    text_splitter = SemanticChunker(OpenAIEmbeddings(), number_of_chunks=1000)

except Exception as e:
    logger.error(f"Initialization failed: {e}")
    raise

def read_pdf_from_gcs(bucket_name, blob_names):
    """Read PDFs from GCS and extract text with error handling"""
    complete_document = []
    for blob_name in blob_names:
        try:
            logger.info(f"Processing blob: {blob_name}")
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            pdf_bytes = blob.download_as_bytes()
            pdf_file = BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            data = []
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                if text:
                    data.append(text)
                else:
                    logger.warning(f"No text extracted from page {page_num} in blob {blob_name}")
            pdf = '. '.join(data)

            # Split the document into chunks
            try:
                docs = text_splitter.create_documents([pdf])
                complete_document.append(docs)
            except Exception as e:
                logger.error(f"Error during text splitting for {blob_name}: {e}")

        except Exception as e:
            logger.error(f"Error processing blob {blob_name}: {e}")

    return list(chain.from_iterable(complete_document))

def embeddings_from_gcb(bucket_name, blob_names):
    try:
        docs = read_pdf_from_gcs(bucket_name, blob_names)
        if not docs:
            logger.warning("No documents were extracted from the PDFs.")
            return "No documents extracted."

        if os.path.exists("faiss_index"):
            try:
                vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
                logger.info("Loaded existing FAISS index.")
                result_message = "Used existing Faiss_index"
            except Exception as e:
                logger.error(f"Failed to load existing FAISS index: {e}")
                return f"Error loading existing FAISS index: {e}"
        else:
            try:
                dim = len(embeddings.embed_query("hello world"))
                index = faiss.IndexFlatL2(dim)
                vector_store = FAISS(
                    embedding_function=embeddings,
                    index=index,
                    docstore=InMemoryDocstore(),
                    index_to_docstore_id={},
                )
                logger.info("Created new FAISS index.")
                result_message = "Created new Faiss_index"
            except Exception as e:
                logger.error(f"Failed to create new FAISS index: {e}")
                return f"Error creating FAISS index: {e}"

        try:
            vector_store.add_documents(documents=docs)
            vector_store.save_local("faiss_index")
            logger.info("Documents added and index saved successfully.")
        except Exception as e:
            logger.error(f"Failed to add documents to FAISS or save: {e}")
            return f"Error adding documents or saving FAISS index: {e}"

        return result_message

    except Exception as e:
        logger.error(f"Error in embeddings_from_gcb: {e}")
        return f"An error occurred: {e}"
