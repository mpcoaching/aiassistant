FROM python:3.11-slim

RUN pip install --no-cache-dir langgraph-api langgraph-runtime-inmem

COPY ./src /app
WORKDIR /app

EXPOSE 8000

ENV LANGGRAPH_RUNTIME_EDITION=inmem

CMD ["uvicorn", "langgraph_api.server:app", "--host", "0.0.0.0", "--port", "8000"]
