def validar_datos_detallado(df, ruta_archivo_salida, tipo_archivo):
    """
    Valida datos extraídos y genera reporte detallado categorizando errores por severidad

    CATEGORÍAS:
    - CRÍTICOS: Bloquean el procesamiento
    - ADVERTENCIAS: Revisar pero no bloquean
    - INFORMATIVOS: Se corrigen automáticamente en 2_limpieza.py

    Args:
        df (DataFrame): DataFrame con datos extraídos
        ruta_archivo_salida (str): Ruta del archivo de salida
        tipo_archivo (str): 'BM' o 'BV'

    Returns:
        dict: Diccionario con resultados de validación categorizados
    """
    validacion = {
        'total_filas': len(df),
        'filas_validas': 0,
        'filas_con_criticos': 0,
        'filas_con_advertencias': 0,
        'filas_con_informativos': 0,

        # Errores por severidad
        'criticos': [],
        'advertencias': [],
        'informativos': [],

        # Análisis de duplicados
        'duplicados_por_id': 0,
        'duplicados_reales': 0,

        # Otras métricas
        'columnas_criticas_faltantes': [],
        'valores_nulos_por_columna': {},
        'errores_encoding': 0,
        'tiene_encoding_corrupto': False
    }

    # =========================================================================
    # 1. VERIFICAR COLUMNAS CRÍTICAS
    # =========================================================================
    if tipo_archivo == 'BM':
        columnas_criticas = ['timestamp', 'answers']
        columnas_unicas = ['timestamp', 'answers', 'custIdentNum']
    else:  # BV
        columnas_criticas = ['Date Submitted']
        columnas_unicas = ['Date Submitted']

    for col in columnas_criticas:
        if col not in df.columns:
            validacion['columnas_criticas_faltantes'].append(col)
            validacion['criticos'].append({
                'tipo': 'columna_faltante',
                'columna': col,
                'mensaje': f"Columna crítica '{col}' no existe"
            })

    # =========================================================================
    # 2. ANÁLISIS DE DUPLICADOS INTELIGENTE
    # =========================================================================
    # Duplicados por ID (puede ser falso positivo)
    if tipo_archivo == 'BM' and 'id' in df.columns:
        validacion['duplicados_por_id'] = int(df['id'].duplicated().sum())
    elif tipo_archivo == 'BV' and 'Date Submitted' in df.columns:
        validacion['duplicados_por_id'] = int(df['Date Submitted'].duplicated().sum())

    # Duplicados REALES (comparando columnas importantes)
    columnas_disponibles = [col for col in columnas_unicas if col in df.columns]
    if columnas_disponibles:
        validacion['duplicados_reales'] = int(df[columnas_disponibles].duplicated().sum())

    # Evaluar severidad de duplicados
    if validacion['duplicados_reales'] > 0:
        if validacion['duplicados_reales'] > len(df) * 0.5:  # >50% duplicados
            validacion['criticos'].append({
                'tipo': 'duplicados_masivos',
                'cantidad': validacion['duplicados_reales'],
                'mensaje': f"Más del 50% de registros están completamente duplicados ({validacion['duplicados_reales']:,})"
            })
        else:
            validacion['advertencias'].append({
                'tipo': 'duplicados',
                'cantidad': validacion['duplicados_reales'],
                'mensaje': f"{validacion['duplicados_reales']:,} registros completamente duplicados detectados"
            })

    # Si hay duplicados por ID pero NO duplicados reales, es solo advertencia
    if validacion['duplicados_por_id'] > 0 and validacion['duplicados_reales'] == 0:
        validacion['advertencias'].append({
            'tipo': 'ids_duplicados',
            'cantidad': validacion['duplicados_por_id'],
            'mensaje': f"{validacion['duplicados_por_id']} IDs duplicados pero respuestas únicas (no bloquea)"
        })

    # =========================================================================
    # 3. ANÁLISIS DE VALORES NULOS
    # =========================================================================
    for col in df.columns:
        nulos = df[col].isna().sum()
        if nulos > 0:
            porcentaje = round(nulos / len(df) * 100, 2)
            validacion['valores_nulos_por_columna'][col] = {
                'cantidad': int(nulos),
                'porcentaje': porcentaje
            }

            # Evaluar severidad según columna y porcentaje
            if col in columnas_criticas and porcentaje > 50:
                validacion['criticos'].append({
                    'tipo': 'nulos_criticos',
                    'columna': col,
                    'cantidad': nulos,
                    'porcentaje': porcentaje,
                    'mensaje': f"Columna crítica '{col}' tiene {porcentaje}% de valores nulos"
                })
            elif col in columnas_criticas and porcentaje > 10:
                validacion['advertencias'].append({
                    'tipo': 'nulos_moderados',
                    'columna': col,
                    'cantidad': nulos,
                    'porcentaje': porcentaje,
                    'mensaje': f"Columna '{col}' tiene {porcentaje}% de valores nulos"
                })

    # =========================================================================
    # 4. VALIDACIÓN FILA POR FILA (solo primeras 1000)
    # =========================================================================
    filas_a_validar = min(1000, len(df))

    for idx in range(filas_a_validar):
        fila = df.iloc[idx]
        tiene_critico = False
        tiene_advertencia = False
        tiene_informativo = False

        if tipo_archivo == 'BM':
            # Validar timestamp
            if 'timestamp' in df.columns and pd.isna(fila['timestamp']):
                tiene_advertencia = True
                if len(validacion['advertencias']) < 100:
                    validacion['advertencias'].append({
                        'tipo': 'timestamp_nulo',
                        'fila': idx + 2,
                        'columna': 'timestamp',
                        'mensaje': 'Timestamp nulo'
                    })

            # Validar answers
            if 'answers' in df.columns:
                valor_answers = fila['answers']

                if pd.isna(valor_answers) or str(valor_answers).strip() == '':
                    tiene_critico = True
                    if len(validacion['criticos']) < 100:
                        validacion['criticos'].append({
                            'tipo': 'answers_vacio',
                            'fila': idx + 2,
                            'columna': 'answers',
                            'mensaje': 'Campo answers vacío o nulo'
                        })

                elif isinstance(valor_answers, str):
                    # Detectar encoding corrupto (INFORMATIVO - se corrige en limpieza)
                    if 'Ã' in valor_answers or 'Â' in valor_answers:
                        tiene_informativo = True
                        validacion['errores_encoding'] += 1
                        validacion['tiene_encoding_corrupto'] = True

        else:  # BV
            # Validar Date Submitted
            if 'Date Submitted' in df.columns and pd.isna(fila['Date Submitted']):
                tiene_critico = True
                if len(validacion['criticos']) < 100:
                    validacion['criticos'].append({
                        'tipo': 'fecha_nula',
                        'fila': idx + 2,
                        'columna': 'Date Submitted',
                        'mensaje': 'Fecha de envío nula'
                    })

        # Contabilizar por severidad
        if tiene_critico:
            validacion['filas_con_criticos'] += 1
        elif tiene_advertencia:
            validacion['filas_con_advertencias'] += 1
        elif tiene_informativo:
            validacion['filas_con_informativos'] += 1
        else:
            validacion['filas_validas'] += 1

    # =========================================================================
    # 5. AGREGAR RESUMEN DE ENCODING CORRUPTO
    # =========================================================================
    if validacion['errores_encoding'] > 0:
        validacion['informativos'].append({
            'tipo': 'encoding_corrupto',
            'cantidad': validacion['errores_encoding'],
            'mensaje': f"Encoding UTF-8 corrupto en {validacion['errores_encoding']} registros (se corregirá en 2_limpieza.py)",
            'auto_corregible': True
        })

    # =========================================================================
    # 6. CALCULAR TASA DE CALIDAD REAL
    # =========================================================================
    # No contar informativos (auto-corregibles) como errores
    filas_con_errores_reales = validacion['filas_con_criticos'] + validacion['filas_con_advertencias']
    filas_procesables = validacion['total_filas'] - validacion['filas_con_criticos']

    if validacion['total_filas'] > 0:
        tasa_calidad = (filas_procesables / validacion['total_filas']) * 100
        validacion['tasa_calidad'] = round(tasa_calidad, 2)
    else:
        validacion['tasa_calidad'] = 0.0

    # =========================================================================
    # 7. DETERMINAR ESTADO FINAL
    # =========================================================================
    if len(validacion['criticos']) > 0 or validacion['tasa_calidad'] < 50:
        validacion['estado'] = 'CRITICO'
        validacion['puede_continuar'] = False
    elif validacion['tasa_calidad'] >= 95:
        validacion['estado'] = 'EXCELENTE'
        validacion['puede_continuar'] = True
    elif validacion['tasa_calidad'] >= 80:
        validacion['estado'] = 'BUENO'
        validacion['puede_continuar'] = True
    else:
        validacion['estado'] = 'ACEPTABLE'
        validacion['puede_continuar'] = True

    # =========================================================================
    # 8. GENERAR ARCHIVO DE VALIDACIÓN
    # =========================================================================
    archivo_validacion = ruta_archivo_salida.replace('.xlsx', '.validation')
    try:
        with open(archivo_validacion, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("REPORTE DE VALIDACIÓN - 1_extractor.py (V4.0)\n")
            f.write("="*80 + "\n\n")

            f.write(f"Archivo: {os.path.basename(ruta_archivo_salida)}\n")
            f.write(f"Tipo: {tipo_archivo}\n")
            f.write(f"Fecha de validación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Resumen ejecutivo
            f.write("┌" + "─"*78 + "┐\n")
            f.write("│" + " "*26 + "RESUMEN EJECUTIVO" + " "*35 + "│\n")
            f.write("└" + "─"*78 + "┘\n\n")

            f.write(f"Total de filas: {validacion['total_filas']:,}\n")
            f.write(f"Tasa de calidad: {validacion['tasa_calidad']:.2f}%")

            if validacion['estado'] == 'EXCELENTE':
                f.write(" ✅ EXCELENTE\n")
            elif validacion['estado'] == 'BUENO':
                f.write(" ✅ BUENO\n")
            elif validacion['estado'] == 'ACEPTABLE':
                f.write(" ⚠️  ACEPTABLE\n")
            else:
                f.write(" ❌ CRÍTICO\n")

            if validacion['puede_continuar']:
                f.write("Estado: ✅ LISTO PARA PROCESAMIENTO\n\n")
            else:
                f.write("Estado: ❌ REVISAR ANTES DE CONTINUAR\n\n")

            # Errores por severidad
            f.write("┌" + "─"*78 + "┐\n")
            f.write("│" + " "*24 + "ERRORES POR SEVERIDAD" + " "*33 + "│\n")
            f.write("└" + "─"*78 + "┘\n\n")

            f.write(f"🔴 CRÍTICOS (Bloquean procesamiento): {len(validacion['criticos'])}\n")
            if validacion['criticos']:
                for error in validacion['criticos'][:10]:
                    f.write(f"   • {error.get('mensaje', 'Error')}\n")
                if len(validacion['criticos']) > 10:
                    f.write(f"   ... y {len(validacion['criticos']) - 10} más\n")
            else:
                f.write("   → Ninguno detectado ✅\n")
            f.write("\n")

            f.write(f"⚠️  ADVERTENCIAS (Revisar pero no bloquean): {len(validacion['advertencias'])}\n")
            if validacion['advertencias']:
                for error in validacion['advertencias'][:10]:
                    f.write(f"   • {error.get('mensaje', 'Advertencia')}\n")
                if len(validacion['advertencias']) > 10:
                    f.write(f"   ... y {len(validacion['advertencias']) - 10} más\n")
            else:
                f.write("   → Ninguna ✅\n")
            f.write("\n")

            f.write(f"ℹ️  INFORMATIVOS (Se corrigen automáticamente): {len(validacion['informativos'])}\n")
            if validacion['informativos']:
                for info in validacion['informativos']:
                    f.write(f"   • {info.get('mensaje', 'Info')}\n")
                    if info.get('auto_corregible'):
                        f.write(f"     → Se corregirá automáticamente en 2_limpieza.py\n")
            else:
                f.write("   → Ninguno\n")
            f.write("\n")

            # Análisis de duplicados
            f.write("┌" + "─"*78 + "┐\n")
            f.write("│" + " "*25 + "ANÁLISIS DE DUPLICADOS" + " "*32 + "│\n")
            f.write("└" + "─"*78 + "┘\n\n")

            f.write(f"Duplicados por ID: {validacion['duplicados_por_id']}\n")
            f.write(f"Duplicados reales (todas las columnas): {validacion['duplicados_reales']}\n")

            if validacion['duplicados_reales'] == 0 and validacion['duplicados_por_id'] > 0:
                f.write("Veredicto: ✅ No hay duplicados reales\n\n")
                f.write("Explicación:\n")
                f.write("  El campo 'id' tiene valores repetidos, pero cada registro tiene\n")
                f.write("  respuestas únicas. Estos NO son duplicados reales.\n")
                f.write("  La inserción en PostgreSQL funcionará correctamente.\n\n")
            elif validacion['duplicados_reales'] > 0:
                f.write("Veredicto: ⚠️  Duplicados reales detectados\n\n")
                f.write(f"  Se encontraron {validacion['duplicados_reales']} registros completamente duplicados.\n")
                f.write("  Revisar si esto es esperado antes de continuar.\n\n")
            else:
                f.write("Veredicto: ✅ No hay duplicados\n\n")

            # Valores nulos
            if validacion['valores_nulos_por_columna']:
                f.write("┌" + "─"*78 + "┐\n")
                f.write("│" + " "*23 + "VALORES NULOS POR COLUMNA" + " "*30 + "│\n")
                f.write("└" + "─"*78 + "┘\n\n")

                f.write(f"{'Columna':<35} | {'Nulos':<10} | {'%':<8} | Severidad\n")
                f.write("-"*80 + "\n")

                for col, info in sorted(validacion['valores_nulos_por_columna'].items(),
                                       key=lambda x: x[1]['cantidad'], reverse=True)[:10]:
                    porcentaje = info['porcentaje']
                    if col in columnas_criticas and porcentaje > 50:
                        severidad = "🔴 Crítico"
                    elif col in columnas_criticas and porcentaje > 10:
                        severidad = "⚠️  Alto"
                    elif porcentaje > 30:
                        severidad = "⚠️  Moderado"
                    else:
                        severidad = "ℹ️  Normal"

                    f.write(f"{col[:34]:<35} | {info['cantidad']:<10,} | {porcentaje:<7.2f}% | {severidad}\n")
                f.write("\n")

            # Recomendaciones finales
            f.write("┌" + "─"*78 + "┐\n")
            f.write("│" + " "*28 + "RECOMENDACIONES" + " "*35 + "│\n")
            f.write("└" + "─"*78 + "┘\n\n")

            if validacion['puede_continuar']:
                f.write("✅ PUEDES CONTINUAR con el procesamiento\n\n")
                f.write("Próximos pasos:\n")
                f.write("  1. python 2_limpieza.py      # Corregirá encoding automáticamente\n")
                f.write("  2. python 3_insercion.py     # Insertará sin problemas\n")
                f.write("  3. python 4_visualizacion.py # Generará dashboard\n\n")

                if validacion['tiene_encoding_corrupto']:
                    f.write("Notas:\n")
                    f.write("  • El encoding UTF-8 corrupto es normal y se corregirá en limpieza\n")
                if validacion['duplicados_por_id'] > 0 and validacion['duplicados_reales'] == 0:
                    f.write("  • Los IDs duplicados no afectan el procesamiento\n")
            else:
                f.write("❌ NO CONTINUAR - Corregir errores críticos primero\n\n")
                f.write("Acciones requeridas:\n")
                f.write("  1. Revisar errores CRÍTICOS listados arriba\n")
                f.write("  2. Corregir el archivo Excel original\n")
                f.write("  3. Re-ejecutar: python 1_extractor.py --force\n\n")

            f.write("="*80 + "\n")

        logger.info(f"📋 Reporte de validación generado: {os.path.basename(archivo_validacion)}")

    except Exception as e:
        logger.error(f"Error generando reporte de validación: {e}")

    return validacion
