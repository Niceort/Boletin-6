from __future__ import annotations

import os
import tkinter as tk
import unicodedata
from typing import List, Optional

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import END, filedialog
from tkinter.scrolledtext import ScrolledText

from chart_generator import ChartGenerator
from electoral_services import SeatCalculatorService, StatisticsService, ValidationService
from excel_loader import ElectionDataLoader, ExcelStructureError
from models import DomainMessageBuilder, EleccionCongreso2023
from party_color_registry import PartyColorRegistry
from results_visual_components import PactometerWidget, ResultsBlocksCanvas
from territorial_view_service import TerritorialPartySummary, TerritorialViewService


class ElectionAnalyzerApplication(ctk.CTk):
    def __init__(self, project_root: str, default_excel_path: str) -> None:
        super().__init__()
        self.project_root = project_root
        self.default_excel_path = default_excel_path
        self.title("Analizador de Elecciones Generales 2023")
        self.geometry("1520x960")
        self.minsize(1180, 780)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.validation_service = ValidationService()
        self.seat_calculator_service = SeatCalculatorService()
        self.statistics_service = StatisticsService()
        self.chart_generator = ChartGenerator()
        self.territorial_view_service = TerritorialViewService()
        self.party_color_registry = PartyColorRegistry()

        self.election: Optional[EleccionCongreso2023] = None
        self.validation_messages: List[str] = []
        self.loader_messages: List[str] = []
        self.current_territorial_view = None
        self.current_results_options: List[str] = []
        self.current_coalition_codes: List[str] = []
        self.map_image_path = self._find_map_image_path()
        self.original_map_image: Optional[tk.PhotoImage] = None
        self.rendered_map_image: Optional[tk.PhotoImage] = None

        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header_frame.grid_columnconfigure(1, weight=1)

        self.path_entry = ctk.CTkEntry(header_frame)
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        self.path_entry.insert(0, self.default_excel_path)

        browse_button = ctk.CTkButton(header_frame, text="Buscar Excel", command=self.browse_excel_file)
        browse_button.grid(row=0, column=2, padx=8, pady=8)

        load_button = ctk.CTkButton(header_frame, text="Cargar Excel", command=self.load_election_file)
        load_button.grid(row=0, column=3, padx=8, pady=8)

        reload_button = ctk.CTkButton(header_frame, text="Recalcular y validar", command=self.recalculate_and_validate)
        reload_button.grid(row=0, column=4, padx=8, pady=8)

        title_label = ctk.CTkLabel(header_frame, text="Ruta del Excel:")
        title_label.grid(row=0, column=0, padx=8, pady=8)

        self.status_label = ctk.CTkLabel(header_frame, text="Pendiente de carga")
        self.status_label.grid(row=1, column=0, columnspan=5, sticky="w", padx=8, pady=8)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.tab_results = self.tabview.add("Resultados")
        self.tab_provinces = self.tabview.add("Provincias")
        self.tab_validations = self.tabview.add("Validaciones")
        self.tab_statistics = self.tabview.add("Estadisticas")
        self.tab_charts = self.tabview.add("Graficos")

        self._build_results_tab()
        self._build_provinces_tab()
        self._build_validation_tab()
        self._build_statistics_tab()
        self._build_charts_tab()

    def _build_results_tab(self) -> None:
        self.tab_results.grid_columnconfigure(0, weight=3)
        self.tab_results.grid_columnconfigure(1, weight=2)
        self.tab_results.grid_rowconfigure(1, weight=1)

        controls_frame = ctk.CTkFrame(self.tab_results)
        controls_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=12)
        controls_frame.grid_columnconfigure(1, weight=1)

        territorial_label = ctk.CTkLabel(controls_frame, text="Vista territorial:")
        territorial_label.grid(row=0, column=0, padx=8, pady=8, sticky="w")

        self.circunscription_selector = ctk.CTkComboBox(
            controls_frame,
            values=["General — 100.00%"],
            command=self.on_circunscription_selected,
            width=320,
        )
        self.circunscription_selector.grid(row=0, column=1, padx=8, pady=8, sticky="w")
        self.circunscription_selector.set("General — 100.00%")

        refresh_results_button = ctk.CTkButton(
            controls_frame,
            text="Actualizar vista",
            command=self.refresh_results_view,
        )
        refresh_results_button.grid(row=0, column=2, padx=8, pady=8)

        self.results_feedback_label = ctk.CTkLabel(
            controls_frame,
            text="Selecciona una vista territorial y arrastra partidos al pactómetro.",
            anchor="w",
            justify="left",
        )
        self.results_feedback_label.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))

        left_panel = ctk.CTkFrame(self.tab_results)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(2, weight=1)
        left_panel.grid_rowconfigure(3, weight=0)

        self.results_title_label = ctk.CTkLabel(left_panel, text="Resultados visuales", font=ctk.CTkFont(size=22, weight="bold"))
        self.results_title_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        self.results_summary_label = ctk.CTkLabel(left_panel, text="Carga el Excel para ver el resumen territorial.", anchor="w", justify="left")
        self.results_summary_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        blocks_frame = ctk.CTkFrame(left_panel)
        blocks_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        blocks_frame.grid_columnconfigure(0, weight=1)
        blocks_frame.grid_rowconfigure(0, weight=1)

        self.blocks_canvas = ResultsBlocksCanvas(
            blocks_frame,
            color_registry=self.party_color_registry,
            drop_callback=self.on_party_dropped,
            status_callback=self.set_results_feedback,
            bg="#1E293B",
        )
        self.blocks_canvas.grid(row=0, column=0, sticky="nsew")

        blocks_scrollbar = tk.Scrollbar(blocks_frame, orient="vertical")
        blocks_scrollbar.grid(row=0, column=1, sticky="ns")
        self.blocks_canvas.attach_scrollbar(blocks_scrollbar)

        self.pactometer_widget = PactometerWidget(
            left_panel,
            color_registry=self.party_color_registry,
            remove_callback=self.remove_party_from_pactometer,
            bg="#10212F",
            height=148,
        )
        self.pactometer_widget.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

        right_panel = ctk.CTkFrame(self.tab_results)
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)

        coalition_title = ctk.CTkLabel(right_panel, text="Coalición actual", font=ctk.CTkFont(size=20, weight="bold"))
        coalition_title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

        self.coalition_summary_label = ctk.CTkLabel(
            right_panel,
            text="Todavía no hay partidos añadidos al pactómetro.",
            justify="left",
            anchor="w",
        )
        self.coalition_summary_label.grid(row=1, column=0, sticky="new", padx=12, pady=(0, 8))

        self.coalition_list_frame = ctk.CTkScrollableFrame(right_panel, label_text="Partidos añadidos")
        self.coalition_list_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.coalition_list_frame.grid_columnconfigure(0, weight=1)

        clear_button = ctk.CTkButton(right_panel, text="Vaciar pactómetro", command=self.clear_pactometer)
        clear_button.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _build_provinces_tab(self) -> None:
        self.tab_provinces.grid_columnconfigure(0, weight=2)
        self.tab_provinces.grid_columnconfigure(1, weight=3)
        self.tab_provinces.grid_rowconfigure(1, weight=1)

        controls_frame = ctk.CTkFrame(self.tab_provinces)
        controls_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=12)
        controls_frame.grid_columnconfigure(1, weight=1)

        province_label = ctk.CTkLabel(controls_frame, text="Provincia:")
        province_label.grid(row=0, column=0, padx=8, pady=8, sticky="w")

        self.province_selector = ctk.CTkComboBox(
            controls_frame,
            values=["Sin datos"],
            command=self.on_province_selected,
            width=320,
        )
        self.province_selector.grid(row=0, column=1, padx=8, pady=8, sticky="w")
        self.province_selector.set("Sin datos")

        refresh_provinces_button = ctk.CTkButton(
            controls_frame,
            text="Actualizar provincia",
            command=self.render_provinces_view,
        )
        refresh_provinces_button.grid(row=0, column=2, padx=8, pady=8)

        self.provinces_status_label = ctk.CTkLabel(
            controls_frame,
            text="Carga el Excel para inspeccionar una provincia sobre el mapa.",
            anchor="w",
            justify="left",
        )
        self.provinces_status_label.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))

        left_panel = ctk.CTkFrame(self.tab_provinces)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(2, weight=1)

        self.province_title_label = ctk.CTkLabel(left_panel, text="Detalle provincial", font=ctk.CTkFont(size=22, weight="bold"))
        self.province_title_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        self.province_summary_label = ctk.CTkLabel(
            left_panel,
            text="Selecciona una provincia para mostrar sus datos electorales.",
            anchor="w",
            justify="left",
        )
        self.province_summary_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.province_results_text = ScrolledText(left_panel, wrap="word", height=18)
        self.province_results_text.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._write_text(self.province_results_text, "Todavía no hay resultados cargados.")

        right_panel = ctk.CTkFrame(self.tab_provinces)
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)

        map_title = ctk.CTkLabel(right_panel, text="Mapa de España", font=ctk.CTkFont(size=20, weight="bold"))
        map_title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

        self.map_canvas = tk.Canvas(right_panel, bg="#0F172A", highlightthickness=0)
        self.map_canvas.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.map_canvas.bind("<Configure>", self._on_map_canvas_resize)

        self.map_caption_label = ctk.CTkLabel(
            right_panel,
            text="La imagen del mapa se buscará automáticamente dentro de la carpeta data.",
            anchor="w",
            justify="left",
        )
        self.map_caption_label.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

        self._render_map_image()

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

        self.compare_a_selector = ctk.CTkComboBox(controls, values=[""], width=220)
        self.compare_a_selector.grid(row=0, column=0, padx=8, pady=8)
        self.compare_b_selector = ctk.CTkComboBox(controls, values=[""], width=220)
        self.compare_b_selector.grid(row=0, column=1, padx=8, pady=8)

        update_chart_button = ctk.CTkButton(controls, text="Actualizar graficos", command=self.render_charts)
        update_chart_button.grid(row=0, column=2, padx=8, pady=8)

        self.charts_container = ctk.CTkFrame(self.tab_charts)
        self.charts_container.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        self.charts_container.grid_columnconfigure(0, weight=1)
        self.charts_container.grid_rowconfigure(0, weight=1)
        self.charts_container.grid_rowconfigure(1, weight=1)

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
            self.populate_selectors()
            self.recalculate_and_validate()
            self.refresh_results_view()
            self.render_statistics()
            self.render_charts()
            self.render_provinces_view()
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
        self.refresh_results_view()
        self.render_statistics()
        self.render_charts()
        self.render_provinces_view()

    def populate_selectors(self) -> None:
        if self.election is None:
            return
        self.current_results_options = self.territorial_view_service.build_selector_options(self.election)
        self.circunscription_selector.configure(values=self.current_results_options)
        if len(self.current_results_options) > 0:
            self.circunscription_selector.set(self.current_results_options[0])

        compare_values: List[str] = []
        province_values: List[str] = []
        for circunscripcion in self.election.obtener_circunscripciones_ordenadas():
            compare_values.append("{0} - {1}".format(circunscripcion.codigo, circunscripcion.nombre))
            province_values.append(circunscripcion.nombre)
        if len(compare_values) == 0:
            compare_values = [""]
        if len(province_values) == 0:
            province_values = ["Sin datos"]
        self.compare_a_selector.configure(values=compare_values)
        self.compare_b_selector.configure(values=compare_values)
        self.compare_a_selector.set(compare_values[0])
        self.compare_b_selector.set(compare_values[min(1, len(compare_values) - 1)])
        self.province_selector.configure(values=province_values)
        self.province_selector.set(province_values[0])

    def on_circunscription_selected(self, _: str) -> None:
        self.clear_pactometer(silent=True)
        self.refresh_results_view()

    def on_province_selected(self, _: str) -> None:
        self.render_provinces_view()

    def refresh_results_view(self) -> None:
        territorial_view = None
        if self.election is not None:
            selector_value = self.circunscription_selector.get().strip()
            if selector_value == "":
                selector_value = "General — 100.00%"
            territory_code = self.territorial_view_service.extract_code_from_selector_value(selector_value)
            territorial_view = self.territorial_view_service.build_view(self.election, territory_code)

        self.current_territorial_view = territorial_view
        if territorial_view is None:
            self.results_title_label.configure(text="Resultados visuales")
            self.results_summary_label.configure(text="Carga el Excel para visualizar bloques de partidos.")
            self.blocks_canvas.render_view(self._build_empty_view())
            self.pactometer_widget.render(None, [])
            self._render_coalition_panel([])
            return

        summary_text = self._build_results_summary_text(territorial_view)
        self.results_title_label.configure(text="{0} — bloques por partido".format(territorial_view.nombre))
        self.results_summary_label.configure(text=summary_text)
        self.blocks_canvas.render_view(territorial_view)
        coalition_parties = self._get_current_coalition_parties()
        self.pactometer_widget.render(territorial_view, coalition_parties)
        self._render_coalition_panel(coalition_parties)

    def render_provinces_view(self) -> None:
        if self.election is None:
            self.province_title_label.configure(text="Detalle provincial")
            self.province_summary_label.configure(text="Carga el Excel para consultar una provincia.")
            self.provinces_status_label.configure(text="No hay datos cargados todavía.")
            self._write_text(self.province_results_text, "Todavía no hay resultados cargados.")
            self._render_map_image()
            return

        province_name = self.province_selector.get().strip()
        if province_name == "":
            province_name = self.election.obtener_circunscripciones_ordenadas()[0].nombre
            self.province_selector.set(province_name)
        territorial_view = self.territorial_view_service.build_view(self.election, province_name)
        self.province_title_label.configure(text="{0} — detalle provincial".format(territorial_view.nombre))
        self.province_summary_label.configure(text=self._build_results_summary_text(territorial_view))
        self.provinces_status_label.configure(
            text="Mostrando la provincia {0} sobre la referencia del mapa disponible.".format(territorial_view.nombre)
        )
        self.map_caption_label.configure(text=self._build_map_caption_text(territorial_view.nombre))
        self._write_text(self.province_results_text, self._build_province_report(territorial_view))
        self._render_map_image()

    def on_party_dropped(self, party_code: str, root_x: int, root_y: int) -> None:
        if self.current_territorial_view is None:
            self.set_results_feedback(DomainMessageBuilder.build_error("No hay una vista territorial activa."))
            return
        if not self.pactometer_widget.is_inside_widget(root_x, root_y):
            self.set_results_feedback(DomainMessageBuilder.build_error("Debes soltar el bloque dentro del pactómetro."))
            return
        for existing_code in self.current_coalition_codes:
            if existing_code == party_code:
                self.set_results_feedback(DomainMessageBuilder.build_error("Ese partido ya esta presente en la coalicion."))
                return
        self.current_coalition_codes.append(party_code)
        coalition_parties = self._get_current_coalition_parties()
        self.pactometer_widget.render(self.current_territorial_view, coalition_parties)
        self._render_coalition_panel(coalition_parties)
        party = self._find_party_in_current_view(party_code)
        if party is not None:
            self.set_results_feedback(
                DomainMessageBuilder.build_confirmation(
                    "Se añadio {0} al pactometro con {1} escaños.".format(party.etiqueta, party.escanos_oficiales)
                )
            )

    def remove_party_from_pactometer(self, party_code: str) -> None:
        if party_code not in self.current_coalition_codes:
            self.set_results_feedback(DomainMessageBuilder.build_error("El partido indicado no esta en el pactometro."))
            return
        updated_codes: List[str] = []
        for existing_code in self.current_coalition_codes:
            if existing_code != party_code:
                updated_codes.append(existing_code)
        self.current_coalition_codes = updated_codes
        coalition_parties = self._get_current_coalition_parties()
        self.pactometer_widget.render(self.current_territorial_view, coalition_parties)
        self._render_coalition_panel(coalition_parties)
        party = self._find_party_in_current_view(party_code)
        if party is not None:
            self.set_results_feedback(
                DomainMessageBuilder.build_confirmation(
                    "Se retiro {0} del pactometro.".format(party.etiqueta)
                )
            )

    def clear_pactometer(self, silent: bool = False) -> None:
        self.current_coalition_codes = []
        coalition_parties: List[TerritorialPartySummary] = []
        self.pactometer_widget.render(self.current_territorial_view, coalition_parties)
        self._render_coalition_panel(coalition_parties)
        if not silent:
            self.set_results_feedback(DomainMessageBuilder.build_confirmation("Se vacio el pactometro actual."))

    def set_results_feedback(self, message: str) -> None:
        self.results_feedback_label.configure(text=message)

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

        circ_a = self._get_selected_circunscription_for_charts(self.compare_a_selector.get())
        circ_b = self._get_selected_circunscription_for_charts(self.compare_b_selector.get())
        if circ_a is None or circ_b is None:
            return

        figure_votes = self.chart_generator.build_votes_chart(circ_a, circ_b)
        canvas_votes = FigureCanvasTkAgg(figure_votes, master=self.charts_container)
        canvas_votes.draw()
        canvas_votes.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        figure_seats = self.chart_generator.build_seats_chart(circ_a, circ_b)
        canvas_seats = FigureCanvasTkAgg(figure_seats, master=self.charts_container)
        canvas_seats.draw()
        canvas_seats.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

    def _get_selected_circunscription_for_charts(self, selector_value: str):
        if self.election is None:
            return None
        if selector_value.strip() == "":
            return None
        circ_code = selector_value.split(" - ", 1)[0]
        return self.election.circunscripciones.get(circ_code)

    def _build_results_summary_text(self, territorial_view) -> str:
        visible_parties = territorial_view.partidos_visibles
        return (
            "Peso territorial: {0:.2f}% del total nacional de escaños\n"
            "Votos a candidaturas: {1}\n"
            "Escaños oficiales: {2}\n"
            "Mayoría necesaria: {3}\n"
            "Partidos visibles: {4}"
        ).format(
            territorial_view.porcentaje_peso_escanos,
            territorial_view.total_votos,
            territorial_view.total_escanos_oficiales,
            territorial_view.mayoria_necesaria,
            len(visible_parties),
        )

    def _build_province_report(self, territorial_view) -> str:
        lines: List[str] = []
        lines.append("Provincia: {0}".format(territorial_view.nombre))
        lines.append("Escaños oficiales: {0}".format(territorial_view.total_escanos_oficiales))
        lines.append("Escaños calculados: {0}".format(territorial_view.total_escanos_calculados))
        lines.append("Votos a candidaturas: {0}".format(territorial_view.total_votos))
        lines.append("")
        lines.append("Partidos con representación:")
        if len(territorial_view.partidos_visibles) == 0:
            lines.append("- No hay partidos con escaños oficiales en esta provincia.")
            return "\n".join(lines)

        ranking = 1
        for party in territorial_view.partidos_visibles:
            difference = party.escanos_calculados - party.escanos_oficiales
            lines.append(
                "{0}. {1} | votos: {2} | escaños oficiales: {3} | escaños calculados: {4} | diferencia: {5}".format(
                    ranking,
                    party.etiqueta,
                    party.votos,
                    party.escanos_oficiales,
                    party.escanos_calculados,
                    difference,
                )
            )
            ranking = ranking + 1
        return "\n".join(lines)

    def _build_map_caption_text(self, province_name: str) -> str:
        if self.map_image_path is None:
            return (
                "No se ha encontrado el PNG del mapa en la carpeta data. "
                "Añádelo como 'Mapa españa.png' o con un nombre similar para mostrarlo aquí."
            )
        return "Mapa cargado desde: {0}\nProvincia seleccionada: {1}".format(self.map_image_path, province_name)

    def _get_current_coalition_parties(self) -> List[TerritorialPartySummary]:
        coalition_parties: List[TerritorialPartySummary] = []
        if self.current_territorial_view is None:
            return coalition_parties
        for party_code in self.current_coalition_codes:
            party = self._find_party_in_current_view(party_code)
            if party is not None:
                coalition_parties.append(party)
        return coalition_parties

    def _find_party_in_current_view(self, party_code: str) -> Optional[TerritorialPartySummary]:
        if self.current_territorial_view is None:
            return None
        for party in self.current_territorial_view.partidos_visibles:
            if party.codigo == party_code:
                return party
        return None

    def _render_coalition_panel(self, coalition_parties: List[TerritorialPartySummary]) -> None:
        for widget in self.coalition_list_frame.winfo_children():
            widget.destroy()
        if self.current_territorial_view is None:
            self.coalition_summary_label.configure(text="Carga el Excel para activar el pactómetro.")
            return

        coalition_total = 0
        for party in coalition_parties:
            coalition_total = coalition_total + party.escanos_oficiales

        if coalition_total >= self.current_territorial_view.mayoria_necesaria:
            majority_text = "Mayoría alcanzada"
        else:
            missing_seats = self.current_territorial_view.mayoria_necesaria - coalition_total
            majority_text = "Faltan {0} escaños".format(missing_seats)

        self.coalition_summary_label.configure(
            text="Coalición actual: {0} / {1} escaños\n{2}".format(
                coalition_total,
                self.current_territorial_view.total_escanos_vista,
                majority_text,
            )
        )

        if len(coalition_parties) == 0:
            empty_label = ctk.CTkLabel(self.coalition_list_frame, text="Arrastra bloques al pactómetro o pulsa sobre sus segmentos para retirarlos.")
            empty_label.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        row_index = 0
        for party in coalition_parties:
            fill_color, _ = self.party_color_registry.get_party_colors(party.codigo, party.nombre, party.etiqueta)
            row_frame = ctk.CTkFrame(self.coalition_list_frame)
            row_frame.grid(row=row_index, column=0, sticky="ew", padx=8, pady=6)
            row_frame.grid_columnconfigure(1, weight=1)

            color_indicator = tk.Canvas(row_frame, width=18, height=18, highlightthickness=0, bg="#1F2937")
            color_indicator.grid(row=0, column=0, padx=(8, 6), pady=8)
            color_indicator.create_oval(2, 2, 16, 16, fill=fill_color, outline=fill_color)

            party_label = ctk.CTkLabel(
                row_frame,
                text="{0} — {1} escaños".format(party.etiqueta, party.escanos_oficiales),
                anchor="w",
            )
            party_label.grid(row=0, column=1, sticky="ew", padx=4, pady=8)

            remove_button = ctk.CTkButton(
                row_frame,
                text="Quitar",
                width=90,
                command=lambda code=party.codigo: self.remove_party_from_pactometer(code),
            )
            remove_button.grid(row=0, column=2, padx=8, pady=8)
            row_index = row_index + 1

    def _render_map_image(self) -> None:
        self.map_canvas.delete("all")
        self.map_image_path = self._find_map_image_path()
        if self.map_image_path is None:
            self.original_map_image = None
            self.rendered_map_image = None
            self.map_canvas.create_text(
                24,
                24,
                anchor="nw",
                text="No se ha encontrado 'Mapa españa' dentro de data.",
                fill="#E2E8F0",
                font=("Arial", 14, "bold"),
                width=max(self.map_canvas.winfo_width() - 48, 220),
            )
            return

        try:
            self.original_map_image = tk.PhotoImage(file=self.map_image_path)
        except tk.TclError:
            self.original_map_image = None
            self.rendered_map_image = None
            self.map_canvas.create_text(
                24,
                24,
                anchor="nw",
                text="No se pudo abrir la imagen del mapa. Asegúrate de que sea un PNG compatible con Tk.",
                fill="#FCA5A5",
                font=("Arial", 14, "bold"),
                width=max(self.map_canvas.winfo_width() - 48, 220),
            )
            return

        self._draw_resized_map_image()

    def _draw_resized_map_image(self) -> None:
        self.map_canvas.delete("all")
        if self.original_map_image is None:
            return
        canvas_width = max(self.map_canvas.winfo_width(), 320)
        canvas_height = max(self.map_canvas.winfo_height(), 320)
        image_width = self.original_map_image.width()
        image_height = self.original_map_image.height()
        sample_ratio = max(1, (image_width + canvas_width - 1) // canvas_width, (image_height + canvas_height - 1) // canvas_height)
        self.rendered_map_image = self.original_map_image.subsample(sample_ratio, sample_ratio)
        center_x = canvas_width // 2
        center_y = canvas_height // 2
        self.map_canvas.create_image(center_x, center_y, image=self.rendered_map_image)

    def _on_map_canvas_resize(self, _event) -> None:
        if self.original_map_image is None:
            self._render_map_image()
            return
        self._draw_resized_map_image()

    def _find_map_image_path(self) -> Optional[str]:
        data_directory = os.path.join(self.project_root, "data")
        if not os.path.isdir(data_directory):
            return None

        preferred_keywords = ["mapaespaña", "mapaespana", "mapa españa", "mapa espana"]
        supported_extensions = {".png", ".gif", ".ppm", ".pgm"}
        candidates: List[str] = []
        for entry_name in os.listdir(data_directory):
            entry_path = os.path.join(data_directory, entry_name)
            if not os.path.isfile(entry_path):
                continue
            extension = os.path.splitext(entry_name)[1].lower()
            if extension not in supported_extensions:
                continue
            normalized_name = self._normalize_text_for_lookup(os.path.splitext(entry_name)[0])
            if any(keyword in normalized_name for keyword in preferred_keywords):
                return entry_path
            candidates.append(entry_path)
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _normalize_text_for_lookup(self, value: str) -> str:
        normalized = unicodedata.normalize("NFD", value)
        without_accents = "".join(character for character in normalized if unicodedata.category(character) != "Mn")
        return without_accents.lower().replace("_", " ").replace("-", " ")

    def _build_empty_view(self):
        class EmptyView:
            nombre = "Sin datos"
            partidos_visibles: List[TerritorialPartySummary] = []

        return EmptyView()

    def _write_text(self, widget: ScrolledText, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", END)
        widget.insert(END, content)
        widget.configure(state="disabled")
