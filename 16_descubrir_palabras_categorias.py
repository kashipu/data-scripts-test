#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Descubridor Automático de Palabras Clave para Categorías

Extrae palabras con alta correlación a categorías desde textos ya categorizados,
detecta duplicados y categorías incorrectas, y actualiza automáticamente el YAML.
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

# ======================================================================================
# VARIABLES DE CONFIGURACIÓN - AJUSTABLES
# ======================================================================================

# FRECUENCIA MÍNIMA
# Cuántas veces debe aparecer una palabra para ser considerada candidata
# Valores sugeridos: 20-100
# - Bajo (20): Más palabras, mayor cobertura, pero más ruido
# - Medio (50): Equilibrado (RECOMENDADO)
# - Alto (100): Solo palabras muy frecuentes, más precisas
MIN_FRECUENCIA = 50

# CORRELACIÓN MÍNIMA
# Qué porcentaje de apariciones deben estar en una categoría
# Valores sugeridos: 0.60-0.85
# - 0.60 (60%): Menos estricto, más palabras
# - 0.70 (70%): Equilibrado (RECOMENDADO)
# - 0.85 (85%): Muy estricto, solo palabras altamente específicas
MIN_CORRELACION = 0.70

# MÁXIMO DE PALABRAS NUEVAS POR CATEGORÍA
# Límite de palabras nuevas a agregar por cada categoría
# Valores sugeridos: 30-100
# - 30: Crecimiento conservador (RECOMENDADO para primera ejecución)
# - 50: Crecimiento moderado
# - 100: Crecimiento agresivo
MAX_POR_CATEGORIA = 30

# CONFIANZA MÍNIMA PARA ANÁLISIS
# Solo analizar textos ya categorizados con esta confianza mínima
# Valores sugeridos: 0.6-0.9
# - 0.6: Incluye más textos pero menos confiables
# - 0.7: Equilibrado (RECOMENDADO)
# - 0.9: Solo textos con categorización muy segura
MIN_CONFIANZA_ANALISIS = 0.7

# UMBRAL PARA CORRECCIÓN AUTOMÁTICA
# Solo mover palabras entre categorías si correlación correcta >= este valor
# Valores sugeridos: 0.80-0.90
# - 0.80: Más correcciones
# - 0.85: Equilibrado (RECOMENDADO)
# - 0.90: Solo correcciones muy obvias
UMBRAL_CORRECCION = 0.85

# ======================================================================================
# CONFIGURACIÓN DEL SISTEMA
# ======================================================================================

DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}

YAML_PATH = "categorias/categorias.yml"

# Categorías especiales que NO se analizan ni reciben palabras nuevas
CATEGORIAS_EXCLUIDAS = [
    'Texto Sin Sentido / Ruido',
    'Otros',
    'Falta de Información / N/A'
]

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
    'era', 'han', 'hay', 'he', 'has', 'ha', 'estoy', 'está', 'están', 'sea',
    'mas', 'solo', 'bien', 'cual', 'donde', 'quien', 'cada'
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('descubrir_palabras_categorias.log', encoding='utf-8'),
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


def normalize_text(text):
    """
    Normaliza texto igual que 05_categorizar_motivos.py
    lowercase, sin acentos, sin puntuación extra
    """
    if pd.isna(text) or text is None:
        return ""
    text = str(text).lower().strip()
    # Remover acentos
    text = text.replace('á', 'a').replace('é', 'e').replace('í', 'i')
    text = text.replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text)
    return text


def tokenizar(texto):
    """
    Tokeniza texto en palabras individuales
    """
    # Separar por espacios y puntuación
    palabras = re.findall(r'\b[a-z]+\b', texto)

    # Filtrar
    palabras_limpias = [
        p for p in palabras
        if len(p) >= 3  # mínimo 3 caracteres
        and len(p) <= 25  # máximo 25 caracteres
        and p not in STOPWORDS  # no stopwords
    ]

    return palabras_limpias


