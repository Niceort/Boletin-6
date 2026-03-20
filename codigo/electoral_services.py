from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from models import Circunscripcion, DomainMessageBuilder, EleccionCongreso2023, Partido, ResultadoPartido


@dataclass
class TerritorialPartyView:
    codigo_partido: str
    nombre_partido: str
    sigla_partido: str
    votos: int
    porcentaje_voto: float
    escanos_oficiales: int
    escanos_calculados: int

    @property
    def escanos_visibles(self) -> int:
        return self.escanos_calculados


@dataclass
class TerritorialViewData:
    codigo: str
    nombre: str
    etiqueta_selector: str
    es_general: bool
    peso_escanos_porcentaje: float
    escanos_totales: int
    mayoria_necesaria: int
    total_votos: int
    partidos: List[TerritorialPartyView] = field(default_factory=list)

    @property
    def total_escanos_visibles(self) -> int:
        acumulado = 0
        for partido in self.partidos:
            acumulado = acumulado + partido.escanos_visibles
        return acumulado


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

    def build_report(self, election: EleccionCongreso2023) -> str:
        data = self.build_general_statistics(election)
        lines: List[str] = []
        lines.append("RESUMEN GENERAL")
        lines.append("- Circunscripciones cargadas: {0}".format(data["total_circunscripciones"]))
        lines.append("- Partidos detectados: {0}".format(data["total_partidos"]))
        lines.append("- Votos validos calculados: {0}".format(data["total_votos"]))
        lines.append("- Escaños oficiales acumulados: {0}".format(data["total_escanos_oficiales"]))
        lines.append("- Escaños calculados acumulados: {0}".format(data["total_escanos_calculados"]))
        lines.append("")
        lines.append("RANKING NACIONAL POR VOTOS")
        position = 1
        for item in data["ranking_partidos"]:
            lines.append(
                "{0}. {1}: {2} votos, {3} escaños oficiales, {4} escaños calculados".format(
                    position,
                    item["sigla"] if item["sigla"] != "" else item["nombre"],
                    item["votos"],
                    item["escanos_oficiales"],
                    item["escanos_calculados"],
                )
            )
            position = position + 1
            if position > 15:
                break

        lines.append("")
        lines.append("DIFERENCIAS ENTRE ESCAÑOS OFICIALES Y CALCULADOS")
        diferencias = data["diferencias"]
        if len(diferencias) == 0:
            lines.append("- No se detectaron diferencias.")
        else:
            for diferencia in diferencias[0:20]:
                lines.append(
                    "- {0} / {1}: oficiales={2}, calculados={3}, diferencia={4}".format(
                        diferencia["circunscripcion"],
                        diferencia["partido"],
                        diferencia["oficiales"],
                        diferencia["calculados"],
                        diferencia["diferencia"],
                    )
                )
        return "\n".join(lines)


