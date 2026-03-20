from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class DomainMessageBuilder:
    @staticmethod
    def build_confirmation(message: str) -> str:
        return "CONFIRMACION: " + message

    @staticmethod
    def build_error(message: str) -> str:
        return "ERROR: " + message


@dataclass
class Partido:
    codigo: str
    nombre: str
    sigla: str

    def get_identificador_presentacion(self) -> str:
        if self.sigla:
            return self.sigla
        return self.nombre


@dataclass
class ResultadoPartido:
    partido: Partido
    votos: int
    escanos_oficiales: int = 0
    escanos_calculados: int = 0

    @property
    def diferencia_escanos(self) -> int:
        return self.escanos_calculados - self.escanos_oficiales


@dataclass
class Circunscripcion:
    codigo: str
    nombre: str
    provincia: str
    comunidad_autonoma: str
    escanos_oficiales_totales: int
    votos_totales_candidaturas_oficiales: Optional[int] = None
    resultados_por_partido: Dict[str, ResultadoPartido] = field(default_factory=dict)

    def agregar_resultado(self, resultado: ResultadoPartido) -> str:
        identificador = resultado.partido.codigo
        if resultado.votos <= 0:
            return DomainMessageBuilder.build_confirmation(
                "Se omitio el resultado del partido {0} en {1} por tener 0 votos.".format(
                    resultado.partido.get_identificador_presentacion(), self.nombre
                )
            )
        self.resultados_por_partido[identificador] = resultado
        return DomainMessageBuilder.build_confirmation(
            "Se registro el resultado del partido {0} en la circunscripcion {1}.".format(
                resultado.partido.get_identificador_presentacion(), self.nombre
            )
        )

    def obtener_resultados_ordenados_por_votos(self) -> List[ResultadoPartido]:
        resultados = list(self.resultados_por_partido.values())
        resultados.sort(key=lambda elemento: (-elemento.votos, elemento.partido.nombre))
        return resultados

    @property
    def total_votos_validos_calculado(self) -> int:
        acumulado = 0
        for resultado in self.resultados_por_partido.values():
            acumulado = acumulado + resultado.votos
        return acumulado

    @property
    def total_escanos_calculados(self) -> int:
        acumulado = 0
        for resultado in self.resultados_por_partido.values():
            acumulado = acumulado + resultado.escanos_calculados
        return acumulado

    @property
    def total_escanos_oficiales(self) -> int:
        acumulado = 0
        for resultado in self.resultados_por_partido.values():
            acumulado = acumulado + resultado.escanos_oficiales
        return acumulado

    def obtener_porcentaje_partido(self, codigo_partido: str) -> float:
        if codigo_partido not in self.resultados_por_partido:
            return 0.0
        total_votos = self.total_votos_validos_calculado
        if total_votos == 0:
            return 0.0
        votos = self.resultados_por_partido[codigo_partido].votos
        return (float(votos) / float(total_votos)) * 100.0


@dataclass
class EleccionCongreso2023:
    nombre: str
    archivo_origen: str
    partidos: Dict[str, Partido] = field(default_factory=dict)
    circunscripciones: Dict[str, Circunscripcion] = field(default_factory=dict)
    metadatos_columnas: Dict[str, str] = field(default_factory=dict)

    def registrar_partido(self, partido: Partido) -> str:
        if partido.codigo in self.partidos:
            partido_existente = self.partidos[partido.codigo]
            if not partido_existente.nombre and partido.nombre:
                partido_existente.nombre = partido.nombre
            if not partido_existente.sigla and partido.sigla:
                partido_existente.sigla = partido.sigla
            return DomainMessageBuilder.build_confirmation(
                "Se reutilizo el partido {0}.".format(partido.codigo)
            )
        self.partidos[partido.codigo] = partido
        return DomainMessageBuilder.build_confirmation(
            "Se registro el partido {0}.".format(partido.codigo)
        )

    def registrar_circunscripcion(self, circunscripcion: Circunscripcion) -> str:
        self.circunscripciones[circunscripcion.codigo] = circunscripcion
        return DomainMessageBuilder.build_confirmation(
            "Se registro la circunscripcion {0}.".format(circunscripcion.nombre)
        )

    def obtener_circunscripciones_ordenadas(self) -> List[Circunscripcion]:
        elementos = list(self.circunscripciones.values())
        elementos.sort(key=lambda circunscripcion: circunscripcion.nombre)
        return elementos

    def obtener_partidos_ordenados(self) -> List[Partido]:
        elementos = list(self.partidos.values())
        elementos.sort(key=lambda partido: partido.nombre)
        return elementos

    def obtener_resultados_de_partido(self, codigo_partido: str) -> List[ResultadoPartido]:
        resultados: List[ResultadoPartido] = []
        for circunscripcion in self.circunscripciones.values():
            if codigo_partido in circunscripcion.resultados_por_partido:
                resultados.append(circunscripcion.resultados_por_partido[codigo_partido])
        resultados.sort(key=lambda resultado: (-resultado.votos, resultado.partido.nombre))
        return resultados

    def obtener_resumen_nacional_por_partido(self) -> List[Dict[str, object]]:
        resumen: Dict[str, Dict[str, object]] = {}
        for circunscripcion in self.circunscripciones.values():
            for resultado in circunscripcion.resultados_por_partido.values():
                codigo = resultado.partido.codigo
                if codigo not in resumen:
                    resumen[codigo] = {
                        "codigo": codigo,
                        "nombre": resultado.partido.nombre,
                        "sigla": resultado.partido.sigla,
                        "votos": 0,
                        "escanos_oficiales": 0,
                        "escanos_calculados": 0,
                    }
                resumen[codigo]["votos"] = int(resumen[codigo]["votos"]) + resultado.votos
                resumen[codigo]["escanos_oficiales"] = int(resumen[codigo]["escanos_oficiales"]) + resultado.escanos_oficiales
                resumen[codigo]["escanos_calculados"] = int(resumen[codigo]["escanos_calculados"]) + resultado.escanos_calculados
        lista = list(resumen.values())
        lista.sort(key=lambda elemento: (-int(elemento["votos"]), str(elemento["nombre"])))
        return lista
