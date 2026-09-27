"""
Simulador de Estrés Financiero
==============================
Herramienta final del libro "Ingeniería de Deuda" (Nivel 2).

Audita un crédito antes de firmarlo: calcula el CFT real (más allá de la
TNA de vidriera), muestra la tabla de amortización del Sistema Francés,
mide el impacto en las 3 Cajas del Nivel 1, y somete la operación a
3 escenarios de estrés financiero.

Ejecutar con:  streamlit run app.py
Dependencias:  streamlit, pandas, numpy, numpy_financial, plotly
"""

import numpy_financial as npf
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ============================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ============================================================================

st.set_page_config(
    page_title="Simulador de Estrés Financiero",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Paleta consistente con el resto del programa (modo oscuro industrial)
COLOR_VERDE = "#00C853"
COLOR_AMARILLO = "#DFFF00"
COLOR_ROJO = "#FF4136"
COLOR_TEXTO_DIM = "#8A8A8A"

CUSTOM_CSS = f"""
<style>
    .stMetric {{
        background-color: #1E1E1E;
        border: 1px solid #333333;
        border-radius: 10px;
        padding: 14px 16px;
    }}
    div[data-testid="stMetricValue"] {{
        font-size: 1.7rem;
    }}
    .banner-rojo {{
        background-color: #2A0F0D; border: 2px solid {COLOR_ROJO};
        border-radius: 10px; padding: 22px 26px; text-align: center;
        box-shadow: 0 0 22px rgba(255,65,54,0.35);
    }}
    .banner-amarillo {{
        background-color: #241F06; border: 2px solid {COLOR_AMARILLO};
        border-radius: 10px; padding: 22px 26px; text-align: center;
        box-shadow: 0 0 22px rgba(223,255,0,0.25);
    }}
    .banner-verde {{
        background-color: #0E1F16; border: 2px solid {COLOR_VERDE};
        border-radius: 10px; padding: 22px 26px; text-align: center;
        box-shadow: 0 0 22px rgba(0,200,83,0.30);
    }}
    .banner-titulo {{ font-size: 1.9rem; font-weight: 800; margin: 0; }}
    .banner-sub {{ font-size: 1.0rem; opacity: 0.85; margin-top: 6px; }}
    .caja-card {{
        background-color: #1A1A1A; border: 1px solid #333;
        border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;
    }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================================
# MOTOR MATEMÁTICO
# ============================================================================

def calcular_cuota_francesa(monto: float, plazo: int, tna: float) -> float:
    """Cuota pura del Sistema Francés (sin gastos ni seguros).

    Maneja el caso borde de TNA = 0 (financiación sin interés) para
    evitar división por cero.
    """
    if plazo <= 0:
        return 0.0
    i = tna / 12
    if i == 0:
        return monto / plazo
    return monto * (i / (1 - (1 + i) ** (-plazo)))


def generar_tabla_amortizacion(monto: float, plazo: int, tna: float, cuota_pura: float) -> pd.DataFrame:
    """Genera la tabla mes a mes: interés, capital y saldo restante."""
    i = tna / 12
    saldo = monto
    filas = []
    for mes in range(1, plazo + 1):
        interes = saldo * i
        capital = cuota_pura - interes
        # Corrección de redondeo en la última cuota para que el saldo cierre en $0
        if mes == plazo:
            capital = saldo
        saldo = max(saldo - capital, 0.0)
        filas.append({"Mes": mes, "Interes": interes, "Capital": capital, "Saldo": saldo})
    return pd.DataFrame(filas)


def calcular_cft_anual(monto: float, gastos_otorgamiento: float, cuota_total: float, plazo: int):
    """Costo Financiero Total anualizado, vía TIR del flujo de fondos real.

    Devuelve None si la TIR no converge (numpy_financial devuelve NaN),
    para que la interfaz pueda mostrar una advertencia en vez de romperse.
    """
    if plazo <= 0 or cuota_total <= 0:
        return None
    monto_neto = monto - gastos_otorgamiento
    flujo = [monto_neto] + [-cuota_total] * plazo
    try:
        irr_mensual = npf.irr(flujo)
    except Exception:
        return None
    if irr_mensual is None or pd.isna(irr_mensual):
        return None
    return (1 + irr_mensual) ** 12 - 1


def evaluar_escenario_1(ingreso_neto: float, costo_operacion_nuevo: float):
    """Estrés 1 — Shock de ingresos: el sueldo cae un 30%."""
    ingreso_shock = ingreso_neto * 0.70
    margen_shock = ingreso_shock - costo_operacion_nuevo
    ratio = margen_shock / ingreso_shock if ingreso_shock > 0 else -1

    if margen_shock < 0:
        return ("rojo", "🔴 Bomba financiera",
                f"Si mañana ganás un 30% menos (**${ingreso_shock:,.0f}**), esta cuota sola te "
                f"deja en **${margen_shock:,.0f}**. No estás evaluando un crédito: estás evaluando una bomba.")
    elif ratio < 0.10:
        return ("amarillo", "🟡 Raspando",
                f"Sobrevivís con **${margen_shock:,.0f}** de margen, pero es menos del 10% de tu "
                f"ingreso reducido. Un imprevisto más y esto se rompe.")
    else:
        return ("verde", "🟢 Aguanta el golpe",
                f"Con un 30% menos de ingreso, todavía te queda **${margen_shock:,.0f}** de margen. "
                f"La operación resiste un shock de ingresos.")


def evaluar_escenario_2(ingreso_neto: float, costo_real_operacion: float,
                        cuota_total: float, caja_futuro_actual: float):
    """Estrés 2 — Salto inflacionario / UVA: la cuota sube un 40%."""
    cuota_shock = cuota_total * 1.40
    costo_operacion_shock = costo_real_operacion + cuota_shock
    margen_shock = ingreso_neto - costo_operacion_shock

    if margen_shock < 0:
        return ("rojo", "🔴 No te alcanza el sueldo",
                f"Si la cuota se ajusta un 40% (pasa a **${cuota_shock:,.0f}**), tu margen queda en "
                f"**${margen_shock:,.0f}**. Esto no es hipotético: es lo que le pasó a miles de créditos UVA.")
    elif margen_shock < caja_futuro_actual:
        return ("amarillo", "🟡 Te comés el futuro",
                f"Sobrevivís, con **${margen_shock:,.0f}** de margen, pero es menos de lo que hoy "
                f"destinás a tu Caja de Futuro (**${caja_futuro_actual:,.0f}**). El ajuste no es gratis.")
    else:
        return ("verde", "🟢 Tenés colchón",
                f"Aun con la cuota un 40% más cara (**${cuota_shock:,.0f}**), te queda "
                f"**${margen_shock:,.0f}** de margen. Podés absorber el salto.")


def evaluar_escenario_3(cft_anual, rendimiento_anual: float):
    """Estrés 3 — Costo de oportunidad: CFT vs. lo que rendiría tu propio capital."""
    if cft_anual is None:
        return ("amarillo", "🟡 No se pudo calcular el CFT",
                "No pudimos converger en una TIR válida con estos datos. Revisá el monto, "
                "el plazo y la cuota total antes de sacar conclusiones sobre este escenario.")

    diferencia = (cft_anual - rendimiento_anual) * 100  # en puntos porcentuales

    if diferencia > 5:
        return ("rojo", "🔴 Te conviene pagar de contado",
                f"Tu CFT real (**{cft_anual*100:,.1f}%**) le gana por **{diferencia:,.1f} puntos** "
                f"al rendimiento que le sacarías a tu plata (**{rendimiento_anual*100:,.1f}%**). "
                f"Financiar acá te sale más caro que pagar de contado.")
    elif diferencia >= -5:
        return ("amarillo", "🟡 Está empatado",
                f"CFT real de **{cft_anual*100:,.1f}%** contra un rendimiento de "
                f"**{rendimiento_anual*100:,.1f}%**. Ni ganás ni perdés financiando — la decisión "
                f"pasa por liquidez y flexibilidad, no por matemática pura.")
    else:
        return ("verde", "🟢 Financiar te conviene",
                f"Tu CFT real (**{cft_anual*100:,.1f}%**) es más barato que lo que tu capital te "
                f"rendiría invertido (**{rendimiento_anual*100:,.1f}%**). Acá la plata del banco "
                f"trabaja a tu favor.")


def semaforo_general(colores: list[str]):
    """Toma el peor resultado de los 3 escenarios."""
    if "rojo" in colores:
        return ("rojo", "🔴 PELIGRO DE ASFIXIA",
                "Este crédito, tal como está planteado, pone en riesgo tu operación completa. "
                "No es que 'no te conviene': en el peor escenario razonable, no te alcanza.")
    elif "amarillo" in colores:
        return ("amarillo", "🟡 ENTRA CON LO JUSTO",
                "Este crédito pasa, pero sin margen de error. Mirá el detalle de cada escenario "
                "antes de firmar.")
    else:
        return ("verde", "🟢 OPERACIÓN SEGURA",
                "Este crédito sobrevive a un shock de ingresos, a un salto de cuota, y tiene "
                "sentido frente a tu costo de oportunidad. Es una decisión de capital, no un salto de fe.")


# ============================================================================
# BARRA LATERAL — CARGA DE DATOS
# ============================================================================

st.sidebar.title("🏭 Simulador de Estrés Financiero")
st.sidebar.caption("Cargá los datos y auditá el crédito antes de firmarlo.")

with st.sidebar.form("form_datos"):

    st.subheader("A · Datos del préstamo")
    monto = st.number_input(
        "Monto ($)", min_value=0.0, value=1_000_000.0, step=10_000.0,
        help="El número grande que te ofrecieron, sin descontar nada.",
    )
    plazo = st.number_input(
        "Plazo (meses)", min_value=1, value=24, step=1,
        help="Ejemplo: para 5 años, poné 60.",
    )
    tna = st.number_input(
        "TNA — Tasa Nominal Anual (%)", min_value=0.0, value=65.0, step=1.0,
        help="La tasa nominal anual de la vidriera. Ojo: esto NO es lo que realmente vas a pagar.",
    ) / 100
    gastos_mensuales = st.number_input(
        "Seguros / gastos ocultos mensuales ($)", min_value=0.0, value=0.0, step=500.0,
        help="Seguro de vida, mantenimiento de cuenta, gastos administrativos. Si no te lo dijeron, preguntá.",
    )
    gastos_otorgamiento = st.number_input(
        "Gastos de otorgamiento ($)", min_value=0.0, value=0.0, step=1_000.0,
        help="Lo que te cobran una sola vez, al firmar: sellado, gestoría, comisión de apertura.",
    )

    st.subheader("B · Contexto (Nivel 1)")
    ingreso_neto = st.number_input(
        "Ingreso Neto mensual ($)", min_value=0.0, value=800_000.0, step=10_000.0,
        help="Lo que cobrás en mano. El mismo número que usaste en tu Tablero de Control.",
    )
    costo_real_operacion = st.number_input(
        "Costo Real de Operación ($)", min_value=0.0, value=550_000.0, step=10_000.0,
        help="Fijos + variables + fugas, sin este crédito nuevo.",
    )

    st.subheader("C · Costo de oportunidad")
    rendimiento_anual = st.number_input(
        "Rendimiento anual esperado (%)", min_value=0.0, value=45.0, step=1.0,
        help="Si en vez de gastar esta plata la invirtieras, ¿cuánto te rendiría por año? "
             "Si no tenés idea, usá un plazo fijo tradicional como referencia.",
    ) / 100

    submitted = st.form_submit_button("🔍 Auditar mi crédito", use_container_width=True)


# ============================================================================
# VALIDACIONES BÁSICAS
# ============================================================================

if not submitted:
    st.title("🏭 Simulador de Estrés Financiero")
    st.info(
        "👈 Cargá los datos de tu préstamo en la barra lateral y apretá "
        "**'Auditar mi crédito'** para ver el diagnóstico completo."
    )
    st.stop()

errores = []
if monto <= 0:
    errores.append("El monto del préstamo tiene que ser mayor a $0.")
if plazo <= 0:
    errores.append("El plazo tiene que ser de al menos 1 mes.")
if ingreso_neto <= 0:
    errores.append("El Ingreso Neto tiene que ser mayor a $0 para poder evaluar los escenarios de estrés.")

if errores:
    st.error("No pudimos auditar el crédito con estos datos:\n\n" + "\n".join(f"- {e}" for e in errores))
    st.stop()


# ============================================================================
# CÁLCULOS
# ============================================================================

cuota_pura = calcular_cuota_francesa(monto, int(plazo), tna)
cuota_total = cuota_pura + gastos_mensuales
tabla = generar_tabla_amortizacion(monto, int(plazo), tna, cuota_pura)
interes_total = tabla["Interes"].sum()
cft_anual = calcular_cft_anual(monto, gastos_otorgamiento, cuota_total, int(plazo))

# Cajas ANTES del crédito nuevo
margen_actual = ingreso_neto - costo_real_operacion
caja_disfrute_actual = max(margen_actual, 0) * 0.5
caja_futuro_actual = max(margen_actual, 0) * 0.5

# Cajas DESPUÉS del crédito nuevo
costo_operacion_nuevo = costo_real_operacion + cuota_total
margen_nuevo = ingreso_neto - costo_operacion_nuevo
caja_disfrute_nueva = max(margen_nuevo, 0) * 0.5
caja_futuro_nueva = max(margen_nuevo, 0) * 0.5

# Escenarios de estrés
color_1, titulo_1, msg_1 = evaluar_escenario_1(ingreso_neto, costo_operacion_nuevo)
color_2, titulo_2, msg_2 = evaluar_escenario_2(ingreso_neto, costo_real_operacion, cuota_total, caja_futuro_actual)
color_3, titulo_3, msg_3 = evaluar_escenario_3(cft_anual, rendimiento_anual)

color_general, titulo_general, msg_general = semaforo_general([color_1, color_2, color_3])


# ============================================================================
# DASHBOARD — ENCABEZADO Y SEMÁFORO GENERAL
# ============================================================================

st.title("🏭 Simulador de Estrés Financiero")
st.caption("Auditoría completa antes de firmar. Basado en tu Tablero de Control del Nivel 1.")

st.markdown(
    f"""
    <div class="banner-{color_general}">
        <p class="banner-titulo">{titulo_general}</p>
        <p class="banner-sub">{msg_general}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)


