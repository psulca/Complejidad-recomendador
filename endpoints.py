from fastapi import APIRouter, HTTPException
from typing import List, Optional
import os
import networkx as nx
from models import UsuarioCreate, UsuarioUpdate, StudentInput, HistorialCreate, HistorialUpdate
from services import UsuarioService, CursoService, PlanificacionService
from motor_academico import MotorAcademico
from database import get_supabase

router = APIRouter()
motor: Optional[MotorAcademico] = None


def set_motor(m: MotorAcademico):
    global motor
    motor = m


@router.get("/")
def home():
    return {"status": "ok", "message": "API del Motor Académico funcionando"}


@router.get("/api/usuario/{user_id}")
def get_usuario(user_id: str):
    return UsuarioService.obtener_usuario(user_id)


@router.post("/api/usuario")
def crear_usuario(usuario: UsuarioCreate, user_id: str):
    return UsuarioService.crear_usuario(usuario, user_id)


@router.put("/api/usuario/{user_id}")
def actualizar_usuario(user_id: str, usuario: UsuarioUpdate):
    """Actualizar información del usuario/estudiante"""
    try:
        return UsuarioService.actualizar_usuario(user_id, usuario)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[ENDPOINT ACTUALIZAR USUARIO] Error inesperado: {type(e).__name__}: {str(e)}")
        print(f"[ENDPOINT ACTUALIZAR USUARIO] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar usuario: {str(e)}"
        )


@router.get("/api/usuario/{user_id}/historial")
def obtener_historial_completo(user_id: str, carrera: Optional[str] = None):
    """Obtener el historial académico completo del usuario con detalles de cursos"""
    return UsuarioService.obtener_historial_completo(user_id, carrera)


@router.post("/api/usuario/{user_id}/historial")
def agregar_curso_aprobado(user_id: str, historial_data: HistorialCreate):
    """Agregar un curso aprobado al historial académico del usuario"""
    try:
        return UsuarioService.agregar_curso_aprobado(
            user_id, 
            historial_data.curso_codigo, 
            historial_data.carrera
        )
    except HTTPException as e:
        print(f"[ENDPOINT] HTTPException capturada: {e.status_code} - {e.detail}")
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ENDPOINT] Error inesperado al agregar curso:")
        print(f"[ENDPOINT] {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al agregar curso al historial: {str(e)}"
        )


@router.put("/api/usuario/{user_id}/historial/{curso_codigo}")
def actualizar_curso_aprobado(user_id: str, curso_codigo: str, historial_update: HistorialUpdate):
    """Actualizar un curso aprobado en el historial académico"""
    return UsuarioService.actualizar_curso_aprobado(user_id, curso_codigo, historial_update)


@router.delete("/api/usuario/{user_id}/historial/{curso_codigo}")
def eliminar_curso_aprobado(user_id: str, curso_codigo: str, carrera: Optional[str] = None):
    """Eliminar un curso aprobado del historial académico"""
    return UsuarioService.eliminar_curso_aprobado(user_id, curso_codigo, carrera)


