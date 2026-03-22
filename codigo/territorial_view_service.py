from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models import Circunscripcion, EleccionCongreso2023


GENERAL_VIEW_CODE = "GENERAL"


@dataclass
class TerritorialPartySummary:
    codigo: str
    nombre: str
    sigla: str
    votos: int
    escanos_oficiales: int
    escanos_calculados: int

    @property
    def etiqueta(self) -> str:
        if self.sigla:
            return self.sigla
        return self.nombre


@dataclass
class TerritorialViewSummary:
    codigo: str
    nombre: str
    total_votos: int
    total_escanos_oficiales: int
    total_escanos_calculados: int
    mayoria_necesaria: int
    porcentaje_peso_escanos: float
    es_general: bool
    partidos: List[TerritorialPartySummary] = field(default_factory=list)

    @property
    def total_escanos_vista(self) -> int:
        return self.total_escanos_oficiales

    @property
    def partidos_visibles(self) -> List[TerritorialPartySummary]:
        visibles: List[TerritorialPartySummary] = []
        for partido in self.partidos:
            if partido.escanos_oficiales > 0:
                visibles.append(partido)
        return visibles

    @property
    def resumen_general_filtrado_sin_ceros(self) -> List[TerritorialPartySummary]:
        return self.partidos_visibles


class TerritorialViewService:
    def build_selector_options(self, election: EleccionCongreso2023) -> List[str]:
        options: List[str] = []
        general_view = self.build_general_view(election)
        options.append(self.build_selector_label(general_view))
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            territorial_view = self.build_circunscription_view(election, circunscripcion.codigo)
            options.append(self.build_selector_label(territorial_view))
        return options

    def build_selector_label(self, territorial_view: TerritorialViewSummary) -> str:
        return "{0} — {1:.2f}%".format(territorial_view.nombre, territorial_view.porcentaje_peso_escanos)

    def extract_code_from_selector_value(self, selector_value: str) -> str:
        if " — " in selector_value:
            territory_name = selector_value.split(" — ", 1)[0].strip()
        else:
            territory_name = selector_value.strip()
        if territory_name.upper() == "GENERAL":
            return GENERAL_VIEW_CODE
        return territory_name

    def build_view(self, election: EleccionCongreso2023, territory_code: str) -> TerritorialViewSummary:
        if territory_code == GENERAL_VIEW_CODE:
            return self.build_general_view(election)
        return self.build_circunscription_view(election, territory_code)

    def build_general_view(self, election: EleccionCongreso2023) -> TerritorialViewSummary:
        national_total_seats = self._get_national_total_official_seats(election)
        grouped_parties: Dict[str, TerritorialPartySummary] = {}
        total_votes = 0
        total_calculated_seats = 0

        for circunscripcion in election.circunscripciones.values():
            total_votes = total_votes + circunscripcion.total_votos_validos_calculado
            total_calculated_seats = total_calculated_seats + circunscripcion.total_escanos_calculados
            for resultado in circunscripcion.resultados_por_partido.values():
                if resultado.partido.codigo not in grouped_parties:
                    grouped_parties[resultado.partido.codigo] = TerritorialPartySummary(
                        codigo=resultado.partido.codigo,
                        nombre=resultado.partido.nombre,
                        sigla=resultado.partido.sigla,
                        votos=0,
                        escanos_oficiales=0,
                        escanos_calculados=0,
                    )
                summary = grouped_parties[resultado.partido.codigo]
                summary.votos = summary.votos + resultado.votos
                summary.escanos_oficiales = summary.escanos_oficiales + resultado.escanos_oficiales
                summary.escanos_calculados = summary.escanos_calculados + resultado.escanos_calculados

        partidos = list(grouped_parties.values())
        self._sort_party_summaries(partidos)
        return TerritorialViewSummary(
            codigo=GENERAL_VIEW_CODE,
            nombre="General",
            total_votos=total_votes,
            total_escanos_oficiales=national_total_seats,
            total_escanos_calculados=total_calculated_seats,
            mayoria_necesaria=self.calculate_majority_threshold(national_total_seats, True),
            porcentaje_peso_escanos=100.0,
            es_general=True,
            partidos=partidos,
        )

    def build_circunscription_view(self, election: EleccionCongreso2023, territory_code: str) -> TerritorialViewSummary:
        circunscripcion = self._find_circunscription(election, territory_code)
        national_total_seats = self._get_national_total_official_seats(election)
        partidos: List[TerritorialPartySummary] = []
        for resultado in circunscripcion.obtener_resultados_ordenados_por_votos():
            partidos.append(
                TerritorialPartySummary(
                    codigo=resultado.partido.codigo,
                    nombre=resultado.partido.nombre,
                    sigla=resultado.partido.sigla,
                    votos=resultado.votos,
                    escanos_oficiales=resultado.escanos_oficiales,
                    escanos_calculados=resultado.escanos_calculados,
                )
            )
        self._sort_party_summaries(partidos)
        return TerritorialViewSummary(
            codigo=circunscripcion.codigo,
            nombre=circunscripcion.nombre,
            total_votos=circunscripcion.total_votos_validos_calculado,
            total_escanos_oficiales=circunscripcion.escanos_oficiales_totales,
            total_escanos_calculados=circunscripcion.total_escanos_calculados,
            mayoria_necesaria=self.calculate_majority_threshold(circunscripcion.escanos_oficiales_totales, False),
            porcentaje_peso_escanos=self.calculate_seat_weight_percentage(
                circunscripcion.escanos_oficiales_totales,
                national_total_seats,
            ),
            es_general=False,
            partidos=partidos,
        )

    def calculate_seat_weight_percentage(self, territory_seats: int, national_total_seats: int) -> float:
        if national_total_seats <= 0:
            return 0.0
        return (float(territory_seats) / float(national_total_seats)) * 100.0

    def calculate_majority_threshold(self, total_seats: int, is_general: bool) -> int:
        if is_general:
            return 176
        return (total_seats // 2) + 1

    def _get_national_total_official_seats(self, election: EleccionCongreso2023) -> int:
        total_seats = 0
        for circunscripcion in election.circunscripciones.values():
            total_seats = total_seats + circunscripcion.escanos_oficiales_totales
        return total_seats

    def _find_circunscription(self, election: EleccionCongreso2023, territory_code: str) -> Circunscripcion:
        if territory_code in election.circunscripciones:
            return election.circunscripciones[territory_code]
        for circunscripcion in election.circunscripciones.values():
            if circunscripcion.nombre == territory_code:
                return circunscripcion
        raise KeyError("No se encontro la circunscripcion: {0}".format(territory_code))

    def _sort_party_summaries(self, partidos: List[TerritorialPartySummary]) -> None:
        partidos.sort(key=lambda item: (-item.escanos_oficiales, -item.votos, item.etiqueta))
