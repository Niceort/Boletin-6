from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from party_color_registry import PartyColorRegistry
from territorial_view_service import TerritorialPartySummary, TerritorialViewSummary


@dataclass
class PartyBlockLayout:
    codigo: str
    etiqueta: str
    escanos: int
    votos: int
    fill_color: str
    border_color: str
    x0: float
    y0: float
    x1: float
    y1: float

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


class ResultsBlocksCanvas(tk.Canvas):
    def __init__(
        self,
        master,
        color_registry: PartyColorRegistry,
        drop_callback: Callable[[str, int, int], None],
        status_callback: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(master, highlightthickness=0, **kwargs)
        self.color_registry = color_registry
        self.drop_callback = drop_callback
        self.status_callback = status_callback
        self.current_view: Optional[TerritorialViewSummary] = None
        self.layouts: List[PartyBlockLayout] = []
        self.dragging_party_code: Optional[str] = None
        self.dragging_overlay_id: Optional[int] = None
        self.dragging_text_id: Optional[int] = None
        self.vertical_scrollbar: Optional[tk.Scrollbar] = None

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_resize)

    def attach_scrollbar(self, scrollbar: tk.Scrollbar) -> None:
        self.vertical_scrollbar = scrollbar
        self.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=self.yview)

    def render_view(self, territorial_view: TerritorialViewSummary) -> None:
        self.current_view = territorial_view
        self.delete("all")
        self.layouts = []
        visible_parties = territorial_view.partidos_visibles
        if len(visible_parties) == 0:
            self.create_text(
                24,
                24,
                anchor="nw",
                text="No hay partidos con escaños oficiales en esta vista.",
                fill="#F5F5F5",
                font=("Arial", 14, "bold"),
            )
            self.configure(scrollregion=(0, 0, self.winfo_width(), 120))
            return

        self._build_layouts(visible_parties)
        self._draw_layouts()

    def _build_layouts(self, parties: List[TerritorialPartySummary]) -> None:
        self.layouts = []
        width = max(self.winfo_width(), 760)
        available_width = max(width - 36, 360)
        x = 18.0
        y = 18.0
        row_height = 0.0
        max_seats = max(party.escanos_oficiales for party in parties)

        for party in parties:
            side = self._calculate_block_side(party.escanos_oficiales, max_seats)
            if x + side > available_width:
                x = 18.0
                y = y + row_height + 18.0
                row_height = 0.0
            fill_color, border_color = self.color_registry.get_party_colors(
                party.codigo,
                party.nombre,
                party.etiqueta,
            )
            self.layouts.append(
                PartyBlockLayout(
                    codigo=party.codigo,
                    etiqueta=party.etiqueta,
                    escanos=party.escanos_oficiales,
                    votos=party.votos,
                    fill_color=fill_color,
                    border_color=border_color,
                    x0=x,
                    y0=y,
                    x1=x + side,
                    y1=y + side,
                )
            )
            x = x + side + 18.0
            if side > row_height:
                row_height = side

        total_height = y + row_height + 24.0
        self.configure(scrollregion=(0, 0, available_width + 20, total_height))

    def _calculate_block_side(self, seats: int, max_seats: int) -> float:
        minimum_side = 98.0
        maximum_side = 180.0
        if max_seats <= 0:
            return minimum_side
        ratio = math.sqrt(float(seats) / float(max_seats))
        return minimum_side + ((maximum_side - minimum_side) * ratio)

    def _draw_layouts(self) -> None:
        self.delete("all")
        for layout in self.layouts:
            self.create_rectangle(
                layout.x0,
                layout.y0,
                layout.x1,
                layout.y1,
                fill=layout.fill_color,
                outline=layout.border_color,
                width=3,
                tags=("party_block", layout.codigo),
            )
            center_x = (layout.x0 + layout.x1) / 2.0
            center_y = (layout.y0 + layout.y1) / 2.0
            self.create_text(
                center_x,
                center_y - 18,
                text=layout.etiqueta,
                fill="#FFFFFF",
                font=("Arial", 14, "bold"),
                width=max((layout.x1 - layout.x0) - 20, 60),
            )
            self.create_text(
                center_x,
                center_y + 12,
                text="{0} escaños".format(layout.escanos),
                fill="#F4F4F4",
                font=("Arial", 12),
            )

    def _get_layout_at(self, x: float, y: float) -> Optional[PartyBlockLayout]:
        for layout in self.layouts:
            adjusted_y = float(self.canvasy(y))
            if layout.contains(x, adjusted_y):
                return layout
        return None

    def _on_press(self, event) -> None:
        layout = self._get_layout_at(float(event.x), float(event.y))
        if layout is None:
            self.dragging_party_code = None
            return
        self.dragging_party_code = layout.codigo
        self._clear_drag_overlay()
        self.dragging_overlay_id = self.create_rectangle(
            event.x - 70,
            self.canvasy(event.y) - 28,
            event.x + 70,
            self.canvasy(event.y) + 28,
            fill=layout.fill_color,
            outline=layout.border_color,
            dash=(4, 2),
            width=2,
        )
        self.dragging_text_id = self.create_text(
            event.x,
            self.canvasy(event.y),
            text=layout.etiqueta,
            fill="#FFFFFF",
            font=("Arial", 12, "bold"),
        )
        self.status_callback("Arrastrando {0} hacia el pactómetro.".format(layout.etiqueta))

    def _on_drag(self, event) -> None:
        if self.dragging_party_code is None:
            return
        if self.dragging_overlay_id is None or self.dragging_text_id is None:
            return
        current_y = self.canvasy(event.y)
        self.coords(self.dragging_overlay_id, event.x - 70, current_y - 28, event.x + 70, current_y + 28)
        self.coords(self.dragging_text_id, event.x, current_y)

    def _on_release(self, event) -> None:
        if self.dragging_party_code is None:
            self._clear_drag_overlay()
            return
        root_x = self.winfo_rootx() + event.x
        root_y = self.winfo_rooty() + event.y
        party_code = self.dragging_party_code
        self._clear_drag_overlay()
        self.dragging_party_code = None
        self.drop_callback(party_code, root_x, root_y)

    def _clear_drag_overlay(self) -> None:
        if self.dragging_overlay_id is not None:
            self.delete(self.dragging_overlay_id)
            self.dragging_overlay_id = None
        if self.dragging_text_id is not None:
            self.delete(self.dragging_text_id)
            self.dragging_text_id = None

    def _on_resize(self, _event) -> None:
        if self.current_view is not None:
            self.render_view(self.current_view)


