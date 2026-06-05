# -*- coding: utf-8 -*-
"""Download cross-encoder model with explicit online mode."""
import os
import sys

# Force online mode
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ["TRANSFORMERS_OFFLINE"] = "0"
os.environ["HF_DATASETS_OFFLINE"] = "0"

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("Downloading cross-encoder/ms-marco-MiniLM-L-6-v2...")

from sentence_transformers import CrossEncoder

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=256)
print("Model downloaded and loaded successfully!")

# Quick test
pairs = [("What is Python?", "Python is a programming language.")]
scores = model.predict(pairs)
print(f"Test score: {scores[0]:.4f}")
