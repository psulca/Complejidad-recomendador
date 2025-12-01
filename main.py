import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor_academico import MotorAcademico
from endpoints import router, set_motor

app = FastAPI(title="API Motor Académico UPC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def cargar_datos():
    csv_file = "mallas_consolidadas.csv"
    motor = MotorAcademico(csv_file if os.path.exists(csv_file) else None)
    set_motor(motor)