def cargar_yaml_actual():
    """Carga el YAML actual de categorías"""
    try:
        with open(YAML_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Archivo {YAML_PATH} no encontrado")
        sys.exit(1)


def crear_backup_yaml():
    """Crea backup del YAML actual"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{YAML_PATH}.backup.{timestamp}"

    try:
        with open(YAML_PATH, 'r', encoding='utf-8') as f:
            contenido = f.read()

        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(contenido)

        logger.info(f"Backup creado: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Error creando backup: {e}")
        return None


def guardar_yaml(data):
    """Guarda datos en el YAML preservando estructura"""
    try:
        with open(YAML_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        logger.info(f"YAML actualizado: {YAML_PATH}")
        return True
    except Exception as e:
        logger.error(f"Error guardando YAML: {e}")
        return False


# ======================================================================================
# FASE 1: EXTRACCIÓN Y ANÁLISIS
# ======================================================================================

def extraer_textos_categorizados(engine, min_confianza):
    """Extrae textos ya categorizados con confianza alta"""

    # Excluir categorías especiales
    categorias_excluidas_str = "', '".join(CATEGORIAS_EXCLUIDAS)

    query = f"""
        SELECT
            motivo_texto,
            categoria
        FROM respuestas_nps_csat
        WHERE categoria IS NOT NULL
          AND categoria NOT IN ('{categorias_excluidas_str}')
          AND categoria_confianza >= {min_confianza}
          AND motivo_texto IS NOT NULL
          AND LENGTH(TRIM(motivo_texto)) > 0
    """

    logger.info(f"Extrayendo textos categorizados (confianza >= {min_confianza})...")
    df = pd.read_sql(text(query), engine)
    logger.info(f"{len(df):,} textos cargados")

    return df


def calcular_correlaciones_por_categoria(df, min_frecuencia):
    """
    Calcula correlación de cada palabra con cada categoría

    Returns:
        dict: {palabra: {categoria: freq, total: N, correlacion: X, dominante: Y}}
    """
    logger.info("Analizando palabras y calculando correlaciones por categoría...")

    # Contadores
    palabra_categoria = defaultdict(lambda: defaultdict(int))
    palabra_total = Counter()

    # Procesar cada texto
    for _, row in df.iterrows():
        texto = normalize_text(row['motivo_texto'])
        categoria = row['categoria']

        palabras = tokenizar(texto)
        palabras_unicas = set(palabras)  # contar una vez por texto

        for palabra in palabras_unicas:
            palabra_categoria[palabra][categoria] += 1
            palabra_total[palabra] += 1

    # Calcular correlaciones
    resultados = {}

    for palabra, total in palabra_total.items():
        if total < min_frecuencia:
            continue

        freqs = palabra_categoria[palabra]

        # Determinar categoría dominante
        categoria_dominante = max(freqs, key=freqs.get)
        freq_max = freqs[categoria_dominante]
        correlacion = freq_max / total

        resultados[palabra] = {
            'distribucion': dict(freqs),
            'total': total,
            'correlacion': correlacion,
            'dominante': categoria_dominante
        }

    logger.info(f"{len(resultados):,} palabras únicas analizadas (freq >= {min_frecuencia})")

    return resultados


def filtrar_candidatas(correlaciones, yaml_actual, min_correlacion):
    """
    Filtra palabras candidatas para agregar al YAML

    Criterios:
    - Correlación >= min_correlacion
    - NO está en el YAML actual
    """
    # Obtener todas las palabras actuales (normalizadas)
    palabras_existentes = set()

    for categoria_obj in yaml_actual.get('categorias', []):
        nombre = categoria_obj.get('nombre', '')
        if nombre in CATEGORIAS_EXCLUIDAS:
            continue

        palabras = categoria_obj.get('palabras_clave', [])
        palabras_existentes.update([normalize_text(p) for p in palabras])

    # Filtrar candidatas por categoría
    candidatas = defaultdict(list)

    for palabra, stats in correlaciones.items():
        if stats['correlacion'] >= min_correlacion and palabra not in palabras_existentes:
            categoria_dom = stats['dominante']
            candidatas[categoria_dom].append((palabra, stats))

    # Ordenar por correlación descendente
    for cat in candidatas:
        candidatas[cat].sort(key=lambda x: x[1]['correlacion'], reverse=True)

    logger.info(f"Candidatas encontradas:")
    total_candidatas = 0
    for cat, palabras in sorted(candidatas.items()):
        logger.info(f"  - {cat}: {len(palabras)}")
        total_candidatas += len(palabras)
    logger.info(f"Total: {total_candidatas} palabras candidatas")

    return candidatas


# ======================================================================================
# FASE 2: DETECCIÓN DE PROBLEMAS
# ======================================================================================

def detectar_duplicados_categorias(yaml_actual):
    """Detecta palabras que están en múltiples categorías"""
    palabra_ubicaciones = defaultdict(list)

    for categoria_obj in yaml_actual.get('categorias', []):
        nombre = categoria_obj.get('nombre', '')
        palabras = categoria_obj.get('palabras_clave', [])

        for palabra in palabras:
            palabra_norm = normalize_text(palabra)
            palabra_ubicaciones[palabra_norm].append((nombre, palabra))

    # Filtrar solo duplicados
    duplicados = {k: v for k, v in palabra_ubicaciones.items() if len(v) > 1}

    if duplicados:
        logger.warning(f"{len(duplicados)} duplicados detectados:")
        for palabra, ubicaciones in list(duplicados.items())[:10]:  # mostrar solo primeros 10
            cats = [u[0] for u in ubicaciones]
            logger.warning(f"  - '{palabra}' en: {', '.join(cats)}")
        if len(duplicados) > 10:
            logger.warning(f"  ... y {len(duplicados) - 10} más")

    return duplicados


def validar_categorias_correctas(yaml_actual, correlaciones):
    """
    Valida que las palabras existentes están en la categoría correcta
    """
    problemas = {}

    for categoria_obj in yaml_actual.get('categorias', []):
        nombre = categoria_obj.get('nombre', '')
        if nombre in CATEGORIAS_EXCLUIDAS:
            continue

        palabras = categoria_obj.get('palabras_clave', [])

        for palabra in palabras:
            palabra_norm = normalize_text(palabra)

            if palabra_norm not in correlaciones:
                continue  # palabra muy rara, sin suficientes datos

            stats = correlaciones[palabra_norm]

            # Verificar si dominante coincide con categoría actual
            if stats['dominante'] != nombre:
                # Calcular correlación con categoría actual
                corr_actual = stats['distribucion'].get(nombre, 0) / stats['total']

                # Si correlación con categoría actual es baja
                if corr_actual < 0.50:
                    problemas[palabra] = {
                        'categoria_actual': nombre,
                        'deberia_ser': stats['dominante'],
                        'correlacion_actual': corr_actual,
                        'correlacion_correcta': stats['correlacion']
                    }

    if problemas:
        logger.warning(f"{len(problemas)} palabras con categoría posiblemente incorrecta:")
        for palabra, info in list(problemas.items())[:10]:  # mostrar solo primeras 10
            logger.warning(f"  - '{palabra}': {info['categoria_actual']} -> {info['deberia_ser']} (corr: {info['correlacion_correcta']:.2f})")
        if len(problemas) > 10:
            logger.warning(f"  ... y {len(problemas) - 10} más")

    return problemas


# ======================================================================================
# FASE 3: ACTUALIZACIÓN DEL YAML
# ======================================================================================

def agregar_nuevas_palabras_categorias(yaml_actual, candidatas, max_por_categoria):
    """Agrega nuevas palabras candidatas al YAML por categoría"""
    stats = {}

    for categoria_obj in yaml_actual.get('categorias', []):
        nombre = categoria_obj.get('nombre', '')

        if nombre in CATEGORIAS_EXCLUIDAS:
            continue

        if 'palabras_clave' not in categoria_obj:
            categoria_obj['palabras_clave'] = []

        # Tomar top N candidatas para esta categoría
        if nombre in candidatas:
            palabras_agregar = [p[0] for p in candidatas[nombre][:max_por_categoria]]

            # Agregar y ordenar alfabéticamente
            categoria_obj['palabras_clave'].extend(palabras_agregar)
            categoria_obj['palabras_clave'] = sorted(list(set(categoria_obj['palabras_clave'])))

            stats[nombre] = len(palabras_agregar)

            if palabras_agregar:
                logger.info(f"{len(palabras_agregar)} palabras agregadas a '{nombre}'")

    return stats


def resolver_duplicados_categorias(yaml_actual, duplicados, correlaciones):
    """Resuelve duplicados manteniendo palabra en categoría con mayor correlación"""
    resueltos = 0

    for palabra_norm, ubicaciones in duplicados.items():
        # Si la palabra no tiene datos de correlación, saltar
        if palabra_norm not in correlaciones:
            continue

        stats = correlaciones[palabra_norm]
        categoria_correcta = stats['dominante']

        # Eliminar de todas las categorías incorrectas
        for cat_nombre, palabra_original in ubicaciones:
            if cat_nombre == categoria_correcta:
                continue  # mantener aquí

            # Buscar y eliminar de categoría incorrecta
            for categoria_obj in yaml_actual.get('categorias', []):
                if categoria_obj.get('nombre') == cat_nombre:
                    palabras = categoria_obj.get('palabras_clave', [])
                    if palabra_original in palabras:
                        palabras.remove(palabra_original)
                        resueltos += 1

    if resueltos > 0:
        logger.info(f"{resueltos} duplicados resueltos")

    return resueltos


def corregir_categorias_incorrectas(yaml_actual, problemas, umbral_correccion):
    """Mueve palabras a su categoría correcta según correlación"""
    corregidas = 0

    for palabra, info in problemas.items():
        cat_actual = info['categoria_actual']
        cat_correcta = info['deberia_ser']

        # Solo corregir si correlación correcta es MUY alta
        if info['correlacion_correcta'] < umbral_correccion:
            continue

        # Eliminar de categoría actual
        for categoria_obj in yaml_actual.get('categorias', []):
            if categoria_obj.get('nombre') == cat_actual:
                palabras = categoria_obj.get('palabras_clave', [])
                if palabra in palabras:
                    palabras.remove(palabra)

        # Agregar a categoría correcta
        for categoria_obj in yaml_actual.get('categorias', []):
            if categoria_obj.get('nombre') == cat_correcta:
                if 'palabras_clave' not in categoria_obj:
                    categoria_obj['palabras_clave'] = []

                if palabra not in categoria_obj['palabras_clave']:
                    categoria_obj['palabras_clave'].append(palabra)
                    categoria_obj['palabras_clave'] = sorted(categoria_obj['palabras_clave'])
                    corregidas += 1

    if corregidas > 0:
        logger.info(f"{corregidas} categorías incorrectas corregidas")

    return corregidas


# ======================================================================================
# MAIN
# ======================================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Descubre y actualiza automáticamente palabras clave para categorías'
    )
    parser.add_argument('--min-frecuencia', type=int, default=MIN_FRECUENCIA,
                       help=f'Frecuencia mínima de apariciones (default: {MIN_FRECUENCIA})')
    parser.add_argument('--min-correlacion', type=float, default=MIN_CORRELACION,
                       help=f'Correlación mínima con categoría (default: {MIN_CORRELACION})')
    parser.add_argument('--max-por-categoria', type=int, default=MAX_POR_CATEGORIA,
                       help=f'Máximo de palabras nuevas por categoría (default: {MAX_POR_CATEGORIA})')
    parser.add_argument('--no-backup', action='store_true',
                       help='No crear backup del YAML antes de modificar')
    parser.add_argument('--dry-run', action='store_true',
                       help='Solo mostrar qué haría, no modificar YAML')

    args = parser.parse_args()

    print("=" * 73)
    print("DESCUBRIDOR AUTOMATICO DE PALABRAS CLAVE PARA CATEGORIAS")
    print("=" * 73)
    print()

    # 1. Conectar BD
    try:
        engine = get_engine()
        logger.info("1. Conectando a BD...")
    except Exception as e:
        logger.error(f"Error conectando a BD: {e}")
        sys.exit(1)

    # 2. Cargar YAML actual
    logger.info("2. Cargando YAML actual...")
    yaml_actual = cargar_yaml_actual()
    total_categorias = len(yaml_actual.get('categorias', []))
    total_palabras_actual = sum([
        len(cat.get('palabras_clave', []))
        for cat in yaml_actual.get('categorias', [])
    ])
    logger.info(f"   {total_categorias} categorias, {total_palabras_actual} palabras clave existentes")

    # 3. Extraer textos
    logger.info("3. Extrayendo textos categorizados...")
    df = extraer_textos_categorizados(engine, MIN_CONFIANZA_ANALISIS)

    if df.empty:
        logger.error("No hay textos categorizados con confianza suficiente")
        sys.exit(1)

    # 4. Calcular correlaciones
    logger.info("4. Analizando palabras...")
    correlaciones = calcular_correlaciones_por_categoria(df, min_frecuencia=args.min_frecuencia)

    # 5. Identificar candidatas
    logger.info("5. Identificando palabras candidatas...")
    candidatas = filtrar_candidatas(correlaciones, yaml_actual, min_correlacion=args.min_correlacion)

    # 6. Detectar problemas
    logger.info("6. Detectando problemas...")
    duplicados = detectar_duplicados_categorias(yaml_actual)
    problemas_categorias = validar_categorias_correctas(yaml_actual, correlaciones)

    # Modo dry-run: solo mostrar, no modificar
    if args.dry_run:
        print()
        print("=" * 73)
        print("MODO DRY-RUN: No se modificara el YAML")
        print("=" * 73)
        total_agregar = sum(len(candidatas[cat][:args.max_por_categoria]) for cat in candidatas)
        logger.info(f"Se agregarian {total_agregar} palabras en total")
        logger.info(f"Se resolverian {len(duplicados)} duplicados")
        logger.info(f"Se corregiran {sum(1 for p in problemas_categorias.values() if p['correlacion_correcta'] >= UMBRAL_CORRECCION)} categorias incorrectas")
        sys.exit(0)

    # 7. Crear backup
    if not args.no_backup:
        logger.info("7. Creando backup...")
        backup_path = crear_backup_yaml()
        if not backup_path:
            logger.error("No se pudo crear backup, abortando")
            sys.exit(1)
    else:
        logger.info("7. Saltando backup (--no-backup)")

    # 8. Actualizar YAML
    logger.info("8. Actualizando YAML...")

    stats_nuevas = agregar_nuevas_palabras_categorias(yaml_actual, candidatas, max_por_categoria=args.max_por_categoria)
    stats_duplicados = resolver_duplicados_categorias(yaml_actual, duplicados, correlaciones)
    stats_corregidas = corregir_categorias_incorrectas(yaml_actual, problemas_categorias, UMBRAL_CORRECCION)

    # 9. Guardar
    if not guardar_yaml(yaml_actual):
        logger.error("Error guardando YAML")
        sys.exit(1)

    # Resumen
    print()
    print("=" * 73)
    print("RESULTADO: YAML ACTUALIZADO EXITOSAMENTE")
    print("=" * 73)
    total_agregadas = sum(stats_nuevas.values())
    print(f"Total palabras agregadas: {total_agregadas}")
    for cat, count in sorted(stats_nuevas.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  - {cat}: +{count}")
    if len(stats_nuevas) > 5:
        print(f"  ... y {len(stats_nuevas) - 5} categorias mas")
    print(f"{stats_duplicados} duplicados resueltos")
    print(f"{stats_corregidas} categorias incorrectas corregidas")
    print()
    if not args.no_backup:
        print(f"Backup: {backup_path}")
    print(f"Log: descubrir_palabras_categorias.log")
    print("=" * 73)


if __name__ == '__main__':
    main()
