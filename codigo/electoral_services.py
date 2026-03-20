from __future__ import annotations

from typing import Dict, List, Tuple

from models import Circunscripcion, EleccionCongreso2023, ResultadoPartido


class ValidationService:
    def validate_election(self, election: EleccionCongreso2023) -> List[str]:
        messages: List[str] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            messages.extend(self.validate_circunscription(circunscripcion))
        if len(messages) == 0:
            messages.append("CONFIRMACION: La validacion general no detecto incidencias.")
        return messages

    def validate_circunscription(self, circunscripcion: Circunscripcion) -> List[str]:
        messages: List[str] = []
        total_votos = circunscripcion.total_votos_validos_calculado
        total_oficial = circunscripcion.votos_totales_candidaturas_oficiales
        if total_oficial is not None:
            if total_votos == total_oficial:
                messages.append(
                    "CONFIRMACION: La suma de votos de {0} coincide con el total oficial ({1}).".format(
                        circunscripcion.nombre, total_oficial
                    )
                )
            else:
                messages.append(
                    "ERROR: La suma de votos de {0} es {1} y no coincide con el total oficial {2}.".format(
                        circunscripcion.nombre, total_votos, total_oficial
                    )
                )
        else:
            messages.append(
                "CONFIRMACION: La circunscripcion {0} no incluye total oficial de votos a candidaturas; se usa el total calculado {1}.".format(
                    circunscripcion.nombre, total_votos
                )
            )

        total_escanos_oficiales = circunscripcion.total_escanos_oficiales
        if total_escanos_oficiales == circunscripcion.escanos_oficiales_totales:
            messages.append(
                "CONFIRMACION: La suma de escaños oficiales por partido en {0} coincide con los {1} escaños de la circunscripcion.".format(
                    circunscripcion.nombre, circunscripcion.escanos_oficiales_totales
                )
            )
        else:
            messages.append(
                "ERROR: Los escaños oficiales por partido en {0} suman {1} y la circunscripcion declara {2}.".format(
                    circunscripcion.nombre, total_escanos_oficiales, circunscripcion.escanos_oficiales_totales
                )
            )
        return messages


class SeatCalculatorService:
    def __init__(self, threshold_percentage: float = 3.0) -> None:
        self.threshold_percentage = threshold_percentage

    def calculate_for_election(self, election: EleccionCongreso2023) -> List[str]:
        messages: List[str] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            messages.extend(self.calculate_for_circunscription(circunscripcion))
        return messages

    def calculate_for_circunscription(self, circunscripcion: Circunscripcion) -> List[str]:
        total_votos = circunscripcion.total_votos_validos_calculado
        if total_votos <= 0:
            return [
                "ERROR: No se pueden recalcular escaños en {0} porque no hay votos validos.".format(
                    circunscripcion.nombre
                )
            ]

        elegibles: List[ResultadoPartido] = []
        for resultado in circunscripcion.resultados_por_partido.values():
            porcentaje = (float(resultado.votos) / float(total_votos)) * 100.0
            resultado.escanos_calculados = 0
            if porcentaje >= self.threshold_percentage:
                elegibles.append(resultado)

        cocientes: List[Tuple[float, str]] = []
        for resultado in elegibles:
            divisor = 1
            while divisor <= circunscripcion.escanos_oficiales_totales:
                cociente = float(resultado.votos) / float(divisor)
                cocientes.append((cociente, resultado.partido.codigo))
                divisor = divisor + 1

        cocientes.sort(key=lambda item: (-item[0], item[1]))
        adjudicaciones = cocientes[0 : circunscripcion.escanos_oficiales_totales]
        for _, codigo_partido in adjudicaciones:
            circunscripcion.resultados_por_partido[codigo_partido].escanos_calculados = (
                circunscripcion.resultados_por_partido[codigo_partido].escanos_calculados + 1
            )

        return [
            "CONFIRMACION: Se recalcularon los escaños de {0} mediante D'Hondt con barrera del {1}% sobre votos validos a candidaturas.".format(
                circunscripcion.nombre, self.threshold_percentage
            )
        ]


