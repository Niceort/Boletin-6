# Analizador de elecciones generales 2023

Aplicación orientada a objetos para cargar un Excel con resultados del Congreso de los Diputados de 2023, validar su coherencia, recalcular escaños con D'Hondt y ofrecer consultas, estadísticas y gráficos.

## Cómo se cubren los requisitos

- **POO**: el dominio está separado en clases para elecciones, circunscripciones, partidos y resultados en `codigo/models.py`.
- **Lectura del Excel**: `codigo/excel_loader.py` detecta la hoja y cabecera válidas, interpreta columnas equivalentes y crea el modelo de dominio.
- **Omisión de votos cero**: los resultados partido-circunscripción con 0 votos se descartan al agregarlos a la circunscripción.
- **Validación de coherencia**: `codigo/electoral_services.py` comprueba el total de votos por circunscripción, la suma de escaños oficiales y las diferencias entre escaños oficiales y recalculados.
- **Cálculo de escaños**: el servicio de cálculo aplica D'Hondt con barrera del 3% sobre votos válidos a candidaturas.
- **Consultas y análisis**: la interfaz permite consultar resultados por circunscripción y partido, además de mostrar estadísticas agregadas y diferencias.
- **Gráficos**: la pestaña de gráficos compara votos y escaños entre dos circunscripciones.

## Estructura principal

- `codigo/main.py`: arranque de la aplicación.
- `codigo/gui_app.py`: interfaz gráfica con pestañas de resultados, validaciones, estadísticas y gráficos.
- `codigo/excel_loader.py`: lectura robusta del Excel.
- `codigo/models.py`: entidades del dominio.
- `codigo/electoral_services.py`: validaciones, cálculo de escaños y estadísticas.
- `codigo/chart_generator.py`: generación de gráficas con Matplotlib.

## Nota de diseño

Se ha reforzado la separación entre lectura, lógica y presentación para ajustarse al enunciado y facilitar la reutilización del código.
