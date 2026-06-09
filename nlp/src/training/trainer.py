"""BERT trainer with HuggingFace integration."""
import os
import logging
from typing import Optional, Callable

import torch
import numpy as np
from datasets import Dataset
from transformers import (
    BertTokenizer,
    BertForSequenceClassification,
    TrainingArguments,
    Trainer as HFTrainer,
    EarlyStoppingCallback,
)
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from nlp.src.data_processing.preprocessor import ReviewPreprocessor
from nlp.src.models.bert.config import BERTConfig

logger = logging.getLogger(__name__)


def _compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="weighted"
    )
    acc = accuracy_score(labels, predictions)
    return {"accuracy": acc, "f1": f1, "precision": precision, "recall": recall}


def train_bert_model(
    train_data: str,
    val_data: Optional[str] = None,
    config: Optional[BERTConfig] = None,
    model_name: Optional[str] = None,
    output_dir: Optional[str] = None,
    callback: Optional[Callable] = None,
):
    if config is None:
        config = BERTConfig()

    model_name = model_name or config.model_name
    output_dir = output_dir or config.output_dir

    preprocessor = ReviewPreprocessor()

    df = preprocessor.load_csv(train_data)
    df = preprocessor.preprocess_dataframe(df, label_column="label")
    logger.info("Loaded %d training samples", len(df))

    if val_data:
        val_df = preprocessor.load_csv(val_data)
        val_df = preprocessor.preprocess_dataframe(val_df, label_column="label")
    else:
        train_df, val_df = preprocessor.train_val_split(df, val_ratio=0.2)
        df = train_df

    tokenizer = BertTokenizer.from_pretrained(model_name)

    def tokenize_fn(examples):
        return tokenizer(
            examples["content"],
            truncation=True,
            padding="max_length",
            max_length=config.max_length,
        )

    train_dataset = Dataset.from_pandas(df[["content", "label"]]).map(
        tokenize_fn, batched=True
    )
    val_dataset = Dataset.from_pandas(val_df[["content", "label"]]).map(
        tokenize_fn, batched=True
    )

    train_dataset.set_format("torch", columns=["input_ids", "attention_mask", "label"])
    val_dataset.set_format("torch", columns=["input_ids", "attention_mask", "label"])

    model = BertForSequenceClassification.from_pretrained(
        model_name,
        num_labels=config.num_labels,
        hidden_dropout_prob=config.hidden_dropout,
    )

    training_args = TrainingArguments(
        output_dir=output_dir,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.batch_size,
        per_device_eval_batch_size=config.batch_size * 2,
        num_train_epochs=config.epochs,
        weight_decay=config.weight_decay,
        warmup_ratio=config.warmup_ratio,
        logging_steps=50,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        save_total_limit=config.save_total_limit,
        fp16=config.fp16 and torch.cuda.is_available(),
        dataloader_num_workers=2,
    )

    trainer = HFTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=_compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=config.early_stopping_patience)],
    )

    trainer.train()
    os.makedirs(output_dir, exist_ok=True)
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    logger.info("Model saved to %s", output_dir)

    eval_result = trainer.evaluate()
    logger.info("Final evaluation: %s", eval_result)
    return eval_result