# ============================================================================
# MÉTRICAS CLAVE
# ============================================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("TNA informada", f"{tna*100:,.1f}%")

with col2:
    if cft_anual is not None:
        delta_pts = (cft_anual - tna) * 100
        st.metric("CFT real", f"{cft_anual*100:,.1f}%", delta=f"{delta_pts:+.1f} pts vs. TNA",
                   delta_color="inverse")
    else:
        st.metric("CFT real", "No calculable")

with col3:
    st.metric("Cuota total mensual", f"${cuota_total:,.0f}",
               help="Cuota pura del Sistema Francés + seguros y gastos mensuales.")

with col4:
    st.metric("Interés total del crédito", f"${interes_total:,.0f}",
               help="Todo lo que vas a pagar de interés puro a lo largo de todo el préstamo.")

if cft_anual is None:
    st.warning(
        "⚠️ No pudimos calcular una TIR válida con estos datos (esto puede pasar con montos, "
        "plazos o gastos muy chicos o inconsistentes). Los escenarios de estrés 1 y 2 siguen "
        "siendo válidos; el escenario 3 no se puede evaluar sin el CFT."
    )

st.divider()


# ============================================================================
# GRÁFICO DE AMORTIZACIÓN (SISTEMA FRANCÉS)
# ============================================================================

