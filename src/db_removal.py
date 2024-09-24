import chromadb
from chromadb.config import Settings
import os
from sqlalchemy_utils import database_exists, drop_database
from dotenv import load_dotenv

load_dotenv()

def remove_chroma():
    # https://docs.trychroma.com/guides
    # https://stackoverflow.com/questions/78752139/chroma-db-reset-enabling-issue

    base_dir = "/Users/shuyuzhou/Documents/github/rag-clean-energy/src"
    vector_db = "db_chroma"

    full_path = os.path.join(base_dir, vector_db)

    client = chromadb.PersistentClient(path=full_path, settings=Settings(allow_reset=True))

    vs_collections = ['default', 'docs_en', 'docs_zh']
    for collection_name in vs_collections:
        try:
            collection = client.get_collection(name=collection_name)
            print(f"inspect first 10 items: {collection.peek()}")
            print(f"inspect total # of items: {collection.count()}")
            client.delete_collection(name=collection_name) # Delete a collection and all associated embeddings, documents, and metadata. This is destructive and not reversible!
            print(f"Collection {collection_name} deleted!!!")
        except Exception as e:
            print(f"Collection {collection_name} not found: {e}")

    client.reset() # Empties and completely resets the database. This is destructive and not reversible!

def remove_mysql():
    TEST_DB_CONFIG = {
        'host': 'localhost',
        'user': 'root',
        'password': os.getenv('MYSQL_PASSWORD'),
        'port': 3306,
        'database': 'rmi_test'
    }
    TEST_DB_URI = f"mysql+mysqlconnector://{TEST_DB_CONFIG['user']}:{TEST_DB_CONFIG['password']}@" \
             f"{TEST_DB_CONFIG['host']}:{TEST_DB_CONFIG['port']}/{TEST_DB_CONFIG['database']}"
    
    if database_exists(TEST_DB_URI):
        drop_database(TEST_DB_URI)
        print(f"Database {TEST_DB_CONFIG['database']} dropped!!!")



if __name__ == "__main__":
    remove_chroma()
    remove_mysql()