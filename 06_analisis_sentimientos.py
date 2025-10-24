#!/usr/bin/env python3
"""
======================================================================================
SCRIPT: 06_analisis_sentimientos.py
======================================================================================
PROPÓSITO:
    Analiza sentimientos de comentarios NPS/CSAT usando Ollama y detecta
    contenido ofensivo. Actualiza la tabla unificada con los resultados.

QUÉ HACE:
    1. Lee motivos sin análisis de sentimiento de respuestas_nps_csat
    2. Analiza sentimientos (POSITIVO/NEUTRAL/NEGATIVO) con Ollama
    3. Detecta contenido ofensivo (groserías, insultos, amenazas)
    4. Actualiza campos: sentimiento, sentimiento_confianza, es_ofensivo
    5. Procesamiento incremental (solo nuevos)

CARACTERÍSTICAS:
    ✅ Procesamiento incremental: solo analiza comentarios sin sentimiento
    ✅ Detección automática de contenido ofensivo
    ✅ Procesamiento paralelo para mayor velocidad
    ✅ Manejo robusto de errores de Ollama
    ✅ Batch processing configurable

REQUISITOS:
    - Ollama instalado y corriendo: ollama serve
    - Modelo descargado: ollama pull llama3.1:8b

USO:
    python 06_analisis_sentimientos.py                 # 1000 comentarios
    python 06_analisis_sentimientos.py --limit 5000    # 5000 comentarios
    python 06_analisis_sentimientos.py --limit 0       # TODOS los pendientes

SIGUIENTE PASO:
    python 07_visualizar_metricas_nps_csat.py
======================================================================================
"""

import argparse
import json
import logging
import re
import requests
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from sqlalchemy import create_engine, text

# ======================================================================================
# CONFIGURACIÓN
# ======================================================================================

DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}

OLLAMA_CONFIG = {
    'base_url': 'http://localhost:11434',
    'model': 'llama3.1:8b',
    'timeout': 60,
    'temperature': 0.1,  # Baja para consistencia
}

# Procesamiento
BATCH_SIZE = 50
MIN_PALABRAS = 2
MAX_WORKERS = 4  # Threads paralelos