st.subheader("📉 Amortización mes a mes — así se reparte tu cuota")
st.caption(
    "Mirá cómo, al principio, casi toda la cuota es interés puro. Tu deuda real "
    "(el capital) recién empieza a bajar en serio sobre el final."
)

fig_amort = go.Figure()
fig_amort.add_trace(go.Bar(
    x=tabla["Mes"], y=tabla["Interes"], name="Interés",
    marker_color=COLOR_ROJO,
))
fig_amort.add_trace(go.Bar(
    x=tabla["Mes"], y=tabla["Capital"], name="Capital",
    marker_color=COLOR_VERDE,
))
fig_amort.update_layout(
    barmode="stack",
    template="plotly_dark",
    xaxis_title="Mes",
    yaxis_title="$",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(t=40, b=10),
    height=380,
)
st.plotly_chart(fig_amort, use_container_width=True)

pct_interes_cuota1 = (tabla.iloc[0]["Interes"] / cuota_pura * 100) if cuota_pura > 0 else 0
st.caption(
    f"💡 En tu primera cuota, el **{pct_interes_cuota1:,.0f}%** es interés puro. "
    f"Si cancelás este crédito a mitad de camino, vas a descubrir que el capital bajó mucho menos "
    f"de lo que la cantidad de cuotas pagadas te hace sentir."
)

