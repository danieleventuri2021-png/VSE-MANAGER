from pathlib import Path
import re


def read_xml_document_text(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return extract_xml_document_text(text)


def extract_xml_document_text(text: str) -> str:
    stripped = text.lstrip("\ufeff\r\n\t ")
    prefix_len = len(text) - len(stripped)
    match = re.search(r"<([A-Za-z_][\w:.-]*)(?:\s|>|/>)", stripped)
    if not match:
        return text
    root_name = match.group(1)
    end_tag = f"</{root_name}>"
    end_index = stripped.rfind(end_tag)
    if end_index < 0:
        return text
    end_index += len(end_tag)
    return text[:prefix_len] + stripped[:end_index]
