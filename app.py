
from flask import Flask, request, jsonify, send_file
from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener

from BazilioLexer import BazilioLexer
from BazilioParser import BazilioParser
from BazilioSemanticVisitor import BazilioSemanticVisitor

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent


class CapturadorErrores(ErrorListener):
    def __init__(self):
        super().__init__()
        self.errores = []

    def syntaxError(
        self, recognizer, offendingSymbol,
        line, column, msg, e
    ):
        self.errores.append(
            f"Linea {line}, columna {column + 1}: {msg}"
        )


@app.route("/")
def inicio():
    return send_file(BASE_DIR / "index.html")


@app.route("/api/analizar", methods=["POST"])
def analizar():
    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({
            "correcto": False,
            "errores": ["Se esperaba un objeto JSON."]
        }), 400

    codigo = datos.get("codigo", "")
    octava = datos.get("octava", 4)

    if not isinstance(codigo, str) or not codigo.strip():
        return jsonify({
            "correcto": False,
            "errores": ["No se recibieron notas musicales."]
        }), 400

    if len(codigo) > 10000:
        return jsonify({
            "correcto": False,
            "errores": ["El codigo es demasiado largo."]
        }), 400

    if type(octava) is not int or not 2 <= octava <= 6:
        return jsonify({
            "correcto": False,
            "errores": ["La octava debe estar entre 2 y 6."]
        }), 400

    # ANTLR4: analisis lexico
    entrada = InputStream(codigo)
    lexer = BazilioLexer(entrada)

    errores_lexicos = CapturadorErrores()
    lexer.removeErrorListeners()
    lexer.addErrorListener(errores_lexicos)

    tokens = CommonTokenStream(lexer)

    # ANTLR4: analisis sintactico
    parser = BazilioParser(tokens)

    errores_sintacticos = CapturadorErrores()
    parser.removeErrorListeners()
    parser.addErrorListener(errores_sintacticos)

    arbol = parser.programa()

    errores = (
        errores_lexicos.errores +
        errores_sintacticos.errores
    )

    if errores:
        return jsonify({
            "correcto": False,
            "fase": "lexico_sintactico",
            "errores": errores
        }), 400

    # ANTLR4: analisis semantico
    visitante = BazilioSemanticVisitor()
    visitante.octava_base = octava

    salida = StringIO()

    with redirect_stdout(salida):
        visitante.visit(arbol)

    if visitante.errores > 0:
        return jsonify({
            "correcto": False,
            "fase": "semantico",
            "errores": [salida.getvalue().strip()]
        }), 400

    eventos = []

    for midi in visitante.notas_midi:
        if midi == -1:
            eventos.append({
                "tipo": "silencio",
                "midi": -1
            })
        else:
            frecuencia = 440 * (2 ** ((midi - 69) / 12))

            eventos.append({
                "tipo": "nota",
                "midi": midi,
                "frecuencia": round(frecuencia, 2)
            })

    return jsonify({
        "correcto": True,
        "mensaje": "Compilacion exitosa con ANTLR4",
        "analisis_lexico": "CORRECTO",
        "analisis_sintactico": "CORRECTO",
        "analisis_semantico": "CORRECTO",
        "total_eventos": len(eventos),
        "eventos": eventos,
        "arbol": arbol.toStringTree(recog=parser)
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
