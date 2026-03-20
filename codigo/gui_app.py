from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import END, filedialog
from tkinter.scrolledtext import ScrolledText

from chart_generator import ChartGenerator
from electoral_services import (
    CoalitionPactometer,
    SeatCalculatorService,
    StatisticsService,
    TerritorialPartyView,
    TerritorialViewAdapter,
    TerritorialViewData,
    ValidationService,
)
from excel_loader import ElectionDataLoader, ExcelStructureError
from gui_components import PactometerWidget, PartyBlockWidget, PoliticalColorManager
from models import DomainMessageBuilder, EleccionCongreso2023


class ElectionAnalyzerApplication(ctk.CTk):
    def __init__(self, project_root: str, default_excel_path: str) -> None:
        super().__init__()
        self.project_root = project_root
        self.default_excel_path = default_excel_path
        self.title("Analizador de Elecciones Generales 2023")
        self.geometry("1560x980")
        self.minsize(1280, 820)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.validation_service = ValidationService()
        self.seat_calculator_service = SeatCalculatorService()
        self.statistics_service = StatisticsService()
        self.chart_generator = ChartGenerator()
        self.territorial_view_adapter = TerritorialViewAdapter()
        self.color_manager = PoliticalColorManager()
        self.pactometer_model = CoalitionPactometer()

        self.election: Optional[EleccionCongreso2023] = None
        self.current_view_data: Optional[TerritorialViewData] = None
        self.current_color_map: Dict[str, str] = {}
        self.validation_messages: List[str] = []
        self.loader_messages: List[str] = []
        self.drag_overlay: Optional[ctk.CTkLabel] = None
        self.dragged_party_widget: Optional[PartyBlockWidget] = None

        self._build_layout()
        self._show_project_structure()
        self._show_code_files()
        self.bind("<Configure>", self._on_application_resized)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header_frame.grid_columnconfigure(1, weight=1)

        title_label = ctk.CTkLabel(header_frame, text="Ruta del Excel:")
        title_label.grid(row=0, column=0, padx=8, pady=8)

        self.path_entry = ctk.CTkEntry(header_frame)
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        self.path_entry.insert(0, self.default_excel_path)

        browse_button = ctk.CTkButton(header_frame, text="Buscar Excel", command=self.browse_excel_file)
        browse_button.grid(row=0, column=2, padx=8, pady=8)

        load_button = ctk.CTkButton(header_frame, text="Cargar Excel", command=self.load_election_file)
        load_button.grid(row=0, column=3, padx=8, pady=8)

        reload_button = ctk.CTkButton(header_frame, text="Recalcular y validar", command=self.recalculate_and_validate)
        reload_button.grid(row=0, column=4, padx=8, pady=8)

        self.status_label = ctk.CTkLabel(header_frame, text="Pendiente de carga")
        self.status_label.grid(row=1, column=0, columnspan=5, sticky="w", padx=8, pady=8)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.tab_results = self.tabview.add("Resultados")
        self.tab_validations = self.tabview.add("Validaciones")
        self.tab_statistics = self.tabview.add("Estadisticas")
        self.tab_charts = self.tabview.add("Graficos")
        self.tab_structure = self.tabview.add("Estructura")
        self.tab_code = self.tabview.add("Codigo")

        self._build_results_tab()
        self._build_validation_tab()
        self._build_statistics_tab()
        self._build_charts_tab()
        self._build_structure_tab()
        self._build_code_tab()

    def _build_results_tab(self) -> None:
        self.tab_results.grid_columnconfigure(0, weight=3)
        self.tab_results.grid_columnconfigure(1, weight=2)
        self.tab_results.grid_rowconfigure(1, weight=1)
        self.tab_results.grid_rowconfigure(2, weight=0)

        filter_frame = ctk.CTkFrame(self.tab_results)
        filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=12)
        filter_frame.grid_columnconfigure(1, weight=1)

        selector_label = ctk.CTkLabel(filter_frame, text="Provincia o vista general")
        selector_label.grid(row=0, column=0, padx=8, pady=8)

        self.circunscription_selector = ctk.CTkComboBox(
            filter_frame,
            values=["GENERAL - España — 100.00%"],
            command=self.on_circunscription_selected,
            width=420,
        )
        self.circunscription_selector.grid(row=0, column=1, padx=8, pady=8, sticky="w")
        self.circunscription_selector.set("GENERAL - España — 100.00%")

        self.view_summary_label = ctk.CTkLabel(filter_frame, text="Selecciona un Excel para ver bloques y pactómetro.")
        self.view_summary_label.grid(row=0, column=2, padx=8, pady=8, sticky="w")

        self.party_blocks_scroll = ctk.CTkScrollableFrame(self.tab_results, label_text="Representación por bloques")
        self.party_blocks_scroll.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        self.party_blocks_scroll.grid_columnconfigure(0, weight=1)

        right_panel = ctk.CTkFrame(self.tab_results)
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)

        self.selection_detail_text = ScrolledText(right_panel, wrap="word")
        self.selection_detail_text.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 6))

        self.action_message_label = ctk.CTkLabel(right_panel, text="Mensajes de interacción")
        self.action_message_label.grid(row=1, column=0, sticky="nw", padx=12, pady=(6, 12))

        self.pactometer_widget = PactometerWidget(
            self.tab_results,
            coalition_model=self.pactometer_model,
            remove_callback=self.remove_party_from_pactometer,
        )
        self.pactometer_widget.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))

    def _build_validation_tab(self) -> None:
        self.validation_text = ScrolledText(self.tab_validations, wrap="word")
        self.validation_text.pack(fill="both", expand=True, padx=12, pady=12)

    def _build_statistics_tab(self) -> None:
        self.statistics_text = ScrolledText(self.tab_statistics, wrap="word")
        self.statistics_text.pack(fill="both", expand=True, padx=12, pady=12)

    def _build_charts_tab(self) -> None:
        self.tab_charts.grid_columnconfigure(0, weight=1)
        self.tab_charts.grid_rowconfigure(1, weight=1)

        controls = ctk.CTkFrame(self.tab_charts)
        controls.grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        self.compare_a_selector = ctk.CTkComboBox(controls, values=["GENERAL - España — 100.00%"], width=300)
        self.compare_a_selector.grid(row=0, column=0, padx=8, pady=8)
        self.compare_b_selector = ctk.CTkComboBox(controls, values=["GENERAL - España — 100.00%"], width=300)
        self.compare_b_selector.grid(row=0, column=1, padx=8, pady=8)

        update_chart_button = ctk.CTkButton(controls, text="Actualizar graficos", command=self.render_charts)
        update_chart_button.grid(row=0, column=2, padx=8, pady=8)

        self.charts_container = ctk.CTkFrame(self.tab_charts)
        self.charts_container.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        self.charts_container.grid_columnconfigure(0, weight=1)
        self.charts_container.grid_rowconfigure(0, weight=1)
        self.charts_container.grid_rowconfigure(1, weight=1)

    def _build_structure_tab(self) -> None:
        self.structure_text = ScrolledText(self.tab_structure, wrap="none")
        self.structure_text.pack(fill="both", expand=True, padx=12, pady=12)

    def _build_code_tab(self) -> None:
        self.code_tabview = ctk.CTkTabview(self.tab_code)
        self.code_tabview.pack(fill="both", expand=True, padx=12, pady=12)

    def browse_excel_file(self) -> None:
        initial_directory = self._get_initial_directory()
        selected_path = filedialog.askopenfilename(
            title="Selecciona el archivo Excel de resultados",
            initialdir=initial_directory,
            filetypes=[("Archivos Excel", "*.xlsx *.xlsm *.xltx *.xltm"), ("Todos los archivos", "*.*")],
        )
        if selected_path == "":
            return
        self.path_entry.delete(0, END)
        self.path_entry.insert(0, selected_path)
        self.status_label.configure(text="Archivo seleccionado: {0}".format(selected_path))

    def _get_initial_directory(self) -> str:
        entry_path = self.path_entry.get().strip()
        expanded_entry_path = os.path.expanduser(entry_path)
        if os.path.isdir(expanded_entry_path):
            return expanded_entry_path
        if os.path.isfile(expanded_entry_path):
            return os.path.dirname(expanded_entry_path)
        project_data_directory = os.path.join(self.project_root, "data")
        if os.path.isdir(project_data_directory):
            return project_data_directory
        return self.project_root

    def _resolve_excel_path(self, raw_path: str) -> str:
        candidate = os.path.expanduser(raw_path.strip())
        if candidate == "":
            raise FileNotFoundError("Debes indicar una ruta de Excel antes de cargar los datos.")

        candidate = os.path.normpath(candidate)
        if os.path.isabs(candidate):
            return candidate

        project_relative_path = os.path.normpath(os.path.join(self.project_root, candidate))
        if os.path.exists(project_relative_path):
            return project_relative_path
        return candidate

    def load_election_file(self) -> None:
        raw_path = self.path_entry.get().strip()
        try:
            resolved_path = self._resolve_excel_path(raw_path)
            self.path_entry.delete(0, END)
            self.path_entry.insert(0, resolved_path)
            loader = ElectionDataLoader(resolved_path)
            election, messages = loader.load_election()
            self.election = election
            self.loader_messages = messages
            self.status_label.configure(text="Archivo cargado correctamente: {0}".format(resolved_path))
            self.recalculate_and_validate()
            self.populate_selectors()
            self.refresh_current_selection()
            self.render_statistics()
            self.render_charts()
        except FileNotFoundError as error:
            self.status_label.configure(text=str(error))
            self._write_text(self.validation_text, str(error))
        except ExcelStructureError as error:
            self.status_label.configure(text=str(error))
            self._write_text(self.validation_text, str(error))
        except Exception as error:
            self.status_label.configure(text="Error inesperado: {0}".format(error))
            self._write_text(self.validation_text, "Error inesperado: {0}".format(error))

    def recalculate_and_validate(self) -> None:
        if self.election is None:
            self._write_text(self.validation_text, "No hay datos cargados para validar.")
            return
        calculation_messages = self.seat_calculator_service.calculate_for_election(self.election)
        validation_messages = self.validation_service.validate_election(self.election)
        self.validation_messages = []
        self.validation_messages.extend(self.loader_messages)
        self.validation_messages.extend(calculation_messages)
        self.validation_messages.extend(validation_messages)
        self._write_text(self.validation_text, "\n".join(self.validation_messages))
        self.render_statistics()
        self.refresh_current_selection()
        self.render_charts()

    def populate_selectors(self) -> None:
        if self.election is None:
            return
        view_values = self.territorial_view_adapter.build_selector_options(self.election)
        self.circunscription_selector.configure(values=view_values)
        self.compare_a_selector.configure(values=view_values)
        self.compare_b_selector.configure(values=view_values)
        if len(view_values) > 0:
            self.circunscription_selector.set(view_values[0])
            self.compare_a_selector.set(view_values[0])
            self.compare_b_selector.set(view_values[min(1, len(view_values) - 1)])

    def on_circunscription_selected(self, _: str) -> None:
        self.refresh_current_selection()
        self.render_charts()

    def refresh_current_selection(self) -> None:
        if self.election is None:
            self._write_text(self.selection_detail_text, "No hay datos cargados.")
            return
        selection_value = self.circunscription_selector.get().strip()
        view_data = self.territorial_view_adapter.build_view_data(self.election, selection_value)
        self.current_view_data = view_data
        self.current_color_map = self.color_manager.build_color_map(view_data.partidos)
        self.pactometer_model.clear()
        self._set_action_message(DomainMessageBuilder.build_confirmation("Se reinicio la coalicion para la nueva vista territorial."))
        self._render_view_summary(view_data)
        self._render_party_blocks(view_data)
        self._render_selection_details(view_data)
        self.pactometer_widget.set_context(view_data, self.current_color_map)

    def _render_view_summary(self, view_data: TerritorialViewData) -> None:
        self.view_summary_label.configure(
            text="{0} | Peso en escaños: {1:.2f}% | Escaños totales: {2} | Mayoría: {3}".format(
                view_data.nombre,
                view_data.peso_escanos_porcentaje,
                view_data.escanos_totales,
                view_data.mayoria_necesaria,
            )
        )

    def _render_party_blocks(self, view_data: TerritorialViewData) -> None:
        for widget in self.party_blocks_scroll.winfo_children():
            widget.destroy()
        if len(view_data.partidos) == 0:
            empty_label = ctk.CTkLabel(
                self.party_blocks_scroll,
                text="No hay partidos con escaños calculados en la vista seleccionada.",
            )
            empty_label.grid(row=0, column=0, padx=12, pady=12, sticky="w")
            return
        available_width = self.party_blocks_scroll.winfo_width()
        if available_width <= 20:
            available_width = 840
        block_count = len(view_data.partidos)
        columns = self._calculate_columns(available_width, block_count)
        row_index = 0
        column_index = 0
        for party_view in view_data.partidos:
            block_size = self._calculate_block_size(party_view.escanos_visibles, view_data.escanos_totales)
            color_hex = self.current_color_map.get(party_view.codigo_partido, "#607D8B")
            widget = PartyBlockWidget(
                self.party_blocks_scroll,
                party_view=party_view,
                color_hex=color_hex,
                block_size=block_size,
                drag_start_callback=self.on_party_drag_start,
                drag_move_callback=self.on_party_drag_move,
                drag_release_callback=self.on_party_drag_release,
            )
            widget.grid(row=row_index, column=column_index, padx=10, pady=10, sticky="nsew")
            column_index = column_index + 1
            if column_index >= columns:
                column_index = 0
                row_index = row_index + 1
        for column_number in range(0, columns):
            self.party_blocks_scroll.grid_columnconfigure(column_number, weight=1)

    def _calculate_columns(self, available_width: int, block_count: int) -> int:
        if block_count <= 1:
            return 1
        estimated_columns = int(available_width / 230)
        if estimated_columns < 1:
            estimated_columns = 1
        if estimated_columns > 4:
            estimated_columns = 4
        if estimated_columns > block_count:
            estimated_columns = block_count
        return estimated_columns

    def _calculate_block_size(self, seats: int, total_seats: int) -> Tuple[int, int]:
        minimum_size = 150
        maximum_size = 250
        if total_seats <= 0:
            return (minimum_size, minimum_size)
        ratio = float(seats) / float(total_seats)
        size = minimum_size + int((maximum_size - minimum_size) * math.sqrt(ratio))
        if size < minimum_size:
            size = minimum_size
        if size > maximum_size:
            size = maximum_size
        height = size
        if height < 150:
            height = 150
        return (size, height)

    def _render_selection_details(self, view_data: TerritorialViewData) -> None:
        lines: List[str] = []
        lines.append("Vista territorial: {0}".format(view_data.nombre))
        lines.append("Peso en el total nacional: {0:.2f}%".format(view_data.peso_escanos_porcentaje))
        lines.append("Escaños de la vista: {0}".format(view_data.escanos_totales))
        lines.append("Mayoría necesaria: {0}".format(view_data.mayoria_necesaria))
        lines.append("Partidos representados visualmente: {0}".format(len(view_data.partidos)))
        lines.append("")
        lines.append("PARTIDOS CON ESCAÑOS")
        for party_view in view_data.partidos:
            label = party_view.sigla_partido if party_view.sigla_partido != "" else party_view.nombre_partido
            lines.append(
                "- {0}: votos={1}, % voto={2:.2f}, escaños oficiales={3}, escaños calculados={4}".format(
                    label,
                    party_view.votos,
                    party_view.porcentaje_voto,
                    party_view.escanos_oficiales,
                    party_view.escanos_calculados,
                )
            )
        self._write_text(self.selection_detail_text, "\n".join(lines))

    def on_party_drag_start(self, party_widget: PartyBlockWidget, x_root: int, y_root: int) -> None:
        self.dragged_party_widget = party_widget
        if self.drag_overlay is not None:
            self.drag_overlay.destroy()
        label_text = party_widget.party_view.sigla_partido
        if label_text == "":
            label_text = party_widget.party_view.nombre_partido
        self.drag_overlay = ctk.CTkLabel(
            self,
            text="Arrastrando: {0}".format(label_text),
            fg_color=party_widget.color_hex,
            corner_radius=14,
            text_color="#FFFFFF",
            padx=14,
            pady=8,
        )
        self.drag_overlay.place(x=x_root - self.winfo_rootx(), y=y_root - self.winfo_rooty())

    def on_party_drag_move(self, party_widget: PartyBlockWidget, x_root: int, y_root: int) -> None:
        if self.drag_overlay is None:
            return
        self.drag_overlay.place(x=x_root - self.winfo_rootx() + 10, y=y_root - self.winfo_rooty() + 10)

    def on_party_drag_release(self, party_widget: PartyBlockWidget, x_root: int, y_root: int) -> None:
        if self.drag_overlay is not None:
            self.drag_overlay.destroy()
            self.drag_overlay = None
        if self.pactometer_widget.is_point_inside_drop_zone(x_root, y_root):
            message = self.pactometer_model.add_party(party_widget.party_view)
            self._set_action_message(message)
            self.pactometer_widget.refresh()
        else:
            self._set_action_message(DomainMessageBuilder.build_error("Debes soltar el partido dentro de la barra del pactometro."))
        self.dragged_party_widget = None

    def remove_party_from_pactometer(self, codigo_partido: str) -> None:
        message = self.pactometer_model.remove_party(codigo_partido)
        self._set_action_message(message)
        self.pactometer_widget.refresh()

    def render_statistics(self) -> None:
        if self.election is None:
            self._write_text(self.statistics_text, "No hay datos cargados para calcular estadisticas.")
            return
        report = self.statistics_service.build_report(self.election)
        self._write_text(self.statistics_text, report)

    def render_charts(self) -> None:
        for widget in self.charts_container.winfo_children():
            widget.destroy()

        if self.election is None:
            return

        view_data_a = self.territorial_view_adapter.build_view_data(self.election, self.compare_a_selector.get())
        view_data_b = self.territorial_view_adapter.build_view_data(self.election, self.compare_b_selector.get())

        color_map_a = self.color_manager.build_color_map(view_data_a.partidos)
        figure_votes = self.chart_generator.build_party_votes_chart(view_data_a, color_map_a)
        canvas_votes = FigureCanvasTkAgg(figure_votes, master=self.charts_container)
        canvas_votes.draw()
        canvas_votes.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        figure_seats = self.chart_generator.build_seats_chart(view_data_a, color_map_a)
        canvas_seats = FigureCanvasTkAgg(figure_seats, master=self.charts_container)
        canvas_seats.draw()
        canvas_seats.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        figure_comparison = self.chart_generator.build_comparison_chart(view_data_a, view_data_b)
        canvas_comparison = FigureCanvasTkAgg(figure_comparison, master=self.charts_container)
        canvas_comparison.draw()
        canvas_comparison.get_tk_widget().grid(row=0, column=1, rowspan=2, sticky="nsew", padx=8, pady=8)
        self.charts_container.grid_columnconfigure(1, weight=1)

    def _set_action_message(self, message: str) -> None:
        self.action_message_label.configure(text=message)

    def _on_application_resized(self, _event) -> None:
        if self.current_view_data is not None:
            self.after(150, self._refresh_blocks_if_needed)
        self.after(150, self.pactometer_widget.refresh)

    def _refresh_blocks_if_needed(self) -> None:
        if self.current_view_data is None:
            return
        self._render_party_blocks(self.current_view_data)

    def _show_project_structure(self) -> None:
        lines: List[str] = []
        for current_root, directories, files in os.walk(self.project_root):
            directories.sort()
            files.sort()
            relative_root = os.path.relpath(current_root, self.project_root)
            depth = 0 if relative_root == "." else relative_root.count(os.sep) + 1
            indent = "    " * depth
            folder_name = os.path.basename(current_root) if relative_root != "." else os.path.basename(self.project_root)
            lines.append("{0}{1}/".format(indent, folder_name))
            child_indent = "    " * (depth + 1)
            for filename in files:
                lines.append("{0}{1}".format(child_indent, filename))
        self._write_text(self.structure_text, "\n".join(lines))

    def _show_code_files(self) -> None:
        code_directory = os.path.join(self.project_root, "codigo")
        if not os.path.isdir(code_directory):
            return
        for filename in sorted(os.listdir(code_directory)):
            if not filename.endswith(".py"):
                continue
            tab_name = filename.replace(".py", "")
            tab = self.code_tabview.add(tab_name)
            text_box = ScrolledText(tab, wrap="none")
            text_box.pack(fill="both", expand=True)
            file_path = os.path.join(code_directory, filename)
            with open(file_path, "r", encoding="utf-8") as code_file:
                text_box.insert(END, code_file.read())
            text_box.configure(state="disabled")

    def _write_text(self, widget: ScrolledText, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", END)
        widget.insert(END, content)
        widget.configure(state="disabled")
