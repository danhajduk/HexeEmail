from __future__ import annotations

import json
import os
import pickle
from collections import Counter
from datetime import datetime
from pathlib import Path

from providers.gmail.runtime import GmailRuntimeLayout


class GmailTrainingModelError(RuntimeError):
    pass


class GmailTrainingModelStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.layout = GmailRuntimeLayout(runtime_dir)
        self.layout.ensure_layout()

    def status(self) -> dict[str, object]:
        meta = self._load_meta()
        if not meta:
            return {
                "trained": False,
                "trained_at": None,
                "sample_count": 0,
                "train_count": 0,
                "test_count": 0,
                "test_accuracy": None,
                "class_counts": {},
                "detail": "Model has not been trained yet.",
            }
        return {
            "trained": True,
            "trained_at": meta.get("trained_at"),
            "sample_count": int(meta.get("sample_count", 0) or 0),
            "train_count": int(meta.get("train_count", 0) or 0),
            "test_count": int(meta.get("test_count", 0) or 0),
            "test_accuracy": meta.get("test_accuracy"),
            "class_counts": meta.get("class_counts", {}),
            "detail": meta.get("detail") or "Model is available.",
        }

    def train(self, texts: list[str], labels: list[str]) -> dict[str, object]:
        if len(texts) != len(labels):
            raise GmailTrainingModelError("training texts and labels must have the same length")
        if len(texts) < 2:
            raise GmailTrainingModelError("at least two manually classified emails are required to train the model")
        if len(set(labels)) < 2:
            raise GmailTrainingModelError("training requires at least two distinct labels")

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            from sklearn.model_selection import train_test_split
            from sklearn.pipeline import Pipeline
        except ModuleNotFoundError as exc:
            raise GmailTrainingModelError("scikit-learn is required for TF-IDF + LogisticRegression training") from exc

        sample_count = len(texts)
        test_count = max(1, round(sample_count * 0.2))
        if sample_count - test_count < 2:
            raise GmailTrainingModelError("training requires enough manual classifications to support an 80/20 split")

        stratify_labels = labels if len(set(labels)) > 1 and min(Counter(labels).values()) >= 2 else None
        train_texts, test_texts, train_labels, test_labels = train_test_split(
            texts,
            labels,
            test_size=test_count,
            random_state=42,
            stratify=stratify_labels,
        )

        pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1)),
                ("logreg", LogisticRegression(max_iter=1000, class_weight="balanced")),
            ]
        )
        pipeline.fit(train_texts, train_labels)
        test_accuracy = float(pipeline.score(test_texts, test_labels)) if test_texts else None

        self.layout.training_model_path.write_bytes(pickle.dumps(pipeline))
        self._set_mode(self.layout.training_model_path, 0o600)

        class_counts = dict(Counter(labels))
        meta = {
            "trained_at": datetime.now().astimezone().isoformat(),
            "sample_count": sample_count,
            "train_count": len(train_texts),
            "test_count": len(test_texts),
            "test_accuracy": test_accuracy,
            "class_counts": class_counts,
            "detail": "TF-IDF + LogisticRegression model trained from manual classifications with an 80/20 split.",
        }
        self.layout.training_model_meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._set_mode(self.layout.training_model_meta_path, 0o600)
        return self.status()

    def predict(self, texts: list[str], *, threshold: float) -> list[dict[str, object]]:
        if not texts:
            return []
        pipeline = self._load_model()
        try:
            probabilities = pipeline.predict_proba(texts)
            classes = list(pipeline.classes_)
        except AttributeError as exc:
            raise GmailTrainingModelError("trained model does not support probability output") from exc

        results: list[dict[str, object]] = []
        for text, probs in zip(texts, probabilities, strict=False):
            del text
            best_index = max(range(len(probs)), key=lambda idx: probs[idx])
            best_label = str(classes[best_index])
            best_confidence = float(probs[best_index])
            results.append(
                {
                    "predicted_label": best_label if best_confidence >= threshold else "unknown",
                    "predicted_confidence": best_confidence,
                    "raw_predicted_label": best_label,
                }
            )
        return results

    def _load_model(self):
        if not self.layout.training_model_path.exists():
            raise GmailTrainingModelError("model has not been trained yet")
        try:
            return pickle.loads(self.layout.training_model_path.read_bytes())
        except Exception as exc:  # noqa: BLE001
            raise GmailTrainingModelError(f"training model is invalid: {exc}") from exc

    def _load_meta(self) -> dict[str, object]:
        try:
            payload = json.loads(self.layout.training_model_meta_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _set_mode(self, path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            return
