#!/usr/bin/env python3
"""
Script de prueba para verificar que las reacciones funcionen correctamente
"""

import os
import sys
import logging
from queue import Queue
from env_manager import init_config, get_config, require_config

init_config(
    "config/config_vars.yaml",
    secret_origin=None, 
    gcp_project_id=None,
    strict=None,
    dotenv_path=None,
    debug=False,
)

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Agregar el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from slack_api.messages import SlackBot

def test_reactions():
    """
    Prueba básica de las reacciones
    """
    print("=" * 60)
    print("PRUEBA DE REACCIONES")
    print("=" * 60)
    
    # Configuración de prueba
    bot_token = get_config("SLACK_BOT_TOKEN")
    app_token = get_config("SLACK_APP_TOKEN")
    
    if not bot_token or not app_token:
        print("❌ Error: Variables de entorno no configuradas")
        print("Asegúrate de tener configuradas:")
        print("   - SLACK_BOT_TOKEN")
        print("   - SLACK_APP_TOKEN")
        return False
    
    print("✅ Tokens configurados correctamente")
    
    # Crear cola de mensajes
    message_queue = Queue()
    
    # Crear instancia del bot con debug habilitado
    bot = SlackBot(
        message_queue=message_queue,
        bot_token=bot_token,
        app_token=app_token,
        debug=True  # Habilitar debug para ver logs detallados
    )
    
    print("✅ Bot inicializado correctamente")
    print("\nAhora puedes:")
    print("1. Enviar un mensaje de texto al bot")
    print("2. Enviar un archivo de audio al bot")
    print("3. Verificar que aparezca el ✅ en el mensaje")
    print("\nPresiona Ctrl+C para salir")
    
    try:
        # Iniciar el bot
        bot.start()
        print("✅ Bot iniciado - escuchando mensajes...")
        
        # Mantener el script corriendo
        import time
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Bot detenido por el usuario")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_reactions()
    
    if success:
        print("\n🎉 Prueba completada exitosamente!")
    else:
        print("\n💥 Prueba falló!")
        sys.exit(1) 