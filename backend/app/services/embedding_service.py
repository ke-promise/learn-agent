from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from app.core.config import settings


class EmbeddingService:
    """轻量 embedding 服务。

    这个项目没有接真实 Embedding API，而是用哈希向量做一个本地可运行实现。
    它的目标不是替代专业向量模型，而是让 RAG、Memory 和 pgvector 链路都能跑通。
    """

    def __init__(self, dimensions: int | None = None) -> None:
        self.dimensions = dimensions or settings.embedding_dimensions

    def embed_text(self, text: str) -> list[float]:
        """把文本映射成固定维度向量。"""
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dimensions

        counts = Counter(tokens)
        vector = [0.0] * self.dimensions
        total = sum(counts.values()) or 1

        # 这里采用最简单的“token 哈希桶”策略：
        # 同一个 token 总是落到同一个桶，统计频次后再归一化。
        for token, count in counts.items():
            vector[hash(token) % self.dimensions] += count / total
        return self._normalize(vector)

    def similarity(self, left: list[float] | dict[str, float], right: list[float] | dict[str, float]) -> float:
        """计算两个向量的余弦相似度。"""
        left_vector = self._coerce(left)
        right_vector = self._coerce(right)
        numerator = sum(a * b for a, b in zip(left_vector, right_vector))
        left_norm = math.sqrt(sum(v * v for v in left_vector))
        right_norm = math.sqrt(sum(v * v for v in right_vector))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _coerce(self, value: list[float] | dict[str, float]) -> list[float]:
        """把输入统一转换成固定维度向量。

        这样做是为了兼容：
        - 已经是向量列表的数据
        - 类似 `{token: score}` 的稀疏结构
        """
        if isinstance(value, list):
            if len(value) == self.dimensions:
                return value
            result = [0.0] * self.dimensions
            for index, item in enumerate(value[: self.dimensions]):
                result[index] = float(item)
            return result

        vector = [0.0] * self.dimensions
        for token, score in value.items():
            vector[hash(token) % self.dimensions] += float(score)
        return self._normalize(vector)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """做一个足够轻量的中英文分词。

        中文按单字切，英文和数字按词切。对当前 Demo 来说已经够用。
        """
        return re.findall(r'[\u4e00-\u9fff]|[a-z0-9_]+', text.lower())

    @staticmethod
    def _normalize(vector: Iterable[float]) -> list[float]:
        items = list(vector)
        norm = math.sqrt(sum(v * v for v in items))
        if norm == 0:
            return items
        return [v / norm for v in items]