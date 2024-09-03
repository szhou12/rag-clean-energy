from db_mysql import MySQLManager
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

mysql_config = {
        'user': 'root',
        'host': 'localhost',
        'port': 3306,
        'password': os.getenv('MYSQL_PASSWORD'),
        'db_name': 'rmi_test'
    }
    
manager = MySQLManager(**mysql_config)
session = manager.create_session()

# Example usage
page_id = manager.insert_web_page(session, "https://example.com", refresh_freq=7)
manager.insert_web_page_chunks(session, hashlib.sha256("https://example.com".encode('utf-8')).hexdigest(), ["chunk1", "chunk2"])

manager.close_session(session)
manager.close()