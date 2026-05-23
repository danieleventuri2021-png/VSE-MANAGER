from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from pydantic import computed_field


class JobCreate(BaseModel):
    titolo: str = Field(min_length=1, max_length=255)
    cliente_nome: str | None = None
    mtr_folder: str | None = None
    workflow_mode: str | None = None


class FolderRequest(BaseModel):
    folder_path: str


class PdfGenerateRequest(BaseModel):
    output_dir: str | None = None


class JobRead(BaseModel):
    id: int
    titolo: str
    cliente_nome: str | None
    stato: str
    excel_path: str | None
    mtr_folder: str | None
    summary: dict[str, Any]
    tecnico_default: str | None = None
    firma_default_path: str | None = None
    proprieta_default: str | None = None
    periodicita_default: str | None = None
    tensione_default: str | None = None
    frequenza_default: str | None = None
    protezione_default: str | None = None
    template_pdf: str | None = None
    intestazione_pdf: str | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def workflow_mode(self) -> str:
        if (self.summary or {}).get("workflow_mode") == "simple":
            return "simple"
        if self.titolo == "Generazione PDF" and not self.excel_path and not self.cliente_nome:
            return "simple"
        return "full"

    model_config = {"from_attributes": True}


class ApplyResult(BaseModel):
    backup_dir: str
    renamed: list[dict[str, str]]
    conflicts: list[dict[str, str]]


class SystemPorts(BaseModel):
    backend: dict[str, Any]
    frontend: dict[str, Any]
