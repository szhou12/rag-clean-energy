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

## Improvements To-Do
1. Llama-index node parser
2. Embedding model selection: huggingface
3. Persist data in Chroma

## Resources
### Langchain
- [langchain_core](https://api.python.langchain.com/en/latest/core_api_reference.html)
- [langchain_openai ChatOpenAI](https://api.python.langchain.com/en/latest/chat_models/langchain_openai.chat_models.base.ChatOpenAI.html)
- [Streaming](https://python.langchain.com/v0.1/docs/expression_language/streaming/)
- [Conversational RAG](https://python.langchain.com/v0.2/docs/tutorials/qa_chat_history/)
- [Streaming Retrieval Chain](https://python.langchain.com/v0.2/docs/how_to/qa_streaming/)

### Tutorials
- [Tutorial | Chat with any Website using Python and Langchain (LATEST VERSION)](https://www.youtube.com/watch?v=bupx08ZgSFg&t=1968s&ab_channel=AlejandroAO-Software%26Ai)
- [Stream LLMs with LangChain + Streamlit | Tutorial](https://www.youtube.com/watch?v=zKGeRWjJlTU&t=240s&ab_channel=AlejandroAO-Software%26Ai)
- [Differences between Langchain & LlamaIndex](https://stackoverflow.com/questions/76990736/differences-between-langchain-llamaindex)