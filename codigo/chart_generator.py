from __future__ import annotations

from typing import List

from matplotlib.figure import Figure

from models import Circunscripcion, EleccionCongreso2023


class ChartGenerator:

    def build_votes_chart(self, circunscripcion_a: Circunscripcion, circunscripcion_b: Circunscripcion) -> Figure:
        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        nombres = [circunscripcion_a.nombre, circunscripcion_b.nombre]
        votos = [
            circunscripcion_a.total_votos_validos_calculado,
            circunscripcion_b.total_votos_validos_calculado,
        ]
        axis.bar(nombres, votos, color=["#2fa572", "#f39c12"])
        axis.set_title("Comparativa de votos validos")
        axis.set_ylabel("Votos")
        figure.tight_layout()
        return figure

    def build_seats_chart(self, circunscripcion_a: Circunscripcion, circunscripcion_b: Circunscripcion) -> Figure:
        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        nombres = [circunscripcion_a.nombre, circunscripcion_b.nombre]
        escanos = [
            circunscripcion_a.total_escanos_calculados,
            circunscripcion_b.total_escanos_calculados,
        ]
        axis.bar(nombres, escanos, color=["#7b61ff", "#ff6b6b"])
        axis.set_title("Comparativa de escaños calculados")
        axis.set_ylabel("Escaños")
        figure.tight_layout()
        return figure
    def build_party_votes_chart(self, election: EleccionCongreso2023, limit: int = 10) -> Figure:
        resumen = election.obtener_resumen_nacional_por_partido()[0:limit]
        etiquetas: List[str] = []
        valores: List[int] = []
        for item in resumen:
            etiqueta = str(item["sigla"]) if str(item["sigla"]) else str(item["nombre"])
            etiquetas.append(etiqueta)
            valores.append(int(item["votos"]))

        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        axis.bar(etiquetas, valores, color="#1f6aa5")
        axis.set_title("Ranking nacional por votos")
        axis.set_ylabel("Votos")
        axis.tick_params(axis="x", rotation=30)
        figure.tight_layout()
        return figure

    def build_circunscription_seats_chart(self, circunscripcion: Circunscripcion) -> Figure:
        resultados = circunscripcion.obtener_resultados_ordenados_por_votos()
        etiquetas: List[str] = []
        valores: List[int] = []
        for resultado in resultados:
            if resultado.escanos_calculados > 0:
                etiquetas.append(resultado.partido.get_identificador_presentacion())
                valores.append(resultado.escanos_calculados)

        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        if len(valores) == 0:
            axis.text(0.5, 0.5, "Sin escaños calculados", ha="center", va="center")
            axis.axis("off")
        else:
            axis.pie(valores, labels=etiquetas, autopct="%1.0f")
            axis.set_title("Distribucion de escaños calculados en {0}".format(circunscripcion.nombre))
        figure.tight_layout()
        return figure

    def build_circunscription_comparison_chart(
        self, election: EleccionCongreso2023, codigo_a: str, codigo_b: str
    ) -> Figure:
        circ_a = election.circunscripciones[codigo_a]
        circ_b = election.circunscripciones[codigo_b]

        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        nombres = [circ_a.nombre, circ_b.nombre]
        votos = [circ_a.total_votos_validos_calculado, circ_b.total_votos_validos_calculado]
        axis.bar(nombres, votos, color=["#2fa572", "#f39c12"])
        axis.set_title("Comparativa de votos validos")
        axis.set_ylabel("Votos")
        figure.tight_layout()
        return figure
