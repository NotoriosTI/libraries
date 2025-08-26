from .orders import ShopifyOrders

shopify_orders = ShopifyOrders()

# Productos que el cliente desea comprar
productos = [
    {'variant_id': '50570543333675', 'quantity': 1},

]

# Nota opcional
nota = "Pedido asistido por agente"  # Opcional, puedes poner None

# Crear el permalink de checkout
checkout_url = shopify_orders.create_checkout_permalink(
    productos, 
    email="snparada@gmail.com",
    phone="3128666666"
)

# El agente puede enviar este enlace al cliente
if checkout_url:
    print(f"¡Todo listo! Complete su compra aquí: {checkout_url}")