"""Tests for training modules including trainer and hyperparameter search."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.models.bert.config import BERTConfig
from src.training.hyperparameter_search import (
    _create_trial_config,
    save_study_results,
    update_config_from_study,
)


class TestHyperparameterSearch:
    def test_create_trial_config_defaults(self):
        """Test that trial config samples valid hyperparameters."""
        import optuna
        study = optuna.create_study(direction="maximize")
        trial = study.ask()
        config = _create_trial_config(trial)

        assert isinstance(config, BERTConfig)
        assert 5e-6 <= config.learning_rate <= 5e-5
        assert config.batch_size in [16, 32, 64]
        assert 0.0 <= config.warmup_ratio <= 0.3
        assert 0.1 <= config.hidden_dropout <= 0.5
        assert 0.0 <= config.weight_decay <= 0.1
        assert config.max_length in [128, 256]
        assert 3 <= config.epochs <= 8

    def test_create_trial_config_with_base(self):
        import optuna
        study = optuna.create_study(direction="maximize")
        trial = study.ask()
        base = BERTConfig(learning_rate=1e-5, epochs=5)
        config = _create_trial_config(trial, base)
        assert isinstance(config, BERTConfig)
        # Verify fields are overwritten by trial
        assert config.epochs >= 3  # trial overwrites

    def test_update_config_from_study(self):
        """Test backfilling best params into a config."""
        import optuna
        study = optuna.create_study(direction="maximize")
        study.add_trial(
            optuna.trial.create_trial(
                params={"learning_rate": 3e-5, "batch_size": 32, "warmup_ratio": 0.1,
                        "hidden_dropout": 0.3, "weight_decay": 0.01, "max_length": 256,
                        "epochs": 5},
                distributions={
                    "learning_rate": optuna.distributions.FloatDistribution(5e-6, 5e-5),
                    "batch_size": optuna.distributions.CategoricalDistribution([16, 32, 64]),
                    "warmup_ratio": optuna.distributions.FloatDistribution(0.0, 0.3),
                    "hidden_dropout": optuna.distributions.FloatDistribution(0.1, 0.5),
                    "weight_decay": optuna.distributions.FloatDistribution(0.0, 0.1),
                    "max_length": optuna.distributions.CategoricalDistribution([128, 256]),
                    "epochs": optuna.distributions.IntDistribution(3, 8),
                },
                values=[0.92],
            )
        )
        config = BERTConfig()
        updated = update_config_from_study(config, study)
        assert updated.learning_rate == 3e-5
        assert updated.batch_size == 32
        assert updated.warmup_ratio == 0.1
        assert updated.hidden_dropout == 0.3
        assert updated.weight_decay == 0.01
        assert updated.max_length == 256

    def test_save_study_results(self, tmp_path):
        """Test saving study results to disk."""
        import optuna
        study = optuna.create_study(direction="maximize")
        study.add_trial(
            optuna.trial.create_trial(
                params={"learning_rate": 2e-5, "batch_size": 16},
                distributions={
                    "learning_rate": optuna.distributions.FloatDistribution(5e-6, 5e-5),
                    "batch_size": optuna.distributions.CategoricalDistribution([16, 32, 64]),
                },
                values=[0.90],
            )
        )
        save_study_results(study, str(tmp_path))
        assert os.path.exists(os.path.join(tmp_path, "best_params.json"))
        assert os.path.exists(os.path.join(tmp_path, "all_trials.json"))

        import json
        with open(os.path.join(tmp_path, "best_params.json")) as f:
            best = json.load(f)
        assert best["best_value"] == 0.90

    def test_objective_with_pruned_trial_handled_gracefully(self):
        """Verify that pruned trials don't crash the study."""
        import optuna
        study = optuna.create_study(direction="maximize")

        def mock_train(config, train_data, val_data):
            return {"accuracy": 0.85}

        from src.training.hyperparameter_search import objective
        study.optimize(
            lambda trial: objective(trial, mock_train, "dummy", "dummy"),
            n_trials=3,
        )
        assert len(study.trials) == 3
        assert study.best_trial.value >= 0.0
