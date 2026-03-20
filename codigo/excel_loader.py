from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from openpyxl import load_workbook

from models import Circunscripcion, EleccionCongreso2023, Partido, ResultadoPartido


class ExcelStructureError(Exception):
    pass


class ElectionDataLoader:
    def __init__(self, excel_path: str) -> None:
        self.excel_path = excel_path
        self.column_aliases = {
            "circunscripcion_codigo": [
                "codprovincia",
                "cod_provincia",
                "codigo_provincia",
                "cod circunscripcion",
                "codcircunscripcion",
                "codigo circunscripcion",
                "circunscripcion codigo",
            ],
            "circunscripcion_nombre": [
                "provincia",
                "nombre provincia",
                "circunscripcion",
                "nombre circunscripcion",
                "provincia circunscripcion",
            ],
            "comunidad_autonoma": [
                "comunidad autonoma",
                "autonomia",
                "ccaa",
                "nombre comunidad autonoma",
            ],
            "partido_codigo": [
                "cod candidatura",
                "cod candidatura acumulado",
                "codpartido",
                "codigo partido",
                "codigo candidatura",
                "sigla candidatura",
                "cod cand",
            ],
            "partido_nombre": [
                "denominacion candidatura",
                "candidatura",
                "nombre candidatura",
                "partido",
                "nombre partido",
            ],
            "partido_sigla": [
                "siglas candidatura",
                "sigla",
                "siglas",
                "abreviatura candidatura",
            ],
            "votos": [
                "votos",
                "num votos",
                "votos candidatura",
                "votos obtenidos",
                "votoscand",
            ],
            "escanos_oficiales_partido": [
                "diputados",
                "escanos",
                "escanos partido",
                "diputados electos",
            ],
            "escanos_circunscripcion": [
                "numero diputados",
                "diputados a elegir",
                "escanos circunscripcion",
                "diputados circunscripcion",
                "num diputados",
            ],
            "votos_totales_candidaturas": [
                "votos a candidaturas",
                "votos candidaturas",
                "total votos candidaturas",
                "votos validos",
            ],
        }

    def load_election(self) -> Tuple[EleccionCongreso2023, List[str]]:
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(
                "No se encontro el archivo Excel en la ruta: {0}".format(self.excel_path)
            )

        rows = self._read_candidate_rows()
        if len(rows) == 0:
            raise ExcelStructureError("No se encontraron filas de datos utilizables en el Excel.")

        headers = list(rows[0].keys())
        column_mapping = self._resolve_column_mapping(headers)
        normalized_rows = self._prepare_rows(rows, column_mapping)

        election = EleccionCongreso2023(
            nombre="Elecciones generales al Congreso 2023",
            archivo_origen=self.excel_path,
            metadatos_columnas=column_mapping,
        )
        messages: List[str] = []

        for row in normalized_rows:
            circunscripcion = self._get_or_create_circunscripcion(election, row)
            partido = self._build_partido(row)
            messages.append(election.registrar_partido(partido))
            resultado = ResultadoPartido(
                partido=partido,
                votos=int(row["votos"]),
                escanos_oficiales=int(row["escanos_oficiales_partido"]),
            )
            messages.append(circunscripcion.agregar_resultado(resultado))

        return election, messages

    def _read_candidate_rows(self) -> List[Dict[str, object]]:
        workbook = load_workbook(self.excel_path, read_only=True, data_only=True)
        if len(workbook.sheetnames) == 0:
            raise ExcelStructureError("El libro Excel no contiene hojas.")

        selected_sheet_name: Optional[str] = None
        for sheet_name in workbook.sheetnames:
            lower_name = sheet_name.lower()
            if "cand" in lower_name or "part" in lower_name or "result" in lower_name:
                selected_sheet_name = sheet_name
                break
        if selected_sheet_name is None:
            selected_sheet_name = workbook.sheetnames[0]

        sheet = workbook[selected_sheet_name]
        iterator = sheet.iter_rows(values_only=True)
        try:
            header_row = next(iterator)
        except StopIteration:
            raise ExcelStructureError("La hoja seleccionada no contiene cabeceras.")

        headers: List[str] = []
        for value in header_row:
            if value is None:
                headers.append("")
            else:
                headers.append(str(value).strip())

        rows: List[Dict[str, object]] = []
        for data_row in iterator:
            row_dictionary: Dict[str, object] = {}
            is_empty = True
            for index in range(0, len(headers)):
                header = headers[index]
                value = None
                if index < len(data_row):
                    value = data_row[index]
                row_dictionary[header] = value
                if value is not None and str(value).strip() != "":
                    is_empty = False
            if not is_empty:
                rows.append(row_dictionary)
        workbook.close()
        return rows

    def _normalize_text(self, value: object) -> str:
        if value is None:
            return ""
        text = str(value).strip().lower()
        replacements = {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ü": "u",
            "ñ": "n",
            "_": " ",
            "-": " ",
            ".": " ",
            "/": " ",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        text = " ".join(text.split())
        return text

    def _resolve_column_mapping(self, headers: List[str]) -> Dict[str, str]:
        normalized_source_columns: Dict[str, str] = {}
        for column in headers:
            normalized_source_columns[self._normalize_text(column)] = str(column)

        mapping: Dict[str, str] = {}
        required_fields = [
            "circunscripcion_codigo",
            "circunscripcion_nombre",
            "partido_codigo",
            "partido_nombre",
            "votos",
            "escanos_circunscripcion",
        ]

        for logical_name, aliases in self.column_aliases.items():
            resolved = self._search_column_by_alias(normalized_source_columns, aliases)
            if resolved is not None:
                mapping[logical_name] = resolved

        missing_fields: List[str] = []
        for field_name in required_fields:
            if field_name not in mapping:
                missing_fields.append(field_name)

        if len(missing_fields) > 0:
            raise ExcelStructureError(
                "No se pudieron identificar las columnas obligatorias: {0}. Columnas encontradas: {1}".format(
                    ", ".join(missing_fields), ", ".join(headers)
                )
            )
        return mapping

    def _search_column_by_alias(
        self, normalized_source_columns: Dict[str, str], aliases: List[str]
    ) -> Optional[str]:
        for alias in aliases:
            normalized_alias = self._normalize_text(alias)
            if normalized_alias in normalized_source_columns:
                return normalized_source_columns[normalized_alias]
        for normalized_name, original_name in normalized_source_columns.items():
            for alias in aliases:
                normalized_alias = self._normalize_text(alias)
                if normalized_alias in normalized_name:
                    return original_name
        return None

    def _prepare_rows(
        self, rows: List[Dict[str, object]], column_mapping: Dict[str, str]
    ) -> List[Dict[str, object]]:
        normalized_rows: List[Dict[str, object]] = []
        for original_row in rows:
            normalized_row: Dict[str, object] = {}
            for logical_name, source_name in column_mapping.items():
                normalized_row[logical_name] = original_row.get(source_name)

            normalized_row["comunidad_autonoma"] = self._as_text(
                normalized_row.get("comunidad_autonoma", "")
            )
            normalized_row["partido_sigla"] = self._as_text(normalized_row.get("partido_sigla", ""))
            normalized_row["circunscripcion_codigo"] = self._as_text(
                normalized_row.get("circunscripcion_codigo", "")
            )
            normalized_row["partido_codigo"] = self._as_text(normalized_row.get("partido_codigo", ""))
            normalized_row["circunscripcion_nombre"] = self._as_text(
                normalized_row.get("circunscripcion_nombre", "")
            )
            normalized_row["partido_nombre"] = self._as_text(normalized_row.get("partido_nombre", ""))
            normalized_row["votos"] = self._as_integer(normalized_row.get("votos"))
            normalized_row["escanos_circunscripcion"] = self._as_integer(
                normalized_row.get("escanos_circunscripcion")
            )
            normalized_row["escanos_oficiales_partido"] = self._as_integer(
                normalized_row.get("escanos_oficiales_partido"), default_value=0
            )
            normalized_row["votos_totales_candidaturas"] = self._as_optional_integer(
                normalized_row.get("votos_totales_candidaturas")
            )

            if normalized_row["votos"] is None or normalized_row["escanos_circunscripcion"] is None:
                continue
            if int(normalized_row["votos"]) <= 0:
                continue
            if normalized_row["circunscripcion_nombre"] == "" or normalized_row["partido_nombre"] == "":
                continue
            normalized_rows.append(normalized_row)
        return normalized_rows

    def _as_text(self, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _as_integer(self, value: object, default_value: Optional[int] = None) -> Optional[int]:
        if value is None or str(value).strip() == "":
            return default_value
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default_value

    def _as_optional_integer(self, value: object) -> Optional[int]:
        return self._as_integer(value, default_value=None)

    def _get_or_create_circunscripcion(
        self, election: EleccionCongreso2023, row: Dict[str, object]
    ) -> Circunscripcion:
        codigo = str(row["circunscripcion_codigo"])
        if codigo in election.circunscripciones:
            return election.circunscripciones[codigo]

        circunscripcion = Circunscripcion(
            codigo=codigo,
            nombre=str(row["circunscripcion_nombre"]),
            provincia=str(row["circunscripcion_nombre"]),
            comunidad_autonoma=str(row.get("comunidad_autonoma", "")),
            escanos_oficiales_totales=int(row["escanos_circunscripcion"]),
            votos_totales_candidaturas_oficiales=row.get("votos_totales_candidaturas"),
        )
        election.registrar_circunscripcion(circunscripcion)
        return circunscripcion

    def _build_partido(self, row: Dict[str, object]) -> Partido:
        return Partido(
            codigo=str(row["partido_codigo"]),
            nombre=str(row["partido_nombre"]),
            sigla=str(row.get("partido_sigla", "")),
        )
