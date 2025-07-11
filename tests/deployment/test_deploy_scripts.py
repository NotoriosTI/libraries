#!/usr/bin/env python3
"""
Test para verificar los scripts de deployment
"""
import os
import subprocess
import sys

def test_deploy_scripts_exist():
    """Verificar que los scripts de deployment existen."""
    print("🔍 Verificando existencia de scripts de deployment...")
    
    scripts = [
        "deployment/scripts/deploy.sh",
        "deployment/scripts/test_deploy.sh"
    ]
    
    for script in scripts:
        if not os.path.exists(script):
            print(f"❌ Script no encontrado: {script}")
            return False
        else:
            print(f"✅ Script encontrado: {script}")
    
    return True

def test_scripts_executable():
    """Verificar que los scripts tienen permisos de ejecución."""
    print("\n🔍 Verificando permisos de ejecución...")
    
    scripts = [
        "deployment/scripts/deploy.sh",
        "deployment/scripts/test_deploy.sh"
    ]
    
    for script in scripts:
        if not os.path.exists(script):
            print(f"❌ Script no encontrado: {script}")
            return False
        
        if os.access(script, os.X_OK):
            print(f"✅ Script ejecutable: {script}")
        else:
            print(f"❌ Script no ejecutable: {script}")
            return False
    
    return True

def test_script_syntax():
    """Verificar sintaxis básica de los scripts bash."""
    print("\n🔍 Verificando sintaxis de scripts...")
    
    scripts = [
        "deployment/scripts/deploy.sh",
        "deployment/scripts/test_deploy.sh"
    ]
    
    for script in scripts:
        if not os.path.exists(script):
            print(f"❌ Script no encontrado: {script}")
            return False
        
        try:
            # Verificar sintaxis con bash -n
            result = subprocess.run(
                ["bash", "-n", script],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Error de sintaxis en {script}: {result.stderr}")
                return False
            else:
                print(f"✅ Sintaxis válida: {script}")
        
        except Exception as e:
            print(f"❌ Error verificando sintaxis de {script}: {e}")
            return False
    
    return True

def test_script_help_function():
    """Verificar que los scripts tienen función de ayuda."""
    print("\n🔍 Verificando funciones de ayuda...")
    
    scripts = [
        "deployment/scripts/deploy.sh",
        "deployment/scripts/test_deploy.sh"
    ]
    
    for script in scripts:
        if not os.path.exists(script):
            print(f"❌ Script no encontrado: {script}")
            return False
        
        try:
            with open(script, 'r') as f:
                content = f.read()
            
            # Verificar que tiene función de ayuda
            if "show_usage" in content or "help" in content:
                print(f"✅ Función de ayuda encontrada en {script}")
            else:
                print(f"⚠️  No se encontró función de ayuda en {script}")
        
        except Exception as e:
            print(f"❌ Error leyendo {script}: {e}")
            return False
    
    return True

def test_script_error_handling():
    """Verificar manejo de errores en scripts."""
    print("\n🔍 Verificando manejo de errores...")
    
    scripts = [
        "deployment/scripts/deploy.sh",
        "deployment/scripts/test_deploy.sh"
    ]
    
    for script in scripts:
        if not os.path.exists(script):
            print(f"❌ Script no encontrado: {script}")
            return False
        
        try:
            with open(script, 'r') as f:
                content = f.read()
            
            # Verificar set -e (exit on error)
            if "set -e" in content:
                print(f"✅ 'set -e' encontrado en {script}")
            else:
                print(f"⚠️  'set -e' no encontrado en {script}")
            
            # Verificar funciones de cleanup
            if "cleanup" in content:
                print(f"✅ Función de cleanup encontrada en {script}")
            else:
                print(f"⚠️  Función de cleanup no encontrada en {script}")
        
        except Exception as e:
            print(f"❌ Error verificando manejo de errores en {script}: {e}")
            return False
    
    return True

def test_required_commands_check():
    """Verificar que los scripts verifican comandos requeridos."""
    print("\n🔍 Verificando verificación de comandos requeridos...")
    
    scripts = [
        "deployment/scripts/deploy.sh",
        "deployment/scripts/test_deploy.sh"
    ]
    
    required_commands = ["docker", "gcloud"]
    
    for script in scripts:
        if not os.path.exists(script):
            print(f"❌ Script no encontrado: {script}")
            return False
        
        try:
            with open(script, 'r') as f:
                content = f.read()
            
            for command in required_commands:
                if f"command -v {command}" in content:
                    print(f"✅ Verificación de {command} encontrada en {script}")
                else:
                    print(f"⚠️  Verificación de {command} no encontrada en {script}")
        
        except Exception as e:
            print(f"❌ Error verificando comandos requeridos en {script}: {e}")
            return False
    
    return True

def test_project_configuration():
    """Verificar configuración del proyecto en scripts."""
    print("\n🔍 Verificando configuración del proyecto...")
    
    scripts = [
        "deployment/scripts/deploy.sh",
        "deployment/scripts/test_deploy.sh"
    ]
    
    for script in scripts:
        if not os.path.exists(script):
            print(f"❌ Script no encontrado: {script}")
            return False
        
        try:
            with open(script, 'r') as f:
                content = f.read()
            
            # Verificar PROJECT_ID
            if "PROJECT_ID" in content:
                print(f"✅ PROJECT_ID configurado en {script}")
            else:
                print(f"❌ PROJECT_ID no configurado en {script}")
                return False
            
            # Verificar REGION configuración
            if "REGION" in content:
                print(f"✅ REGION configurado en {script}")
            else:
                print(f"❌ REGION no configurado en {script}")
                return False
        
        except Exception as e:
            print(f"❌ Error verificando configuración en {script}: {e}")
            return False
    
    return True

def test_test_deploy_script_specific():
    """Verificar funcionalidades específicas del script de test."""
    print("\n🔍 Verificando funcionalidades específicas del script de test...")
    
    script = "deployment/scripts/test_deploy.sh"
    
    if not os.path.exists(script):
        print(f"❌ Script no encontrado: {script}")
        return False
    
    try:
        with open(script, 'r') as f:
            content = f.read()
        
        # Verificar tipos de test
        test_types = ["setup", "complete", "integration", "search", "pytest", "all"]
        
        for test_type in test_types:
            if f'"{test_type}"' in content:
                print(f"✅ Tipo de test {test_type} soportado")
            else:
                print(f"❌ Tipo de test {test_type} no soportado")
                return False
        
        # Verificar configuración de test
        if "USE_TEST_ODOO=true" in content:
            print("✅ Configuración de test Odoo encontrada")
        else:
            print("❌ Configuración de test Odoo no encontrada")
            return False
        
        return True
    
    except Exception as e:
        print(f"❌ Error verificando script de test: {e}")
        return False

def main():
    """Función principal del test."""
    print("🧪 TESTING DEPLOYMENT SCRIPTS")
    print("=" * 50)
    
    # Verificar que estamos en el directorio correcto
    if not os.path.exists("deployment"):
        print("❌ Error: Debe ejecutarse desde el directorio raíz del proyecto")
        return 1
    
    # Ejecutar todos los tests
    tests = [
        test_deploy_scripts_exist,
        test_scripts_executable,
        test_script_syntax,
        test_script_help_function,
        test_script_error_handling,
        test_required_commands_check,
        test_project_configuration,
        test_test_deploy_script_specific
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Error en test {test.__name__}: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 RESUMEN: {passed} tests pasados, {failed} tests fallados")
    
    if failed == 0:
        print("✅ ¡Todos los tests de scripts pasaron!")
        return 0
    else:
        print("❌ Algunos tests fallaron")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 