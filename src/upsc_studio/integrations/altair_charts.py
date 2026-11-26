"""Altair (BSD-3-Clause) Vega-Lite JSON and standalone HTML data-chart exporter."""

from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd


class AltairChartAdapter:
    """Exports publication-grade Vega-Lite specs and interactive HTML charts using installed Altair."""

    @staticmethod
    def is_available() -> bool:
        return hasattr(alt, "Chart")

    def export_bar_chart(
        self,
        out_dir: Path,
        scene_id: str,
        title: str,
        rows: list[tuple[str, float]],
        x_label: str,
        y_label: str,
        source_label: str,
    ) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame([{x_label: lbl, y_label: val} for lbl, val in rows])
        chart = (
            alt.Chart(df)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#38bdf8")
            .encode(
                x=alt.X(f"{x_label}:N", sort=None, title=x_label),
                y=alt.Y(f"{y_label}:Q", title=y_label),
                tooltip=[x_label, y_label],
            )
            .properties(
                title={"text": title, "subtitle": f"Source: {source_label}"},
                width=720,
                height=420,
            )
            .configure(background="#0f172a")
            .configure_axis(labelColor="#e2e8f0", titleColor="#f59e0b", gridColor="#334155")
            .configure_title(color="#f8fafc", subtitleColor="#94a3b8")
        )
        vl_path = out_dir / f"{scene_id}_chart.vl.json"
        html_path = out_dir / f"{scene_id}_chart.html"
        vl_path.write_text(json.dumps(chart.to_dict(), indent=2), encoding="utf-8")
        chart.save(str(html_path))
        return {"vega_lite_json": str(vl_path), "interactive_html": str(html_path)}
