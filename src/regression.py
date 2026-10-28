"""
Panel-regression helpers. Same shape as the WB and IPEDS projects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS


@dataclass
class RegressionResult:
    name: str
    n_obs: int
    n_entities: int
    r2_within: float
    coef_table: pd.DataFrame

    def as_markdown(self) -> str:
        return (
            f"### {self.name}\n\n"
            f"- Observations: {self.n_obs:,}\n"
            f"- Entities: {self.n_entities:,}\n"
            f"- Within R²: {self.r2_within:.3f}\n\n"
            + self.coef_table.round(4).to_markdown()
        )


def _to_panel(df: pd.DataFrame, entity: str, time: str = "year") -> pd.DataFrame:
    df = df.copy()
    df[time] = pd.to_numeric(df[time], errors="coerce").astype("Int64")
    df = df.dropna(subset=[entity, time])
    return df.set_index([entity, time])


def fixed_effects_panel(
    df: pd.DataFrame,
    dependent: str,
    regressors: Iterable[str],
    entity: str = "country",
    entity_effects: bool = True,
    time_effects: bool = True,
    cluster_entity: bool = True,
    name: str = "panel",
) -> RegressionResult:
    """Two-way fixed-effects panel OLS with cluster-robust SEs."""
    panel_df = _to_panel(df, entity=entity)
    regressors = list(regressors)
    both = pd.concat([panel_df[dependent], panel_df[regressors]], axis=1).dropna()
    y = both[dependent]
    X = both[regressors]

    model = PanelOLS(y, X, entity_effects=entity_effects, time_effects=time_effects, drop_absorbed=True)
    res = model.fit(cov_type="clustered", cluster_entity=cluster_entity)

    ci = res.conf_int()
    table = pd.DataFrame({
        "coef": res.params,
        "stderr": res.std_errors,
        "tstat": res.tstats,
        "pvalue": res.pvalues,
        "ci_low": ci["lower"],
        "ci_high": ci["upper"],
    })
    return RegressionResult(
        name=name,
        n_obs=int(res.nobs),
        n_entities=int(res.entity_info.total),
        r2_within=float(res.rsquared_within),
        coef_table=table,
    )
