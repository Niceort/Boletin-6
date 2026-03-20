from __future__ import annotations

import os
from typing import List, Optional

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import END
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
        self._show_project_structure()
        self._show_code_files()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header_frame.grid_columnconfigure(1, weight=1)

        self.path_entry = ctk.CTkEntry(header_frame)
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        self.path_entry.insert(0, self.default_excel_path)

        load_button = ctk.CTkButton(header_frame, text="Cargar Excel", command=self.load_election_file)
        load_button.grid(row=0, column=2, padx=8, pady=8)

        reload_button = ctk.CTkButton(header_frame, text="Recalcular y validar", command=self.recalculate_and_validate)
        reload_button.grid(row=0, column=3, padx=8, pady=8)

        title_label = ctk.CTkLabel(header_frame, text="Ruta del Excel:")
        title_label.grid(row=0, column=0, padx=8, pady=8)

        self.status_label = ctk.CTkLabel(header_frame, text="Pendiente de carga")
        self.status_label.grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=8)

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

    def _build_structure_tab(self) -> None:
        self.structure_text = ScrolledText(self.tab_structure, wrap="none")
        self.structure_text.pack(fill="both", expand=True, padx=12, pady=12)

    def _build_code_tab(self) -> None:
        self.code_tabview = ctk.CTkTabview(self.tab_code)
        self.code_tabview.pack(fill="both", expand=True, padx=12, pady=12)

    def load_election_file(self) -> None:
        path = self.path_entry.get().strip()
        try:
            loader = ElectionDataLoader(path)
            election, messages = loader.load_election()
            self.election = election
            self.loader_messages = messages
            self.status_label.configure(text="Archivo cargado correctamente: {0}".format(path))
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
        selected = self.circunscription_selector.get().strip()
        if selected == "":
            return
        codigo = selected.split(" - ")[0]
        circunscripcion = self.election.circunscripciones[codigo]
        selected_party = self.party_selector.get().strip()
        for resultado in circunscripcion.obtener_resultados_ordenados_por_votos():
            if selected_party not in ["", "Todos"]:
                codigo_partido = selected_party.split(" - ")[0]
                if resultado.partido.codigo != codigo_partido:
                    continue
            porcentaje = circunscripcion.obtener_porcentaje_partido(resultado.partido.codigo)
            self.results_tree.insert(
                "",
                END,
                values=(
                    resultado.partido.get_identificador_presentacion(),
                    resultado.votos,
                    "{0:.2f}".format(porcentaje),
                    resultado.escanos_oficiales,
                    resultado.escanos_calculados,
                    resultado.diferencia_escanos,
                ),
            )

    def render_statistics(self) -> None:
        if self.election is None:
            self._write_text(self.statistics_text, "No hay datos cargados.")
            return
        statistics = self.statistics_service.build_general_statistics(self.election)
        lines: List[str] = []
        lines.append("Resumen general")
        lines.append("- Circunscripciones: {0}".format(statistics["total_circunscripciones"]))
        lines.append("- Partidos: {0}".format(statistics["total_partidos"]))
        lines.append("- Votos validos: {0}".format(statistics["total_votos"]))
        lines.append("- Escaños oficiales acumulados: {0}".format(statistics["total_escanos_oficiales"]))
        lines.append("- Escaños calculados acumulados: {0}".format(statistics["total_escanos_calculados"]))
        lines.append("")
        lines.append("Ranking nacional por votos")
        ranking = statistics["ranking_partidos"]
        for index in range(0, min(15, len(ranking))):
            item = ranking[index]
            lines.append(
                "{0}. {1} -> votos={2}, esc_of={3}, esc_calc={4}".format(
                    index + 1,
                    item["sigla"] if item["sigla"] else item["nombre"],
                    item["votos"],
                    item["escanos_oficiales"],
                    item["escanos_calculados"],
                )
            )
        lines.append("")
        lines.append("Diferencias entre escaños oficiales y calculados")
        diferencias = statistics["diferencias"]
        if len(diferencias) == 0:
            lines.append("No se detectaron diferencias.")
        else:
            for item in diferencias[0:20]:
                lines.append(
                    "- {0} / {1}: oficiales={2}, calculados={3}, diferencia={4}".format(
                        item["circunscripcion"],
                        item["partido"],
                        item["oficiales"],
                        item["calculados"],
                        item["diferencia"],
                    )
                )
        self._write_text(self.statistics_text, "\n".join(lines))

    def render_charts(self) -> None:
        for widget in self.charts_container.winfo_children():
            widget.destroy()
        if self.election is None:
            return

        selected = self.circunscription_selector.get().strip()
        if selected == "":
            return
        codigo = selected.split(" - ")[0]
        circunscripcion = self.election.circunscripciones[codigo]

        top_figure = self.chart_generator.build_party_votes_chart(self.election)
        top_canvas = FigureCanvasTkAgg(top_figure, master=self.charts_container)
        top_canvas.draw()
        top_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        seats_figure = self.chart_generator.build_circunscription_seats_chart(circunscripcion)
        seats_canvas = FigureCanvasTkAgg(seats_figure, master=self.charts_container)
        seats_canvas.draw()
        seats_canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        compare_a = self.compare_a_selector.get().strip()
        compare_b = self.compare_b_selector.get().strip()
        if compare_a != "" and compare_b != "":
            codigo_a = compare_a.split(" - ")[0]
            codigo_b = compare_b.split(" - ")[0]
            comparison_figure = self.chart_generator.build_circunscription_comparison_chart(
                self.election, codigo_a, codigo_b
            )
            comparison_canvas = FigureCanvasTkAgg(comparison_figure, master=self.charts_container)
            comparison_canvas.draw()
            comparison_canvas.get_tk_widget().grid(row=2, column=0, sticky="nsew", padx=8, pady=8)

    def _show_project_structure(self) -> None:
        lines: List[str] = []
        lines.append("EJERCICIO 2/")
        lines.append("├── codigo/")
        code_directory = os.path.join(self.project_root, "codigo")
        if os.path.isdir(code_directory):
            file_names = sorted([name for name in os.listdir(code_directory) if name.endswith(".py")])
            for index, name in enumerate(file_names):
                prefix = "└──" if index == len(file_names) - 1 else "├──"
                lines.append("│   {0} {1}".format(prefix, name))
        lines.append("└── data/")
        data_directory = os.path.join(self.project_root, "data")
        if os.path.isdir(data_directory):
            data_names = sorted(os.listdir(data_directory))
            for index, name in enumerate(data_names):
                prefix = "└──" if index == len(data_names) - 1 else "├──"
                lines.append("    {0} {1}".format(prefix, name))
        self._write_text(self.structure_text, "\n".join(lines))

    def _show_code_files(self) -> None:
        code_directory = os.path.join(self.project_root, "codigo")
        if not os.path.isdir(code_directory):
            return
        file_names = sorted([name for name in os.listdir(code_directory) if name.endswith(".py")])
        for name in file_names:
            tab = self.code_tabview.add(name)
            viewer = ScrolledText(tab, wrap="none")
            viewer.pack(fill="both", expand=True)
            with open(os.path.join(code_directory, name), "r", encoding="utf-8") as handler:
                viewer.insert("1.0", handler.read())
            viewer.configure(state="disabled")

    def _write_text(self, widget: ScrolledText, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", END)
        widget.insert("1.0", content)
        widget.configure(state="disabled")
