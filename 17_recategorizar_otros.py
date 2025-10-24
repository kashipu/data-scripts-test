#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Re-categorizador de Textos "Otros"

Re-procesa textos en categoría "Otros" usando el YAML enriquecido
para mejorar la cobertura de categorización.
"""

import argparse
import logging
import sys
import re
from datetime import datetime
from collections import defaultdict
from sqlalchemy import create_engine, text
import pandas as pd
import yaml
import ahocorasick

# ======================================================================================
# VARIABLES DE CONFIGURACIÓN - AJUSTABLES
# ======================================================================================

# BATCH SIZE
# Cuántos registros procesar por lote
# Valores sugeridos: 1000-10000
# - Más alto: Más rápido pero más uso de memoria
# - Más bajo: Más lento pero más seguro
BATCH_SIZE = 5000

# CONFIANZA MÍNIMA PARA ACEPTAR RE-CATEGORIZACIÓN
# Solo actualizar si nueva categorización tiene confianza >= este valor
# Valores sugeridos: 0.3-0.7
# - 0.3: Aceptar categorizaciones con baja confianza (más cobertura)
# - 0.5: Equilibrado (RECOMENDADO)
# - 0.7: Solo categorizaciones con alta confianza (más conservador)
MIN_CONFIANZA_RECATEGORIZACION = 0.5

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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('recategorizar_otros.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================================================================================
# FUNCIONES AUXILIARES (compatibles con 05_categorizar_motivos.py)
# ======================================================================================

def get_engine():
    """Crea engine de SQLAlchemy"""
    conn_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?client_encoding=utf8"
    return create_engine(conn_string)


def normalize_text(text):
    """Normaliza texto: lowercase, sin acentos, sin puntuación extra"""
    if pd.isna(text) or text is None:
        return ""
    text = str(text).lower().strip()
    # Remover acentos
    text = text.replace('á', 'a').replace('é', 'e').replace('í', 'i')
    text = text.replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text)
    return text


class TextCleaner:
    """Detecta y filtra textos sin sentido (ruido) - compatible con 05_categorizar_motivos.py"""

    def __init__(self, min_length=3, min_alpha_ratio=0.5):
        self.min_length = min_length
        self.min_alpha_ratio = min_alpha_ratio

    def is_valid(self, text):
        """
        Valida si un texto es válido o es ruido
        Returns: (is_valid, reason_if_invalid)
        """
        if pd.isna(text) or not text or not str(text).strip():
            return (False, "texto_vacio")

        text_clean = str(text).strip()

        # Muy corto
        if len(text_clean) < self.min_length:
            return (False, "muy_corto")

        # Demasiados caracteres no alfabéticos
        alpha_chars = sum(c.isalpha() for c in text_clean)
        if alpha_chars == 0:
            return (False, "sin_letras")

        ratio = alpha_chars / len(text_clean)
        if ratio < self.min_alpha_ratio:
            return (False, "pocos_caracteres_alfabeticos")

        # Caracteres repetidos (ej: "aaaaaaa", "......")
        if re.search(r'(.)\1{5,}', text_clean):
            return (False, "caracteres_repetidos")

        # Solo puntuación
        if re.match(r'^[^\w\s]+$', text_clean):
            return (False, "solo_puntuacion")

        return (True, None)


class CategorizerAhoCorasick:
    """Categorizador usando Aho-Corasick - compatible con 05_categorizar_motivos.py"""

    def __init__(self, categorias_config):
        self.categorias = categorias_config.get('categorias', [])
        self.automaton = self._build_automaton()

    def _build_automaton(self):
        """Construye el autómata de Aho-Corasick"""
        A = ahocorasick.Automaton()

        for categoria in self.categorias:
            nombre = categoria['nombre']
            palabras_clave = categoria.get('palabras_clave', [])

            for palabra in palabras_clave:
                palabra_norm = normalize_text(palabra)
                if palabra_norm:
                    A.add_word(palabra_norm, (nombre, palabra))

        A.make_automaton()
        return A

    def categorize(self, text):
        """
        Categoriza un texto
        Returns: (categoria, confidence, metadata)
        """
        if not text or pd.isna(text):
            return ("Otros", 0.0, {})

        text_norm = normalize_text(text)
        if not text_norm:
            return ("Otros", 0.0, {})

        # Buscar coincidencias
        matches = defaultdict(list)
        for end_index, (categoria, palabra) in self.automaton.iter(text_norm):
            matches[categoria].append(palabra)

        if not matches:
            return ("Otros", 0.0, {})

        # Calcular score por categoría
        categoria_scores = {}
        for categoria, palabras in matches.items():
            # Score = número de palabras clave encontradas
            score = len(palabras)
            categoria_scores[categoria] = score

        # Categoría ganadora
        best_categoria = max(categoria_scores, key=categoria_scores.get)
        best_score = categoria_scores[best_categoria]

        # Calcular confianza (normalizada)
        total_matches = sum(categoria_scores.values())
        confidence = best_score / total_matches if total_matches > 0 else 0.0

        metadata = {
            'palabras_encontradas': matches[best_categoria],
            'num_matches': best_score,
            'total_matches': total_matches
        }

        return (best_categoria, confidence, metadata)


# ======================================================================================
# FUNCIONES PRINCIPALES
# ======================================================================================

def cargar_yaml_categorias():
    """Carga el YAML de categorías"""
    try:
        with open(YAML_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Archivo {YAML_PATH} no encontrado")
        sys.exit(1)


def extraer_textos_otros(engine):
    """Extrae textos en categoría 'Otros'"""
    query = """
        SELECT id, motivo_texto
        FROM respuestas_nps_csat
        WHERE categoria = 'Otros'
          AND motivo_texto IS NOT NULL
        ORDER BY id
    """

    logger.info("Extrayendo textos en categoria 'Otros'...")
    df = pd.read_sql(text(query), engine)
    logger.info(f"{len(df):,} textos en 'Otros' encontrados")

    return df


def recategorizar_lote(df_lote, categorizer, text_cleaner, min_confianza):
    """
    Re-categoriza un lote de textos

    Returns: lista de (id, nueva_categoria, nueva_confianza) para UPDATE
    """
    actualizaciones = []

    for _, row in df_lote.iterrows():
        texto = row['motivo_texto']

        # Verificar si es ruido
        is_valid, razon = text_cleaner.is_valid(texto)
        if not is_valid:
            # Es ruido, clasificar como tal
            actualizaciones.append({
                'id': row['id'],
                'categoria': 'Texto Sin Sentido / Ruido',
                'confianza': 1.0
            })
            continue

        # Intentar categorizar
        categoria, confianza, metadata = categorizer.categorize(texto)

        # Solo actualizar si confianza es suficiente
        if confianza >= min_confianza:
            actualizaciones.append({
                'id': row['id'],
                'categoria': categoria,
                'confianza': confianza
            })

    return actualizaciones


def actualizar_bd(engine, actualizaciones):
    """Actualiza la BD con las nuevas categorizaciones"""
    if not actualizaciones:
        return 0

    with engine.begin() as conn:
        for update in actualizaciones:
            query = text("""
                UPDATE respuestas_nps_csat
                SET categoria = :categoria,
                    categoria_confianza = :confianza
                WHERE id = :id
            """)
            conn.execute(query, update)

    return len(actualizaciones)


# ======================================================================================
# MAIN
# ======================================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Re-categoriza textos en "Otros" usando YAML enriquecido'
    )
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE,
                       help=f'Tamaño de lote para procesamiento (default: {BATCH_SIZE})')
    parser.add_argument('--min-confianza', type=float, default=MIN_CONFIANZA_RECATEGORIZACION,
                       help=f'Confianza mínima para aceptar re-categorización (default: {MIN_CONFIANZA_RECATEGORIZACION})')
    parser.add_argument('--dry-run', action='store_true',
                       help='Solo mostrar qué haría, NO actualizar BD')
    parser.add_argument('--yes', action='store_true',
                       help='No pedir confirmación')

    args = parser.parse_args()

    print("=" * 73)
    print("RE-CATEGORIZADOR DE TEXTOS \"OTROS\"")
    print("=" * 73)
    print()

    # 1. Conectar BD
    try:
        engine = get_engine()
        logger.info("1. Conectando a BD...")
    except Exception as e:
        logger.error(f"Error conectando a BD: {e}")
        sys.exit(1)

    # 2. Cargar categorías
    logger.info("2. Cargando categorias...")
    yaml_config = cargar_yaml_categorias()
    total_categorias = len(yaml_config.get('categorias', []))
    total_palabras = sum([len(cat.get('palabras_clave', [])) for cat in yaml_config.get('categorias', [])])
    logger.info(f"   {total_categorias} categorias cargadas")
    logger.info(f"   {total_palabras} palabras clave totales")

    # 3. Extraer textos "Otros"
    logger.info("3. Extrayendo textos en 'Otros'...")
    df = extraer_textos_otros(engine)

    if df.empty:
        logger.info("No hay textos en categoria 'Otros'")
        sys.exit(0)

    total_textos = len(df)

    # Confirmación
    if not args.yes and not args.dry_run:
        respuesta = input(f"\n¿Re-categorizar {total_textos:,} textos? (s/n): ")
        if respuesta.lower() != 's':
            logger.info("Cancelado por el usuario")
            sys.exit(0)

    # 4. Inicializar categorizador
    logger.info("4. Inicializando categorizador...")
    categorizer = CategorizerAhoCorasick(yaml_config)
    text_cleaner = TextCleaner()

    # 5. Procesar por lotes
    logger.info("5. Re-categorizando...")
    total_actualizados = 0
    distribucion = defaultdict(int)

    num_lotes = (total_textos + args.batch_size - 1) // args.batch_size

    for i in range(0, total_textos, args.batch_size):
        lote_num = (i // args.batch_size) + 1
        df_lote = df.iloc[i:i + args.batch_size]

        actualizaciones = recategorizar_lote(
            df_lote,
            categorizer,
            text_cleaner,
            min_confianza=args.min_confianza
        )

        # Contabilizar distribución
        for update in actualizaciones:
            distribucion[update['categoria']] += 1

        # Actualizar BD (si no es dry-run)
        if not args.dry_run:
            actualizados = actualizar_bd(engine, actualizaciones)
            total_actualizados += actualizados
        else:
            total_actualizados += len(actualizaciones)

        logger.info(f"   Lote {lote_num}/{num_lotes} completado ({len(df_lote):,} registros, {len(actualizaciones)} actualizados)")

    # Resumen
    print()
    print("=" * 73)
    if args.dry_run:
        print("MODO DRY-RUN: No se actualizó la BD")
    else:
        print("RESULTADO: RE-CATEGORIZACION COMPLETADA")
    print("=" * 73)
    print(f"Total procesados: {total_textos:,}")
    print(f"Re-categorizados: {total_actualizados:,} ({total_actualizados/total_textos*100:.1f}%)")
    print(f"Permanecen en 'Otros': {total_textos - total_actualizados:,} ({(total_textos - total_actualizados)/total_textos*100:.1f}%)")
    print()
    print("Distribucion de nuevas categorizaciones:")

    # Top 10 categorías
    for categoria, count in sorted(distribucion.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {categoria}: {count:,}")

    if len(distribucion) > 10:
        print(f"  ... y {len(distribucion) - 10} categorias mas")

    print()
    print(f"Log: recategorizar_otros.log")
    print("=" * 73)


if __name__ == '__main__':
    main()
