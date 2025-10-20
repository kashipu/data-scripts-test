"""
Generador de nubes de palabras para análisis de motivos NPS/CSAT
Versión 4 - BM: NPS (3) + CSAT (2) | BV: NPS (3) = 8 nubes totales
"""
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from sqlalchemy import create_engine
import logging
from pathlib import Path
import re
from collections import Counter

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cloudwords.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Configuración de base de datos
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}

# Stopwords personalizadas (español + dominio específico)
CUSTOM_STOPWORDS = {
    # Artículos, preposiciones, conjunciones
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'al', 'a', 'en', 'por', 'para', 'con', 'sin',
    'y', 'o', 'u', 'e', 'pero', 'sino', 'que', 'cual', 'cuales',
    'mi', 'tu', 'su', 'nuestro', 'vuestro', 'sus', 'mis', 'tus',
    'me', 'te', 'se', 'nos', 'os', 'lo', 'le', 'les',
    'este', 'ese', 'aquel', 'esta', 'esa', 'aquella',
    'muy', 'mas', 'más', 'menos', 'mucho', 'poco', 'bastante',
    'si', 'no', 'ni', 'también', 'tampoco', 'porque',
    'como', 'cuando', 'donde', 'quien', 'quienes',
    'hay', 'ha', 'he', 'hemos', 'han', 'ser', 'estar', 'es', 'son',
    'fue', 'fueron', 'sido', 'siendo', 'esta', 'están',
    # Palabras del dominio bancario que no aportan
    'banco', 'bancos', 'bancaria', 'bancarias', 'bancario',
    'movil', 'móvil', 'virtual', 'app', 'aplicacion', 'aplicación',
    'sistema', 'plataforma', 'servicio', 'servicios',
    # Palabras genéricas
    'cosa', 'cosas', 'algo', 'nada', 'todo', 'todos', 'todas',
    'vez', 'veces', 'momento', 'momentos', 'tiempo',
    'aquí', 'ahi', 'ahí', 'allí', 'acá', 'allá',
    'si', 'sí', 'no', 'ya', 'aun', 'aún',
    # Palabras relacionadas con encuestas
    'encuesta', 'pregunta', 'respuesta', 'comentario',
    'calificacion', 'calificación', 'puntuacion', 'puntuación'
}

