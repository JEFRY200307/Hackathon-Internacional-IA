from __future__ import annotations

import json
import math
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings

_TOKEN = re.compile(r"[a-záéíóúñ0-9]+", re.I)


class RagIndex:
    def __init__(self) -> None:
        self.docs: list[dict] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._embeddings: np.ndarray | None = None

    def build(self, alerts: list[dict], patients: list[dict], rules: list[str], variables: list[dict]) -> None:
        self.docs = []
        for alert in alerts:
            body = {
                "title": alert["title"],
                "level": alert["level"],
                "pattern": alert["pattern"],
                "evidence": alert["evidence"],
                "missing_sources": alert["missing_sources"],
                "score": alert["score"],
            }
            self.docs.append(
                {
                    "id": f"alert:{alert['id']}",
                    "kind": "alert",
                    "patient_id": alert["patient_id"],
                    "title": f"{alert['id']} {alert['patient_id']} {alert['level']} {alert['title']}",
                    "text": json.dumps(body, ensure_ascii=False),
                }
            )
        for p in patients:
            self.docs.append(
                {
                    "id": f"patient:{p['patient_id']}",
                    "kind": "patient",
                    "patient_id": p["patient_id"],
                    "title": f"Paciente {p['patient_id']} {p.get('care_program', '')} {p.get('region_type', '')}".strip(),
                    "text": json.dumps(p, ensure_ascii=False),
                }
            )
        for i, rule in enumerate(rules, start=1):
            self.docs.append(
                {
                    "id": f"rule:R-{i:02d}",
                    "kind": "rule",
                    "patient_id": None,
                    "title": f"Regla R-{i:02d}",
                    "text": rule,
                }
            )
        for var in variables:
            self.docs.append(
                {
                    "id": f"var:{var['key']}",
                    "kind": "variable",
                    "patient_id": None,
                    "title": var["name"],
                    "text": json.dumps(var, ensure_ascii=False),
                }
            )
        corpus = [f"{d['title']} {d['text']}" for d in self.docs]
        self._vectorizer = TfidfVectorizer(min_df=1, token_pattern=_TOKEN.pattern)
        self._matrix = self._vectorizer.fit_transform(corpus)
        self._embeddings = None
        if settings.openai_api_key:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=settings.openai_api_key)
                response = client.embeddings.create(model="text-embedding-3-small", input=corpus)
                self._embeddings = np.array([item.embedding for item in response.data], dtype=float)
            except Exception:
                self._embeddings = None

    def search(
        self,
        query: str,
        k: int = 4,
        *,
        patient_ids: set[str] | None = None,
    ) -> list[dict]:
        if not self.docs:
            return []
        candidates = [
            index
            for index, doc in enumerate(self.docs)
            if patient_ids is None
            or doc["kind"] in {"rule", "variable"}
            or doc.get("patient_id") in patient_ids
        ]
        if not candidates:
            return []
        if self._embeddings is not None and settings.openai_api_key:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=settings.openai_api_key)
                q = client.embeddings.create(model="text-embedding-3-small", input=[query])
                qv = np.array(q.data[0].embedding, dtype=float)
                matrix = self._embeddings[candidates]
                sims = matrix @ qv / (
                    np.linalg.norm(matrix, axis=1) * (np.linalg.norm(qv) + 1e-9) + 1e-9
                )
                order = np.argsort(-sims)[:k]
                return [self._hit(candidates[int(i)], float(sims[int(i)])) for i in order]
            except Exception:
                pass
        assert self._vectorizer is not None and self._matrix is not None
        q = self._vectorizer.transform([query])
        sims = cosine_similarity(q, self._matrix[candidates]).ravel()
        order = np.argsort(-sims)[:k]
        return [self._hit(candidates[int(i)], float(sims[int(i)])) for i in order]

    def _hit(self, i: int, score: float) -> dict:
        doc = self.docs[i]
        snippet = doc["text"][:420]
        return {
            "source_id": doc["id"],
            "kind": doc["kind"],
            "patient_id": doc["patient_id"],
            "title": doc["title"],
            "snippet": snippet,
            "score": round(float(score) if math.isfinite(score) else 0.0, 4),
        }


RULES_TEXT = [
    "PROGRESSIVE_MULTISOURCE: se marca cuando hay tendencia en una vital (FC o presión sistólica) Y un marcador de laboratorio (LAB_A..D) en la misma ventana, ambos por encima/debajo del percentil calibrado sobre la población de RISA Data V1.0. No es un umbral estático de una sola variable.",
    "CONTEXTUAL: FC alta solo coincide con ACTIVITY_LEVEL alto (wearable); en reposo la FC es la esperada. Se DESCARTA, no se oculta, se explica con ambas fuentes.",
    "TRANSIENT: 1–2 outliers de FC que vuelven a la mediana, sin pendiente sostenida, se DESCARTA como ruido de una sola lectura.",
    "LOW_QUALITY: si el signal_quality_index del dispositivo es consistentemente bajo, la señal se DESCARTA en vez de escalarse a CRITICAL sin corroborar (gestión de falsas alertas).",
    "EARLY_SIGNAL: SpO2 con pendiente negativa combinada con FR en aumento (ambas fuera del percentil poblacional calibrado), o temperatura y FC medias ambas en el extremo alto de la población.",
    "MISSING_SOURCE: si falta laboratorio se informa explícitamente; no se inventan valores (RF-08).",
    "Los umbrales de 'cambio significativo' se calibran en cada corrida contra el percentil 90/10 de la propia población de RISA (no son constantes clínicas fijas).",
    "El prototipo no diagnostica ni prescribe (RN-03). Score y nivel son prioridad de revisión, no certeza clínica.",
]