# Palabras clave para detección de contenido ofensivo (fallback)
PALABRAS_OFENSIVAS = [
    'mierda', 'maldita', 'maldito', 'carajo', 'joder', 'puta', 'puto',
    'idiota', 'estupido', 'estúpido', 'imbecil', 'imbécil', 'pendejo',
    'ladron', 'ladrón', 'ladrones', 'robar', 'estafa', 'estafadores',
    'incompetente', 'incompetentes', 'basura', 'porquería', 'porqueria',
    'odio', 'odiar', 'asqueroso', 'asco', 'malditos', 'malditas'
]

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('analisis_sentimientos.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================================================================================
# FUNCIONES
# ======================================================================================

def get_engine():
    """Crea conexión a PostgreSQL"""
    conn_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?client_encoding=utf8"
    return create_engine(conn_string)

def verificar_ollama():
    """Verifica que Ollama está disponible"""
    try:
        response = requests.get(f"{OLLAMA_CONFIG['base_url']}/api/tags", timeout=5)
        if response.status_code == 200:
            logger.info("✅ Ollama está corriendo")
            return True
        else:
            logger.error(f"❌ Ollama responde pero con error: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("❌ No se puede conectar a Ollama. ¿Está corriendo?")
        logger.error("   Ejecuta: ollama serve")
        return False
    except Exception as e:
        logger.error(f"❌ Error verificando Ollama: {str(e)}")
        return False

def es_texto_valido(texto):
    """Verifica si el texto es válido para análisis"""
    if not texto or not texto.strip():
        return False

    # Contar palabras
    palabras = texto.strip().split()
    if len(palabras) < MIN_PALABRAS:
        return False

    return True

def detectar_ofensivo_keywords(texto):
    """
    Detecta contenido ofensivo usando palabras clave (fallback)
    Returns: True si contiene palabras ofensivas
    """
    texto_lower = texto.lower()
    for palabra in PALABRAS_OFENSIVAS:
        if palabra in texto_lower:
            return True
    return False

def analizar_sentimiento_ollama(texto):
    """
    Analiza el sentimiento de un texto usando Ollama y detecta contenido ofensivo
    Returns: (sentimiento, confianza, es_ofensivo) o (None, None, None) si falla
    """
    if not es_texto_valido(texto):
        return ('NEUTRAL', 0.5, False)  # Textos muy cortos se marcan como neutrales

    prompt = f"""Eres un sistema de análisis de moderación de contenido para una empresa bancaria.
Tu tarea es analizar feedback de clientes para identificar sentimientos y contenido inapropiado.

CONTEXTO: Este es un comentario real de un cliente que necesita ser categorizado para mejorar el servicio.

INSTRUCCIONES:
1. Clasifica el SENTIMIENTO: POSITIVO, NEUTRAL o NEGATIVO
2. Indica la CONFIANZA de tu clasificación (0.0 a 1.0)
3. Detecta si contiene lenguaje OFENSIVO (groserías, insultos, amenazas, lenguaje inapropiado)

Responde ÚNICAMENTE en este formato JSON válido:
{{"sentimiento": "POSITIVO", "confianza": 0.95, "ofensivo": false}}

Comentario del cliente: "{texto}"

Análisis JSON:"""

    try:
        response = requests.post(
            f"{OLLAMA_CONFIG['base_url']}/api/generate",
            json={
                "model": OLLAMA_CONFIG['model'],
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": OLLAMA_CONFIG['temperature'],
                    "num_predict": 100
                }
            },
            timeout=OLLAMA_CONFIG['timeout']
        )

        if response.status_code != 200:
            logger.warning(f"Ollama error {response.status_code}")
            return (None, None, None)

        result = response.json()
        respuesta = result.get('response', '')

        # Extraer JSON de la respuesta
        json_match = re.search(r'\{[^}]+\}', respuesta)
        if not json_match:
            # Ollama rechazó la solicitud - usar fallback
            logger.info(f"Ollama rechazó - usando fallback por keywords")
            es_ofensivo = detectar_ofensivo_keywords(texto)
            # Si es ofensivo, asumimos sentimiento negativo
            sentimiento = 'NEGATIVO' if es_ofensivo else 'NEUTRAL'
            return (sentimiento, 0.7, es_ofensivo)

        try:
            data = json.loads(json_match.group())
            sentimiento = data.get('sentimiento', '').upper()
            confianza = float(data.get('confianza', 0.5))
            es_ofensivo = bool(data.get('ofensivo', False))

            # Si Ollama no detectó ofensivo, verificar con keywords también
            if not es_ofensivo:
                es_ofensivo = detectar_ofensivo_keywords(texto)

            # Validar sentimiento
            if sentimiento not in ['POSITIVO', 'NEUTRAL', 'NEGATIVO']:
                logger.warning(f"Sentimiento inválido: {sentimiento}")
                return (None, None, None)

            # Normalizar confianza
            confianza = max(0.0, min(1.0, confianza))

            return (sentimiento, confianza, es_ofensivo)
        except json.JSONDecodeError:
            # Error parseando JSON - usar fallback
            logger.info(f"Error parseando JSON - usando fallback")
            es_ofensivo = detectar_ofensivo_keywords(texto)
            sentimiento = 'NEGATIVO' if es_ofensivo else 'NEUTRAL'
            return (sentimiento, 0.7, es_ofensivo)

    except requests.exceptions.Timeout:
        logger.warning("Timeout en Ollama")
        return (None, None, None)
    except Exception as e:
        logger.warning(f"Error analizando: {str(e)}")
        return (None, None, None)

def procesar_lote(lote):
    """
    Procesa un lote de registros en paralelo
    Returns: lista de (id, sentimiento, confianza, es_ofensivo)
    """
    resultados = []

    def analizar_registro(registro):
        registro_id, texto = registro
        sentimiento, confianza, es_ofensivo = analizar_sentimiento_ollama(texto)
        return (registro_id, sentimiento, confianza, es_ofensivo)

    # Procesar en paralelo
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(analizar_registro, reg) for reg in lote]
        for future in futures:
            try:
                resultado = future.result(timeout=OLLAMA_CONFIG['timeout'] + 10)
                resultados.append(resultado)
            except Exception as e:
                logger.error(f"Error en thread: {str(e)}")

    return resultados

def actualizar_sentimientos(engine, resultados):
    """Actualiza los sentimientos en la BD"""
    actualizados = 0
    fallidos = 0

    with engine.connect() as conn:
        for registro_id, sentimiento, confianza, es_ofensivo in resultados:
            if sentimiento is None:
                fallidos += 1
                continue

            try:
                update_query = """
                    UPDATE respuestas_nps_csat
                    SET sentimiento = :sentimiento,
                        sentimiento_confianza = :confianza,
                        es_ofensivo = :es_ofensivo
                    WHERE id = :id
                """
                conn.execute(text(update_query), {
                    "id": registro_id,
                    "sentimiento": sentimiento,
                    "confianza": round(confianza, 4),
                    "es_ofensivo": es_ofensivo
                })
                actualizados += 1
            except Exception as e:
                logger.error(f"Error actualizando registro {registro_id}: {str(e)}")
                fallidos += 1

        conn.commit()

    return (actualizados, fallidos)

