"""生成阶段 2 验收所需的最小 PDF 测试夹具。

用最朴素的 PDF 语法手工构造含文本流的两类文件：
- short.pdf：单页，包含可提取文本
- multi_page.pdf：两页，第二页为空白，验证空白页跳过
- broken.pdf：无法解析的损坏文件
不再依赖 reportlab，避免额外依赖。

用法：
    .venv\\Scripts\\python.exe tests/make_fixture_pdfs.py
"""
from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def make_text_pdf(pages_text: list[str]) -> bytes:
    """构造一个带 Type1/Helvetica 文本流的简单多页 PDF。"""
    n = len(pages_text)
    if n == 0:
        n = 1
        pages_text = [""]
    font_num = 3 + 2 * n
    total = font_num

    bodies: dict[int, bytes] = {}

    for i, text in enumerate(pages_text):
        page_num = 3 + i
        content_num = 3 + n + i
        stream = (f"BT /F1 12 Tf 72 720 Td ({_escape(text)}) Tj ET\n").encode("ascii")
        bodies[content_num] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"endstream"
        )
        bodies[page_num] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_num} 0 R >> >> "
            f"/Contents {content_num} 0 R >>"
        ).encode("ascii")

    kids = " ".join(f"{3 + i} 0 R" for i in range(n)).encode("ascii")
    bodies[2] = f"<< /Type /Pages /Kids [{kids.decode()}] /Count {n} >>".encode("ascii")
    bodies[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    bodies[font_num] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for num in range(1, total + 1):
        offsets[num] = len(out)
        out.extend(f"{num} 0 obj\n".encode("ascii"))
        out.extend(bodies[num])
        out.extend(b"\nendobj\n")

    xref_start = len(out)
    out.extend(f"xref\n0 {total + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for num in range(1, total + 1):
        out.extend(f"{offsets[num]:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {total + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


def main() -> None:
    root = Path(__file__).resolve().parent / "fixtures"
    root.mkdir(parents=True, exist_ok=True)
    (root / "short.pdf").write_bytes(make_text_pdf(["PolicyRAG Employee Handbook Short Page"]))
    (root / "multi_page.pdf").write_bytes(
        make_text_pdf(["PolicyRAG Page One Overtime Policy", ""])
    )
    (root / "broken.pdf").write_bytes(b"this is not a real pdf file")

    print("pdf fixtures written to", root)


if __name__ == "__main__":
    main()
