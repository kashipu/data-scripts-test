#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Descubridor Automático de Palabras Clave para Análisis de Sentimientos

Extrae palabras con alta correlación a sentimientos desde la BD,
detecta categorías incorrectas, y actualiza automáticamente el YAML.
"""

import argparse
import logging
import sys
import re
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict
from sqlalchemy import create_engine, text
import pandas as pd
import yaml
from unidecode import unidecode

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

YAML_PATH = "palabras_clave_sentimientos.yml"

# Stopwords comunes en español
STOPWORDS = {
    'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'haber',
    'por', 'con', 'su', 'para', 'como', 'estar', 'tener', 'le', 'lo', 'todo',
    'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
    'la', 'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'él', 'muy',
    'sin', 'vez', 'mucho', 'saber', 'qué', 'sobre', 'mi', 'alguno', 'mismo',
    'yo', 'también', 'hasta', 'año', 'dos', 'querer', 'entre', 'así', 'primero',
    'desde', 'grande', 'eso', 'ni', 'nos', 'llegar', 'pasar', 'tiempo', 'ella',
    'del', 'al', 'los', 'las', 'una', 'unos', 'unas', 'es', 'son', 'fue',
    'era', 'han', 'hay', 'he', 'has', 'ha', 'estoy', 'está', 'están', 'sea'
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('descubrir_palabras.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================================================================================
# FUNCIONES AUXILIARES
# ======================================================================================

def get_engine():
    """Crea engine de SQLAlchemy"""
    conn_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?client_encoding=utf8"
    return create_engine(conn_string)


def normalizar_texto(texto):
    """
    Normaliza texto: lowercase, sin acentos

    Args:
        texto: string

    Returns:
        texto normalizado
    """
    if not texto or not isinstance(texto, str):
        return ""

    texto = texto.lower()
    texto = unidecode(texto)  # elimina acentos
    return texto


def tokenizar(texto):
    """
    Tokeniza texto en palabras individuales

    Args:
        texto: string normalizado

    Returns:
        lista de palabras limpias
    """
    # Separar por espacios y puntuación
    palabras = re.findall(r'\b[a-z]+\b', texto)

    # Filtrar
    palabras_limpias = [
        p for p in palabras
        if len(p) >= 3  # mínimo 3 caracteres
        and len(p) <= 20  # máximo 20 caracteres
        and p not in STOPWORDS  # no stopwords
    ]

    return palabras_limpias


def cargar_yaml_actual():
    """Carga el YAML actual de palabras clave"""
    try:
        with open(YAML_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"Archivo {YAML_PATH} no encontrado, se creará uno nuevo")
        return {
            'positivas': [],
            'negativas': [],
            'neutrales': [],
            'ofensivas': [],
            'intensificadores': {'positivos': [], 'negativos': []}
        }


def crear_backup_yaml():
    """Crea backup del YAML actual"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{YAML_PATH}.backup.{timestamp}"

    try:
        with open(YAML_PATH, 'r', encoding='utf-8') as f:
            contenido = f.read()

        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(contenido)

        logger.info(f"✓ Backup creado: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Error creando backup: {e}")
        return None


