import json
from langchain.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

def load_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return json.dumps(data)

def load_faiss_index():
    index_path='faiss_index_vectors_manuals'
    embeddings = OpenAIEmbeddings()
    faiss_index = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    return faiss_index
