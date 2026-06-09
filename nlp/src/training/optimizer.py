"""Optimizer and learning rate scheduler configuration."""
from transformers import AdamW, get_linear_schedule_with_warmup


def create_optimizer(model, learning_rate: float = 2e-5, weight_decay: float = 0.01):
    no_decay = ["bias", "LayerNorm.weight"]
    optimizer_grouped_parameters = [
        {
            "params": [
                p for n, p in model.named_parameters()
                if not any(nd in n for nd in no_decay)
            ],
            "weight_decay": weight_decay,
        },
        {
            "params": [
                p for n, p in model.named_parameters()
                if any(nd in n for nd in no_decay)
            ],
            "weight_decay": 0.0,
        },
    ]
    return AdamW(optimizer_grouped_parameters, lr=learning_rate)


def create_scheduler(optimizer, train_steps: int, warmup_ratio: float = 0.1):
    warmup_steps = int(train_steps * warmup_ratio)
    return get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=train_steps,
    )
