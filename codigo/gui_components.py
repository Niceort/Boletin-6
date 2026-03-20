from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk
from tkinter import Canvas

from electoral_services import CoalitionPactometer, TerritorialPartyView, TerritorialViewData


class PoliticalColorManager:
    def __init__(self) -> None:
        self.color_by_code: Dict[str, str] = {
            "PP": "#1E5AA8",
            "PSOE": "#C62828",
            "VOX": "#2E7D32",
            "SUMAR": "#D81B60",
            "PODEMOS": "#6A1B9A",
            "ERC": "#F9A825",
            "JUNTS": "#00ACC1",
            "EH BILDU": "#43A047",
            "EAJ-PNV": "#2E7D32",
            "BNG": "#4CAF50",
            "CCA": "#F57C00",
            "UPN": "#004D99",
        }
        self.default_color = "#607D8B"

    def resolve_color(self, party_view: TerritorialPartyView) -> str:
        candidates: List[str] = []
        if party_view.sigla_partido != "":
            candidates.append(party_view.sigla_partido.upper())
        if party_view.nombre_partido != "":
            candidates.append(party_view.nombre_partido.upper())
        if party_view.codigo_partido != "":
            candidates.append(party_view.codigo_partido.upper())
        for candidate in candidates:
            if candidate in self.color_by_code:
                return self.color_by_code[candidate]
        return self.default_color

    def build_color_map(self, parties: List[TerritorialPartyView]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for party_view in parties:
            mapping[party_view.codigo_partido] = self.resolve_color(party_view)
        return mapping


class PartyBlockWidget(ctk.CTkFrame):
    def __init__(
        self,
        master,
        party_view: TerritorialPartyView,
        color_hex: str,
        block_size: Tuple[int, int],
        drag_start_callback: Callable[["PartyBlockWidget", int, int], None],
        drag_move_callback: Callable[["PartyBlockWidget", int, int], None],
        drag_release_callback: Callable[["PartyBlockWidget", int, int], None],
    ) -> None:
        super().__init__(master, fg_color=color_hex, corner_radius=18, width=block_size[0], height=block_size[1])
        self.party_view = party_view
        self.color_hex = color_hex
        self.block_size = block_size
        self.drag_start_callback = drag_start_callback
        self.drag_move_callback = drag_move_callback
        self.drag_release_callback = drag_release_callback
        self.grid_propagate(False)
        self._build_content()
        self._bind_drag_events(self)

    def _build_content(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        title = self.party_view.sigla_partido if self.party_view.sigla_partido != "" else self.party_view.nombre_partido
        text = "{0}\n{1} escaños\n{2:.2f}% voto".format(
            title,
            self.party_view.escanos_visibles,
            self.party_view.porcentaje_voto,
        )
        label = ctk.CTkLabel(
            self,
            text=text,
            justify="center",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#FFFFFF",
            wraplength=max(110, self.block_size[0] - 24),
        )
        label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._bind_drag_events(label)

    def _bind_drag_events(self, widget) -> None:
        widget.bind("<ButtonPress-1>", self._on_drag_start)
        widget.bind("<B1-Motion>", self._on_drag_motion)
        widget.bind("<ButtonRelease-1>", self._on_drag_release)

    def _on_drag_start(self, event) -> None:
        self.drag_start_callback(self, event.x_root, event.y_root)

    def _on_drag_motion(self, event) -> None:
        self.drag_move_callback(self, event.x_root, event.y_root)

    def _on_drag_release(self, event) -> None:
        self.drag_release_callback(self, event.x_root, event.y_root)


class PactometerWidget(ctk.CTkFrame):
    def __init__(
        self,
        master,
        coalition_model: CoalitionPactometer,
        remove_callback: Callable[[str], None],
    ) -> None:
        super().__init__(master, corner_radius=18)
        self.coalition_model = coalition_model
        self.remove_callback = remove_callback
        self.current_view: Optional[TerritorialViewData] = None
        self.color_map: Dict[str, str] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.title_label = ctk.CTkLabel(self, text="Pactómetro", font=ctk.CTkFont(size=18, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self.summary_label = ctk.CTkLabel(self, text="Coalición vacía")
        self.summary_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

        self.canvas = Canvas(self, height=110, highlightthickness=0, background="#F5F7FA")
        self.canvas.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 10))

        self.party_button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.party_button_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

    def set_context(self, view_data: TerritorialViewData, color_map: Dict[str, str]) -> None:
        self.current_view = view_data
        self.color_map = color_map
        self.refresh()

    def refresh(self) -> None:
        self._draw_pactometer_bar()
        self._refresh_party_buttons()

    def is_point_inside_drop_zone(self, x_root: int, y_root: int) -> bool:
        left = self.canvas.winfo_rootx()
        top = self.canvas.winfo_rooty()
        right = left + self.canvas.winfo_width()
        bottom = top + self.canvas.winfo_height()
        return x_root >= left and x_root <= right and y_root >= top and y_root <= bottom

    def _draw_pactometer_bar(self) -> None:
        self.canvas.delete("all")
        if self.current_view is None:
            return
        width = self.canvas.winfo_width()
        if width <= 10:
            width = 900
        height = self.canvas.winfo_height()
        if height <= 10:
            height = 110
        start_x = 20
        end_x = width - 20
        bar_width = end_x - start_x
        start_y = 36
        end_y = 76

        self.canvas.create_rectangle(start_x, start_y, end_x, end_y, fill="#DDE4EC", outline="#B0BEC5", width=2)

        threshold_ratio = 0.0
        if self.current_view.escanos_totales > 0:
            threshold_ratio = float(self.current_view.mayoria_necesaria) / float(self.current_view.escanos_totales)
        threshold_x = start_x + int(bar_width * threshold_ratio)
        self.canvas.create_line(threshold_x, start_y - 10, threshold_x, end_y + 10, fill="#D32F2F", width=3, dash=(6, 6))
        self.canvas.create_text(threshold_x + 6, start_y - 16, anchor="w", text="Mayoría {0}".format(self.current_view.mayoria_necesaria), fill="#B71C1C")

        current_x = start_x
        for party_view in self.coalition_model.selected_parties.values():
            seat_ratio = 0.0
            if self.current_view.escanos_totales > 0:
                seat_ratio = float(party_view.escanos_visibles) / float(self.current_view.escanos_totales)
            segment_width = int(bar_width * seat_ratio)
            if segment_width < 8 and party_view.escanos_visibles > 0:
                segment_width = 8
            segment_end_x = min(end_x, current_x + segment_width)
            color = self.color_map.get(party_view.codigo_partido, "#607D8B")
            self.canvas.create_rectangle(current_x, start_y, segment_end_x, end_y, fill=color, outline="#FFFFFF", width=2)
            label = party_view.sigla_partido if party_view.sigla_partido != "" else party_view.nombre_partido
            self.canvas.create_text((current_x + segment_end_x) / 2, (start_y + end_y) / 2, text=label, fill="#FFFFFF")
            current_x = segment_end_x
            if current_x >= end_x:
                break

        total = self.coalition_model.get_total_seats()
        majority_text = "Sí" if self.coalition_model.has_majority(self.current_view.mayoria_necesaria) else "No"
        labels = self.coalition_model.get_party_labels()
        labels_text = ", ".join(labels) if len(labels) > 0 else "Ninguno"
        self.summary_label.configure(
            text="Coalición: {0} escaños de {1}. Mayoría alcanzada: {2}. Partidos: {3}".format(
                total,
                self.current_view.escanos_totales,
                majority_text,
                labels_text,
            )
        )

    def _refresh_party_buttons(self) -> None:
        for widget in self.party_button_frame.winfo_children():
            widget.destroy()
        parties = list(self.coalition_model.selected_parties.values())
        parties.sort(key=lambda item: (-item.escanos_visibles, item.nombre_partido))
        if len(parties) == 0:
            empty_label = ctk.CTkLabel(self.party_button_frame, text="Arrastra partidos aquí para formar una coalición.")
            empty_label.pack(anchor="w")
            return
        for party_view in parties:
            label = party_view.sigla_partido if party_view.sigla_partido != "" else party_view.nombre_partido
            button = ctk.CTkButton(
                self.party_button_frame,
                text="Quitar {0}".format(label),
                fg_color=self.color_map.get(party_view.codigo_partido, "#607D8B"),
                command=lambda code=party_view.codigo_partido: self.remove_callback(code),
            )
            button.pack(side="left", padx=6, pady=4)
