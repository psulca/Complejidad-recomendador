from typing import List, Optional, Dict
from datetime import datetime
from fastapi import HTTPException
from database import get_supabase
from models import UsuarioCreate, UsuarioUpdate, HistorialUpdate


class UsuarioService:
    @staticmethod
    def obtener_usuario(user_id: str) -> Dict:
        supabase = get_supabase()
        
        # Usar la función SQL que combina datos de auth.users y usuarios
        response = supabase.rpc("get_user_profile", {"p_user_id": user_id}).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Verificar si es una lista o un diccionario
        if isinstance(response.data, list):
            if not response.data or len(response.data) == 0:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
            usuario = response.data[0]
        elif isinstance(response.data, dict):
            usuario = response.data
        else:
            raise HTTPException(status_code=500, detail="Formato de respuesta inesperado")
        
        # Obtener historial simple (solo códigos) de forma eficiente
        historial = UsuarioService._obtener_historial(user_id)
        usuario["historial_aprobados"] = historial
        
        # Los créditos totales ya vienen del get_user_profile desde la tabla usuarios
        # Solo se recalculan cuando se modifica el historial (en agregar/eliminar curso)
        
        return usuario
    
    @staticmethod
    def crear_usuario(usuario: UsuarioCreate, user_id: str) -> Dict:
        supabase = get_supabase()
        
        update_data = {}
        if usuario.carrera is not None:
            update_data["carrera"] = usuario.carrera
        if usuario.codigo_alumno is not None:
            update_data["codigo_alumno"] = usuario.codigo_alumno
        
        if not update_data:
            update_data["creditos_totales"] = 0.0
        
        update_data["updated_at"] = datetime.now().isoformat()
        
        response = supabase.table("usuarios").upsert({
            "id": user_id,
            **update_data
        }, on_conflict="id").execute()
        
        return response.data[0] if response.data else {"id": user_id, **update_data}
    
    @staticmethod
    def actualizar_usuario(user_id: str, usuario: UsuarioUpdate) -> Dict:
        supabase = get_supabase()
        
        print(f"[ACTUALIZAR USUARIO] Iniciando actualización para usuario: {user_id}")
        print(f"[ACTUALIZAR USUARIO] Datos recibidos: {usuario.dict()}")
        
        # Verificar que el usuario existe primero
        usuario_existente = supabase.table("usuarios").select("*").eq("id", user_id).execute()
        print(f"[ACTUALIZAR USUARIO] Usuario existente: {usuario_existente.data}")
        
        if not usuario_existente.data:
            print(f"[ACTUALIZAR USUARIO] ERROR: Usuario no encontrado en BD")
            raise HTTPException(status_code=404, detail=f"Usuario {user_id} no encontrado")
        
        update_data = usuario.dict(exclude_unset=True)
        
        # Remover creditos_totales si viene (se calcula automáticamente)
        update_data.pop("creditos_totales", None)
        
        if not update_data:
            print(f"[ACTUALIZAR USUARIO] No hay cambios para actualizar")
            return {"message": "No hay cambios para actualizar"}
        
        print(f"[ACTUALIZAR USUARIO] Datos a actualizar: {update_data}")
        
        update_data["updated_at"] = datetime.now().isoformat()
        
        try:
            print(f"[ACTUALIZAR USUARIO] Ejecutando UPDATE en BD...")
            response = supabase.table("usuarios").update(update_data).eq("id", user_id).execute()
            print(f"[ACTUALIZAR USUARIO] Respuesta del update - Tipo: {type(response)}")
            print(f"[ACTUALIZAR USUARIO] Respuesta del update - Data: {response.data}")
            print(f"[ACTUALIZAR USUARIO] Respuesta del update - Status: {getattr(response, 'status_code', 'N/A')}")
            
            # Intentar obtener el usuario actualizado siempre (por si el UPDATE no devuelve datos)
            print(f"[ACTUALIZAR USUARIO] Obteniendo usuario actualizado después del UPDATE...")
            usuario_actualizado_query = supabase.table("usuarios").select("*").eq("id", user_id).execute()
            print(f"[ACTUALIZAR USUARIO] Usuario obtenido después del UPDATE: {usuario_actualizado_query.data}")
            
            if usuario_actualizado_query.data and len(usuario_actualizado_query.data) > 0:
                usuario_actualizado = usuario_actualizado_query.data[0]
                
                # Recalcular créditos después de actualizar (por si cambió la carrera)
                UsuarioService._actualizar_creditos_usuario(user_id)
                
                # Obtener créditos actualizados
                usuario_actualizado["creditos_totales"] = UsuarioService._calcular_creditos_desde_historial(user_id)
                
                print(f"[ACTUALIZAR USUARIO] Usuario actualizado exitosamente")
                return usuario_actualizado
            else:
                print(f"[ACTUALIZAR USUARIO] ERROR: No se pudo obtener el usuario después del UPDATE")
                raise HTTPException(status_code=404, detail="Usuario no encontrado después de la actualización")
            
        except Exception as e:
            import traceback
            print(f"[ACTUALIZAR USUARIO] ERROR: {type(e).__name__}: {str(e)}")
            print(f"[ACTUALIZAR USUARIO] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Error al actualizar usuario: {str(e)}")
    
    @staticmethod
    def agregar_curso_aprobado(user_id: str, curso_codigo: str, carrera: Optional[str] = None) -> Dict:
        import traceback
        supabase = get_supabase()
        
        try:
            print(f"[AGREGAR CURSO] Iniciando - user_id: {user_id}, curso_codigo: {curso_codigo}, carrera_provided: {carrera}")
            
            if not carrera:
                print(f"[AGREGAR CURSO] Carrera no proporcionada, obteniendo del usuario...")
                carrera = UsuarioService.obtener_carrera_usuario(user_id)
                if not carrera:
                    error_msg = f"El usuario {user_id} debe tener una carrera asignada"
                    print(f"[AGREGAR CURSO] ERROR: {error_msg}")
                    raise HTTPException(status_code=400, detail=error_msg)
                print(f"[AGREGAR CURSO] Carrera obtenida: {carrera}")
            
            print(f"[AGREGAR CURSO] Buscando curso: {curso_codigo} en carrera: {carrera}")
            curso = CursoService.obtener_curso_por_carrera(curso_codigo, carrera)
            print(f"[AGREGAR CURSO] Curso encontrado: {curso}")
            
            hist_data = {
                "usuario_id": user_id,
                "curso_codigo": curso_codigo,
                "carrera": carrera
            }
            print(f"[AGREGAR CURSO] Datos a insertar: {hist_data}")
            
            print(f"[AGREGAR CURSO] Ejecutando upsert en historial_aprobados...")
            response = supabase.table("historial_aprobados").upsert(
                hist_data, 
                on_conflict="usuario_id,curso_codigo,carrera"
            ).execute()
            print(f"[AGREGAR CURSO] Upsert exitoso: {response.data if hasattr(response, 'data') else 'No data'}")
            
            print(f"[AGREGAR CURSO] Actualizando créditos del usuario desde historial...")
            UsuarioService._actualizar_creditos_usuario(user_id)
            print(f"[AGREGAR CURSO] Créditos actualizados correctamente")
            
            return {"message": "Curso agregado al historial", "curso": curso_codigo, "carrera": carrera}
            
        except HTTPException:
            raise
        except Exception as e:
            error_detail = str(e)
            error_trace = traceback.format_exc()
            print(f"[AGREGAR CURSO] ERROR NO MANEJADO:")
            print(f"[AGREGAR CURSO] Tipo de error: {type(e).__name__}")
            print(f"[AGREGAR CURSO] Mensaje: {error_detail}")
            print(f"[AGREGAR CURSO] Traceback completo:\n{error_trace}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error al agregar curso al historial: {error_detail}. Tipo: {type(e).__name__}"
            )
    
    @staticmethod
    def eliminar_curso_aprobado(user_id: str, curso_codigo: str, carrera: Optional[str] = None) -> Dict:
        supabase = get_supabase()
        
        if not carrera:
            carrera = UsuarioService.obtener_carrera_usuario(user_id)
            if not carrera:
                raise HTTPException(status_code=400, detail="El usuario debe tener una carrera asignada")
        
        curso = CursoService.obtener_curso_por_carrera(curso_codigo, carrera)
        
        supabase.table("historial_aprobados").delete().eq(
            "usuario_id", user_id
        ).eq("curso_codigo", curso_codigo).eq("carrera", carrera).execute()
        
        UsuarioService._actualizar_creditos_usuario(user_id)
        
        return {"message": "Curso eliminado del historial"}
    
    @staticmethod
    def obtener_historial(user_id: str, carrera: Optional[str] = None) -> List[str]:
        return UsuarioService._obtener_historial(user_id, carrera)
    
    @staticmethod
    def obtener_historial_completo(user_id: str, carrera: Optional[str] = None) -> Dict:
        supabase = get_supabase()
        query = supabase.table("historial_aprobados").select(
            "curso_codigo, carrera, aprobado_en"
        ).eq("usuario_id", user_id)
        
        if carrera:
            query = query.eq("carrera", carrera)
        
        response = query.execute()
        historial_items = response.data or []
        
        cursos_detalle = []
        total_creditos = 0.0
        
        for item in historial_items:
            curso_codigo = item["curso_codigo"]
            curso_carrera = item["carrera"]
            
            try:
                curso_info = CursoService.obtener_curso_por_carrera(curso_codigo, curso_carrera)
                cursos_detalle.append({
                    "curso_codigo": curso_codigo,
                    "carrera": curso_carrera,
                    "nombre": curso_info.get("nombre", ""),
                    "creditos": float(curso_info.get("creditos", 0)),
                    "nivel": curso_info.get("nivel", 0),
                    "aprobado_en": item.get("aprobado_en")
                })
                total_creditos += float(curso_info.get("creditos", 0))
            except HTTPException:
                cursos_detalle.append({
                    "curso_codigo": curso_codigo,
                    "carrera": curso_carrera,
                    "nombre": "Curso no encontrado",
                    "creditos": 0,
                    "nivel": 0,
                    "aprobado_en": item.get("aprobado_en")
                })
        
        return {
            "usuario_id": user_id,
            "cursos": cursos_detalle,
            "total_cursos": len(cursos_detalle),
            "total_creditos": total_creditos
        }
    
    @staticmethod
    def actualizar_curso_aprobado(user_id: str, curso_codigo: str, historial_update: HistorialUpdate) -> Dict:
        supabase = get_supabase()
        
        carrera_actual = historial_update.carrera
        if not carrera_actual:
            response = supabase.table("historial_aprobados").select("carrera").eq(
                "usuario_id", user_id
            ).eq("curso_codigo", curso_codigo).execute()
            
            if not response.data:
                raise HTTPException(status_code=404, detail="Curso no encontrado en el historial")
            
            carrera_actual = response.data[0]["carrera"]
        
        update_data = {}
        if historial_update.aprobado_en:
            update_data["aprobado_en"] = historial_update.aprobado_en
        
        carrera_final = historial_update.carrera or carrera_actual
        if carrera_final != carrera_actual:
            update_data["carrera"] = carrera_final
            
            curso = CursoService.obtener_curso_por_carrera(curso_codigo, carrera_final)
            
            supabase.table("historial_aprobados").delete().eq(
                "usuario_id", user_id
            ).eq("curso_codigo", curso_codigo).eq("carrera", carrera_actual).execute()
            
            hist_data = {
                "usuario_id": user_id,
                "curso_codigo": curso_codigo,
                "carrera": carrera_final
            }
            
            if historial_update.aprobado_en:
                hist_data["aprobado_en"] = historial_update.aprobado_en
            
            supabase.table("historial_aprobados").insert(hist_data).execute()
            
            # Recalcular créditos después de actualizar
            UsuarioService._actualizar_creditos_usuario(user_id)
            
            return {"message": "Curso actualizado en el historial", "curso": curso_codigo, "carrera": carrera_final}
        
        if update_data:
            supabase.table("historial_aprobados").update(update_data).eq(
                "usuario_id", user_id
            ).eq("curso_codigo", curso_codigo).eq("carrera", carrera_actual).execute()
            
            # Recalcular créditos después de actualizar
            UsuarioService._actualizar_creditos_usuario(user_id)
            
            return {"message": "Historial actualizado", "curso": curso_codigo, "carrera": carrera_actual}
        
        return {"message": "No hay cambios para actualizar"}
    
    @staticmethod
    def obtener_carrera_usuario(user_id: str) -> Optional[str]:
        supabase = get_supabase()
        print(f"[OBTENER CARRERA] Buscando carrera para usuario: {user_id}")
        try:
            response = supabase.table("usuarios").select("carrera").eq("id", user_id).execute()
            print(f"[OBTENER CARRERA] Respuesta recibida: {response.data}")
            
            if response.data and len(response.data) > 0:
                carrera = response.data[0].get("carrera")
                print(f"[OBTENER CARRERA] Carrera encontrada: {carrera}")
                return carrera
            else:
                print(f"[OBTENER CARRERA] Usuario no encontrado en tabla usuarios")
                return None
        except Exception as e:
            print(f"[OBTENER CARRERA] Error al buscar carrera: {type(e).__name__}: {str(e)}")
            return None
    
    @staticmethod
    def obtener_historial_completo(user_id: str, carrera: Optional[str] = None) -> Dict:
        supabase = get_supabase()
        query = supabase.table("historial_aprobados").select(
            "curso_codigo, carrera, aprobado_en"
        ).eq("usuario_id", user_id)
        
        if carrera:
            query = query.eq("carrera", carrera)
        
        response = query.execute()
        historial_items = response.data or []
        
        cursos_detalle = []
        total_creditos = 0.0
        
        for item in historial_items:
            curso_codigo = item["curso_codigo"]
            curso_carrera = item["carrera"]
            
            try:
                curso_info = CursoService.obtener_curso_por_carrera(curso_codigo, curso_carrera)
                cursos_detalle.append({
                    "curso_codigo": curso_codigo,
                    "carrera": curso_carrera,
                    "nombre": curso_info.get("nombre", ""),
                    "creditos": float(curso_info.get("creditos", 0)),
                    "nivel": curso_info.get("nivel", 0),
                    "aprobado_en": item.get("aprobado_en")
                })
                total_creditos += float(curso_info.get("creditos", 0))
            except HTTPException:
                cursos_detalle.append({
                    "curso_codigo": curso_codigo,
                    "carrera": curso_carrera,
                    "nombre": "Curso no encontrado",
                    "creditos": 0,
                    "nivel": 0,
                    "aprobado_en": item.get("aprobado_en")
                })
        
        return {
            "usuario_id": user_id,
            "cursos": cursos_detalle,
            "total_cursos": len(cursos_detalle),
            "total_creditos": total_creditos
        }
    
    @staticmethod
    def _obtener_historial(user_id: str, carrera: Optional[str] = None) -> List[str]:
        supabase = get_supabase()
        query = supabase.table("historial_aprobados").select("curso_codigo, carrera").eq("usuario_id", user_id)
        
        if carrera:
            query = query.eq("carrera", carrera)
        
        response = query.execute()
        return [h["curso_codigo"] for h in (response.data or [])]
    
    @staticmethod
    def _calcular_creditos_rapido(user_id: str) -> float:
        """Calcula los créditos totales sumando créditos de cursos aprobados (función backend optimizada)"""
        supabase = get_supabase()
        
        # Obtener historial de cursos aprobados
        historial_items = supabase.table("historial_aprobados").select(
            "curso_codigo, carrera"
        ).eq("usuario_id", user_id).execute()
        
        if not historial_items.data:
            return 0.0
        
        # Crear conjunto de códigos únicos y mapeo (codigo, carrera) para filtrar después
        codigos_unicos = list(set([item["curso_codigo"] for item in historial_items.data]))
        codigos_carreras = [(item["curso_codigo"], item["carrera"]) for item in historial_items.data]
        
        # Obtener TODOS los cursos con esos códigos en una sola query (mucho más eficiente)
        # Paginamos si hay muchos códigos
        todos_cursos = []
        batch_size = 100  # Supabase permite múltiples valores en .in()
        
        for i in range(0, len(codigos_unicos), batch_size):
            batch_codigos = codigos_unicos[i:i + batch_size]
            response = supabase.table("cursos").select("codigo, carrera, creditos").in_("codigo", batch_codigos).execute()
            if response.data:
                todos_cursos.extend(response.data)
        
        # Crear diccionario para búsqueda rápida: (codigo, carrera) -> créditos
        cursos_dict = {}
        for curso in todos_cursos:
            key = (curso["codigo"], curso["carrera"])
            cursos_dict[key] = float(curso.get("creditos", 0))
        
        # Sumar créditos solo de los cursos que están en el historial
        total = 0.0
        for codigo, carrera in codigos_carreras:
            total += cursos_dict.get((codigo, carrera), 0.0)
        
        return total
    
    @staticmethod
    def _calcular_creditos_desde_historial(user_id: str) -> float:
        """Calcula los créditos totales sumando todos los cursos en historial_aprobados"""
        return UsuarioService._calcular_creditos_rapido(user_id)
    
    @staticmethod
    def _actualizar_creditos_usuario(user_id: str, creditos: float = None, sumar: bool = True):
        """Actualiza los créditos del usuario. Si creditos es None, los calcula desde el historial"""
        supabase = get_supabase()
        try:
            if creditos is None:
                # Calcular desde el historial real
                creditos_totales = UsuarioService._calcular_creditos_desde_historial(user_id)
                print(f"[ACTUALIZAR CREDITOS] Créditos calculados desde historial: {creditos_totales}")
            else:
                # Método antiguo (mantener para compatibilidad)
                response = supabase.table("usuarios").select("creditos_totales").eq("id", user_id).execute()
                if response.data:
                    creditos_actuales = float(response.data[0]["creditos_totales"])
                    creditos_totales = creditos_actuales + creditos if sumar else max(0, creditos_actuales - creditos)
                    print(f"[ACTUALIZAR CREDITOS] Créditos calculados manualmente: {creditos_totales}")
                else:
                    creditos_totales = 0.0
            
            # Actualizar en la base de datos
            supabase.table("usuarios").update({
                "creditos_totales": creditos_totales,
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            print(f"[ACTUALIZAR CREDITOS] Créditos actualizados en BD: {creditos_totales}")
        except Exception as e:
            print(f"[ACTUALIZAR CREDITOS] ERROR: {type(e).__name__}: {str(e)}")
            raise


class CursoService:
    @staticmethod
    def obtener_cursos(carrera: Optional[str] = None) -> Dict:
        supabase = get_supabase()
        query = supabase.table("cursos").select("codigo, nombre, carrera, creditos, nivel")
        
        if carrera:
            query = query.ilike("carrera", f"%{carrera}%")
        
        response = query.order("codigo").execute()
        cursos = response.data or []
        
        lista_cursos = [
            {
                "value": curso["codigo"],
                "label": f"{curso['codigo']} - {curso['nombre']}",
                "carrera": curso.get("carrera", ""),
                "creditos": curso.get("creditos", 0),
                "nivel": curso.get("nivel", 0)
            }
            for curso in cursos
        ]
        
        return {
            "total": len(lista_cursos),
            "carrera_filtro": carrera if carrera else "Todas",
            "cursos": lista_cursos
        }
    
    @staticmethod
    def obtener_carreras() -> Dict:
        supabase = get_supabase()
        
        try:
            response = supabase.rpc("get_unique_carreras").execute()
            
            if response.data:
                carreras = sorted([
                    item.get("carrera", "").strip()
                    for item in response.data
                    if item and item.get("carrera") and item.get("carrera").strip()
                ])
            else:
                carreras = []
        except Exception:
            response = supabase.table("cursos").select("carrera").execute()
            cursos = response.data or []
            
            carreras = sorted(set([
                curso.get("carrera", "").strip()
                for curso in cursos
                if curso.get("carrera") and curso.get("carrera").strip()
            ]))
        
        return {
            "total": len(carreras),
            "carreras": carreras
        }
    
    @staticmethod
    def obtener_curso(codigo: str) -> Dict:
        supabase = get_supabase()
        response = supabase.table("cursos").select("codigo, creditos").eq("codigo", codigo).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Curso no encontrado")
        
        return response.data[0]
    
    @staticmethod
    def obtener_curso_por_carrera(codigo: str, carrera: str) -> Dict:
        supabase = get_supabase()
        print(f"[OBTENER CURSO] Buscando curso: codigo={codigo}, carrera={carrera}")
        
        try:
            response = supabase.table("cursos").select("codigo, nombre, creditos, carrera, nivel").eq("codigo", codigo).eq("carrera", carrera).execute()
            print(f"[OBTENER CURSO] Respuesta recibida: {len(response.data) if response.data else 0} curso(s) encontrado(s)")
            
            if not response.data:
                error_msg = f"Curso {codigo} no encontrado para la carrera {carrera}"
                print(f"[OBTENER CURSO] ERROR: {error_msg}")
                raise HTTPException(status_code=404, detail=error_msg)
            
            curso = response.data[0]
            print(f"[OBTENER CURSO] Curso encontrado: {curso}")
            return curso
        except HTTPException:
            raise
        except Exception as e:
            print(f"[OBTENER CURSO] Error inesperado: {type(e).__name__}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al buscar curso {codigo} en carrera {carrera}: {str(e)}"
            )


class PlanificacionService:
    @staticmethod
    def calcular_creditos_previos(historial: List[str], motor, carrera: Optional[str] = None) -> float:
        creditos = 0.0
        for codigo in historial:
            if carrera:
                id_curso = motor._crear_id_curso(codigo, carrera)
                info = motor.get_info_curso(id_curso, carrera)
            else:
                info = motor.get_info_curso(codigo)
            if info:
                creditos += info["creditos"]
        return creditos

