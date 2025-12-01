from pydantic import BaseModel
from typing import List, Optional, Any


class Usuario(BaseModel):
    id: str
    email: Optional[str] = None
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    carrera: Optional[str] = None
    codigo_alumno: Optional[str] = None
    creditos_totales: float = 0.0
    tiene_perfil: Optional[bool] = None


class UsuarioCreate(BaseModel):
    carrera: Optional[str] = None
    codigo_alumno: Optional[str] = None


class UsuarioUpdate(BaseModel):
    carrera: Optional[str] = None
    codigo_alumno: Optional[str] = None


class StudentInput(BaseModel):
    historial: List[str]
    max_creditos: float = 22.0
    carrera: str


class CursoItem(BaseModel):
    id: str
    nombre: str
    creditos: float
    nivel: Any = 0
    impacto: int


class PlanResponse(BaseModel):
    resumen_creditos_aprobados: float
    cursos_disponibles: List[CursoItem]
    recomendacion_optima: List[CursoItem]


class CursoAprobado(BaseModel):
    curso_codigo: str
    carrera: str
    nombre: Optional[str] = None
    creditos: Optional[float] = None
    nivel: Optional[int] = None
    aprobado_en: Optional[str] = None


class HistorialResponse(BaseModel):
    usuario_id: str
    cursos: List[CursoAprobado]
    total_cursos: int
    total_creditos: float


class HistorialCreate(BaseModel):
    curso_codigo: str
    carrera: Optional[str] = None


class HistorialUpdate(BaseModel):
    curso_codigo: str
    carrera: Optional[str] = None
    aprobado_en: Optional[str] = None

