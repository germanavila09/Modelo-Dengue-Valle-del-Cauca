def construir_escenarios(priorizacion):
    """Placeholder para modelos de demanda, rutas o escenarios turisticos."""
    escenarios = priorizacion.copy()
    if "indice_oportunidad_turistica" in escenarios.columns:
        escenarios["escenario_prioritario"] = escenarios["indice_oportunidad_turistica"].apply(
            lambda valor: "alto" if valor >= 0.66 else "medio" if valor >= 0.33 else "bajo"
        )
    return escenarios
