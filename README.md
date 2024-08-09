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

Test link: https://www.iea.org/topics/global-energy-transitions-stocktake

## Improvements To-Do
1. Abstract retrieval chain: to be a class
2. Llama-index node parser
3. Embedding model selection: huggingface
4. Persist data in Chroma + cloud deployment
5. how to solve chat history overloads 
6. upload and parse pdf, word, excel files
7. auto download

## Resources
### Langchain
- [langchain_core](https://api.python.langchain.com/en/latest/core_api_reference.html)
- [langchain_openai ChatOpenAI](https://api.python.langchain.com/en/latest/chat_models/langchain_openai.chat_models.base.ChatOpenAI.html)
- [langchain Chroma](https://python.langchain.com/v0.2/docs/integrations/vectorstores/chroma/)
- [Streaming](https://python.langchain.com/v0.1/docs/expression_language/streaming/)
- [Conversational RAG](https://python.langchain.com/v0.2/docs/tutorials/qa_chat_history/)
- [Streaming Retrieval Chain](https://python.langchain.com/v0.2/docs/how_to/qa_streaming/)
- [Simplifying PDF using GPT-4, PyMuPDF and Streamlit](https://medium.com/@contact.blessin/simplifying-pdf-using-gpt-4-pymupdf-and-streamlit-e1e4e5de9399)
    - gives instruction on loading pdf files by PyMuPDF without saving pdf files to local first. It uses string concatenation on streams.It may not be efficient.
- [Understanding LangChain's RecursiveCharacterTextSplitter](https://dev.to/eteimz/understanding-langchains-recursivecharactertextsplitter-2846)


### Chroma
- [Run Chroma DB on a local machine and as a Docker container](https://abhishektatachar.medium.com/run-chroma-db-on-a-local-machine-and-as-a-docker-container-a9d4b91d2a97)

### Tutorials
- [Langchain PDF App (GUI) | Create a ChatGPT For Your PDF in Python](https://www.youtube.com/watch?v=wUAUdEw5oxM&t=1030s&ab_channel=AlejandroAO-Software%26Ai)
- [Tutorial | Chat with any Website using Python and Langchain (LATEST VERSION)](https://www.youtube.com/watch?v=bupx08ZgSFg&t=1968s&ab_channel=AlejandroAO-Software%26Ai)
- [Stream LLMs with LangChain + Streamlit | Tutorial](https://www.youtube.com/watch?v=zKGeRWjJlTU&t=240s&ab_channel=AlejandroAO-Software%26Ai)
- [Differences between Langchain & LlamaIndex](https://stackoverflow.com/questions/76990736/differences-between-langchain-llamaindex)

### LLM
- [零一万物Repo](https://github.com/01-ai/Yi?tab=readme-ov-file)
- [使用 Dify、Meilisearch、零一万物模型实现最简单的 RAG 应用（三）：AI 电影推荐](https://mp.weixin.qq.com/s/Ri2ap9_5EMzdfiBhSSL_MQ)
- [YiLLM Langchain](https://api.python.langchain.com/en/latest/llms/langchain_community.llms.yi.YiLLM.html#langchain_community.llms.yi.YiLLM)

### AliYun
- [使用docker和streamlit阿里云服务器部署简单的演示网页](https://jackiexiao.github.io/blog/%E6%8A%80%E6%9C%AF/%E4%BD%BF%E7%94%A8docker%E5%92%8Cstreamlit%E9%98%BF%E9%87%8C%E4%BA%91%E6%9C%8D%E5%8A%A1%E5%99%A8%E9%83%A8%E7%BD%B2%E7%AE%80%E5%8D%95%E7%9A%84%E6%BC%94%E7%A4%BA%E7%BD%91%E9%A1%B5/)
- [阿里云 部署django全攻略](https://developer.aliyun.com/article/633111)
- [Docker 部署Streamlit项目 | Streamlit如何部署到云服务器](https://developer.aliyun.com/article/1436718)
- [怎么把Streamlit部署到阿里云](https://wenku.csdn.net/answer/b2ded916ab19491b9bdc403183039ef5)
- [网站如何部署到阿里云服务器教程](https://developer.aliyun.com/article/773053)