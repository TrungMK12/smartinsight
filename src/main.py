from vectordatabase import MiniVectorBase
from data_loader import clean_text
from utils import chunking_text

vdb = MiniVectorBase()

def add_document(mode:str, path:str):
    text = clean_text(mode, path)
    chunks = chunking_text(text)
    for chunk in chunks:
        vdb.add(chunk)

def search_document(query:str, top_k:int=3):
    results = vdb.search(query, top_k)
    return results

