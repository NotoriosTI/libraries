#!/usr/bin/env python3
"""
Test para verificar las configuraciones de entorno para deployment
"""
import os
import yaml
import sys

def test_env_file_template():
    """Verificar que existe un template de archivo .env."""
    print("🔍 Verificando template de archivo .env...")
    
    # Verificar si existe .env.example o similar
    env_templates = [".env.example", ".env.template", ".env.sample"]
    
    for template in env_templates:
        if os.path.exists(template):
            print(f"✅ Template de .env encontrado: {template}")
            return True
    
    print("⚠️  No se encontró template de .env (recomendado para deployment)")
    return True  # No es crítico

def test_docker_compose_environment_variables():
    """Verificar variables de entorno en docker-compose files."""
    print("\n🔍 Verificando variables de entorno en docker-compose...")
    
    compose_files = [
        "deployment/docker-compose.prod.yml",
        "deployment/docker-compose.test.yml"
    ]
    
    required_vars = [
        "ENVIRONMENT",
        "GCP_PROJECT_ID",
        "USE_TEST_ODOO"
    ]
    
    for compose_file in compose_files:
        if not os.path.exists(compose_file):
            print(f"❌ Archivo no encontrado: {compose_file}")
            return False
        
        try:
            with open(compose_file, 'r') as f:
                content = f.read()
                
            # Verificar que las variables requeridas estén mencionadas
            for var in required_vars:
                if var not in content:
                    print(f"❌ Variable {var} no encontrada en {compose_file}")
                    return False
                else:
                    print(f"✅ Variable {var} encontrada en {compose_file}")
        
        except Exception as e:
            print(f"❌ Error leyendo {compose_file}: {e}")
            return False
    
    return True

def test_production_vs_test_config():
    """Verificar diferencias entre configuración de producción y test."""
    print("\n🔍 Verificando configuraciones de producción vs test...")
    
    # Verificar que en test se use TEST_ODOO=true
    test_compose = "deployment/docker-compose.test.yml"
    prod_compose = "deployment/docker-compose.prod.yml"
    
    if not os.path.exists(test_compose) or not os.path.exists(prod_compose):
        print("❌ Archivos docker-compose no encontrados")
        return False
    
    try:
        # Leer archivo de test
        with open(test_compose, 'r') as f:
            test_content = f.read()
        
        # Leer archivo de producción
        with open(prod_compose, 'r') as f:
            prod_content = f.read()
        
        # Verificar que test usa TEST_ODOO=true
        if "USE_TEST_ODOO" in test_content:
            print("✅ USE_TEST_ODOO configurado en test")
        else:
            print("❌ USE_TEST_ODOO no configurado en test")
            return False
        
        # Verificar que producción usa variables PRODUCT_DB_*
        if "PRODUCT_DB_HOST" in prod_content:
            print("✅ Variables PRODUCT_DB_* configuradas en producción")
        else:
            print("❌ Variables PRODUCT_DB_* no configuradas en producción")
            return False
        
        return True
    
    except Exception as e:
        print(f"❌ Error comparando configuraciones: {e}")
        return False

def test_secret_manager_integration():
    """Verificar integración con Secret Manager."""
    print("\n🔍 Verificando integración con Secret Manager...")
    
    # Verificar que los scripts mencionan Secret Manager
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
            
            # Verificar menciones de Secret Manager
            if "SECRET" in content or "secret" in content:
                print(f"✅ Integración con Secret Manager en {script}")
            else:
                print(f"⚠️  No hay mención de Secret Manager en {script}")
        
        except Exception as e:
            print(f"❌ Error leyendo {script}: {e}")
            return False
    
    return True

def test_database_configuration():
    """Verificar configuración de base de datos."""
    print("\n🔍 Verificando configuración de base de datos...")
    
    # Verificar que se usan variables PRODUCT_DB_*
    compose_file = "deployment/docker-compose.prod.yml"
    
    if not os.path.exists(compose_file):
        print(f"❌ Archivo no encontrado: {compose_file}")
        return False
    
    try:
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Verificar variables de base de datos específicas para producto
        db_vars = [
            "PRODUCT_DB_HOST",
            "PRODUCT_DB_PORT"
        ]
        
        for var in db_vars:
            if var in content:
                print(f"✅ Variable {var} configurada")
            else:
                print(f"❌ Variable {var} no configurada")
                return False
        
        return True
    
    except Exception as e:
        print(f"❌ Error verificando configuración de DB: {e}")
        return False

def test_cloud_sql_proxy_config():
    """Verificar configuración de Cloud SQL Proxy."""
    print("\n🔍 Verificando configuración de Cloud SQL Proxy...")
    
    compose_files = [
        "deployment/docker-compose.prod.yml",
        "deployment/docker-compose.test.yml"
    ]
    
    for compose_file in compose_files:
        if not os.path.exists(compose_file):
            print(f"❌ Archivo no encontrado: {compose_file}")
            return False
        
        try:
            with open(compose_file, 'r') as f:
                content = f.read()
            
            # Verificar que se configure Cloud SQL Proxy
            if "cloud-sql-proxy" in content:
                print(f"✅ Cloud SQL Proxy configurado en {compose_file}")
            else:
                print(f"❌ Cloud SQL Proxy no configurado en {compose_file}")
                return False
        
        except Exception as e:
            print(f"❌ Error verificando Cloud SQL Proxy: {e}")
            return False
    
    return True

def main():
    """Función principal del test."""
    print("🧪 TESTING ENVIRONMENT CONFIGURATION")
    print("=" * 50)
    
    # Verificar que estamos en el directorio correcto
    if not os.path.exists("deployment"):
        print("❌ Error: Debe ejecutarse desde el directorio raíz del proyecto")
        return 1
    
    # Ejecutar todos los tests
    tests = [
        test_env_file_template,
        test_docker_compose_environment_variables,
        test_production_vs_test_config,
        test_secret_manager_integration,
        test_database_configuration,
        test_cloud_sql_proxy_config
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
        print("✅ ¡Todos los tests de configuración pasaron!")
        return 0
    else:
        print("❌ Algunos tests fallaron")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 