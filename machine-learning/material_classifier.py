import hashlib
import sqlite3
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms
from torchvision.models import resnet18, ResNet18_Weights


class PredictionCache:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path), timeout=30)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=30000")
        self.connection.execute("CREATE TABLE IF NOT EXISTS predictions (model_hash TEXT NOT NULL, input_hash TEXT NOT NULL, probabilities BLOB NOT NULL, PRIMARY KEY (model_hash, input_hash))")
        self.connection.commit()

    def get(self, model_hash, input_hash, count):
        row = self.connection.execute("SELECT probabilities FROM predictions WHERE model_hash = ? AND input_hash = ?", (model_hash, input_hash)).fetchone()
        if row is None:
            return None
        values = np.frombuffer(row[0], dtype=np.float32).copy()
        return values if len(values) == count else None

    def put(self, model_hash, input_hash, probabilities):
        values = np.asarray(probabilities, dtype=np.float32)
        self.connection.execute("INSERT OR REPLACE INTO predictions (model_hash, input_hash, probabilities) VALUES (?, ?, ?)", (model_hash, input_hash, values.tobytes()))
        self.connection.commit()

    def close(self):
        self.connection.close()


def checkpoint_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MaterialClassifier:
    def __init__(self, model_paths, device, method="soft", cache_path="outputs/prediction_cache.sqlite", tie_tolerance=0.005):
        if method not in ("soft", "hard"):
            raise ValueError("method must be 'soft' or 'hard'")
        if not model_paths:
            raise ValueError("At least one model must be selected")

        self.device = device
        self.method = method
        self.tie_tolerance = tie_tolerance
        self.cache = PredictionCache(cache_path) if cache_path is not None else None
        self.hits = 0
        self.misses = 0
        self.models = []
        common_transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

        for name, model_path in model_paths.items():
            checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
            classes = [str(value).strip().lower() for value in checkpoint["classes"]]
            if len(set(classes)) != len(classes):
                raise ValueError(f"Duplicate material labels after normalization in {model_path}")

            model = resnet18(weights=None)
            model.fc = nn.Linear(model.fc.in_features, len(classes))
            model.load_state_dict(checkpoint["model_state_dict"])
            model = model.to(device)
            model.eval()

            transform = ResNet18_Weights.DEFAULT.transforms() if name in ("minc", "minc_legacy") else common_transform
            self.models.append({"name": name, "model": model, "classes": classes, "transform": transform, "hash": checkpoint_hash(model_path)})

        self.classes = sorted(set().union(*(item["classes"] for item in self.models)))
    #check the database if a prediction exists, then load it, otherwise run Resnet18 and store the result as a hash.
    def _model_probabilities(self, item, image):
        tensor = item["transform"](image.convert("RGB")).unsqueeze(0).contiguous()
        input_hash = hashlib.sha256(tensor.numpy().tobytes()).hexdigest()

        if self.cache is not None:
            cached = self.cache.get(item["hash"], input_hash, len(item["classes"]))
            if cached is not None:
                self.hits += 1
                return cached

        self.misses += 1
        with torch.inference_mode():
            logits = item["model"](tensor.to(self.device))
            probabilities = torch.softmax(logits, dim=1)[0].float().cpu().numpy().astype(np.float32)

        if self.cache is not None:
            self.cache.put(item["hash"], input_hash, probabilities)
        return probabilities

    #Two options here: Soft voting or Winner takes all.
    def predict(self, image):
        model_outputs = []
        for item in self.models:
            values = self._model_probabilities(item, image)
            model_outputs.append((item, values))

        if self.method == "soft":
            scores = {label: 0.0 for label in self.classes}
            for item, values in model_outputs:
                for label, value in zip(item["classes"], values):
                    scores[label] += float(value) / len(model_outputs)
            tied_materials = []
        else:
            leaders = []
            for item, values in model_outputs:
                index = int(np.argmax(values))
                leaders.append((float(values[index]), item["classes"][index], item, values))

            leaders.sort(key=lambda candidate: (-candidate[0], candidate[1], candidate[2]["name"]))
            best_score, best_label, chosen, chosen_values = leaders[0]
            tied_materials = sorted({label for score, label, _, _ in leaders if best_score - score <= self.tie_tolerance})
            if len(tied_materials) < 2:
                tied_materials = []
            scores = {label: 0.0 for label in self.classes}

            for item, values in model_outputs:
                for label, value in zip(item["classes"], values):
                    scores[label] = max(scores[label], float(value))

        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return ranked, tied_materials

    def close(self):
        if self.cache is not None:
            self.cache.close()
