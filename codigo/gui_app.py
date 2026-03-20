from __future__ import annotations

import os
from typing import List, Optional

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import END, filedialog
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from chart_generator import ChartGenerator
from electoral_services import SeatCalculatorService, StatisticsService, ValidationService
from excel_loader import ElectionDataLoader, ExcelStructureError
from models import EleccionCongreso2023


class ElectionAnalyzerApplication(ctk.CTk):
    def __init__(self, project_root: str, default_excel_path: str) -> None:
        super().__init__()
        self.project_root = project_root
        self.default_excel_path = default_excel_path
        self.title("Analizador de Elecciones Generales 2023")
        self.geometry("1480x920")

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.validation_service = ValidationService()
        self.seat_calculator_service = SeatCalculatorService()
        self.statistics_service = StatisticsService()
        self.chart_generator = ChartGenerator()

        self.election: Optional[EleccionCongreso2023] = None
        self.validation_messages: List[str] = []
        self.loader_messages: List[str] = []

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
        self.tab_validations = self.tabview.add("Validaciones")
        self.tab_statistics = self.tabview.add("Estadisticas")
        self.tab_charts = self.tabview.add("Graficos")

        self._build_results_tab()
        self._build_validation_tab()
        self._build_statistics_tab()
        self._build_charts_tab()

    def _build_results_tab(self) -> None:
        self.tab_results.grid_columnconfigure(0, weight=1)
        self.tab_results.grid_rowconfigure(1, weight=1)

        filters = ctk.CTkFrame(self.tab_results)
        filters.grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        self.circunscription_selector = ctk.CTkComboBox(filters, values=[""], command=self.on_circunscription_selected)
        self.circunscription_selector.grid(row=0, column=0, padx=8, pady=8)

        self.party_selector = ctk.CTkComboBox(filters, values=[""], command=self.on_party_selected)
        self.party_selector.grid(row=0, column=1, padx=8, pady=8)

        self.results_tree = ttk.Treeview(
            self.tab_results,
            columns=("partido", "votos", "porcentaje", "oficiales", "calculados", "diferencia"),
            show="headings",
        )
        columnas = [
            ("partido", "Partido"),
            ("votos", "Votos"),
            ("porcentaje", "% voto"),
            ("oficiales", "Esc. oficiales"),
            ("calculados", "Esc. calculados"),
            ("diferencia", "Diferencia"),
        ]
        for identificador, titulo in columnas:
            self.results_tree.heading(identificador, text=titulo)
            self.results_tree.column(identificador, stretch=True, width=160)
        self.results_tree.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)

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
            self.recalculate_and_validate()
            self.populate_selectors()
            self.fill_results_for_selected_circunscription()
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
        self.fill_results_for_selected_circunscription()
        self.render_statistics()
        self.render_charts()

    def populate_selectors(self) -> None:
        if self.election is None:
            return
        circ_values: List[str] = []
        for circ in self.election.obtener_circunscripciones_ordenadas():
            circ_values.append("{0} - {1}".format(circ.codigo, circ.nombre))
        if len(circ_values) == 0:
            circ_values = [""]
        self.circunscription_selector.configure(values=circ_values)
        self.compare_a_selector.configure(values=circ_values)
        self.compare_b_selector.configure(values=circ_values)
        self.circunscription_selector.set(circ_values[0])
        self.compare_a_selector.set(circ_values[0])
        self.compare_b_selector.set(circ_values[min(1, len(circ_values) - 1)])

        party_values: List[str] = ["Todos"]
        for partido in self.election.obtener_partidos_ordenados():
            etiqueta = "{0} - {1}".format(partido.codigo, partido.get_identificador_presentacion())
            party_values.append(etiqueta)
        self.party_selector.configure(values=party_values)
        self.party_selector.set(party_values[0])

    def on_circunscription_selected(self, _: str) -> None:
        self.fill_results_for_selected_circunscription()
        self.render_charts()

    def on_party_selected(self, _: str) -> None:
        self.fill_results_for_selected_circunscription()

    def fill_results_for_selected_circunscription(self) -> None:
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        if self.election is None:
            return

        circunscription_value = self.circunscription_selector.get().strip()
        if circunscription_value == "":
            return

        circ_code = circunscription_value.split(" - ", 1)[0]
        circunscription = self.election.circunscripciones.get(circ_code)
        if circunscription is None:
            return

        selected_party = self.party_selector.get().strip()
        for result in circunscription.obtener_resultados_ordenados_por_votos():
            if selected_party not in ("", "Todos"):
                selected_party_code = selected_party.split(" - ", 1)[0]
                if result.partido.codigo != selected_party_code:
                    continue

            self.results_tree.insert(
                "",
                END,
                values=(
                    result.partido.get_identificador_presentacion(),
                    result.votos,
                    "{0:.2f}".format(result.obtener_porcentaje_voto(circunscription.votos_totales_candidaturas_calculados)),
                    result.escanos_oficiales,
                    result.escanos_calculados,
                    result.obtener_diferencia_escanos(),
                ),
            )

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

        circ_a = self._get_selected_circunscription(self.compare_a_selector.get())
        circ_b = self._get_selected_circunscription(self.compare_b_selector.get())
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

    def _get_selected_circunscription(self, selector_value: str):
        if self.election is None:
            return None
        if selector_value.strip() == "":
            return None
        circ_code = selector_value.split(" - ", 1)[0]
        return self.election.circunscripciones.get(circ_code)

    def _write_text(self, widget: ScrolledText, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", END)
        widget.insert(END, content)
        widget.configure(state="disabled")
