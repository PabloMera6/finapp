"""
Categorías y subcategorías iniciales del sistema (sección 14 del spec).
Se insertan de forma idempotente en el arranque / seed.
"""

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Vivienda": ["Alquiler", "Hipoteca", "Comunidad", "Suministros", "Otros"],
    "Alimentación": ["Supermercado", "Mercado", "Otros"],
    "Restaurantes": ["Restaurantes", "Bares", "Comida a domicilio"],
    "Transporte": ["Gasolina", "Taxi", "Uber", "Transporte público", "Parking"],
    "Compras": ["Ropa", "Electrónica", "Hogar", "Otros"],
    "Ocio": ["Cine", "Juegos", "Eventos", "Streaming"],
    "Viajes": ["Alojamiento", "Vuelos", "Otros"],
    "Suscripciones": ["Streaming", "Software", "Otros"],
    "Salud": ["Farmacia", "Médico", "Seguro médico", "Otros"],
    "Educación": ["Cursos", "Material", "Otros"],
    "Servicios": ["Telefonía", "Internet", "Otros"],
    "Tecnología": ["Hardware", "Software", "Otros"],
    "Ropa": ["Ropa", "Calzado", "Otros"],
    "Deporte": ["Gimnasio", "Material deportivo", "Otros"],
    "Impuestos": ["IRPF", "IBI", "Otros"],
    "Comisiones": ["Comisiones bancarias", "Comisiones de inversión"],
    "Inversión": ["Compra de activos", "Venta de activos", "Dividendos", "Intereses"],
    "Transferencias": ["Entre cuentas propias", "A terceros"],
    "Bizum": ["Pendiente de categorizar"],
    "Ingresos": ["Nómina", "Otros ingresos"],
    "Otros": ["Sin categorizar"],
}

# Reglas deterministas iniciales: merchant/patrón -> (categoría, subcategoría)
# No se usa IA para esto; es un motor de reglas simple y explicable.
DEFAULT_MERCHANT_RULES: list[tuple[str, str, str]] = [
    ("MERCADONA", "Alimentación", "Supermercado"),
    ("CARREFOUR", "Alimentación", "Supermercado"),
    ("LIDL", "Alimentación", "Supermercado"),
    ("DIA", "Alimentación", "Supermercado"),
    ("UBER EATS", "Restaurantes", "Comida a domicilio"),
    ("GLOVO", "Restaurantes", "Comida a domicilio"),
    ("UBER", "Transporte", "Uber"),
    ("CABIFY", "Transporte", "Taxi"),
    ("REPSOL", "Transporte", "Gasolina"),
    ("CEPSA", "Transporte", "Gasolina"),
    ("NETFLIX", "Suscripciones", "Streaming"),
    ("SPOTIFY", "Suscripciones", "Streaming"),
    ("HBO", "Suscripciones", "Streaming"),
    ("AMAZON PRIME", "Suscripciones", "Streaming"),
    ("GYM", "Deporte", "Gimnasio"),
    ("BASIC FIT", "Deporte", "Gimnasio"),
    ("FARMACIA", "Salud", "Farmacia"),
    ("NOMINA", "Ingresos", "Nómina"),
    ("PAYROLL", "Ingresos", "Nómina"),
]