class WordCloudGenerator:
    """Generador de nubes de palabras para motivos NPS/CSAT"""

    def __init__(self):
        """Inicializa el generador"""
        self.engine = None
        self.logger = logging.getLogger(__name__)

    def connect(self):
        """Establece conexión con PostgreSQL"""
        try:
            connection_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?client_encoding=utf8"
            self.engine = create_engine(connection_string)
            self.logger.info("✓ Conexión a PostgreSQL establecida")
            return True
        except Exception as e:
            self.logger.error(f"✗ Error conectando a PostgreSQL: {e}")
            return False

    def load_bm_nps_by_category(self, category, month_filter=None):
        """Carga motivos de NPS por categoría para BM"""
        try:
            query = f"""
            SELECT
                nps_recomendacion_motivo,
                month_year
            FROM banco_movil_clean
            WHERE nps_category = '{category}'
              AND nps_recomendacion_motivo IS NOT NULL
              AND nps_recomendacion_motivo != ''
            """

            if month_filter:
                query += f" AND month_year = '{month_filter}'"

            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)

            self.logger.info(f"✓ Cargados {len(df)} registros de BM-NPS {category}")
            return df

        except Exception as e:
            self.logger.error(f"✗ Error cargando datos: {e}")
            return pd.DataFrame()

    def load_bm_csat(self, month_filter=None):
        """Carga motivos de CSAT para BM"""
        try:
            query = """
            SELECT
                csat_satisfaccion_motivo,
                csat_satisfaccion_score,
                month_year
            FROM banco_movil_clean
            WHERE csat_satisfaccion_motivo IS NOT NULL
              AND csat_satisfaccion_motivo != ''
              AND csat_satisfaccion_score IS NOT NULL
            """

            if month_filter:
                query += f" AND month_year = '{month_filter}'"

            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)

            self.logger.info(f"✓ Cargados {len(df)} registros de BM-CSAT")
            return df

        except Exception as e:
            self.logger.error(f"✗ Error cargando datos: {e}")
            return pd.DataFrame()

    def load_bv_nps_by_category(self, category, month_filter=None):
        """Carga motivos de NPS por categoría para BV"""
        try:
            query = f"""
            SELECT
                motivo_calificacion,
                month_year
            FROM banco_virtual_clean
            WHERE nps_category = '{category}'
              AND motivo_calificacion IS NOT NULL
              AND motivo_calificacion != ''
            """

            if month_filter:
                query += f" AND month_year = '{month_filter}'"

            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)

            self.logger.info(f"✓ Cargados {len(df)} registros de BV-NPS {category}")
            return df

        except Exception as e:
            self.logger.error(f"✗ Error cargando datos: {e}")
            return pd.DataFrame()

    def clean_text(self, text):
        """Limpia y normaliza texto"""
        if pd.isna(text) or text == '':
            return ''

        # Convertir a minúsculas
        text = str(text).lower()

        # Remover URLs
        text = re.sub(r'http\S+|www\S+', '', text)

        # Remover emails
        text = re.sub(r'\S+@\S+', '', text)

        # Remover números solos
        text = re.sub(r'\b\d+\b', '', text)

        # Remover puntuación pero mantener espacios
        text = re.sub(r'[^\w\s]', ' ', text)

        # Remover espacios múltiples
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def extract_words(self, df, column_name):
        """Extrae palabras limpias de una columna de texto"""
        all_text = ' '.join(df[column_name].dropna().astype(str))
        cleaned_text = self.clean_text(all_text)

        # Separar en palabras
        words = cleaned_text.split()

        # Filtrar stopwords y palabras cortas
        filtered_words = [
            word for word in words
            if word not in CUSTOM_STOPWORDS and len(word) > 2
        ]

        self.logger.info(f"✓ Extraídas {len(filtered_words)} palabras válidas de {len(words)} totales")

        return filtered_words

    def create_wordcloud(self, words, title, output_path, colormap='Reds'):
        """Genera y guarda una nube de palabras"""
        try:
            # Contar frecuencias
            word_freq = Counter(words)

            # Mostrar top 10 palabras
            self.logger.info(f"Top 10 palabras en '{title}':")
            for word, count in word_freq.most_common(10):
                self.logger.info(f"  {word}: {count}")

            # Crear nube de palabras
            wordcloud = WordCloud(
                width=1200,
                height=600,
                background_color='white',
                colormap=colormap,
                max_words=100,
                relative_scaling=0.5,
                min_font_size=10
            ).generate_from_frequencies(word_freq)

            # Crear figura
            plt.figure(figsize=(15, 8))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            plt.title(title, fontsize=20, fontweight='bold', pad=20)
            plt.tight_layout(pad=0)

            # Guardar
            plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close()

            self.logger.info(f"✓ Nube de palabras guardada en: {output_path}")

        except Exception as e:
            self.logger.error(f"✗ Error generando nube de palabras: {e}")

    def generate_bm_nps_all_categories(self, month_filter=None):
        """Genera nubes de palabras para todas las categorías NPS de BM"""
        self.logger.info("=== GENERANDO NUBES DE PALABRAS BM-NPS (TODAS LAS CATEGORÍAS) ===")

        # Crear directorio de salida
        output_dir = Path('visualizaciones')
        output_dir.mkdir(exist_ok=True)

        # Configuración por categoría
        categories_config = {
            'Detractor': {
                'colormap': 'Reds',
                'filename': 'wordcloud_bm_nps_detractores.png'
            },
            'Neutral': {
                'colormap': 'Oranges',
                'filename': 'wordcloud_bm_nps_neutrales.png'
            },
            'Promotor': {
                'colormap': 'Greens',
                'filename': 'wordcloud_bm_nps_promotores.png'
            }
        }

        # Generar una nube por categoría
        for category, config in categories_config.items():
            self.logger.info(f"\n--- Procesando categoría: {category} ---")

            # Cargar datos
            df = self.load_bm_nps_by_category(category, month_filter)

            if df.empty:
                self.logger.warning(f"⚠ No hay datos para {category}")
                continue

            # Extraer palabras
            words = self.extract_words(df, 'nps_recomendacion_motivo')

            if not words:
                self.logger.warning(f"⚠ No se extrajeron palabras válidas para {category}")
                continue

            # Generar nube
            title = f"Motivos de NPS - {category}s (Banco Móvil)"
            if month_filter:
                title += f" - {month_filter}"

            output_path = output_dir / config['filename']
            self.create_wordcloud(words, title, output_path, colormap=config['colormap'])

        self.logger.info("\n=== GENERACIÓN COMPLETADA ===")

    def generate_bm_csat(self, month_filter=None):
        """Genera nubes de palabras para CSAT de BM (separado por score alto/bajo)"""
        self.logger.info("=== GENERANDO NUBES DE PALABRAS BM-CSAT ===")

        # Crear directorio de salida
        output_dir = Path('visualizaciones')
        output_dir.mkdir(exist_ok=True)

        # Cargar datos CSAT
        df = self.load_bm_csat(month_filter)

        if df.empty:
            self.logger.warning("⚠ No hay datos CSAT para procesar")
            return

        # Separar por score alto (satisfechos) y bajo (insatisfechos)
        # CSAT típicamente usa escala 1-5, asumimos >3 = satisfechos, <=3 = insatisfechos
        df_satisfechos = df[df['csat_satisfaccion_score'] > 3]
        df_insatisfechos = df[df['csat_satisfaccion_score'] <= 3]

        self.logger.info(f"  Satisfechos (>3): {len(df_satisfechos)} registros")
        self.logger.info(f"  Insatisfechos (<=3): {len(df_insatisfechos)} registros")

        # Configuración para cada segmento
        segments = [
            {
                'name': 'Satisfechos',
                'df': df_satisfechos,
                'colormap': 'Blues',
                'filename': 'wordcloud_bm_csat_satisfechos.png'
            },
            {
                'name': 'Insatisfechos',
                'df': df_insatisfechos,
                'colormap': 'Purples',
                'filename': 'wordcloud_bm_csat_insatisfechos.png'
            }
        ]

        # Generar nubes
        for segment in segments:
            self.logger.info(f"\n--- Procesando CSAT: {segment['name']} ---")

            if segment['df'].empty:
                self.logger.warning(f"⚠ No hay datos para {segment['name']}")
                continue

            # Extraer palabras
            words = self.extract_words(segment['df'], 'csat_satisfaccion_motivo')

            if not words:
                self.logger.warning(f"⚠ No se extrajeron palabras válidas para {segment['name']}")
                continue

            # Generar nube
            title = f"Motivos de CSAT - {segment['name']} (Banco Móvil)"
            if month_filter:
                title += f" - {month_filter}"

            output_path = output_dir / segment['filename']
            self.create_wordcloud(words, title, output_path, colormap=segment['colormap'])

        self.logger.info("\n=== GENERACIÓN COMPLETADA ===")

    def generate_bv_nps_all_categories(self, month_filter=None):
        """Genera nubes de palabras para todas las categorías NPS de BV"""
        self.logger.info("=== GENERANDO NUBES DE PALABRAS BV-NPS (TODAS LAS CATEGORÍAS) ===")

        # Crear directorio de salida
        output_dir = Path('visualizaciones')
        output_dir.mkdir(exist_ok=True)

        # Configuración por categoría (colores más oscuros para diferenciar de BM)
        categories_config = {
            'Detractor': {
                'colormap': 'YlOrRd',  # Amarillo-Naranja-Rojo
                'filename': 'wordcloud_bv_nps_detractores.png'
            },
            'Neutral': {
                'colormap': 'YlOrBr',  # Amarillo-Naranja-Marrón
                'filename': 'wordcloud_bv_nps_neutrales.png'
            },
            'Promotor': {
                'colormap': 'YlGn',  # Amarillo-Verde
                'filename': 'wordcloud_bv_nps_promotores.png'
            }
        }

        # Generar una nube por categoría
        for category, config in categories_config.items():
            self.logger.info(f"\n--- Procesando categoría BV: {category} ---")

            # Cargar datos
            df = self.load_bv_nps_by_category(category, month_filter)

            if df.empty:
                self.logger.warning(f"⚠ No hay datos para {category} en BV")
                continue

            # Extraer palabras
            words = self.extract_words(df, 'motivo_calificacion')

            if not words:
                self.logger.warning(f"⚠ No se extrajeron palabras válidas para {category} en BV")
                continue

            # Generar nube
            title = f"Motivos de NPS - {category}s (Banco Virtual)"
            if month_filter:
                title += f" - {month_filter}"

            output_path = output_dir / config['filename']
            self.create_wordcloud(words, title, output_path, colormap=config['colormap'])

        self.logger.info("\n=== GENERACIÓN COMPLETADA ===")

def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(description='Generador de nubes de palabras NPS/CSAT')
    parser.add_argument('--month', type=str, help='Filtrar por mes (formato: 2025-08)')

    args = parser.parse_args()

    # Crear generador
    generator = WordCloudGenerator()

    # Conectar a BD
    if not generator.connect():
        return

    # Generar nubes para todas las categorías NPS de BM
    generator.generate_bm_nps_all_categories(month_filter=args.month)

    # Generar nubes para CSAT de BM
    generator.generate_bm_csat(month_filter=args.month)

    # Generar nubes para NPS de BV
    generator.generate_bv_nps_all_categories(month_filter=args.month)

    # Cerrar conexión
    if generator.engine:
        generator.engine.dispose()

if __name__ == "__main__":
    main()
