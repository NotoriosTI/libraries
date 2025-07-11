#!/usr/bin/env python3
"""
Script para verificar los permisos del bot de Slack
"""

import os
import sys
import requests
import json
from config_manager import secrets

def check_bot_permissions():
    """
    Verifica los permisos del bot de Slack
    """
    print("=" * 60)
    print("VERIFICACIÓN DE PERMISOS DEL BOT")
    print("=" * 60)
    
    bot_token = secrets.SLACK_BOT_TOKEN
    
    if not bot_token:
        print("❌ Error: SLACK_BOT_TOKEN no configurado")
        return False
    
    print("✅ Token configurado")
    
    # Verificar información del bot
    headers = {
        'Authorization': f'Bearer {bot_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Obtener información del bot
        response = requests.get('https://slack.com/api/auth.test', headers=headers)
        auth_info = response.json()
        
        if not auth_info.get('ok'):
            print(f"❌ Error al verificar autenticación: {auth_info.get('error')}")
            return False
        
        print("✅ Autenticación exitosa")
        print(f"   - Bot ID: {auth_info.get('bot_id')}")
        print(f"   - User ID: {auth_info.get('user_id')}")
        print(f"   - Team: {auth_info.get('team')}")
        
        # Obtener información del bot
        bot_response = requests.get('https://slack.com/api/bots.info', headers=headers)
        bot_info = bot_response.json()
        
        if bot_info.get('ok'):
            bot_data = bot_info.get('bot', {})
            print(f"   - Bot Name: {bot_data.get('name')}")
            print(f"   - Bot Deleted: {bot_data.get('deleted')}")
            
            # Verificar scopes
            scopes = auth_info.get('scope', '').split(',')
            print(f"\n📋 Scopes del bot:")
            for scope in scopes:
                print(f"   - {scope}")
            
            # Verificar scopes necesarios para reacciones
            required_scopes = [
                'reactions:read',
                'reactions:write'
            ]
            
            missing_scopes = []
            for scope in required_scopes:
                if scope not in scopes:
                    missing_scopes.append(scope)
            
            if missing_scopes:
                print(f"\n❌ Scopes faltantes para reacciones:")
                for scope in missing_scopes:
                    print(f"   - {scope}")
                print("\nPara agregar estos scopes:")
                print("1. Ve a https://api.slack.com/apps")
                print("2. Selecciona tu app")
                print("3. Ve a 'OAuth & Permissions'")
                print("4. Agrega los scopes faltantes")
                print("5. Reinstala la app en tu workspace")
                return False
            else:
                print(f"\n✅ Todos los scopes necesarios están presentes")
        
        # Probar agregar una reacción (en un canal de prueba)
        print(f"\n🧪 Probando agregar reacción...")
        
        # Intentar obtener canales
        channels_response = requests.get('https://slack.com/api/conversations.list', headers=headers)
        channels_info = channels_response.json()
        
        if channels_info.get('ok'):
            channels = channels_info.get('channels', [])
            if channels:
                test_channel = channels[0]['id']
                print(f"   - Canal de prueba: {channels[0]['name']} ({test_channel})")
                
                # Enviar un mensaje de prueba
                test_message = {
                    'channel': test_channel,
                    'text': 'Mensaje de prueba para reacciones'
                }
                
                message_response = requests.post(
                    'https://slack.com/api/chat.postMessage',
                    headers=headers,
                    json=test_message
                )
                
                message_info = message_response.json()
                if message_info.get('ok'):
                    message_ts = message_info['ts']
                    print(f"   - Mensaje enviado con timestamp: {message_ts}")
                    
                    # Intentar agregar reacción
                    reaction_data = {
                        'channel': test_channel,
                        'timestamp': message_ts,
                        'name': 'white_check_mark'
                    }
                    
                    reaction_response = requests.post(
                        'https://slack.com/api/reactions.add',
                        headers=headers,
                        json=reaction_data
                    )
                    
                    reaction_info = reaction_response.json()
                    if reaction_info.get('ok'):
                        print("   ✅ Reacción agregada exitosamente")
                        
                        # Limpiar mensaje de prueba
                        delete_data = {
                            'channel': test_channel,
                            'timestamp': message_ts
                        }
                        
                        delete_response = requests.post(
                            'https://slack.com/api/chat.delete',
                            headers=headers,
                            json=delete_data
                        )
                        
                        if delete_response.json().get('ok'):
                            print("   🧹 Mensaje de prueba eliminado")
                        else:
                            print("   ⚠️ No se pudo eliminar mensaje de prueba")
                        
                        return True
                    else:
                        print(f"   ❌ Error agregando reacción: {reaction_info.get('error')}")
                        return False
                else:
                    print(f"   ❌ Error enviando mensaje: {message_info.get('error')}")
                    return False
            else:
                print("   ❌ No se encontraron canales")
                return False
        else:
            print(f"   ❌ Error obteniendo canales: {channels_info.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error durante la verificación: {e}")
        return False

if __name__ == "__main__":
    success = check_bot_permissions()
    
    if success:
        print("\n🎉 Verificación completada exitosamente!")
        print("El bot debería poder agregar reacciones correctamente.")
    else:
        print("\n💥 Verificación falló!")
        print("Revisa los errores arriba y configura los permisos necesarios.")
        sys.exit(1) 