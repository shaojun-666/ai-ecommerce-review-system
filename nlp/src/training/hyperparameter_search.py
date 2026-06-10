"""Optuna-based hyperparameter search for BERT fine-tuning."""
import os
import json
import logging
from typing import Optional, Callable

import optuna
from optuna.trial import Trial
import numpy as np

from src.models.bert.config import BERTConfig

logger = logging.getLogger(__name__)


def _create_trial_config(trial: Trial, base_config: Optional[BERTConfig] = None) -> BERTConfig:
    """Sample hyperparameters from the search space."""
    cfg = base_config or BERTConfig()

    cfg.learning_rate = trial.suggest_float("learning_rate", 5e-6, 5e-5, log=True)
    cfg.batch_size = trial.suggest_categorical("batch_size", [16, 32, 64])
    cfg.warmup_ratio = trial.suggest_float("warmup_ratio", 0.0, 0.3)
    cfg.hidden_dropout = trial.suggest_float("hidden_dropout", 0.1, 0.5)
    cfg.weight_decay = trial.suggest_float("weight_decay", 0.0, 0.1)
    cfg.max_length = trial.suggest_categorical("max_length", [128, 256])
    cfg.epochs = trial.suggest_int("epochs", 3, 8)

    return cfg


def objective(
    trial: Trial,
    train_fn: Callable,
    train_data,
    val_data=None,
    base_config: Optional[BERTConfig] = None,
) -> float:
    """Optuna objective function.

    Args:
        trial: Optuna trial object.
        train_fn: Training function that takes (config, train_data, val_data) and returns
                  a dict with at least an "accuracy" or "f1" key.
        train_data: Training data (path or DataFrame).
        val_data: Validation data (path or DataFrame), optional.
        base_config: Base configuration to override.

    Returns:
        Validation accuracy (higher is better).
    """
    config = _create_trial_config(trial, base_config)

    try:
        result = train_fn(config=config, train_data=train_data, val_data=val_data)

        # Accept either "accuracy" or "f1" as the optimization metric
        metric = result.get("eval_accuracy") or result.get("accuracy") or result.get("eval_f1") or 0.0

        # Report intermediate values for pruning
        if "history" in result:
            for step, acc in enumerate(result["history"]):
                trial.report(acc, step)
                if trial.should_prune():
                    raise optuna.TrialPruned()

        return float(metric)
    except Exception as e:
        logger.error("Trial failed: %s", e)
        raise optuna.TrialPruned(f"Trial failed: {e}")


def run_hyperparameter_search(
    train_fn: Callable,
    train_data,
    val_data=None,
    base_config: Optional[BERTConfig] = None,
    n_trials: int = 20,
    study_name: str = "bert-sentiment-search",
    storage: Optional[str] = None,
    direction: str = "maximize",
    timeout: Optional[int] = None,
    n_jobs: int = 1,
    seed: int = 42,
) -> optuna.Study:
    """Run hyperparameter search with Optuna.

    Args:
        train_fn: Training function signature (config, train_data, val_data) -> dict.
        train_data: Training data path or DataFrame.
        val_data: Validation data path or DataFrame.
        base_config: Base BERTConfig to start from.
        n_trials: Number of trials to run.
        study_name: Name for the Optuna study.
        storage: Database URL for persistent storage (e.g., "sqlite:///optuna.db").
                 If None, uses in-memory storage.
        direction: "maximize" or "minimize".
        timeout: Time limit in seconds (None = no limit).
        n_jobs: Number of parallel trials.
        seed: Random seed for reproducibility.

    Returns:
        Completed Optuna study with best parameters.
    """
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    # Pruner: Median pruner stops unpromising trials early
    pruner = optuna.pruners.MedianPruner(
        n_startup_trials=5,
        n_warmup_steps=2,
        interval_steps=1,
    )

    # Sampler: TPE with seed for reproducibility
    sampler = optuna.samplers.TPESampler(seed=seed)

    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        load_if_exists=True,
        direction=direction,
        pruner=pruner,
        sampler=sampler,
    )

    logger.info("Starting hyperparameter search: %d trials, %d jobs", n_trials, n_jobs)
    study.optimize(
        lambda trial: objective(trial, train_fn, train_data, val_data, base_config),
        n_trials=n_trials,
        timeout=timeout,
        n_jobs=n_jobs,
    )

    logger.info("Search completed. Best trial: %s", study.best_trial.params)
    return study


def save_study_results(study: optuna.Study, output_dir: str):
    """Save Optuna study results to disk.

    Saves best parameters, all trial results, and optimization history.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Best parameters
    best = {
        "best_params": study.best_trial.params,
        "best_value": study.best_trial.value,
        "best_trial_number": study.best_trial.number,
    }
    with open(os.path.join(output_dir, "best_params.json"), "w") as f:
        json.dump(best, f, indent=2, ensure_ascii=False)

    # All trials
    trials = []
    for t in study.trials:
        trials.append({
            "number": t.number,
            "params": t.params,
            "value": t.value,
            "state": str(t.state),
            "duration": t.duration.total_seconds() if t.duration else None,
        })
    with open(os.path.join(output_dir, "all_trials.json"), "w") as f:
        json.dump(trials, f, indent=2, ensure_ascii=False)

    logger.info("Study results saved to %s (best: %.4f)", output_dir, study.best_trial.value)


def update_config_from_study(config: BERTConfig, study: optuna.Study) -> BERTConfig:
    """Update a BERTConfig with the best parameters from a study."""
    best = study.best_trial.params
    config.learning_rate = best.get("learning_rate", config.learning_rate)
    config.batch_size = best.get("batch_size", config.batch_size)
    config.warmup_ratio = best.get("warmup_ratio", config.warmup_ratio)
    config.hidden_dropout = best.get("hidden_dropout", config.hidden_dropout)
    config.weight_decay = best.get("weight_decay", config.weight_decay)
    config.max_length = best.get("max_length", config.max_length)
    config.epochs = best.get("epochs", config.epochs)
    logger.info("Config updated with best params: %s", best)
    return config
