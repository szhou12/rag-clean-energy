# RAG

## Dependencies
### Conda Environment
```linux
conda create --name rag-energy python=3.10
```

### Python Packages
```linux
pip install -r requirements.txt
```

## Running the App
```linux
streamlit run src/demo.py
streamlit run src/app.py
```

Test link: 
- https://www.iea.org/topics/global-energy-transitions-stocktake
- https://rmi.org.cn/

## MySQL
### Terminal Commands
#### Log in to MySQL
```linux
mysql -u root -p
```
#### MySQL Console
- Check all databases
```linux
mysql> SHOW databases;
```
- Enter a database
```linux
mysql> USE <database_name>;
```
- Log out of MySQL
```linux
mysql> quit
```
- Delete a database
```linux
mysql> DROP DATABASE <database_name>;
```
- Inspect structure of a table
```linux
mysql> DESCRIBE <table_name>;
```
- Count total rows in a table
```linux
mysql> SELECT COUNT(*) FROM <table_name>;
```
### Quiz
1. `session.commit()` should be used inside a function or outside a function?
    - Outside a function if multiple database operations are part of a single workflow and this function is part of this workflow. e.g. Inserting a web page and its corresponding web page chunks are often used jointly.
    - Inside a function if this database operation is meant to be self-contained, and the transaction should be committed immediately after the operation.