class PactometerWidget(tk.Canvas):
    def __init__(self, master, color_registry: PartyColorRegistry, remove_callback: Callable[[str], None], **kwargs) -> None:
        super().__init__(master, highlightthickness=0, **kwargs)
        self.color_registry = color_registry
        self.remove_callback = remove_callback
        self.current_view: Optional[TerritorialViewSummary] = None
        self.coalition_parties: List[TerritorialPartySummary] = []
        self.segment_lookup: Dict[int, str] = {}
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", self._on_resize)

    def render(self, territorial_view: Optional[TerritorialViewSummary], coalition_parties: List[TerritorialPartySummary]) -> None:
        self.current_view = territorial_view
        self.coalition_parties = coalition_parties
        self.delete("all")
        self.segment_lookup = {}

        width = max(self.winfo_width(), 720)
        height = max(self.winfo_height(), 140)
        margin = 24
        bar_top = 46
        bar_bottom = 92
        bar_left = margin
        bar_right = width - margin
        self.create_rectangle(bar_left, bar_top, bar_right, bar_bottom, fill="#ECEFF1", outline="#90A4AE", width=2)

        if territorial_view is None or territorial_view.total_escanos_vista <= 0:
            self.create_text(margin, 20, anchor="w", text="Pactómetro no disponible.", fill="#FAFAFA", font=("Arial", 12, "bold"))
            return

        total_seats = territorial_view.total_escanos_vista
        current_x = float(bar_left)
        available_width = float(bar_right - bar_left)
        coalition_total = 0
        for party in coalition_parties:
            coalition_total = coalition_total + party.escanos_oficiales
            segment_width = available_width * (float(party.escanos_oficiales) / float(total_seats))
            fill_color, border_color = self.color_registry.get_party_colors(party.codigo, party.nombre, party.etiqueta)
            rect_id = self.create_rectangle(current_x, bar_top, current_x + segment_width, bar_bottom, fill=fill_color, outline=border_color, width=2)
            self.segment_lookup[rect_id] = party.codigo
            self.create_text(
                current_x + (segment_width / 2.0),
                (bar_top + bar_bottom) / 2.0,
                text="{0}\n{1}".format(party.etiqueta, party.escanos_oficiales),
                fill="#FFFFFF",
                font=("Arial", 10, "bold"),
                width=max(segment_width - 8, 30),
            )
            current_x = current_x + segment_width

        majority_x = bar_left + (available_width * (float(territorial_view.mayoria_necesaria) / float(total_seats)))
        self.create_line(majority_x, bar_top - 16, majority_x, bar_bottom + 16, fill="#D32F2F", width=3, dash=(8, 4))
        self.create_text(majority_x, bar_top - 22, text="Mayoría {0}".format(territorial_view.mayoria_necesaria), fill="#FFCDD2", font=("Arial", 10, "bold"))

        status_text = "Coalición actual: {0} / {1} escaños".format(coalition_total, total_seats)
        self.create_text(margin, 18, anchor="w", text=status_text, fill="#FAFAFA", font=("Arial", 13, "bold"))
        if coalition_total >= territorial_view.mayoria_necesaria:
            majority_text = "Mayoría alcanzada"
            majority_color = "#A5D6A7"
        else:
            missing_seats = territorial_view.mayoria_necesaria - coalition_total
            majority_text = "Faltan {0} escaños".format(missing_seats)
            majority_color = "#FFE082"
        self.create_text(margin, 118, anchor="w", text=majority_text, fill=majority_color, font=("Arial", 12, "bold"))
        self.create_text(bar_right, 118, anchor="e", text="Haz clic sobre un segmento para quitarlo.", fill="#CFD8DC", font=("Arial", 11))

    def is_inside_widget(self, root_x: int, root_y: int) -> bool:
        left = self.winfo_rootx()
        right = left + self.winfo_width()
        top = self.winfo_rooty()
        bottom = top + self.winfo_height()
        return left <= root_x <= right and top <= root_y <= bottom

    def _on_click(self, event) -> None:
        clicked_items = self.find_overlapping(event.x, event.y, event.x, event.y)
        for item_id in clicked_items:
            if item_id in self.segment_lookup:
                self.remove_callback(self.segment_lookup[item_id])
                return

    def _on_resize(self, _event) -> None:
        if self.current_view is not None:
            self.render(self.current_view, self.coalition_parties)
