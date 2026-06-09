"""Data preprocessing for review text."""
import re
import pandas as pd
from typing import Optional


class ReviewPreprocessor:
    """Preprocess Chinese e-commerce reviews for NLP models."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize review text."""
        if not text:
            return ""

        # Normalize whitespace
        text = re.sub(r"\s+", "", text)

        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)

        # Normalize punctuation
        text = text.replace("…", "...")

        return text.strip()

    @staticmethod
    def load_csv(path: str, text_column: str = "content", **kwargs) -> pd.DataFrame:
        """Load reviews from CSV file."""
        return pd.read_csv(path, **kwargs)

    @staticmethod
    def load_excel(path: str, text_column: str = "content", **kwargs) -> pd.DataFrame:
        """Load reviews from Excel file."""
        return pd.read_excel(path, **kwargs)

    def preprocess_dataframe(
        self,
        df: pd.DataFrame,
        text_column: str = "content",
        label_column: Optional[str] = None,
        min_length: int = 5,
    ) -> pd.DataFrame:
        """Preprocess a DataFrame of reviews."""
        df = df.copy()
        df[text_column] = df[text_column].astype(str).apply(self.clean_text)

        # Remove empty or too-short reviews
        df = df[df[text_column].str.len() >= min_length]

        if label_column and label_column in df.columns:
            df = df.dropna(subset=[label_column])

        return df.reset_index(drop=True)

    @staticmethod
    def train_val_split(df: pd.DataFrame, val_ratio: float = 0.2, random_state: int = 42):
        """Split into training and validation sets."""
        from sklearn.model_selection import train_test_split
        return train_test_split(df, test_size=val_ratio, random_state=random_state)
