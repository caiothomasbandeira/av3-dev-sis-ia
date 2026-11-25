from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from threading import RLock

import pandas as pd


class RecommendationEngine:
    """Hybrid recommendation engine: content similarity plus collaborative preferences."""

    def __init__(self, csv_path: str, state_path: str) -> None:
        self.csv_path = Path(csv_path)
        self.state_path = Path(state_path)
        self._lock = RLock()
        self.users: dict[str, dict[str, object]] = {}
        self.items: dict[str, dict[str, object]] = {}
        self.preferences: dict[str, dict[str, float]] = {}
        self._load_items()
        self._load_state()
        self._build_content_index()

    def _load_items(self) -> None:
        frame = pd.read_csv(self.csv_path).fillna("")
        for row in frame.to_dict("records"):
            item_id = str(row["Id"])
            self.items[item_id] = {
                "id": item_id,
                "name": str(row["Name"]),
                "authors": str(row["Authors"]),
                "publisher": str(row["Publisher"]),
                "language": str(row["Language"]),
                "year": int(row["PublishYear"]) if str(row["PublishYear"]).strip() else None,
                "pages": int(row["pagesNumber"]) if str(row["pagesNumber"]).strip() else None,
                "rating": float(row["Rating"]),
                "isbn": str(row["ISBN"]) or None,
            }

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        with self.state_path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        self.users = state.get("users", {})
        self.preferences = state.get("preferences", {})
        for item in state.get("items", []):
            item_id = str(item["id"])
            self.items[item_id] = item

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        base_item_ids = set(self._dataset_item_ids)
        custom_items = [item for item_id, item in self.items.items() if item_id not in base_item_ids]
        state = {"users": self.users, "preferences": self.preferences, "items": custom_items}
        temporary = self.state_path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
        temporary.replace(self.state_path)

    @property
    def _dataset_item_ids(self) -> set[str]:
        frame = pd.read_csv(self.csv_path, usecols=["Id"])
        return set(frame["Id"].astype(str))

    def _build_content_index(self) -> None:
        self.item_ids = list(self.items)
        token_documents: dict[str, list[str]] = {}
        document_frequency: Counter[str] = Counter()

        for item_id in self.item_ids:
            item = self.items[item_id]
            text = " ".join([
                str(item["name"]),
                str(item["authors"]),
                str(item["publisher"]),
                str(item["language"]),
            ])
            tokens = [token for token in re.findall(r"[\wÀ-ÿ]+", text.lower()) if len(token) > 1]
            token_documents[item_id] = tokens
            document_frequency.update(set(tokens))

        document_count = len(self.item_ids)
        self._item_vectors: dict[str, dict[str, float]] = {}
        for item_id, tokens in token_documents.items():
            counts = Counter(tokens)
            vector: dict[str, float] = {}
            for token, count in counts.items():
                inverse_frequency = math.log((document_count + 1) / (document_frequency[token] + 1)) + 1
                vector[token] = (count / len(tokens)) * inverse_frequency
            self._item_vectors[item_id] = vector

    def add_user(self, user_id: str, name: str, preferences: dict[str, float] | None = None) -> dict:
        with self._lock:
            if user_id in self.users:
                raise ValueError("Usuário já existe")
            valid_preferences = self._validate_preferences(preferences or {})
            self.users[user_id] = {"id": user_id, "name": name}
            self.preferences[user_id] = valid_preferences
            self._save_state()
            return {**self.users[user_id], "preferences": valid_preferences}

    def get_user(self, user_id: str) -> dict:
        if user_id not in self.users:
            raise KeyError("Usuário não encontrado")
        return {**self.users[user_id], "preferences": self.preferences.get(user_id, {})}

    def list_users(self) -> list[dict]:
        return [self.get_user(user_id) for user_id in self.users]

    def add_item(self, item: dict) -> dict:
        with self._lock:
            item_id = str(item["id"])
            if item_id in self.items:
                raise ValueError("Item já existe")
            normalized = {
                "id": item_id,
                "name": item["name"],
                "authors": item.get("authors", ""),
                "publisher": item.get("publisher", ""),
                "language": item.get("language", ""),
                "year": item.get("year"),
                "pages": item.get("pages"),
                "rating": item.get("rating", 0.0),
                "isbn": item.get("isbn"),
            }
            self.items[item_id] = normalized
            self._build_content_index()
            self._save_state()
            return normalized

    def list_items(self, limit: int = 100, offset: int = 0) -> list[dict]:
        values = list(self.items.values())
        return values[offset:offset + limit]

    def update_preferences(self, user_id: str, preferences: dict[str, float]) -> dict:
        with self._lock:
            if user_id not in self.users:
                raise KeyError("Usuário não encontrado")
            valid = self._validate_preferences(preferences)
            self.preferences.setdefault(user_id, {}).update(valid)
            self._save_state()
            return self.get_user(user_id)

    def _validate_preferences(self, preferences: dict[str, float]) -> dict[str, float]:
        valid: dict[str, float] = {}
        for item_id, rating in preferences.items():
            item_id = str(item_id)
            if item_id not in self.items:
                raise ValueError(f"Item inexistente: {item_id}")
            if not 0 <= float(rating) <= 5:
                raise ValueError("Avaliação deve estar entre 0 e 5")
            valid[item_id] = float(rating)
        return valid

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        if len(left) > len(right):
            left, right = right, left
        dot = sum(value * right.get(token, 0.0) for token, value in left.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    def recommend(self, user_id: str, limit: int = 10) -> list[dict]:
        if user_id not in self.users:
            raise KeyError("Usuário não encontrado")

        user_preferences = self.preferences.get(user_id, {})
        rated_ids = set(user_preferences)
        scores: dict[str, float] = {}

        # Conteúdo: pondera itens semelhantes aos itens preferidos pelo usuário.
        if user_preferences:
            for rated_id, rating in user_preferences.items():
                if rated_id not in self.item_ids:
                    continue
                rated_vector = self._item_vectors[rated_id]
                weight = (rating - 2.5) / 2.5
                for item_id in self.item_ids:
                    similarity = self._cosine(rated_vector, self._item_vectors[item_id])
                    if item_id not in rated_ids:
                        scores[item_id] = scores.get(item_id, 0.0) + weight * similarity

        # Colaborativo: usuários semelhantes recebem peso nas suas avaliações.
        collaborative = self._collaborative_scores(user_id)
        for item_id, score in collaborative.items():
            if item_id not in rated_ids:
                scores[item_id] = scores.get(item_id, 0.0) + 0.6 * score

        # Popularidade/avaliação global como fallback e para desempate.
        for item_id in self.item_ids:
            if item_id in rated_ids:
                continue
            if item_id not in scores:
                scores[item_id] = float(self.items[item_id].get("rating", 0.0)) / 5.0

        ranked = sorted(scores, key=lambda item_id: (-scores[item_id], -float(self.items[item_id].get("rating", 0)), str(item_id)))
        recommendations = []
        for item_id in ranked[:limit]:
            recommendations.append({**self.items[item_id], "score": round(float(scores[item_id]), 4)})
        return recommendations

    def _collaborative_scores(self, user_id: str) -> dict[str, float]:
        target = self.preferences.get(user_id, {})
        if not target:
            return {}

        target_items = set(target)
        similarities: list[tuple[float, dict[str, float]]] = []
        for other_id, other_prefs in self.preferences.items():
            if other_id == user_id:
                continue
            common = target_items.intersection(other_prefs)
            if not common:
                continue
            target_vector = [target[item_id] for item_id in common]
            other_vector = [other_prefs[item_id] for item_id in common]
            dot = sum(a * b for a, b in zip(target_vector, other_vector))
            norm = (sum(a * a for a in target_vector) * sum(b * b for b in other_vector)) ** 0.5
            similarity = dot / norm if norm else 0.0
            if similarity > 0:
                similarities.append((similarity, other_prefs))

        result: dict[str, float] = {}
        if not similarities:
            return result
        for similarity, other_prefs in similarities:
            for item_id, rating in other_prefs.items():
                if item_id not in target:
                    result[item_id] = result.get(item_id, 0.0) + similarity * (rating / 5.0)
        return result
