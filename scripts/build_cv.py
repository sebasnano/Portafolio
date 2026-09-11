#!/usr/bin/env python3
"""Build the two deterministic, one-page public CV PDFs."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89
MEDIA_BOX = "[0 0 595.28 841.89]"
ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = {
    "es": ROOT / "assets" / "cv-sebastian-rodriguez-es.pdf",
    "en": ROOT / "assets" / "cv-sebastian-rodriguez-en.pdf",
}

CVS = {
    "es": {
        "name": "SEBASTIÁN RODRÍGUEZ",
        "role": "DATA ENGINEER / DATA PLATFORM ENGINEER",
        "tagline": "Backend en Python · Ingeniería de IA como continuación natural",
        "left": [
            ("PERFIL", [
                "Diseño sistemas donde los datos son confiables, trazables y recuperables. Mi experiencia cubre procesamiento de datos en Python, bases de datos relacionales, almacenamiento de objetos, APIs y servicios, y operación de entornos Linux y cloud. Construyo el backend y la operación alrededor de las garantías que necesitan los datos.",
            ]),
            ("CAPACIDADES SELECCIONADAS", [
                "• Datos — Python, Polars, DuckDB, PostgreSQL, Parquet, PyArrow, almacenamiento de objetos e integridad mediante SHA-256. Aplicado en proyectos actuales.",
                "• Backend y plataforma — FastAPI, Redis, Docker, Linux, systemd, Tailscale, rclone, Nix y Home Manager. Aplicado en proyectos actuales.",
                "• Experiencia complementaria previa — MySQL, Oracle, Django, Flask, Celery, NestJS, TypeORM e integraciones mediante REST y OAuth.",
                "• Desarrollo actual — Ingeniería de Datos, ML Engineering, Ingeniería de IA, MLX, TensorFlow, Keras, PyTorch y sistemas multiagente. Aprendizaje y experimentación en curso; no representa modelos desplegados ni dominio experto demostrado.",
            ]),
        ],
        "right": [
            ("EVIDENCIA Y PROYECTOS SELECCIONADOS", [
                ("PERSONAL DATA LAKE — EN PROGRESO", "Adaptador de almacenamiento de objetos, catálogo PostgreSQL y backfill del inventario existente. Implementación e instantánea verificadas el 06/09/2026: 9.420 objetos comprobados mediante SHA-256 y 9.235 activos únicos tras la deduplicación. Verificación mediante 212 pruebas de host y 45 contra PostgreSQL real. No se presenta como catálogo desplegado en producción."),
                ("PROTECCIÓN DE DATOS — ALCANCE EN PROGRESO", "Estrategia de copia aditiva, manifiestos SHA-256 y privilegios limitados. Instantánea fotográfica verificada el 23/08/2026: 6.570 archivos, aproximadamente 36 GiB y tres ubicaciones verificadas."),
                ("INGENIERÍA ASISTIDA POR IA — FLUJO EN PROGRESO", "Reglas de lectura, especialización, verificación y memoria persistente. Persistencia entre sesiones y copia de seguridad de solo adición verificadas el 23/08/2026; la gobernanza del flujo continúa evolucionando."),
                (None, "Nota de evidencia: “Verificado” indica evidencia observada para el alcance y la fecha declarados. No implica auditoría independiente ni garantiza el estado actual."),
            ]),
            ("DIRECCIÓN ACTUAL", [
                "Mi dirección profesional apunta primero a roles de Data Engineer y Data Platform Engineer, con ML Engineer o AI Engineer como continuación natural. Me interesan los problemas donde es necesario construir la plataforma que vuelve los datos confiables, accesibles y útiles para personas, automatizaciones y sistemas de IA.",
            ]),
            ("CONTACTO PÚBLICO", [
                "https://ingseb.cloud/",
                "https://github.com/sebasnano",
                "https://ingseb.cloud/contacto.html",
            ]),
        ],
    },
    "en": {
        "name": "SEBASTIÁN RODRÍGUEZ",
        "role": "DATA ENGINEER / DATA PLATFORM ENGINEER",
        "tagline": "Python Backend · AI Engineering as a natural next step",
        "left": [
            ("PROFILE", [
                "I design systems in which data is reliable, traceable, and recoverable. My experience covers data processing in Python, relational databases, object storage, APIs and services, and the operation of Linux and cloud environments. I build the backend and operations around the guarantees that the data requires.",
            ]),
            ("SELECTED CAPABILITIES", [
                "• Data — Python, Polars, DuckDB, PostgreSQL, Parquet, PyArrow, object storage, and integrity verification using SHA-256. Applied in current projects.",
                "• Backend and platform — FastAPI, Redis, Docker, Linux, systemd, Tailscale, rclone, Nix, and Home Manager. Applied in current projects.",
                "• Complementary prior experience — MySQL, Oracle, Django, Flask, Celery, NestJS, TypeORM, and integrations using REST and OAuth.",
                "• Current development — Data Engineering, ML Engineering, AI Engineering, MLX, TensorFlow, Keras, PyTorch, and multi-agent systems. Ongoing learning and experimentation; this does not represent deployed models or demonstrated expert-level mastery.",
            ]),
        ],
        "right": [
            ("SELECTED EVIDENCE AND PROJECTS", [
                ("PERSONAL DATA LAKE — IN PROGRESS", "Object storage adapter, PostgreSQL catalog, and backfill of the existing inventory. Implementation and snapshot verified on 6 September 2026: 9,420 objects checked using SHA-256 and 9,235 unique active objects after deduplication. Verification included 212 host tests and 45 tests against a real PostgreSQL instance. It is not presented as a production-deployed catalog."),
                ("DATA PROTECTION — SCOPE IN PROGRESS", "Additive copy strategy, SHA-256 manifests, and limited privileges. Photographic snapshot verified on 23 August 2026: 6,570 files, approximately 36 GiB, and three verified locations."),
                ("AI-ASSISTED ENGINEERING — WORKFLOW IN PROGRESS", "Rules for reading, specialization, verification, and persistent memory. Cross-session persistence and append-only backup verified on 23 August 2026; workflow governance continues to evolve."),
                (None, "Evidence note: “Verified” indicates observed evidence for the stated scope and date. It does not imply an independent audit or guarantee the current state."),
            ]),
            ("CURRENT DIRECTION", [
                "My professional direction focuses first on Data Engineer and Data Platform Engineer roles, with ML Engineer or AI Engineer as a natural next step. I am particularly interested in problems that require building the platform that makes data reliable, accessible, and useful to people, automations, and AI systems.",
            ]),
            ("PUBLIC CONTACT", [
                "https://ingseb.cloud/",
                "https://github.com/sebasnano",
                "https://ingseb.cloud/contacto.html",
            ]),
        ],
    },
}

# Approximate Helvetica widths in ems. Conservative wrapping avoids clipped lines.
NARROW = set(" !'(),.:;Iijl|[]")
WIDE = set("MW@%&QGmwm")


def text_width(text: str, size: float) -> float:
    units = 0.0
    for char in text:
        if char in NARROW:
            units += 0.30
        elif char in WIDE:
            units += 0.82
        elif char.isupper() or char.isdigit():
            units += 0.61
        else:
            units += 0.51
    return units * size


def wrap(text: str, width: float, size: float, continuation_width: float | None = None) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        limit = width if not lines else (continuation_width or width)
        candidate = current + " " + word
        if text_width(candidate, size) <= limit:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def pdf_hex(text: str) -> str:
    return text.encode("cp1252").hex().upper()


def color(rgb: tuple[int, int, int]) -> str:
    return " ".join(f"{channel / 255:.4f}" for channel in rgb)


def add_text(commands: list[str], text: str, x: float, y: float, size: float,
             font: str = "F1", fill: tuple[int, int, int] = (27, 39, 47)) -> None:
    commands.append(
        f"BT /{font} {size:.2f} Tf {color(fill)} rg 1 0 0 1 {x:.2f} {y:.2f} Tm <{pdf_hex(text)}> Tj ET"
    )


def add_wrapped(commands: list[str], text: str, x: float, y: float, width: float,
                size: float = 9.0, leading: float = 11.4,
                fill: tuple[int, int, int] = (47, 61, 69),
                bullet: bool = False, italic_note: bool = False) -> float:
    indent = 10.0 if bullet else 0.0
    lines = wrap(text, width, size, width - indent if bullet else None)
    for index, line in enumerate(lines):
        line_x = x + (indent if bullet and index else 0.0)
        line_fill = (74, 88, 96) if italic_note else fill
        add_text(commands, line, line_x, y, size, "F1", line_fill)
        y -= leading
    return y


def add_heading(commands: list[str], heading: str, x: float, y: float, width: float) -> float:
    commands.append(f"{color((101, 212, 220))} RG 1.4 w {x:.2f} {y + 4.5:.2f} m {x + 18:.2f} {y + 4.5:.2f} l S")
    lines = wrap(heading, width - 24, 10.5)
    for line in lines:
        add_text(commands, line, x + 24, y, 10.5, "F2", (18, 63, 69))
        y -= 12.7
    return y - 6.0


def render_column(commands: list[str], sections: list[tuple[str, list]], x: float,
                  top: float, width: float) -> float:
    y = top
    for section_index, (heading, items) in enumerate(sections):
        if section_index:
            y -= 9.0
        y = add_heading(commands, heading, x, y, width)
        for item_index, item in enumerate(items):
            if item_index:
                y -= 7.0
            if isinstance(item, tuple):
                subheading, paragraph = item
                if subheading:
                    for line in wrap(subheading, width, 9.7):
                        add_text(commands, line, x, y, 9.7, "F2", (194, 102, 40))
                        y -= 12.4
                    y -= 2.0
                y = add_wrapped(
                    commands, paragraph, x, y, width,
                    size=9.8 if subheading else 9.4,
                    leading=13.0 if subheading else 12.2,
                    italic_note=subheading is None,
                )
            else:
                is_bullet = item.startswith("•")
                is_url = item.startswith("https://")
                if is_bullet and item_index:
                    y -= 5.0
                y = add_wrapped(
                    commands, item, x, y, width,
                    size=9.8 if not is_url else 9.5,
                    leading=15.0 if is_bullet else (12.5 if is_url else 13.2),
                    fill=(20, 103, 112) if is_url else (47, 61, 69),
                    bullet=is_bullet,
                )
    return y


def build_content(document: dict) -> bytes:
    commands = [
        "q",
        f"{color((248, 250, 250))} rg 0 0 {PAGE_WIDTH:.2f} {PAGE_HEIGHT:.2f} re f",
        f"{color((13, 19, 24))} rg 0 739 {PAGE_WIDTH:.2f} 102.89 re f",
        f"{color((241, 168, 91))} rg 0 739 8 102.89 re f",
        f"{color((101, 212, 220))} rg 34 752 72 3 re f",
    ]
    add_text(commands, document["name"], 34, 802, 23.0, "F2", (237, 243, 245))
    add_text(commands, document["role"], 35, 781, 10.5, "F2", (101, 212, 220))
    add_text(commands, document["tagline"], 35, 762, 9.0, "F1", (241, 168, 91))

    left_bottom = render_column(commands, document["left"], 34, 715, 250)
    right_bottom = render_column(commands, document["right"], 311, 715, 250)
    commands.extend([
        f"{color((209, 220, 223))} RG 0.7 w 297.5 42 m 297.5 716 l S",
        "Q",
    ])
    if min(left_bottom, right_bottom) < 32:
        raise ValueError(f"CV content exceeds page: bottoms are {left_bottom:.1f}, {right_bottom:.1f}")
    return ("\n".join(commands) + "\n").encode("ascii")


def assemble_pdf(content: bytes) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox {MEDIA_BOX} "
            "/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"endstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def build_all() -> dict[str, bytes]:
    return {language: assemble_pdf(build_content(document)) for language, document in CVS.items()}


def source_sequence(document: dict) -> list[str]:
    values = [document["name"], document["role"], document["tagline"]]
    for column in (document["left"], document["right"]):
        for heading, items in column:
            values.append(heading)
            for item in items:
                if isinstance(item, tuple):
                    if item[0]:
                        values.append(item[0])
                    values.append(item[1])
                else:
                    values.append(item)
    return values


def decoded_text(pdf: bytes) -> str:
    chunks = re.findall(rb"<([0-9A-F]+)> Tj", pdf)
    return "\n".join(bytes.fromhex(chunk.decode("ascii")).decode("cp1252") for chunk in chunks)


def assert_structure(pdf: bytes, language: str) -> None:
    if not pdf.startswith(b"%PDF-1.4\n") or not pdf.endswith(b"%%EOF\n"):
        raise AssertionError(f"{language}: invalid PDF header or EOF")
    if len(re.findall(rb"/Type\s*/Page\b", pdf)) != 1:
        raise AssertionError(f"{language}: PDF must contain exactly one page object")
    if b"/Count 1" not in pdf or f"/MediaBox {MEDIA_BOX}".encode("ascii") not in pdf:
        raise AssertionError(f"{language}: page count or A4 MediaBox is invalid")
    startxref_match = re.search(rb"startxref\n(\d+)\n%%EOF\n$", pdf)
    if not startxref_match:
        raise AssertionError(f"{language}: missing startxref")
    xref_offset = int(startxref_match.group(1))
    if pdf[xref_offset:xref_offset + 5] != b"xref\n":
        raise AssertionError(f"{language}: startxref does not point to xref")
    entries = re.findall(rb"^(\d{10}) 00000 n $", pdf, re.MULTILINE)
    for object_number, entry in enumerate(entries, 1):
        offset = int(entry)
        if not pdf[offset:].startswith(f"{object_number} 0 obj\n".encode("ascii")):
            raise AssertionError(f"{language}: bad xref offset for object {object_number}")
    if b"stream\n" not in pdf or b"\nendstream" not in pdf:
        raise AssertionError(f"{language}: missing renderable content stream")


def assert_content(pdf: bytes, language: str) -> None:
    text = decoded_text(pdf)
    cursor = 0
    for approved in source_sequence(CVS[language]):
        for token in approved.split():
            token_position = text.find(token, cursor)
            if token_position < 0:
                raise AssertionError(f"{language}: missing or reordered approved token {token!r}")
            cursor = token_position + len(token)
    required = ["SHA-256", "9,420" if language == "en" else "9.420", "212", "45",
                "https://ingseb.cloud/", "https://github.com/sebasnano",
                "https://ingseb.cloud/contacto.html"]
    for marker in required:
        if marker not in text:
            raise AssertionError(f"{language}: missing approved marker {marker!r}")
    if language == "en" and ("Datagast" in text or "ingseb.cloud.rect" in text):
        raise AssertionError("en: transcription corruption remains")


def assert_no_forbidden_data(pdf: bytes, language: str) -> None:
    raw = pdf.decode("latin1")
    text = decoded_text(pdf)
    forbidden_raw = [
        r"/CreationDate\b", r"/ModDate\b", r"/Creator\b", r"/Producer\b",
        r"/Author\b", r"/Title\b", r"/Subject\b", r"/Keywords\b",
        r"/Users/", r"[A-Za-z]:\\Users\\", r"file://", r"localhost",
        r"127\.0\.0\.1", r"(?:10|192\.168)\.\d{1,3}\.\d{1,3}",
    ]
    forbidden_text = [
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        r"(?:\+?\d[\s().-]*){10,}",
    ]
    for pattern in forbidden_raw:
        if re.search(pattern, raw, re.IGNORECASE):
            raise AssertionError(f"{language}: forbidden operational pattern {pattern!r}")
    for pattern in forbidden_text:
        if re.search(pattern, text, re.IGNORECASE):
            raise AssertionError(f"{language}: forbidden private-data pattern {pattern!r}")


def check(generated: dict[str, bytes]) -> None:
    for language, pdf in generated.items():
        output = OUTPUTS[language]
        if not output.exists():
            raise AssertionError(f"missing tracked PDF: {output.relative_to(ROOT)}")
        if output.read_bytes() != pdf:
            raise AssertionError(f"generated bytes differ: {output.relative_to(ROOT)}")
        assert_structure(pdf, language)
        assert_content(pdf, language)
        assert_no_forbidden_data(pdf, language)
        print(f"{output.relative_to(ROOT)}: {len(pdf)} bytes sha256={hashlib.sha256(pdf).hexdigest()} page_count=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify committed PDFs without writing")
    args = parser.parse_args()
    generated = build_all()
    if args.check:
        check(generated)
    else:
        for language, pdf in generated.items():
            OUTPUTS[language].parent.mkdir(parents=True, exist_ok=True)
            OUTPUTS[language].write_bytes(pdf)
            print(f"wrote {OUTPUTS[language].relative_to(ROOT)} ({len(pdf)} bytes)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, UnicodeEncodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
