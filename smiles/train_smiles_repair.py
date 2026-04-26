"""Train a ChemBERTa-2 based SMILES repair model.

This script uses a true denoising setup:
- noisy SMILES are fed to the encoder
- clean canonical SMILES are generated autoregressively by a lightweight decoder
- ChemBERTa-2 is used as the encoder backbone

Example:
    python smiles/train_smiles_repair.py \
        --train-file smiles/data/processed/smiles_repair_train.csv \
        --val-file smiles/data/processed/smiles_repair_val.csv \
        --output-dir smiles/runs/chemberta2_repair \
        --model-dir smiles/ChemBERTa-2 \
        --epochs 3 \
        --batch-size 16
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset
from transformers import AutoModel, AutoTokenizer, Trainer, TrainingArguments


PROMPT_TEMPLATE = "Repair SMILES: {input_smiles}"


@dataclass
class TrainConfig:
    model_dir: str
    train_file: str
    val_file: str
    output_dir: str
    max_input_length: int = 192
    max_target_length: int = 192
    batch_size: int = 16
    grad_accumulation: int = 1
    learning_rate: float = 5e-5
    weight_decay: float = 0.01
    epochs: int = 3
    warmup_ratio: float = 0.03
    max_train_samples: int = 0
    max_val_samples: int = 0
    seed: int = 42
    fp16: bool = False
    num_workers: int = 0
    decoder_layers: int = 2
    decoder_heads: int = 8
    decoder_dropout: float = 0.1


class SMILESDenoiseDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, tokenizer, max_input_length: int, max_target_length: int):
        self.frame = frame.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_input_length = max_input_length
        self.max_target_length = max_target_length
        self.bos_token_id = tokenizer.bos_token_id or tokenizer.cls_token_id
        self.eos_token_id = tokenizer.eos_token_id or tokenizer.sep_token_id
        self.pad_token_id = tokenizer.pad_token_id
        if self.pad_token_id is None:
            raise ValueError("Tokenizer must have a pad token for denoising training.")

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        row = self.frame.iloc[idx]
        noisy = str(row["input_smiles"])
        target = str(row["target_smiles"])

        enc = self.tokenizer(
            PROMPT_TEMPLATE.format(input_smiles=noisy),
            truncation=True,
            max_length=self.max_input_length,
            padding="max_length",
            return_tensors="pt",
        )
        tgt = self.tokenizer(
            target,
            truncation=True,
            max_length=self.max_target_length - 1,
            padding="max_length",
            return_tensors="pt",
        )

        decoder_input_ids = torch.full((self.max_target_length,), self.pad_token_id, dtype=torch.long)
        labels = torch.full((self.max_target_length,), -100, dtype=torch.long)

        target_ids = tgt["input_ids"].squeeze(0)
        target_mask = tgt["attention_mask"].squeeze(0)
        valid_tokens = target_ids[target_mask.bool()].tolist()
        target_seq = [self.bos_token_id] + valid_tokens + [self.eos_token_id]
        target_seq = target_seq[: self.max_target_length]
        seq_len = len(target_seq)
        decoder_input_ids[:seq_len] = torch.tensor(target_seq, dtype=torch.long)
        labels[: seq_len - 1] = torch.tensor(target_seq[1:], dtype=torch.long)
        labels[seq_len - 1] = self.eos_token_id

        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "decoder_input_ids": decoder_input_ids,
            "labels": labels,
        }


class ChemBERTaDenoiser(nn.Module):
    def __init__(self, encoder_name_or_path: str, tokenizer, decoder_layers: int = 2, decoder_heads: int = 8, decoder_dropout: float = 0.1):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(encoder_name_or_path)
        hidden_size = self.encoder.config.hidden_size
        vocab_size = len(tokenizer)
        self.token_embed = nn.Embedding(vocab_size, hidden_size)
        self.pos_embed = nn.Embedding(512, hidden_size)
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=hidden_size,
            nhead=decoder_heads,
            dim_feedforward=hidden_size * 4,
            dropout=decoder_dropout,
            batch_first=True,
        )
        self.decoder = nn.TransformerDecoder(decoder_layer, num_layers=decoder_layers)
        self.lm_head = nn.Linear(hidden_size, vocab_size, bias=False)
        self.dropout = nn.Dropout(decoder_dropout)
        self.pad_token_id = tokenizer.pad_token_id

    def forward(self, input_ids, attention_mask, decoder_input_ids, labels=None):
        enc = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        tgt_len = decoder_input_ids.size(1)
        positions = torch.arange(tgt_len, device=decoder_input_ids.device).unsqueeze(0).expand_as(decoder_input_ids)
        tgt = self.token_embed(decoder_input_ids) + self.pos_embed(positions)
        tgt = self.dropout(tgt)
        tgt_mask = nn.Transformer.generate_square_subsequent_mask(tgt_len).to(decoder_input_ids.device)
        memory_key_padding_mask = attention_mask == 0
        tgt_key_padding_mask = decoder_input_ids == self.pad_token_id
        out = self.decoder(
            tgt=tgt,
            memory=enc,
            tgt_mask=tgt_mask,
            tgt_key_padding_mask=tgt_key_padding_mask,
            memory_key_padding_mask=memory_key_padding_mask,
        )
        logits = self.lm_head(out)
        loss = None
        if labels is not None:
            loss_fn = nn.CrossEntropyLoss(ignore_index=-100)
            loss = loss_fn(logits.reshape(-1, logits.size(-1)), labels.reshape(-1))
        return {"loss": loss, "logits": logits}


class Collator:
    def __call__(self, batch):
        return {k: torch.stack([x[k] for x in batch]) for k in batch[0].keys()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train ChemBERTa-2 SMILES repair model.")
    parser.add_argument("--model-dir", type=Path, default=Path(r"C:\Users\lpz\Desktop\RetrosynthesisClaw\smiles\ChemBERTa-2"))
    parser.add_argument("--train-file", type=Path, default=Path(r"C:\Users\lpz\Desktop\RetrosynthesisClaw\smiles\data\processed\smiles_repair_train.csv"))
    parser.add_argument("--val-file", type=Path, default=Path(r"C:\Users\lpz\Desktop\RetrosynthesisClaw\smiles\data\processed\smiles_repair_val.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("smiles/runs/chemberta2_repair"))
    parser.add_argument("--max-input-length", type=int, default=192)
    parser.add_argument("--max-target-length", type=int, default=192)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--grad-accumulation", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--max-train-samples", type=int, default=0)
    parser.add_argument("--max-val-samples", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--eval-steps", type=int, default=1000)
    parser.add_argument("--save-steps", type=int, default=1000)
    parser.add_argument("--decoder-layers", type=int, default=2)
    parser.add_argument("--decoder-heads", type=int, default=8)
    return parser.parse_args()


def _load_frame(path: Path, max_samples: int) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if max_samples and max_samples > 0:
        frame = frame.head(max_samples)
    return frame


def _plot_history(history_path: Path, output_dir: Path) -> None:
    if not history_path.exists():
        return
    with history_path.open("r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if not rows:
        return
    train_steps, train_loss, eval_steps, eval_loss = [], [], [], []
    for row in rows:
        if "loss" in row and "step" in row:
            train_steps.append(row["step"])
            train_loss.append(row["loss"])
        if "eval_loss" in row and "step" in row:
            eval_steps.append(row["step"])
            eval_loss.append(row["eval_loss"])
    plt.figure(figsize=(10, 6))
    if train_steps:
        plt.plot(train_steps, train_loss, label="train_loss")
    if eval_steps:
        plt.plot(eval_steps, eval_loss, label="eval_loss")
    plt.title("Training / Validation Loss")
    plt.xlabel("step")
    plt.ylabel("loss")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "loss_curve.png", dpi=200)
    plt.close()


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    os.environ["PYTHONHASHSEED"] = str(args.seed)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "checkpoints").mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.add_special_tokens({"pad_token": "<pad>"})

    train_frame = _load_frame(args.train_file, args.max_train_samples)
    val_frame = _load_frame(args.val_file, args.max_val_samples)

    train_ds = SMILESDenoiseDataset(train_frame, tokenizer, args.max_input_length, args.max_target_length)
    val_ds = SMILESDenoiseDataset(val_frame, tokenizer, args.max_input_length, args.max_target_length)

    model = ChemBERTaDenoiser(str(args.model_dir), tokenizer, decoder_layers=args.decoder_layers, decoder_heads=args.decoder_heads)
    model.encoder.resize_token_embeddings(len(tokenizer))

    train_cfg = TrainConfig(
        model_dir=str(args.model_dir),
        train_file=str(args.train_file),
        val_file=str(args.val_file),
        output_dir=str(args.output_dir),
        max_input_length=args.max_input_length,
        max_target_length=args.max_target_length,
        batch_size=args.batch_size,
        grad_accumulation=args.grad_accumulation,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        epochs=args.epochs,
        warmup_ratio=args.warmup_ratio,
        max_train_samples=args.max_train_samples,
        max_val_samples=args.max_val_samples,
        seed=args.seed,
        fp16=args.fp16,
        num_workers=args.num_workers,
        decoder_layers=args.decoder_layers,
        decoder_heads=args.decoder_heads,
    )
    with (args.output_dir / "training_config.json").open("w", encoding="utf-8") as f:
        json.dump(asdict(train_cfg), f, ensure_ascii=False, indent=2)

    training_args = TrainingArguments(
        output_dir=str(args.output_dir / "checkpoints"),
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accumulation,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        num_train_epochs=args.epochs,
        warmup_ratio=args.warmup_ratio,
        logging_strategy="steps",
        logging_steps=50,
        eval_strategy="steps",
        eval_steps=args.eval_steps,
        save_strategy="steps",
        save_steps=args.save_steps,
        save_total_limit=2,
        report_to=[],
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        seed=args.seed,
        fp16=args.fp16,
        dataloader_num_workers=args.num_workers,
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=Collator(),
    )

    train_result = trainer.train()
    trainer.save_model(str(args.output_dir / "final_model"))
    tokenizer.save_pretrained(str(args.output_dir / "final_model"))

    eval_metrics = trainer.evaluate()
    metrics = {f"train_{k}": float(v) for k, v in train_result.metrics.items()}
    metrics.update({f"eval_{k}": float(v) if isinstance(v, (int, float, np.floating)) else v for k, v in eval_metrics.items()})

    metrics_path = args.output_dir / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    log_history_path = args.output_dir / "trainer_log_history.jsonl"
    with log_history_path.open("w", encoding="utf-8") as f:
        for row in trainer.state.log_history:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    _plot_history(log_history_path, args.output_dir)

    summary = {
        "model_dir": str(args.model_dir),
        "train_file": str(args.train_file),
        "val_file": str(args.val_file),
        "output_dir": str(args.output_dir),
        "train_rows": len(train_frame),
        "val_rows": len(val_frame),
        "max_input_length": args.max_input_length,
        "max_target_length": args.max_target_length,
        "batch_size": args.batch_size,
        "grad_accumulation": args.grad_accumulation,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "epochs": args.epochs,
        "warmup_ratio": args.warmup_ratio,
        "seed": args.seed,
        "fp16": args.fp16,
        "decoder_layers": args.decoder_layers,
        "decoder_heads": args.decoder_heads,
        "best_model_checkpoint": trainer.state.best_model_checkpoint,
        "metrics": metrics,
        "artifacts": {
            "final_model": str(args.output_dir / "final_model"),
            "loss_curve": str(args.output_dir / "loss_curve.png"),
            "metrics_json": str(metrics_path),
            "log_history_jsonl": str(log_history_path),
        },
    }
    with (args.output_dir / "run_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
