import chromadb
from chromadb.config import Settings
import os

# https://docs.trychroma.com/guides
# https://stackoverflow.com/questions/78752139/chroma-db-reset-enabling-issue

base_dir = "/Users/shuyuzhou/Documents/github/rag-clean-energy/src"
vector_db = "db_chroma"

full_path = os.path.join(base_dir, vector_db)

client = chromadb.PersistentClient(path=full_path, settings=Settings(allow_reset=True))

collection = client.get_collection(name="default")
print(f"inspect first 10 items: {collection.peek()}")
print(f"inspect total # of items: {collection.count()}")


client.delete_collection(name="default") # Delete a collection and all associated embeddings, documents, and metadata. This is destructive and not reversible!

client.reset() # Empties and completely resets the database. This is destructive and not reversible!
