from google.cloud import storage
import os
from io import BytesIO
import PyPDF2
from langchain_experimental.text_splitter import SemanticChunker
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from itertools import chain
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
import getpass
from fastapi import FastAPI
import logging
import json

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

def embeddings_from_website_content():


    # Load JSON file
    json_file_path = "website_data.json"

    with open(json_file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Extract relevant text fields
    documents = []
    for item in data:
        text_parts = []
        if "Title" in item and item["Title"]:
            text_parts.append(item["Title"])
        if "Meta Description" in item and item["Meta Description"] != "No description":
            text_parts.append(item["Meta Description"])
        if "Headings" in item:
            for key, values in item["Headings"].item():
                text_parts.extend(values)
        if "Paragraphs" in item:
            text_parts.extend(item["Paragraphs"])
        
        # Combine extracted text into a single document
        combined_text = " ".join(text_parts).strip()
        if combined_text:
            documents.append(combined_text)

    # Ensure documents are not empty
    if not documents:
        raise ValueError("No relevant text extracted from JSON. Check the JSON structure.")

   

    # Text splitting
    text_chunks = []
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=20,
        length_function=len,
        is_separator_regex=False,
    )

    for doc in documents:
        text_chunks.extend(text_splitter.split_text(doc))

    # Ensure text_chunks are not empty
    if not text_chunks:
        raise ValueError("No text chunks were created. Check if the extracted text is valid.")

    # Generate embeddings
    embeddings = OpenAIEmbeddings()

    # Test the embedding model
    try:
        test_embedding = embeddings.embed_query("test")
    except Exception as e:
        raise RuntimeError(f"Embedding model error: {e}")

    # Convert to FAISS vector database
    faiss_index_vectors = FAISS.from_texts(text_chunks, embeddings)

    # Save FAISS index locally
    faiss_index_vectors.save_local("_Website_faiss_index_vectors")

    return "FAISS vector store saved successfully!"








   
    