def main():
    parser = argparse.ArgumentParser(description='Análisis de sentimientos con Ollama')
    parser.add_argument('--limit', type=int, default=1000,
                        help='Número de comentarios a procesar (0 = todos)')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE,
                        help='Tamaño de lote')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS,
                        help='Threads paralelos')

    args = parser.parse_args()

    print("=" * 70)
    print("ANÁLISIS DE SENTIMIENTOS - OLLAMA")
    print("=" * 70)

    # Verificar Ollama
    if not verificar_ollama():
        sys.exit(1)

    # Conectar BD
    try:
        engine = get_engine()
        logger.info("✅ Conexión a PostgreSQL exitosa")
    except Exception as e:
        logger.error(f"❌ Error conectando a PostgreSQL: {str(e)}")
        sys.exit(1)

    # Contar pendientes
    where_clause = """
        WHERE motivo_texto IS NOT NULL
          AND LENGTH(TRIM(motivo_texto)) > 0
          AND sentimiento IS NULL
          AND es_ruido = FALSE
    """

    with engine.connect() as conn:
        count_result = conn.execute(text(f"SELECT COUNT(*) FROM respuestas_nps_csat {where_clause}")).fetchone()
        total_pendientes = count_result[0]

    if total_pendientes == 0:
        logger.info("✅ No hay motivos pendientes de análisis de sentimiento")
        sys.exit(0)

    # Determinar cuántos procesar
    if args.limit == 0:
        limit = total_pendientes
        logger.info(f"📊 Procesando TODOS los pendientes: {total_pendientes:,}")
    else:
        limit = min(args.limit, total_pendientes)
        logger.info(f"📊 Pendientes: {total_pendientes:,}, procesando: {limit:,}")

    # Estadísticas
    stats = {
        'total': limit,
        'procesados': 0,
        'actualizados': 0,
        'fallidos': 0,
        'positivos': 0,
        'neutrales': 0,
        'negativos': 0,
        'ofensivos': 0,
        'inicio': datetime.now()
    }

    # Procesar en lotes
    offset = 0
    batch_size = args.batch_size

    while offset < limit:
        batch_limit = min(batch_size, limit - offset)

        # Leer lote
        query = f"""
            SELECT id, motivo_texto
            FROM respuestas_nps_csat
            {where_clause}
            ORDER BY id
            LIMIT :lim OFFSET :off
        """

        with engine.connect() as conn:
            rows = conn.execute(text(query), {"lim": batch_limit, "off": offset}).fetchall()

        if not rows:
            break

        logger.info(f"Procesando lote {offset:,} - {offset + len(rows):,}")

        # Analizar lote
        resultados = procesar_lote(rows)

        # Actualizar BD
        actualizados, fallidos = actualizar_sentimientos(engine, resultados)

        # Actualizar estadísticas
        stats['procesados'] += len(resultados)
        stats['actualizados'] += actualizados
        stats['fallidos'] += fallidos

        # Contar por tipo
        for _, sentimiento, _, es_ofensivo in resultados:
            if sentimiento == 'POSITIVO':
                stats['positivos'] += 1
            elif sentimiento == 'NEUTRAL':
                stats['neutrales'] += 1
            elif sentimiento == 'NEGATIVO':
                stats['negativos'] += 1

            if es_ofensivo:
                stats['ofensivos'] += 1

        # Progreso
        progreso = (offset + len(rows)) / limit * 100
        logger.info(f"  Progreso: {progreso:.1f}% ({stats['actualizados']} actualizados, {stats['fallidos']} fallidos)")

        offset += len(rows)

        # Pequeña pausa para no saturar Ollama
        time.sleep(0.5)

    # Resumen final
    stats['fin'] = datetime.now()
    duracion = stats['fin'] - stats['inicio']

    print("\n" + "=" * 70)
    print("📊 RESUMEN DE ANÁLISIS DE SENTIMIENTOS")
    print("=" * 70)
    print(f"Total procesados: {stats['procesados']:,}")
    print(f"Actualizados exitosamente: {stats['actualizados']:,}")
    print(f"Fallidos: {stats['fallidos']:,}")
    print(f"\n📈 Distribución de Sentimientos:")
    total_validos = stats['positivos'] + stats['neutrales'] + stats['negativos']
    if total_validos > 0:
        print(f"  POSITIVO: {stats['positivos']:6,} ({stats['positivos']/total_validos*100:5.1f}%)")
        print(f"  NEUTRAL:  {stats['neutrales']:6,} ({stats['neutrales']/total_validos*100:5.1f}%)")
        print(f"  NEGATIVO: {stats['negativos']:6,} ({stats['negativos']/total_validos*100:5.1f}%)")
    print(f"\n⚠️  Contenido Ofensivo:")
    if stats['actualizados'] > 0:
        print(f"  OFENSIVOS: {stats['ofensivos']:6,} ({stats['ofensivos']/stats['actualizados']*100:5.1f}%)")
    else:
        print(f"  OFENSIVOS: {stats['ofensivos']:6,}")
    print(f"\n⏱️  Tiempo total: {duracion}")
    print(f"   Velocidad: {stats['actualizados']/duracion.total_seconds():.1f} registros/segundo")
    print("=" * 70)

    if stats['actualizados'] > 0:
        print("\n✅ Análisis completado")
        print("\n🎯 SIGUIENTE PASO:")
        print("   # Refrescar vistas materializadas")
        print("   psql -U postgres -d nps_analitycs -f sql/05_refresh_views.sql")
        print("\n   # O continuar con visualizaciones:")
        print("   python 07_visualizar_metricas_nps_csat.py")
    else:
        print("\n⚠️  No se analizaron registros. Revisar logs.")

if __name__ == "__main__":
    main()
