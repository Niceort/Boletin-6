from __future__ import annotations

from typing import Dict, List

from matplotlib.figure import Figure

from electoral_services import TerritorialViewData


class ChartGenerator:
    def __init__(self) -> None:
        self.default_colors: List[str] = [
            "#C62828",
            "#1565C0",
            "#2E7D32",
            "#F9A825",
            "#6A1B9A",
            "#00838F",
            "#5D4037",
            "#AD1457",
        ]

    def build_party_votes_chart(
        self, view_data: TerritorialViewData, color_map: Dict[str, str], limit: int = 10
    ) -> Figure:
        partidos = view_data.partidos[0:limit]
        etiquetas: List[str] = []
        valores: List[int] = []
        colores: List[str] = []
        for item in partidos:
            etiqueta = item.sigla_partido if item.sigla_partido != "" else item.nombre_partido
            etiquetas.append(etiqueta)
            valores.append(item.votos)
            colores.append(self._resolve_color(color_map, item.codigo_partido, len(colores)))

        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        axis.bar(etiquetas, valores, color=colores)
        axis.set_title("Votos en {0}".format(view_data.nombre))
        axis.set_ylabel("Votos")
        axis.tick_params(axis="x", rotation=25)
        figure.tight_layout()
        return figure

    def build_seats_chart(self, view_data: TerritorialViewData, color_map: Dict[str, str]) -> Figure:
        etiquetas: List[str] = []
        valores: List[int] = []
        colores: List[str] = []
        for item in view_data.partidos:
            if item.escanos_visibles <= 0:
                continue
            etiquetas.append(item.sigla_partido if item.sigla_partido != "" else item.nombre_partido)
            valores.append(item.escanos_visibles)
            colores.append(self._resolve_color(color_map, item.codigo_partido, len(colores)))

        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        if len(valores) == 0:
            axis.text(0.5, 0.5, "Sin escaños en la vista actual", ha="center", va="center")
            axis.axis("off")
        else:
            axis.bar(etiquetas, valores, color=colores)
            axis.set_title("Escaños calculados en {0}".format(view_data.nombre))
            axis.set_ylabel("Escaños")
            axis.tick_params(axis="x", rotation=25)
        figure.tight_layout()
        return figure

    def build_comparison_chart(
        self,
        view_data_a: TerritorialViewData,
        view_data_b: TerritorialViewData,
    ) -> Figure:
        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        nombres = [view_data_a.nombre, view_data_b.nombre]
        votos = [view_data_a.total_votos, view_data_b.total_votos]
        axis.bar(nombres, votos, color=["#1F6AA5", "#F39C12"])
        axis.set_title("Comparativa de votos validos")
        axis.set_ylabel("Votos")
        figure.tight_layout()
        return figure

    def _resolve_color(self, color_map: Dict[str, str], codigo_partido: str, index: int) -> str:
        if codigo_partido in color_map:
            return color_map[codigo_partido]
        return self.default_colors[index % len(self.default_colors)]
