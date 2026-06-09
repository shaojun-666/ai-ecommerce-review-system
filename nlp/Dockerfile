FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download BERT model for offline use
RUN python -c "from transformers import BertTokenizer, BertForSequenceClassification; \
    BertTokenizer.from_pretrained('bert-base-chinese'); \
    BertForSequenceClassification.from_pretrained('bert-base-chinese')" || true

CMD ["python"]
