import os
import psycopg2
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

# Carga las variables de entorno desde el archivo .env para desarrollo local
load_dotenv()

app = FastAPI(title="Farmacia Inteligente API")

def get_db_connection():
    """Establece conexión con la base de datos PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        return conn
    except psycopg2.OperationalError as e:
        # Esto ayuda a diagnosticar problemas de conexión
        raise HTTPException(status_code=500, detail=f"Error de conexión con la base de datos: {e}")

@app.get("/api/ventas")
def obtener_ventas():
    """Obtiene un resumen de las ventas."""
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT p.id, p.fecha, c.nombre as cliente, m.nombre as medicamento, pi.cantidad, pi.subtotal
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        JOIN pedido_items pi ON p.id = pi.pedido_id
        JOIN medicamentos m ON pi.medicamento_id = m.id
        WHERE p.estado = 'pagado'
        ORDER BY p.fecha DESC;
    """
    cur.execute(query)
    ventas = cur.fetchall()
    # Esto convierte los resultados en un formato JSON amigable
    columnas = [desc[0] for desc in cur.description]
    resultado = [dict(zip(columnas, row)) for row in ventas]
    cur.close()
    conn.close()
    return resultado

@app.get("/")
def health_check():
    """Endpoint de prueba para verificar que la API está viva."""
    return {"status": "API de Farmacia funcionando correctamente"}