class StatisticsService:

    def build_report(self, election: EleccionCongreso2023) -> str:
        statistics = self.build_general_statistics(election)
        lines: List[str] = []
        lines.append("RESUMEN GENERAL")
        lines.append("- Circunscripciones: {0}".format(statistics["total_circunscripciones"]))
        lines.append("- Partidos: {0}".format(statistics["total_partidos"]))
        lines.append("- Votos a candidaturas: {0}".format(statistics["total_votos"]))
        lines.append("- Escaños oficiales: {0}".format(statistics["total_escanos_oficiales"]))
        lines.append("- Escaños calculados: {0}".format(statistics["total_escanos_calculados"]))
        lines.append("")
        lines.append("TOP 10 PARTIDOS POR VOTO")
        for index, item in enumerate(statistics["ranking_partidos"][0:10], start=1):
            etiqueta = str(item["sigla"]) if str(item["sigla"]) else str(item["nombre"])
            lines.append(
                "{0}. {1}: {2} votos | {3} escaños oficiales | {4} calculados".format(
                    index,
                    etiqueta,
                    item["votos"],
                    item["escanos_oficiales"],
                    item["escanos_calculados"],
                )
            )

        diferencias = statistics["diferencias"]
        lines.append("")
        lines.append("DIFERENCIAS DE ESCAÑOS")
        if len(diferencias) == 0:
            lines.append("- No se detectaron diferencias entre escaños oficiales y calculados.")
        else:
            for item in diferencias[0:20]:
                lines.append(
                    "- {0} | {1}: oficiales={2}, calculados={3}, diferencia={4}".format(
                        item["circunscripcion"],
                        item["partido"],
                        item["oficiales"],
                        item["calculados"],
                        item["diferencia"],
                    )
                )
        return "\n".join(lines)

    def build_general_statistics(self, election: EleccionCongreso2023) -> Dict[str, object]:
        total_circunscripciones = len(election.circunscripciones)
        total_partidos = len(election.partidos)
        total_votos = 0
        total_escanos_oficiales = 0
        total_escanos_calculados = 0

        for circunscripcion in election.circunscripciones.values():
            total_votos = total_votos + circunscripcion.total_votos_validos_calculado
            total_escanos_oficiales = total_escanos_oficiales + circunscripcion.total_escanos_oficiales
            total_escanos_calculados = total_escanos_calculados + circunscripcion.total_escanos_calculados

        resumen_partidos = election.obtener_resumen_nacional_por_partido()
        diferencias = self.build_seat_differences(election)

        return {
            "total_circunscripciones": total_circunscripciones,
            "total_partidos": total_partidos,
            "total_votos": total_votos,
            "total_escanos_oficiales": total_escanos_oficiales,
            "total_escanos_calculados": total_escanos_calculados,
            "ranking_partidos": resumen_partidos,
            "diferencias": diferencias,
        }

    def build_circunscription_comparison(
        self, election: EleccionCongreso2023, circunscripcion_a: str, circunscripcion_b: str
    ) -> Dict[str, object]:
        circ_a = election.circunscripciones[circunscripcion_a]
        circ_b = election.circunscripciones[circunscripcion_b]
        return {
            "circunscripcion_a": circ_a.nombre,
            "circunscripcion_b": circ_b.nombre,
            "votos_a": circ_a.total_votos_validos_calculado,
            "votos_b": circ_b.total_votos_validos_calculado,
            "escanos_a": circ_a.total_escanos_calculados,
            "escanos_b": circ_b.total_escanos_calculados,
            "partidos_a": len(circ_a.resultados_por_partido),
            "partidos_b": len(circ_b.resultados_por_partido),
        }

    def build_seat_differences(self, election: EleccionCongreso2023) -> List[Dict[str, object]]:
        diferencias: List[Dict[str, object]] = []
        for circunscripcion in election.circunscripciones.values():
            for resultado in circunscripcion.resultados_por_partido.values():
                if resultado.diferencia_escanos != 0:
                    diferencias.append(
                        {
                            "circunscripcion": circunscripcion.nombre,
                            "partido": resultado.partido.get_identificador_presentacion(),
                            "oficiales": resultado.escanos_oficiales,
                            "calculados": resultado.escanos_calculados,
                            "diferencia": resultado.diferencia_escanos,
                        }
                    )
        diferencias.sort(key=lambda item: (-abs(int(item["diferencia"])), str(item["circunscripcion"])))
        return diferencias
