from __future__ import annotations

from typing import Dict, List, Tuple


class PartyColorRegistry:
    def __init__(self) -> None:
        self.default_fill_color = "#8A8F98"
        self.default_border_color = "#5C6168"
        self._known_aliases: Dict[str, Tuple[str, str]] = {
            "VOX": ("#4CAF50", "#2E7D32"),
            "PSOE": ("#E53935", "#B71C1C"),
            "PP": ("#1976D2", "#0D47A1"),
            "SUMAR": ("#D81B60", "#880E4F"),
            "PODEMOS": ("#7B1FA2", "#4A148C"),
            "ERC": ("#FBC02D", "#F57F17"),
            "JUNTS": ("#00ACC1", "#006064"),
            "EHBILDU": ("#2E7D32", "#1B5E20"),
            "BILDU": ("#2E7D32", "#1B5E20"),
            "PNV": ("#00897B", "#004D40"),
            "EAJPNV": ("#00897B", "#004D40"),
            "BNG": ("#42A5F5", "#1565C0"),
            "CCA": ("#FFB300", "#E65100"),
            "CC": ("#FFB300", "#E65100"),
            "UPN": ("#1E88E5", "#0D47A1"),
            "PACMA": ("#66BB6A", "#2E7D32"),
            "CUP": ("#FDD835", "#F57F17"),
        }

    def get_party_colors(self, party_code: str, party_name: str, party_label: str) -> Tuple[str, str]:
        candidates = self._build_candidates(party_code, party_name, party_label)
        for candidate in candidates:
            if candidate in self._known_aliases:
                return self._known_aliases[candidate]
        return self.default_fill_color, self.default_border_color

    def _build_candidates(self, party_code: str, party_name: str, party_label: str) -> List[str]:
        candidates: List[str] = []
        for raw_value in [party_code, party_name, party_label]:
            normalized = self._normalize(raw_value)
            if normalized == "":
                continue
            candidates.append(normalized)
            parts = normalized.split()
            if len(parts) > 1:
                candidates.append("".join(parts))
        return candidates

    def _normalize(self, text: str) -> str:
        normalized = text.upper().strip()
        normalized = normalized.replace("-", " ")
        normalized = normalized.replace("_", " ")
        normalized = normalized.replace("'", "")
        normalized = normalized.replace(".", "")
        while "  " in normalized:
            normalized = normalized.replace("  ", " ")
        return normalized
