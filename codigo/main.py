from __future__ import annotations

import os

from gui_app import ElectionAnalyzerApplication


class ApplicationLauncher:
    def __init__(self) -> None:
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.default_excel_path = os.path.join(self.project_root, "data", "PROV_02_202307_1.xlsx")

    def launch(self) -> None:
        application = ElectionAnalyzerApplication(
            project_root=self.project_root,
            default_excel_path=self.default_excel_path,
        )
        application.mainloop()


if __name__ == "__main__":
    launcher = ApplicationLauncher()
    launcher.launch()
