from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FactorResult:
    factor_id: str
    firing: bool
    strength: float  # 0.0–1.0
    label: str
    detail: dict = field(default_factory=dict)
    narrative: str = ""

    def __post_init__(self) -> None:
        self.strength = max(0.0, min(1.0, self.strength))

    @classmethod
    def no_data(cls, factor_id: str, reason: str = "data unavailable") -> "FactorResult":
        return cls(
            factor_id=factor_id,
            firing=False,
            strength=0.0,
            label="NO DATA",
            narrative=reason,
        )


VALID_FACTOR_IDS = {"macro_regime", "technical", "gex", "flow", "dormant", "sentiment"}