st.divider()


# ============================================================================
# LAS 3 CAJAS — ANTES VS DESPUÉS
# ============================================================================

st.subheader("📦 Impacto en tus 3 Cajas (Nivel 1)")

fig_cajas = go.Figure()
categorias = ["Caja de Disfrute", "Caja de Futuro"]
fig_cajas.add_trace(go.Bar(
    name="Antes de este crédito",
    x=categorias, y=[caja_disfrute_actual, caja_futuro_actual],
    marker_color="#5A6B7A",
))
fig_cajas.add_trace(go.Bar(
    name="Después de este crédito",
    x=categorias, y=[caja_disfrute_nueva, caja_futuro_nueva],
    marker_color=COLOR_AMARILLO,
))
fig_cajas.update_layout(
    barmode="group",
    template="plotly_dark",
    yaxis_title="$ disponibles por mes",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(t=40, b=10),
    height=360,
)
st.plotly_chart(fig_cajas, use_container_width=True)

colA, colB = st.columns(2)
with colA:
    st.metric("Margen operativo ANTES", f"${margen_actual:,.0f}")
with colB:
    reduccion = margen_actual - margen_nuevo
    st.metric("Margen operativo DESPUÉS", f"${margen_nuevo:,.0f}", delta=f"-${reduccion:,.0f}",
               delta_color="inverse")