## Improvements To-Do
1. Abstract retrieval chain: to be a class
2. Llama-index node parser
3. Embedding model selection: huggingface
4. Persist data in Chroma + cloud deployment
5. how to solve chat history overloads 
6. upload and parse pdf, word, excel files
7. auto download
8. RAG on Tabular data
    - maybe helful: 
        - [SheetSimplify with RAG LLMs](https://github.com/sivadhulipala1999/SheetSimplify_with_RAG/tree/main)
        - [LLMs for Advanced Question-Answering over Tabular/CSV/SQL Data (Building Advanced RAG, Part 2)](https://www.youtube.com/watch?v=L1o1VPVfbb0)
9. The directory path to store uploaded and downloaded files should configure to environment variable after implementing Database.

## 开发笔记
1. RAGAgent: define a class `RAGAgent` to abstract RAG chain
    - file parser: use **Singleton-Like Approach** to maintain a single instance of each parser type within the RAGAgent class and reuse it for each file upload -> for efficiency.
2. file parser: define a parser class to parse user-uploaded files
    - abstarct class: `BaseParser`
    - subclasses: `PDFParser`, `ExcelParser` extend from `BaseParser`
3. TODO: webscraper class
    1. only enqueue subdirectories given a root URL :white_check_mark:
    2. filter out irrelevant URLs: e.g. "About", "Contact" :white_check_mark:
    3. how to parse downloaded files? Logic: 每一次爬网页的时候，现将附件下载到 downloads 文件夹，在未来的某一时刻，再将这些文件解析，并将完成解析的文件从 downloads 文件夹移到 temp 文件夹。为避免重复下载已解析过的附件文件，每新一轮触发爬网页时，先将temp中所有文件名preload到一个set中？
        - **连接数据库后需要更改: 1. 未解析文件的暂存路径，2. 调取并预载已解析文件Metadata**
    4. 目前所有爬过的网页的网址都储存在text文件里("scraped_urls.txt")，**连接数据库后需要更改: 1. 增加一个method来准备metadata, 2. metadata的存储路径**
4. **TODO** [update Langchain](https://python.langchain.com/v0.2/docs/versions/v0_2/)
5. **TODO** database迁移的处理办法:
    1. files: 把所有需要解析的文件定义为两大类：1. 已解析 2. 未解析 (包括用户上传+网页上抓取)。已解析文件：原始文件不再储存到database, 只存储它的metadata。未解析文件：开辟一个"缓存“空间，暂存这些原始文件，等待解析，解析后，将原始文件从缓存中移除，metadata写入database 
    2. web pages: 将爬过并已经解析的网页的metadata (e.g. URL) 写入database.
    3. Database for metadata: 似乎使用 Relational DB (MySQL) 比较合适？
        - Example Schema : Files Metadata Table
        ```
        CREATE TABLE parsed_files (
            id SERIAL PRIMARY KEY,
            file_name VARCHAR(255),
            file_checksum CHAR(64),  -- SHA-256 or similar checksum
            upload_date TIMESTAMP,
            parsed_date TIMESTAMP,
            vector_store_id VARCHAR(255)  -- Reference to the vector data in the vector store
        );
        ```
        - Schema : Web Pages Metadata Table
        ```
        CREATE TABLE web_page (
            id SERIAL PRIMARY KEY,
            source TEXT, -- URL of the web page
            checksum CHAR(64),  -- SHA-256 checksum of the URL
            date TIMESTAMP, -- date of the web page stored in MySQL
            refresh_frequency INT, -- in days for re-scraping
        );
        ```
        - Schema : Web Page Chunks Metadata Table
        ```
        CREATE TABLE web_page_chunk (
            id TEXT PRIMARY KEY, - UUID4 for this chunk
            source TEXT FOREIGN KEY, -- URL of the web page
        );
        ```
6. **TODO** 缓存空间Buffer: 用来暂存未解析的文件。
    - 可用技术: AWS S3 (simple storage service), Alibaba Cloud OSS (Object Storage Service)
7. **TODO** Cloud-based deployment
    - 下面以AWS为例，阐述流程：AWS EC2是server/VM，相当于租用一台电脑，把整个application部署在这台电脑里，用户通过网址来访问使用。AWS S3是存储服务，在该应用里作为“缓存”暂时存储等待被解析的文件。
8. **TODO** Use `logging` to log errors and debug information

- 明天
1. DAO: `FilePage`, `FilePageChunk`. Modify `extract_metadata`
1. `RAGAgent`: update `refresh_frequency` by a given list of sources or map `{source: url, refresh_freq: 2}`?
2. persist Chroma!!!
    - 2 collections: one for English texts, another for Chinese texts
    - add one more field in MySQL to indicate the language of the text
3. AI response template: 以投喂文本为主，增加citation功能
4. 中英文embedding切换。同时存入中英文两种文本，输出仅限中文。
5. 优先引用储存的文本信息


## Troubleshooting
- [ValueError when using UnstructuredMarkdownLoader](https://github.com/langchain-ai/langchain/issues/8556)

## Resources
### Langchain
1. [Document object](https://python.langchain.com/v0.2/docs/concepts/#documents): A Document object in LangChain contains information about some data. It has 2 attributes:
    1. `page_content: str`: The content of this document. Currently is only a string.
    2. `metadata: dict`: Arbitrary metadata associated with this document. Can track the document id, file name, etc. e.g. `metadata={'source': 'https://www.iea.org/energy-system/fossil-fuels', 'title': 'Fossil Fuels - Energy System - IEA', 'description': '', 'language': 'en-GB'}`


- [langchain_core](https://api.python.langchain.com/en/latest/core_api_reference.html)
    - When you instantiate OpenAI-related models in Langchain, you don't need to explicitly pass in OpenAI API key as arguemnt. This is because Langchain has a built-in function `get_from_dict_or_env()` (from `langchain_core.utils`) that will look for the API key in your environment variables. Therefore, if you define the API key in `.env` file, you only need to use `load_dotenv()` to load the API key into the environment variables. Langchain will help you locate the API key content when you instantiate an OpenAI-related model.
- [langchain_openai ChatOpenAI](https://api.python.langchain.com/en/latest/chat_models/langchain_openai.chat_models.base.ChatOpenAI.html)
- [langchain Chroma](https://python.langchain.com/v0.2/docs/integrations/vectorstores/chroma/)
- [Streaming](https://python.langchain.com/v0.1/docs/expression_language/streaming/)
- [Conversational RAG](https://python.langchain.com/v0.2/docs/tutorials/qa_chat_history/)
- [Streaming Retrieval Chain](https://python.langchain.com/v0.2/docs/how_to/qa_streaming/)
- [Simplifying PDF using GPT-4, PyMuPDF and Streamlit](https://medium.com/@contact.blessin/simplifying-pdf-using-gpt-4-pymupdf-and-streamlit-e1e4e5de9399)
    - gives instruction on loading pdf files by PyMuPDF without saving pdf files to local first. It uses string concatenation on streams.It may not be efficient.
- [Understanding LangChain's RecursiveCharacterTextSplitter](https://dev.to/eteimz/understanding-langchains-recursivecharactertextsplitter-2846)


#### Langchain Retriever
- [Custom Retriever](https://python.langchain.com/v0.1/docs/modules/data_connection/retrievers/custom_retriever/)
- [BaseRetriever](https://api.python.langchain.com/en/latest/retrievers/langchain_core.retrievers.BaseRetriever.html)
- [How to do retrieval with contextual compression](https://python.langchain.com/docs/how_to/contextual_compression/)

### Chroma
- [Run Chroma DB on a local machine and as a Docker container](https://abhishektatachar.medium.com/run-chroma-db-on-a-local-machine-and-as-a-docker-container-a9d4b91d2a97)
- [Changing the distance method in Chroma](https://github.com/langchain-ai/langchain/discussions/22422)
- [Chroma System Constraints](https://cookbook.chromadb.dev/core/system_constraints/)

### Tutorials
- [Langchain PDF App (GUI) | Create a ChatGPT For Your PDF in Python](https://www.youtube.com/watch?v=wUAUdEw5oxM&t=1030s&ab_channel=AlejandroAO-Software%26Ai)
- [Tutorial | Chat with any Website using Python and Langchain (LATEST VERSION)](https://www.youtube.com/watch?v=bupx08ZgSFg&t=1968s&ab_channel=AlejandroAO-Software%26Ai)
- [Stream LLMs with LangChain + Streamlit | Tutorial](https://www.youtube.com/watch?v=zKGeRWjJlTU&t=240s&ab_channel=AlejandroAO-Software%26Ai)
- [Differences between Langchain & LlamaIndex](https://stackoverflow.com/questions/76990736/differences-between-langchain-llamaindex)

### LLM
- [零一万物Repo](https://github.com/01-ai/Yi?tab=readme-ov-file)
- [使用 Dify、Meilisearch、零一万物模型实现最简单的 RAG 应用（三）：AI 电影推荐](https://mp.weixin.qq.com/s/Ri2ap9_5EMzdfiBhSSL_MQ)
- [YiLLM Langchain](https://api.python.langchain.com/en/latest/llms/langchain_community.llms.yi.YiLLM.html#langchain_community.llms.yi.YiLLM)

### Embedding Model
- [Huggingface | BAAI](https://huggingface.co/BAAI)
- [Langchain BGE Embedding](https://python.langchain.com/v0.2/docs/integrations/text_embedding/bge_huggingface/)

### AliYun
- [使用docker和streamlit阿里云服务器部署简单的演示网页](https://jackiexiao.github.io/blog/%E6%8A%80%E6%9C%AF/%E4%BD%BF%E7%94%A8docker%E5%92%8Cstreamlit%E9%98%BF%E9%87%8C%E4%BA%91%E6%9C%8D%E5%8A%A1%E5%99%A8%E9%83%A8%E7%BD%B2%E7%AE%80%E5%8D%95%E7%9A%84%E6%BC%94%E7%A4%BA%E7%BD%91%E9%A1%B5/)
- [阿里云 部署django全攻略](https://developer.aliyun.com/article/633111)
- [Docker 部署Streamlit项目 | Streamlit如何部署到云服务器](https://developer.aliyun.com/article/1436718)
- [怎么把Streamlit部署到阿里云](https://wenku.csdn.net/answer/b2ded916ab19491b9bdc403183039ef5)
- [网站如何部署到阿里云服务器教程](https://developer.aliyun.com/article/773053)

### Nginx
- [Streamlit with Nginx](https://medium.com/featurepreneur/streamlit-with-nginx-bde7a9a41e6c)