class TerritorialViewAdapter:
    def build_selector_options(self, election: EleccionCongreso2023) -> List[str]:
        options: List[str] = [self._build_general_label()]
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            percentage = election.obtener_peso_circunscripcion(circunscripcion.codigo)
            options.append(
                "{0} - {1} — {2:.2f}%".format(
                    circunscripcion.codigo,
                    circunscripcion.nombre,
                    percentage,
                )
            )
        return options

    def build_view_data(self, election: EleccionCongreso2023, selection_value: str) -> TerritorialViewData:
        normalized_selection = selection_value.strip()
        if normalized_selection == "" or normalized_selection.startswith("GENERAL"):
            return self._build_general_view_data(election)
        codigo = normalized_selection.split(" - ", 1)[0]
        if codigo not in election.circunscripciones:
            return self._build_general_view_data(election)
        return self._build_circunscription_view_data(election.circunscripciones[codigo], election)

    def _build_general_label(self) -> str:
        return "GENERAL - España — 100.00%"

    def _build_general_view_data(self, election: EleccionCongreso2023) -> TerritorialViewData:
        partido_map: Dict[str, TerritorialPartyView] = {}
        total_votos = 0
        for item in election.obtener_resumen_nacional_por_partido():
            total_votos = total_votos + int(item["votos"])
        for item in election.obtener_resumen_nacional_por_partido():
            escanos_calculados = int(item["escanos_calculados"])
            if escanos_calculados <= 0:
                continue
            porcentaje_voto = 0.0
            if total_votos > 0:
                porcentaje_voto = (float(int(item["votos"])) / float(total_votos)) * 100.0
            partido_map[str(item["codigo"])] = TerritorialPartyView(
                codigo_partido=str(item["codigo"]),
                nombre_partido=str(item["nombre"]),
                sigla_partido=str(item["sigla"]),
                votos=int(item["votos"]),
                porcentaje_voto=porcentaje_voto,
                escanos_oficiales=int(item["escanos_oficiales"]),
                escanos_calculados=escanos_calculados,
            )
        partidos = list(partido_map.values())
        partidos.sort(key=lambda item: (-item.escanos_visibles, -item.votos, item.nombre_partido))
        return TerritorialViewData(
            codigo="GENERAL",
            nombre="España",
            etiqueta_selector=self._build_general_label(),
            es_general=True,
            peso_escanos_porcentaje=100.0,
            escanos_totales=election.total_escanos_nacionales,
            mayoria_necesaria=election.mayoria_absoluta_nacional,
            total_votos=total_votos,
            partidos=partidos,
        )

    def _build_circunscription_view_data(
        self, circunscripcion: Circunscripcion, election: EleccionCongreso2023
    ) -> TerritorialViewData:
        partidos: List[TerritorialPartyView] = []
        total_votos = circunscripcion.total_votos_validos_calculado
        for resultado in circunscripcion.obtener_resultados_ordenados_por_votos():
            if resultado.escanos_calculados <= 0:
                continue
            partidos.append(
                TerritorialPartyView(
                    codigo_partido=resultado.partido.codigo,
                    nombre_partido=resultado.partido.nombre,
                    sigla_partido=resultado.partido.sigla,
                    votos=resultado.votos,
                    porcentaje_voto=resultado.obtener_porcentaje_voto(total_votos),
                    escanos_oficiales=resultado.escanos_oficiales,
                    escanos_calculados=resultado.escanos_calculados,
                )
            )
        partidos.sort(key=lambda item: (-item.escanos_visibles, -item.votos, item.nombre_partido))
        return TerritorialViewData(
            codigo=circunscripcion.codigo,
            nombre=circunscripcion.nombre,
            etiqueta_selector="{0} - {1} — {2:.2f}%".format(
                circunscripcion.codigo,
                circunscripcion.nombre,
                election.obtener_peso_circunscripcion(circunscripcion.codigo),
            ),
            es_general=False,
            peso_escanos_porcentaje=election.obtener_peso_circunscripcion(circunscripcion.codigo),
            escanos_totales=circunscripcion.escanos_oficiales_totales,
            mayoria_necesaria=circunscripcion.mayoria_absoluta,
            total_votos=total_votos,
            partidos=partidos,
        )


class CoalitionPactometer:
    def __init__(self) -> None:
        self.selected_parties: Dict[str, TerritorialPartyView] = {}

    def clear(self) -> str:
        self.selected_parties = {}
        return DomainMessageBuilder.build_confirmation("Se reinicio el pactometro.")

    def add_party(self, party_view: TerritorialPartyView) -> str:
        if party_view.codigo_partido in self.selected_parties:
            return DomainMessageBuilder.build_error(
                "El partido {0} ya esta añadido al pactometro.".format(self._get_label(party_view))
            )
        self.selected_parties[party_view.codigo_partido] = party_view
        return DomainMessageBuilder.build_confirmation(
            "Se añadio el partido {0} al pactometro.".format(self._get_label(party_view))
        )

    def remove_party(self, codigo_partido: str) -> str:
        if codigo_partido not in self.selected_parties:
            return DomainMessageBuilder.build_error(
                "No se puede eliminar el partido porque no esta presente en el pactometro."
            )
        party_view = self.selected_parties.pop(codigo_partido)
        return DomainMessageBuilder.build_confirmation(
            "Se elimino el partido {0} del pactometro.".format(self._get_label(party_view))
        )

    def get_total_seats(self) -> int:
        total = 0
        for party_view in self.selected_parties.values():
            total = total + party_view.escanos_visibles
        return total

    def has_majority(self, threshold: int) -> bool:
        return self.get_total_seats() >= threshold

    def get_party_labels(self) -> List[str]:
        labels: List[str] = []
        parties = list(self.selected_parties.values())
        parties.sort(key=lambda item: (-item.escanos_visibles, item.nombre_partido))
        for party_view in parties:
            labels.append(self._get_label(party_view))
        return labels

    def _get_label(self, party_view: TerritorialPartyView) -> str:
        if party_view.sigla_partido != "":
            return party_view.sigla_partido
        return party_view.nombre_partido
