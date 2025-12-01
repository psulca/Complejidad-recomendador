import pandas as pd
import networkx as nx
from typing import List, Optional, Dict, Tuple
from database import get_supabase
from parser import parse_requisitos
from utils import limpiar_curso_data, eliminar_duplicados_lote


class MotorAcademico:
    @staticmethod
    def _crear_id_curso(codigo: str, carrera: str) -> str:
        return f"{codigo}|{carrera}"
    
    @staticmethod
    def _extraer_codigo(id_curso: str) -> str:
        return id_curso.split("|")[0] if "|" in id_curso else id_curso
    
    @staticmethod
    def _extraer_carrera(id_curso: str) -> str:
        parts = id_curso.split("|")
        return parts[1] if len(parts) > 1 else ""
    
    def __init__(self, csv_path: Optional[str] = None):
        self.graph = nx.DiGraph()
        self.supabase = get_supabase()
        self.cargar_cursos_desde_db()
        
        if csv_path:
            if len(self.graph.nodes) == 0:
                self.cargar_desde_csv(csv_path)
            else:
                print(f"Ya hay {len(self.graph.nodes)} cursos en la base de datos.")
    
    def cargar_cursos_desde_db(self):
        try:
            all_cursos = []
            offset = 0
            page_size = 1000
            
            while True:
                response = self.supabase.table("cursos").select("*").range(offset, offset + page_size - 1).execute()
                cursos_pagina = response.data or []
                
                if not cursos_pagina:
                    break
                
                all_cursos.extend(cursos_pagina)
                offset += page_size
                
                if len(cursos_pagina) < page_size:
                    break
            
            print(f"📦 Total cursos obtenidos de Supabase: {len(all_cursos)}")
            
            carreras_cargadas = set()
            for curso in all_cursos:
                self._agregar_nodo_al_grafo(
                    codigo=curso["codigo"],
                    creditos=float(curso["creditos"]),
                    nombre=curso["nombre"],
                    nivel=curso.get("nivel", 0),
                    carrera=curso.get("carrera", ""),
                    requisitos_str=curso.get("requisitos", "") or ""
                )
                if curso.get("carrera"):
                    carreras_cargadas.add(curso["carrera"])
            
            self._construir_aristas()
            print(f"✅ Cursos cargados desde Supabase: {len(self.graph.nodes)} nodos, {len(carreras_cargadas)} carreras distintas.")
        except Exception as e:
            print(f"❌ Error cargando cursos desde Supabase: {e}")
            import traceback
            traceback.print_exc()
            self.graph = nx.DiGraph()
    
    def cargar_desde_csv(self, csv_path: str, borrar_existentes: bool = False):
        df = pd.read_csv(csv_path)
        print(f"Cargando TODOS los cursos del CSV ({len(df)} filas encontradas)")
        
        df = df.dropna(subset=["Código", "Asignatura"])
        df["Requisitos"] = df["Requisitos"].fillna("").astype(str)
        
        cursos_para_insertar = []
        
        for _, row in df.iterrows():
            curso_data = self._procesar_fila_csv(row)
            if curso_data:
                self._agregar_nodo_al_grafo(
                    codigo=curso_data["codigo"],
                    creditos=curso_data["creditos"],
                    nombre=curso_data["nombre"],
                    nivel=curso_data["nivel"],
                    carrera=curso_data["carrera"],
                    requisitos_str=curso_data["requisitos"]
                )
                cursos_para_insertar.append(curso_data)
        
        if borrar_existentes:
            self._borrar_cursos_existentes()
        
        if cursos_para_insertar:
            self._insertar_cursos_en_lotes(cursos_para_insertar)
        
        self._construir_aristas()
        print(f"Motor cargado correctamente con {len(self.graph.nodes)} nodos.")
    
    def _procesar_fila_csv(self, row: pd.Series) -> Optional[Dict]:
        cod = str(row["Código"]).strip()
        if not cod or cod.lower() == "nan":
            return None
        
        cr = self._parse_creditos(row.get("Créditos", 0))
        nm = self._parse_string(row.get("Asignatura", ""), "")
        nivel = self._parse_nivel(row.get("Nivel", 0))
        carrera = self._parse_string(row.get("Carrera", "General"), "General")
        requisitos_str = self._parse_string(row.get("Requisitos", ""), "")
        
        return {
            "codigo": cod,
            "nombre": nm if nm else "",
            "creditos": float(cr),
            "nivel": int(nivel),
            "carrera": carrera if carrera else "General",
            "requisitos": requisitos_str if requisitos_str else None
        }
    
    def _parse_creditos(self, valor) -> float:
        try:
            if pd.isna(valor):
                return 0.0
            return float(str(valor).replace(",", "."))
        except:
            return 0.0
    
    def _parse_string(self, valor, default: str = "") -> str:
        if pd.isna(valor):
            return default
        result = str(valor).strip()
        return result if result and result.lower() != "nan" else default
    
    def _parse_nivel(self, valor) -> int:
        if pd.isna(valor):
            return 0
        try:
            return int(float(valor))
        except:
            return 0
    
    def _agregar_nodo_al_grafo(self, codigo: str, creditos: float, nombre: str, 
                                nivel: int, carrera: str, requisitos_str: str):
        parsed = parse_requisitos(requisitos_str)
        
        creditos_generales_requeridos = []
        for r in parsed:
            if r[0] == "CRED" and len(r) > 1:
                creditos_generales_requeridos.append(r[1])
        
        id_curso = self._crear_id_curso(codigo, carrera)
        self.graph.add_node(
            id_curso, 
            codigo=codigo,
            creditos=creditos, 
            nombre=nombre, 
            nivel=nivel, 
            carrera=carrera, 
            reqs_logicos=parsed,
            creditos_generales_requeridos=creditos_generales_requeridos
        )
    
    def _construir_aristas(self):
        for id_curso in self.graph.nodes:
            nodo_data = self.graph.nodes[id_curso]
            carrera_curso = nodo_data.get("carrera", "").strip().lower()
            reqs = nodo_data.get("reqs_logicos", [])
            
            for r in reqs:
                if r[0] == "COURSE":
                    prereq_codigo = r[1]
                    
                    for otro_id in self.graph.nodes:
                        otro_data = self.graph.nodes[otro_id]
                        carrera_prereq = otro_data.get("carrera", "").strip().lower()
                        if (otro_data.get("codigo") == prereq_codigo and 
                            carrera_prereq == carrera_curso):
                            self.graph.add_edge(otro_id, id_curso, tipo="COURSE")
                            break
                elif r[0] == "COURSE_CRED":
                    prereq_codigo = r[1]
                    creditos_requeridos = r[2] if len(r) > 2 else 0
                    
                    for otro_id in self.graph.nodes:
                        otro_data = self.graph.nodes[otro_id]
                        carrera_prereq = otro_data.get("carrera", "").strip().lower()
                        if (otro_data.get("codigo") == prereq_codigo and 
                            carrera_prereq == carrera_curso):
                            self.graph.add_edge(
                                otro_id, id_curso, 
                                tipo="COURSE_CRED",
                                creditos_requeridos=creditos_requeridos
                            )
                            break
    
    def _borrar_cursos_existentes(self):
        try:
            self.supabase.table("cursos").delete().neq("codigo", "").execute()
            print("✅ Cursos existentes eliminados")
        except Exception as e:
            print(f"⚠️  Advertencia al borrar cursos: {e}")
    
    def _insertar_cursos_en_lotes(self, cursos_para_insertar: List[Dict]):
        try:
            cursos_guardados = 0
            for i in range(0, len(cursos_para_insertar), 100):
                lote = cursos_para_insertar[i:i+100]
                lote = eliminar_duplicados_lote(lote)
                lote_limpio = [limpiar_curso_data(curso) for curso in lote]
                
                self.supabase.table("cursos").upsert(
                    lote_limpio, 
                    on_conflict="codigo,carrera"
                ).execute()
                
                cursos_guardados += len(lote)
                print(f"✅ Lote {i//100 + 1}: {len(lote)} cursos procesados")
            
            print(f"✅ Total: {cursos_guardados} cursos guardados en Supabase")
        except Exception as e:
            print(f"❌ Error guardando cursos en Supabase: {e}")
            import traceback
            traceback.print_exc()
    
    def get_info_curso(self, id_curso: str, carrera: Optional[str] = None) -> Optional[Dict]:
        if "|" in id_curso:
            if id_curso not in self.graph.nodes:
                return None
            data = self.graph.nodes[id_curso]
        else:
            if carrera:
                id_buscado = self._crear_id_curso(id_curso, carrera)
                if id_buscado not in self.graph.nodes:
                    return None
                data = self.graph.nodes[id_buscado]
            else:
                for id_nodo in self.graph.nodes:
                    nodo_data = self.graph.nodes[id_nodo]
                    if nodo_data.get("codigo") == id_curso:
                        data = nodo_data
                        break
                else:
                    return None
        
        return {
            "nombre": data.get("nombre", ""),
            "creditos": data.get("creditos", 0),
            "nivel": data.get("nivel", 0),
            "carrera": data.get("carrera", ""),
            "reqs": data.get("reqs_logicos", [])
        }
    
    def get_carrera_curso(self, id_curso: str) -> Optional[str]:
        if "|" in id_curso:
            return self._extraer_carrera(id_curso)
        else:
            info = self.get_info_curso(id_curso)
            return info.get("carrera") if info else None
    
    def cumple_requisitos(self, id_curso_objetivo: str, aprobados_dict: Dict, total_creditos: float) -> bool:
        info = self.get_info_curso(id_curso_objetivo)
        if not info:
            return False
        
        carrera_objetivo = info.get("carrera", "")
        reqs = info["reqs"]
        if not reqs or len(reqs) == 0:
            return True
        
        for r in reqs:
            tipo = r[0]
            if tipo == "COURSE":
                curso_req_codigo = r[1] if len(r) > 1 else None
                if curso_req_codigo:
                    id_prereq = self._crear_id_curso(curso_req_codigo, carrera_objetivo)
                    if id_prereq not in aprobados_dict:
                        return False
            elif tipo == "CRED":
                cred_req = r[1] if len(r) > 1 else 0
                if total_creditos < cred_req:
                    return False
            elif tipo == "COURSE_CRED":
                curso_req_codigo = r[1] if len(r) > 1 else None
                if curso_req_codigo:
                    id_prereq = self._crear_id_curso(curso_req_codigo, carrera_objetivo)
                    if id_prereq not in aprobados_dict:
                        return False
        
        return True
    
    def generar_planificacion(self, historial_alumno: List[str], max_creditos: float, 
                             carrera_filtro: Optional[str] = None) -> Tuple[List[Dict], List[Dict]]:
        aprobados_dict, total_creditos = self._procesar_historial(historial_alumno, carrera_filtro)
        candidatos = self._obtener_candidatos(aprobados_dict, total_creditos, carrera_filtro)
        seleccionados = self._seleccionar_optimos(candidatos, max_creditos)
        
        print(f"📊 Planificación: {len(candidatos)} candidatos, {len(seleccionados)} seleccionados, carrera_filtro={carrera_filtro}")
        
        return candidatos, seleccionados
    
    def _procesar_historial(self, historial: List[str], carrera_filtro: Optional[str] = None) -> Tuple[Dict, float]:
        aprobados_dict = {}
        total_creditos = 0.0
        
        for cod in historial:
            if carrera_filtro:
                id_curso = self._crear_id_curso(cod, carrera_filtro)
                info = self.get_info_curso(id_curso, carrera_filtro)
            else:
                info = self.get_info_curso(cod)
            
            if info:
                cr = info["creditos"]
                id_curso_completo = self._crear_id_curso(cod, info.get("carrera", carrera_filtro or ""))
                aprobados_dict[id_curso_completo] = cr
                total_creditos += cr
            else:
                if carrera_filtro:
                    id_curso_completo = self._crear_id_curso(cod, carrera_filtro)
                else:
                    id_curso_completo = cod
                aprobados_dict[id_curso_completo] = 0
        
        return aprobados_dict, total_creditos
    
    def _obtener_candidatos(self, aprobados_dict: Dict, total_creditos: float, 
                           carrera_filtro: Optional[str]) -> List[Dict]:
        candidatos = []
        
        if not carrera_filtro or not carrera_filtro.strip():
            print(f"⚠️  No se proporcionó carrera para filtrar")
            return candidatos
        
        carrera_filtro_clean = carrera_filtro.strip().lower()
        total_cursos = len(self.graph.nodes)
        cursos_filtrados_carrera = 0
        cursos_excluidos_aprobados = 0
        cursos_excluidos_requisitos = 0
        carreras_encontradas = set()
        
        print(f"🔍 Filtrando cursos por carrera: '{carrera_filtro}' (total nodos: {total_cursos})")
        
        for curso in self.graph.nodes:
            carrera_curso = self.get_carrera_curso(curso)
            if carrera_curso:
                carreras_encontradas.add(carrera_curso.strip())
            carrera_curso_clean = carrera_curso.strip().lower() if carrera_curso else ""
            
            if not carrera_curso_clean or carrera_curso_clean != carrera_filtro_clean:
                continue
            
            cursos_filtrados_carrera += 1
            
            if curso in aprobados_dict:
                cursos_excluidos_aprobados += 1
                continue
            
            if self.cumple_requisitos(curso, aprobados_dict, total_creditos):
                info = self.get_info_curso(curso)
                if not info:
                    cursos_excluidos_requisitos += 1
                    continue
                    
                impacto = len(nx.descendants(self.graph, curso))
                
                codigo_simple = self._extraer_codigo(curso)
                candidatos.append({
                    "id": codigo_simple,
                    "nombre": info["nombre"],
                    "creditos": info["creditos"],
                    "nivel": info["nivel"],
                    "carrera": info.get("carrera", ""),
                    "impacto": impacto
                })
            else:
                cursos_excluidos_requisitos += 1
        
        disponibles = cursos_filtrados_carrera - cursos_excluidos_aprobados
        
        print(f"✅ Resultados: {len(candidatos)} candidatos encontrados")
        print(f"   - Cursos de la carrera '{carrera_filtro}': {cursos_filtrados_carrera}")
        print(f"   - Excluidos (ya aprobados): {cursos_excluidos_aprobados}")
        print(f"   - Cursos disponibles (no aprobados): {disponibles}")
        print(f"   - Excluidos (no cumplen requisitos): {cursos_excluidos_requisitos}")
        print(f"   - Candidatos que cumplen requisitos: {len(candidatos)}")
        
        if len(candidatos) < disponibles:
            print(f"⚠️  Advertencia: Solo {len(candidatos)} de {disponibles} cursos disponibles cumplen requisitos")
        
        if cursos_filtrados_carrera == 0:
            print(f"⚠️  No se encontraron cursos para la carrera '{carrera_filtro}'")
            print(f"   Carreras disponibles (primeras 10): {sorted(list(carreras_encontradas))[:10]}")
            print(f"   Total carreras distintas: {len(carreras_encontradas)}")
        
        candidatos.sort(key=lambda x: x["impacto"], reverse=True)
        return candidatos
    
    def _seleccionar_optimos(self, candidatos: List[Dict], max_creditos: float) -> List[Dict]:
        seleccionados = []
        carga_actual = 0.0
        
        for cand in candidatos:
            if carga_actual + cand["creditos"] <= max_creditos:
                seleccionados.append(cand)
                carga_actual += cand["creditos"]
        
        return seleccionados

