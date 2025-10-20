#!/usr/bin/env python3
"""
Reporte Final de Categorización
"""
import sys
import os
sys.path.append('nueva_etl')

from utils import get_engine
from sqlalchemy import text

def main():
    engine = get_engine('nps_analitycs')

    print("=" * 100)
    print("REPORTE FINAL DE CATEGORIZACIÓN - VERSIÓN 9")
    print("=" * 100)
    print()

    with engine.connect() as conn:
        # 1. Estadísticas generales
        result = conn.execute(text("""
            SELECT COUNT(*) as total
            FROM motivos_categorizados
        """)).fetchone()

        total = result[0]
        print(f"Total de registros categorizados: {total:,}\n")

        # 2. Distribución por categoría
        print("=" * 100)
        print("DISTRIBUCIÓN POR CATEGORÍA")
        print("=" * 100)
        print(f"{'Categoría':<50} {'Cantidad':>12} {'%':>8}")
        print("-" * 100)

        result = conn.execute(text("""
            SELECT categoria, COUNT(*) as cantidad
            FROM motivos_categorizados
            GROUP BY categoria
            ORDER BY cantidad DESC
        """))

        for cat, cant in result:
            pct = (cant / total) * 100
            print(f"{cat:<50} {cant:>12,} {pct:>7.2f}%")

        # 3. Distribución por tipo de texto
        print("\n" + "=" * 100)
        print("DISTRIBUCIÓN POR LONGITUD DE TEXTO (texto_tipo)")
        print("=" * 100)
        print(f"{'Tipo':<20} {'Cantidad':>12} {'%':>8} {'Long. Promedio':>16} {'Min':>8} {'Max':>8}")
        print("-" * 100)

        result = conn.execute(text("""
            SELECT
                texto_tipo,
                COUNT(*) as cantidad,
                ROUND(AVG(LENGTH(texto_motivo)), 1) as longitud_promedio,
                MIN(LENGTH(texto_motivo)) as min,
                MAX(LENGTH(texto_motivo)) as max
            FROM motivos_categorizados
            GROUP BY texto_tipo
            ORDER BY
                CASE texto_tipo
                    WHEN 'muy_corto' THEN 1
                    WHEN 'corto' THEN 2
                    WHEN 'mediano' THEN 3
                    WHEN 'largo' THEN 4
                END
        """))

        for tipo, cant, promedio, min_len, max_len in result:
            pct = (cant / total) * 100
            print(f"{tipo:<20} {cant:>12,} {pct:>7.2f}% {promedio:>15.1f} {min_len:>8} {max_len:>8}")

        # 4. Top 10 categorías por tipo de texto
        print("\n" + "=" * 100)
        print("TOP 10 CATEGORÍAS POR TIPO DE TEXTO")
        print("=" * 100)

        for tipo in ['muy_corto', 'corto', 'mediano', 'largo']:
            print(f"\n{tipo.upper().replace('_', ' ')}:")
            print(f"{'  Categoría':<52} {'Cantidad':>12}")
            print("  " + "-" * 96)

            result = conn.execute(text("""
                SELECT categoria, COUNT(*) as cantidad
                FROM motivos_categorizados
                WHERE texto_tipo = :tipo
                GROUP BY categoria
                ORDER BY cantidad DESC
                LIMIT 10
            """), {"tipo": tipo})

            for cat, cant in result:
                print(f"  {cat:<50} {cant:>12,}")

        # 5. Distribución por canal y métrica
        print("\n" + "=" * 100)
        print("DISTRIBUCIÓN POR CANAL Y MÉTRICA")
        print("=" * 100)
        print(f"{'Canal':<10} {'Métrica':<10} {'Cantidad':>12} {'%':>8}")
        print("-" * 100)

        result = conn.execute(text("""
            SELECT canal, metrica, COUNT(*) as cantidad
            FROM motivos_categorizados
            GROUP BY canal, metrica
            ORDER BY canal, metrica
        """))

        for canal, metrica, cant in result:
            pct = (cant / total) * 100
            print(f"{canal:<10} {metrica:<10} {cant:>12,} {pct:>7.2f}%")

        # 6. Métricas de calidad
        print("\n" + "=" * 100)
        print("MÉTRICAS DE CALIDAD")
        print("=" * 100)

        result = conn.execute(text("""
            SELECT
                ROUND(AVG(confidence), 4) as confianza_promedio,
                ROUND(MIN(confidence), 4) as confianza_minima,
                ROUND(MAX(confidence), 4) as confianza_maxima,
                COUNT(CASE WHEN es_ruido = TRUE THEN 1 END) as total_ruido,
                COUNT(CASE WHEN categoria = 'Otros' THEN 1 END) as total_otros
            FROM motivos_categorizados
            WHERE es_ruido = FALSE
        """)).fetchone()

        conf_prom, conf_min, conf_max, total_ruido, total_otros = result

        textos_utiles = total - total_ruido
        print(f"Confianza promedio: {conf_prom:.4f}")
        print(f"Confianza mínima: {conf_min:.4f}")
        print(f"Confianza máxima: {conf_max:.4f}")
        print(f"Total ruido: {total_ruido:,} ({(total_ruido/total)*100:.2f}%)")
        print(f"Textos útiles: {textos_utiles:,} ({(textos_utiles/total)*100:.2f}%)")
        print(f"Categoría 'Otros': {total_otros:,} ({(total_otros/textos_utiles)*100:.2f}% de textos útiles)")

        # 7. Distribución de confianza
        print("\n" + "=" * 100)
        print("DISTRIBUCIÓN DE CONFIANZA")
        print("=" * 100)

        result = conn.execute(text("""
            SELECT
                CASE
                    WHEN confidence < 0.3 THEN 'Muy baja (< 0.3)'
                    WHEN confidence < 0.5 THEN 'Baja (0.3-0.5)'
                    WHEN confidence < 0.7 THEN 'Media (0.5-0.7)'
                    WHEN confidence < 0.9 THEN 'Alta (0.7-0.9)'
                    ELSE 'Muy alta (0.9-1.0)'
                END as rango,
                COUNT(*) as cantidad
            FROM motivos_categorizados
            WHERE es_ruido = FALSE
            GROUP BY
                CASE
                    WHEN confidence < 0.3 THEN 'Muy baja (< 0.3)'
                    WHEN confidence < 0.5 THEN 'Baja (0.3-0.5)'
                    WHEN confidence < 0.7 THEN 'Media (0.5-0.7)'
                    WHEN confidence < 0.9 THEN 'Alta (0.7-0.9)'
                    ELSE 'Muy alta (0.9-1.0)'
                END
            ORDER BY
                MIN(CASE
                    WHEN confidence < 0.3 THEN 1
                    WHEN confidence < 0.5 THEN 2
                    WHEN confidence < 0.7 THEN 3
                    WHEN confidence < 0.9 THEN 4
                    ELSE 5
                END)
        """))

        print(f"{'Rango':<25} {'Cantidad':>12} {'%':>8}")
        print("-" * 100)

        for rango, cant in result:
            pct = (cant / textos_utiles) * 100
            print(f"{rango:<25} {cant:>12,} {pct:>7.2f}%")

        print("\n" + "=" * 100)
        print("+ CATEGORIZACIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 100)

if __name__ == "__main__":
    main()