def guardar_yaml(data):
    """Guarda datos en el YAML"""
    try:
        with open(YAML_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        logger.info(f"✓ YAML actualizado: {YAML_PATH}")
        return True
    except Exception as e:
        logger.error(f"Error guardando YAML: {e}")
        return False


# ======================================================================================
# FASE 1: EXTRACCIÓN Y ANÁLISIS
# ======================================================================================

def extraer_textos_bd(engine):
    """Extrae todos los textos con sentimiento de la BD"""
    query = """
        SELECT
            motivo_texto,
            sentimiento_py,
            confianza_py
        FROM respuestas_nps_csat
        WHERE sentimiento_py IS NOT NULL
          AND motivo_texto IS NOT NULL
          AND LENGTH(TRIM(motivo_texto)) > 0
    """

    logger.info("Extrayendo textos de la BD...")
    df = pd.read_sql(text(query), engine)
    logger.info(f"✓ {len(df):,} textos cargados")

    return df


def calcular_correlaciones(df, min_frecuencia=50):
    """
    Calcula correlación de cada palabra con cada sentimiento

    Returns:
        dict: {palabra: {sentimiento: freq, total: N, correlacion: X, dominante: Y}}
    """
    logger.info("Analizando palabras y calculando correlaciones...")

    # Contadores
    palabra_sentimiento = defaultdict(lambda: defaultdict(int))
    palabra_total = Counter()

    # Procesar cada texto
    for _, row in df.iterrows():
        texto = normalizar_texto(row['motivo_texto'])
        sentimiento = row['sentimiento_py']

        palabras = tokenizar(texto)
        palabras_unicas = set(palabras)  # contar una vez por texto

        for palabra in palabras_unicas:
            palabra_sentimiento[palabra][sentimiento] += 1
            palabra_total[palabra] += 1

    # Calcular correlaciones
    resultados = {}

    for palabra, total in palabra_total.items():
        if total < min_frecuencia:
            continue

        freqs = palabra_sentimiento[palabra]
        freq_pos = freqs.get('POSITIVO', 0)
        freq_neg = freqs.get('NEGATIVO', 0)
        freq_neu = freqs.get('NEUTRAL', 0)

        # Determinar sentimiento dominante
        max_freq = max(freq_pos, freq_neg, freq_neu)
        correlacion = max_freq / total

        if max_freq == freq_pos:
            dominante = 'POSITIVO'
        elif max_freq == freq_neg:
            dominante = 'NEGATIVO'
        else:
            dominante = 'NEUTRAL'

        resultados[palabra] = {
            'positivo': freq_pos,
            'negativo': freq_neg,
            'neutral': freq_neu,
            'total': total,
            'correlacion': correlacion,
            'dominante': dominante
        }

    logger.info(f"✓ {len(resultados):,} palabras únicas analizadas (freq >= {min_frecuencia})")

    return resultados


def filtrar_candidatas(correlaciones, yaml_actual, min_correlacion=0.75):
    """
    Filtra palabras candidatas para agregar al YAML

    Criterios:
    - Correlación >= min_correlacion
    - NO está en el YAML actual
    """
    # Obtener todas las palabras actuales (normalizadas)
    palabras_existentes = set()

    for categoria in ['positivas', 'negativas', 'neutrales', 'ofensivas']:
        if categoria in yaml_actual:
            palabras_existentes.update([normalizar_texto(p) for p in yaml_actual[categoria]])

    if 'intensificadores' in yaml_actual:
        for tipo in ['positivos', 'negativos']:
            if tipo in yaml_actual['intensificadores']:
                palabras_existentes.update([normalizar_texto(p) for p in yaml_actual['intensificadores'][tipo]])

    # Filtrar candidatas
    candidatas = {
        'POSITIVO': [],
        'NEGATIVO': [],
        'NEUTRAL': []
    }

    for palabra, stats in correlaciones.items():
        if stats['correlacion'] >= min_correlacion and palabra not in palabras_existentes:
            candidatas[stats['dominante']].append((palabra, stats))

    # Ordenar por correlación descendente
    for sent in candidatas:
        candidatas[sent].sort(key=lambda x: x[1]['correlacion'], reverse=True)

    logger.info(f"✓ Candidatas encontradas:")
    logger.info(f"  - POSITIVO: {len(candidatas['POSITIVO'])}")
    logger.info(f"  - NEGATIVO: {len(candidatas['NEGATIVO'])}")
    logger.info(f"  - NEUTRAL: {len(candidatas['NEUTRAL'])}")

    return candidatas


# ======================================================================================
# FASE 2: DETECCIÓN DE PROBLEMAS
# ======================================================================================

def detectar_duplicados(yaml_actual):
    """Detecta palabras que están en múltiples categorías"""
    palabra_categorias = defaultdict(list)

    for categoria in ['positivas', 'negativas', 'neutrales', 'ofensivas']:
        if categoria in yaml_actual:
            for palabra in yaml_actual[categoria]:
                palabra_norm = normalizar_texto(palabra)
                palabra_categorias[palabra_norm].append((categoria, palabra))

    if 'intensificadores' in yaml_actual:
        for tipo in ['positivos', 'negativos']:
            if tipo in yaml_actual['intensificadores']:
                for palabra in yaml_actual['intensificadores'][tipo]:
                    palabra_norm = normalizar_texto(palabra)
                    palabra_categorias[palabra_norm].append((f'intensificadores.{tipo}', palabra))

    # Filtrar solo duplicados
    duplicados = {k: v for k, v in palabra_categorias.items() if len(v) > 1}

    if duplicados:
        logger.warning(f"⚠ {len(duplicados)} duplicados detectados:")
        for palabra, categorias in duplicados.items():
            cats = [c[0] for c in categorias]
            logger.warning(f"  - '{palabra}' en: {', '.join(cats)}")

    return duplicados


def validar_categorias(yaml_actual, correlaciones):
    """
    Valida que las palabras existentes están en la categoría correcta

    Returns:
        dict: {palabra: {categoria_actual: X, deberia_ser: Y, correlacion_actual: Z}}
    """
    problemas = {}

    mapeo_categorias = {
        'positivas': 'POSITIVO',
        'negativas': 'NEGATIVO',
        'neutrales': 'NEUTRAL'
    }

    for categoria, sentimiento in mapeo_categorias.items():
        if categoria not in yaml_actual:
            continue

        for palabra in yaml_actual[categoria]:
            palabra_norm = normalizar_texto(palabra)

            if palabra_norm not in correlaciones:
                continue  # palabra muy rara, sin suficientes datos

            stats = correlaciones[palabra_norm]

            # Verificar si dominante coincide con categoría
            if stats['dominante'] != sentimiento:
                # Calcular correlación con categoría actual
                if sentimiento == 'POSITIVO':
                    corr_actual = stats['positivo'] / stats['total']
                elif sentimiento == 'NEGATIVO':
                    corr_actual = stats['negativo'] / stats['total']
                else:
                    corr_actual = stats['neutral'] / stats['total']

                # Si correlación con categoría actual es muy baja
                if corr_actual < 0.50:
                    problemas[palabra] = {
                        'categoria_actual': categoria,
                        'deberia_ser': stats['dominante'].lower() + 's',
                        'correlacion_actual': corr_actual,
                        'correlacion_correcta': stats['correlacion']
                    }

    if problemas:
        logger.warning(f"⚠ {len(problemas)} palabras con categoría posiblemente incorrecta:")
        for palabra, info in problemas.items():
            logger.warning(f"  - '{palabra}': {info['categoria_actual']} → {info['deberia_ser']} (corr: {info['correlacion_correcta']:.2f})")

    return problemas


# ======================================================================================
# FASE 3: ACTUALIZACIÓN DEL YAML
# ======================================================================================

def agregar_nuevas_palabras(yaml_actual, candidatas, max_por_categoria=50):
    """Agrega nuevas palabras candidatas al YAML"""
    stats = {'positivas': 0, 'negativas': 0, 'neutrales': 0}

    mapeo = {
        'POSITIVO': 'positivas',
        'NEGATIVO': 'negativas',
        'NEUTRAL': 'neutrales'
    }

    for sentimiento, categoria in mapeo.items():
        if categoria not in yaml_actual:
            yaml_actual[categoria] = []

        # Tomar top N candidatas
        palabras_agregar = [p[0] for p in candidatas[sentimiento][:max_por_categoria]]

        # Agregar y ordenar alfabéticamente
        yaml_actual[categoria].extend(palabras_agregar)
        yaml_actual[categoria] = sorted(list(set(yaml_actual[categoria])))

        stats[categoria] = len(palabras_agregar)

        if palabras_agregar:
            logger.info(f"✓ {len(palabras_agregar)} palabras agregadas a '{categoria}'")

    return stats


def resolver_duplicados(yaml_actual, duplicados, correlaciones):
    """
    Resuelve duplicados manteniendo palabra en categoría con mayor correlación
    """
    resueltos = 0

    for palabra_norm, ubicaciones in duplicados.items():
        # Si la palabra no tiene datos de correlación, saltar
        if palabra_norm not in correlaciones:
            continue

        stats = correlaciones[palabra_norm]
        sentimiento_correcto = stats['dominante']

        # Mapeo de sentimiento a categoría
        mapeo_inv = {
            'POSITIVO': 'positivas',
            'NEGATIVO': 'negativas',
            'NEUTRAL': 'neutrales'
        }

        categoria_correcta = mapeo_inv.get(sentimiento_correcto)

        if not categoria_correcta:
            continue

        # Eliminar de todas las categorías incorrectas
        for cat, palabra_original in ubicaciones:
            if cat == categoria_correcta:
                continue  # mantener aquí

            # Eliminar de categoría incorrecta
            if '.' in cat:  # intensificadores
                cat_principal, sub = cat.split('.')
                if cat_principal in yaml_actual and sub in yaml_actual[cat_principal]:
                    if palabra_original in yaml_actual[cat_principal][sub]:
                        yaml_actual[cat_principal][sub].remove(palabra_original)
                        resueltos += 1
            else:
                if cat in yaml_actual and palabra_original in yaml_actual[cat]:
                    yaml_actual[cat].remove(palabra_original)
                    resueltos += 1

    if resueltos > 0:
        logger.info(f"✓ {resueltos} duplicados resueltos")

    return resueltos


def corregir_categorias(yaml_actual, problemas):
    """Mueve palabras a su categoría correcta según correlación"""
    corregidas = 0

    for palabra, info in problemas.items():
        cat_actual = info['categoria_actual']
        cat_correcta = info['deberia_ser']

        # Solo corregir si correlación correcta es MUY alta (>0.85)
        # Esto evita mover palabras semánticamente correctas
        if info['correlacion_correcta'] < 0.85:
            continue

        # Eliminar de categoría actual
        if cat_actual in yaml_actual and palabra in yaml_actual[cat_actual]:
            yaml_actual[cat_actual].remove(palabra)

        # Agregar a categoría correcta
        if cat_correcta not in yaml_actual:
            yaml_actual[cat_correcta] = []

        if palabra not in yaml_actual[cat_correcta]:
            yaml_actual[cat_correcta].append(palabra)
            yaml_actual[cat_correcta] = sorted(yaml_actual[cat_correcta])
            corregidas += 1

    if corregidas > 0:
        logger.info(f"✓ {corregidas} categorías incorrectas corregidas")

    return corregidas


# ======================================================================================
# MAIN
# ======================================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Descubre y actualiza automáticamente palabras clave para análisis de sentimientos'
    )
    parser.add_argument('--min-frecuencia', type=int, default=50,
                       help='Frecuencia mínima de apariciones (default: 50)')
    parser.add_argument('--min-correlacion', type=float, default=0.75,
                       help='Correlación mínima con sentimiento (default: 0.75)')
    parser.add_argument('--max-por-categoria', type=int, default=50,
                       help='Máximo de palabras nuevas por categoría (default: 50)')
    parser.add_argument('--no-backup', action='store_true',
                       help='No crear backup del YAML antes de modificar')
    parser.add_argument('--dry-run', action='store_true',
                       help='Solo mostrar qué haría, no modificar YAML')

    args = parser.parse_args()

    print("=" * 73)
    print("DESCUBRIDOR AUTOMÁTICO DE PALABRAS CLAVE")
    print("=" * 73)
    print()

    # 1. Conectar BD
    try:
        engine = get_engine()
        logger.info("1. Conectando a BD...")
    except Exception as e:
        logger.error(f"❌ Error conectando a BD: {e}")
        sys.exit(1)

    # 2. Cargar YAML actual
    logger.info("2. Cargando YAML actual...")
    yaml_actual = cargar_yaml_actual()
    total_palabras_actual = sum([
        len(yaml_actual.get('positivas', [])),
        len(yaml_actual.get('negativas', [])),
        len(yaml_actual.get('neutrales', [])),
        len(yaml_actual.get('ofensivas', []))
    ])
    logger.info(f"   ✓ {total_palabras_actual} palabras existentes")

    # 3. Extraer textos
    logger.info("3. Extrayendo textos de BD...")
    df = extraer_textos_bd(engine)

    # 4. Calcular correlaciones
    logger.info("4. Analizando palabras...")
    correlaciones = calcular_correlaciones(df, min_frecuencia=args.min_frecuencia)

    # 5. Identificar candidatas
    logger.info("5. Identificando palabras candidatas...")
    candidatas = filtrar_candidatas(correlaciones, yaml_actual, min_correlacion=args.min_correlacion)

    # 6. Detectar problemas
    logger.info("6. Detectando problemas...")
    duplicados = detectar_duplicados(yaml_actual)
    problemas_categorias = validar_categorias(yaml_actual, correlaciones)

    # Modo dry-run: solo mostrar, no modificar
    if args.dry_run:
        print()
        print("=" * 73)
        print("MODO DRY-RUN: No se modificará el YAML")
        print("=" * 73)
        logger.info(f"Se agregarían {len(candidatas['POSITIVO'])} positivas, {len(candidatas['NEGATIVO'])} negativas, {len(candidatas['NEUTRAL'])} neutrales")
        logger.info(f"Se resolverían {len(duplicados)} duplicados")
        logger.info(f"Se corregirían {len(problemas_categorias)} categorías incorrectas")
        sys.exit(0)

    # 7. Crear backup
    if not args.no_backup:
        logger.info("7. Creando backup...")
        backup_path = crear_backup_yaml()
        if not backup_path:
            logger.error("❌ No se pudo crear backup, abortando")
            sys.exit(1)
    else:
        logger.info("7. Saltando backup (--no-backup)")

    # 8. Actualizar YAML
    logger.info("8. Actualizando YAML...")

    stats_nuevas = agregar_nuevas_palabras(yaml_actual, candidatas, max_por_categoria=args.max_por_categoria)
    stats_duplicados = resolver_duplicados(yaml_actual, duplicados, correlaciones)
    stats_corregidas = corregir_categorias(yaml_actual, problemas_categorias)

    # 9. Guardar
    if not guardar_yaml(yaml_actual):
        logger.error("❌ Error guardando YAML")
        sys.exit(1)

    # Resumen
    print()
    print("=" * 73)
    print("RESULTADO: YAML ACTUALIZADO EXITOSAMENTE")
    print("=" * 73)
    print(f"✓ {stats_nuevas['positivas']} nuevas palabras POSITIVAS agregadas")
    print(f"✓ {stats_nuevas['negativas']} nuevas palabras NEGATIVAS agregadas")
    print(f"✓ {stats_nuevas['neutrales']} nuevas palabras NEUTRALES agregadas")
    print(f"✓ {stats_duplicados} duplicados resueltos")
    print(f"✓ {stats_corregidas} categorías incorrectas corregidas")
    print()
    if not args.no_backup:
        print(f"Backup: {backup_path}")
    print(f"Log: descubrir_palabras.log")
    print("=" * 73)


if __name__ == '__main__':
    main()