if margen_nuevo < 0:
    st.error(
        "🔴 Con esta cuota, tu Costo de Operación supera tu ingreso. No te queda margen: "
        "estás financiando un agujero, no una decisión de capital."
    )

st.divider()


# ============================================================================
# LOS 3 ESCENARIOS DE ESTRÉS
# ============================================================================

st.subheader("⚡ Los 3 Escenarios de Estrés")
st.caption("Igual que se prueba un puente con el triple de carga, así se prueba un crédito antes de firmarlo.")

def render_tarjeta(color, titulo, mensaje):
    if color == "rojo":
        st.error(f"**{titulo}**\n\n{mensaje}")
    elif color == "amarillo":
        st.warning(f"**{titulo}**\n\n{mensaje}")
    else:
        st.success(f"**{titulo}**\n\n{mensaje}")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("##### Estrés 1 — Shock de ingresos")
    st.caption("¿Qué pasa si mañana ganás un 30% menos?")
    render_tarjeta(color_1, titulo_1, msg_1)

with c2:
    st.markdown("##### Estrés 2 — Salto inflacionario / UVA")
    st.caption("¿Qué pasa si tu cuota se ajusta un 40% hacia arriba?")
    render_tarjeta(color_2, titulo_2, msg_2)

with c3:
    st.markdown("##### Estrés 3 — Costo de oportunidad")
    st.caption("¿Este crédito es más caro que lo que rendiría tu propia plata?")
    render_tarjeta(color_3, titulo_3, msg_3)

st.divider()
st.caption(
    "Este simulador es una herramienta de apoyo para tomar decisiones, no asesoramiento "
    "financiero, contable ni de inversión profesional. Los resultados dependen enteramente "
    "de la precisión de los datos que cargaste. Para decisiones de deuda de peso, consultá "
    "también a un profesional matriculado."
)
