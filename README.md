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

### Tutorials
- [Langchain PDF App (GUI) | Create a ChatGPT For Your PDF in Python](https://www.youtube.com/watch?v=wUAUdEw5oxM&t=1030s&ab_channel=AlejandroAO-Software%26Ai)
- [Tutorial | Chat with any Website using Python and Langchain (LATEST VERSION)](https://www.youtube.com/watch?v=bupx08ZgSFg&t=1968s&ab_channel=AlejandroAO-Software%26Ai)
- [Stream LLMs with LangChain + Streamlit | Tutorial](https://www.youtube.com/watch?v=zKGeRWjJlTU&t=240s&ab_channel=AlejandroAO-Software%26Ai)
- [Differences between Langchain & LlamaIndex](https://stackoverflow.com/questions/76990736/differences-between-langchain-llamaindex)