@router.get("/api/grafo")
def get_grafo_completo(carrera: Optional[str] = None):
    if not motor:
        raise HTTPException(status_code=500, detail="El motor no está inicializado")
    
    if carrera and carrera.strip():
        carrera_filtro_clean = carrera.strip().lower()
        nodos = []
        nodos_ids_compuestos = set()
        
        for n, data in motor.graph.nodes(data=True):
            if data.get("carrera", "").strip().lower() == carrera_filtro_clean:
                nodos_ids_compuestos.add(n)
                
                creditos_generales_requeridos = data.get("creditos_generales_requeridos", [])
                
                nodo = {
                    "id": motor._extraer_codigo(n),
                    "label": data.get("nombre", n),
                    "nivel": data.get("nivel", 0),
                    "creditos": data.get("creditos", 0),
                    "carrera": data.get("carrera", "")
                }
                
                if creditos_generales_requeridos:
                    nodo["creditos_generales_requeridos"] = max(creditos_generales_requeridos)
                
                nodos.append(nodo)
        
        aristas = []
        for u, v, edge_data in motor.graph.edges(data=True):
            if (u in nodos_ids_compuestos and v in nodos_ids_compuestos
                and motor.graph.nodes[u].get("carrera", "").strip().lower() == carrera_filtro_clean
                and motor.graph.nodes[v].get("carrera", "").strip().lower() == carrera_filtro_clean):
                
                arista = {
                    "source": motor._extraer_codigo(u),
                    "target": motor._extraer_codigo(v)
                }
                
                if edge_data.get("tipo") == "COURSE_CRED" and "creditos_requeridos" in edge_data:
                    arista["tipo"] = "COURSE_CRED"
                    arista["creditos_requeridos"] = edge_data["creditos_requeridos"]
                elif edge_data.get("tipo") == "COURSE":
                    arista["tipo"] = "COURSE"
                
                aristas.append(arista)
    else:
        nodos_por_codigo = {}
        
        for n, data in motor.graph.nodes(data=True):
            codigo = motor._extraer_codigo(n)
            if codigo not in nodos_por_codigo:
                creditos_generales_requeridos = data.get("creditos_generales_requeridos", [])
                
                nodo = {
                    "id": codigo,
                    "label": data.get("nombre", codigo),
                    "nivel": data.get("nivel", 0),
                    "creditos": data.get("creditos", 0),
                    "carrera": ""
                }
                
                if creditos_generales_requeridos:
                    nodo["creditos_generales_requeridos"] = max(creditos_generales_requeridos)
                
                nodos_por_codigo[codigo] = nodo
        
        nodos = list(nodos_por_codigo.values())
        
        aristas_dict = {}
        for u, v, edge_data in motor.graph.edges(data=True):
            codigo_u = motor._extraer_codigo(u)
            codigo_v = motor._extraer_codigo(v)
            if codigo_u != codigo_v:
                key = (codigo_u, codigo_v)
                if key not in aristas_dict:
                    arista = {
                        "source": codigo_u,
                        "target": codigo_v
                    }
                    
                    if edge_data.get("tipo") == "COURSE_CRED" and "creditos_requeridos" in edge_data:
                        arista["tipo"] = "COURSE_CRED"
                        arista["creditos_requeridos"] = edge_data["creditos_requeridos"]
                    elif edge_data.get("tipo") == "COURSE":
                        arista["tipo"] = "COURSE"
                    
                    aristas_dict[key] = arista
        
        aristas = list(aristas_dict.values())
    
    return {
        "nodes": nodos,
        "edges": aristas,
        "total_nodes": len(nodos),
        "total_edges": len(aristas),
        "carrera_filtro": carrera if carrera else None
    }


@router.post("/api/planificar")
def generar_plan(input_data: StudentInput):
    if not motor:
        raise HTTPException(status_code=500, detail="El motor no está inicializado")
    
    creditos_previos = PlanificacionService.calcular_creditos_previos(
        input_data.historial, motor, input_data.carrera
    )
    
    todos, sugeridos = motor.generar_planificacion(
        input_data.historial,
        input_data.max_creditos,
        carrera_filtro=input_data.carrera
    )
    
    return {
        "resumen_creditos_aprobados": creditos_previos,
        "carrera_filtro": input_data.carrera,
        "cursos_disponibles": todos,
        "recomendacion_optima": sugeridos
    }


@router.post("/api/planificar/{user_id}")
def generar_plan_usuario(user_id: str, max_creditos: float = 22.0, carrera: Optional[str] = None):
    if not motor:
        raise HTTPException(status_code=500, detail="El motor no está inicializado")
    
    historial = UsuarioService.obtener_historial(user_id)
    
    if not carrera:
        carrera = UsuarioService.obtener_carrera_usuario(user_id)
    
    creditos_previos = PlanificacionService.calcular_creditos_previos(historial, motor, carrera)
    todos, sugeridos = motor.generar_planificacion(historial, max_creditos, carrera_filtro=carrera)
    
    return {
        "resumen_creditos_aprobados": creditos_previos,
        "carrera_filtro": carrera,
        "cursos_disponibles": todos,
        "recomendacion_optima": sugeridos
    }


@router.get("/api/cursos")
def get_cursos(carrera: Optional[str] = None):
    return CursoService.obtener_cursos(carrera)


@router.get("/api/carreras")
def get_carreras():
    return CursoService.obtener_carreras()


@router.post("/api/cursos/recargar")
def recargar_cursos_desde_csv():
    global motor
    csv_file = "mallas_consolidadas.csv"
    
    if not os.path.exists(csv_file):
        raise HTTPException(status_code=404, detail="No se encontró el archivo 'mallas_consolidadas.csv'")
    
    if motor is None:
        motor = MotorAcademico(None)
    
    motor.graph = nx.DiGraph()
    motor.cargar_desde_csv(csv_file, borrar_existentes=True)
    motor.cargar_cursos_desde_db()
    
    return {
        "message": "Cursos recargados exitosamente",
        "total_cursos": len(motor.graph.nodes)
    }

