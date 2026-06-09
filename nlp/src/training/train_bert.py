"""BERT fine-tuning script for sentiment analysis."""
import os
import argparse
import logging

import torch
import numpy as np
from datasets import Dataset
from transformers import (
    BertTokenizer,
    BertForSequenceClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
)
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from nlp.src.data_processing.preprocessor import ReviewPreprocessor

logger = logging.getLogger(__name__)


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average="weighted")
    acc = accuracy_score(labels, predictions)
    return {"accuracy": acc, "f1": f1, "precision": precision, "recall": recall}


def train_bert(args):
    preprocessor = ReviewPreprocessor()

    # Load and preprocess data
    df = preprocessor.load_csv(args.train_data)
    df = preprocessor.preprocess_dataframe(df, label_column="label")
    logger.info("Loaded %d training samples", len(df))

    # Split
    if args.val_data:
        val_df = preprocessor.load_csv(args.val_data)
        val_df = preprocessor.preprocess_dataframe(val_df, label_column="label")
    else:
        train_df, val_df = preprocessor.train_val_split(df, val_ratio=0.2)
        df = train_df

    # Tokenizer
    tokenizer = BertTokenizer.from_pretrained(args.model_name)

    def tokenize_fn(examples):
        return tokenizer(
            examples["content"],
            truncation=True,
            padding="max_length",
            max_length=args.max_length,
        )

    train_dataset = Dataset.from_pandas(df[["content", "label"]]).map(tokenize_fn, batched=True)
    val_dataset = Dataset.from_pandas(val_df[["content", "label"]]).map(tokenize_fn, batched=True)

    train_dataset.set_format("torch", columns=["input_ids", "attention_mask", "label"])
    val_dataset.set_format("torch", columns=["input_ids", "attention_mask", "label"])

    # Model
    model = BertForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=3,  # negative, neutral, positive
        hidden_dropout_prob=0.3,
    )

    # Training args
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        warmup_ratio=0.1,
        logging_steps=50,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        save_total_limit=2,
        fp16=torch.cuda.is_available(),
        dataloader_num_workers=2,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    # Train
    trainer.train()

    # Save
    os.makedirs(args.output_dir, exist_ok=True)
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    logger.info("Model saved to %s", args.output_dir)

    # Final evaluation
    eval_result = trainer.evaluate()
    logger.info("Final evaluation: %s", eval_result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_data", type=str, required=True)
    parser.add_argument("--val_data", type=str, default=None)
    parser.add_argument("--model_name", type=str, default="bert-base-chinese")
    parser.add_argument("--output_dir", type=str, default="./models/bert-sentiment")
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--max_length", type=int, default=256)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    train_bert(args)
