"""
Pydantic models for the Plan_v3 §3.3 decision schema: BUY, SELL, HOLD, ADJUST, dispatched by
the "action" field. Used by agents/parsers.py to validate the LLM's JSON output.
See Plan_v3 §3.3.
"""
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


class BuyDecision(BaseModel):
    ticker: str
    action: Literal["BUY"]
    shares: int = Field(gt=0)
    entry_low: float = Field(gt=0)
    entry_high: float = Field(gt=0)
    stop_loss_price: float = Field(gt=0)
    target_price: float = Field(gt=0)
    pre_mortem_risk: str
    reasoning: str
    cited_metrics: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_price_logic(self) -> "BuyDecision":
        if not (0 < self.stop_loss_price < self.entry_low <= self.entry_high < self.target_price):
            raise ValueError(
                "price logic must satisfy 0 < stop_loss_price < entry_low <= entry_high < target_price"
            )
        return self


class SellDecision(BaseModel):
    ticker: str
    action: Literal["SELL"]
    reasoning: str


class HoldDecision(BaseModel):
    ticker: str
    action: Literal["HOLD"]
    reasoning: str  # one-line reason


class AdjustDecision(BaseModel):
    ticker: str
    action: Literal["ADJUST"]
    stop_loss_price: Optional[float] = None
    target_price: Optional[float] = None
    reasoning: Optional[str] = None

    @model_validator(mode="after")
    def _require_a_new_value(self) -> "AdjustDecision":
        if self.stop_loss_price is None and self.target_price is None:
            raise ValueError("ADJUST needs a new stop_loss_price and/or target_price")
        return self


DecisionUnion = Annotated[
    Union[BuyDecision, SellDecision, HoldDecision, AdjustDecision], Field(discriminator="action")
]


class DecisionBatch(BaseModel):
    decisions: List[DecisionUnion]
