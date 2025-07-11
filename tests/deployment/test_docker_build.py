#!/usr/bin/env python3
"""
Test para verificar que las imágenes Docker se construyen correctamente
"""
import os
import subprocess
import sys

def test_dockerfile_exists():
    """Verificar que los Dockerfiles existen."""
    print("🔍 Verificando que los Dockerfiles existen...")
    
    dockerfiles = [
        "deployment/Dockerfile",
        "deployment/Dockerfile.test"
    ]
    
    for dockerfile in dockerfiles:
        if not os.path.exists(dockerfile):
            print(f"❌ Dockerfile no encontrado: {dockerfile}")
            return False
        else:
            print(f"✅ Dockerfile encontrado: {dockerfile}")
    
    return True

def test_docker_compose_files_exist():
    """Verificar que los archivos docker-compose existen."""
    print("\n🔍 Verificando que los archivos docker-compose existen...")
    
    compose_files = [
        "deployment/docker-compose.prod.yml",
        "deployment/docker-compose.local.yml", 
        "deployment/docker-compose.test.yml"
    ]
    
    for compose_file in compose_files:
        if not os.path.exists(compose_file):
            print(f"❌ Archivo docker-compose no encontrado: {compose_file}")
            return False
        else:
            print(f"✅ Archivo docker-compose encontrado: {compose_file}")
    
    return True

def test_docker_compose_syntax():
    """Verificar la sintaxis de los archivos docker-compose."""
    print("\n🔍 Verificando sintaxis de docker-compose...")
    
    compose_files = [
        "deployment/docker-compose.prod.yml",
        "deployment/docker-compose.local.yml",
        "deployment/docker-compose.test.yml"
    ]
    
    for compose_file in compose_files:
        try:
            cmd = ["docker-compose", "-f", compose_file, "config"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ Error de sintaxis en {compose_file}: {result.stderr}")
                return False
            else:
                print(f"✅ Sintaxis válida: {compose_file}")
        
        except FileNotFoundError:
            print("⚠️  docker-compose no encontrado. Saltando verificación de sintaxis.")
            break
    
    return True

def test_build_production_image():
    """Intentar construir la imagen de producción."""
    print("\n🐳 Intentando construir imagen de producción...")
    
    try:
        cmd = [
            "docker", "build",
            "-f", "deployment/Dockerfile",
            "--target", "final",
            "-t", "product-engine:test",
            "."
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Error construyendo imagen de producción: {result.stderr}")
            return False
        else:
            print("✅ Imagen de producción construida exitosamente")
            
            # Limpiar imagen de test
            subprocess.run(["docker", "rmi", "product-engine:test"], capture_output=True)
            
        return True
    
    except FileNotFoundError:
        print("⚠️  Docker no encontrado. Saltando construcción de imagen.")
        return True

def test_build_test_image():
    """Intentar construir la imagen de test."""
    print("\n🧪 Intentando construir imagen de test...")
    
    try:
        cmd = [
            "docker", "build",
            "-f", "deployment/Dockerfile.test",
            "--target", "test-runtime",
            "-t", "product-engine:test-runner",
            "."
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Error construyendo imagen de test: {result.stderr}")
            return False
        else:
            print("✅ Imagen de test construida exitosamente")
            
            # Limpiar imagen de test
            subprocess.run(["docker", "rmi", "product-engine:test-runner"], capture_output=True)
            
        return True
    
    except FileNotFoundError:
        print("⚠️  Docker no encontrado. Saltando construcción de imagen.")
        return True

def test_deployment_scripts_exist():
    """Verificar que los scripts de deployment existen."""
    print("\n📜 Verificando que los scripts de deployment existen...")
    
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
            
            # Verificar permisos de ejecución
            if os.access(script, os.X_OK):
                print(f"✅ Script tiene permisos de ejecución: {script}")
            else:
                print(f"⚠️  Script no tiene permisos de ejecución: {script}")
    
    return True

def main():
    """Función principal del test."""
    print("🧪 TESTING DOCKER BUILD CONFIGURATION")
    print("=" * 50)
    
    # Verificar que estamos en el directorio correcto
    if not os.path.exists("deployment"):
        print("❌ Error: Debe ejecutarse desde el directorio raíz del proyecto")
        return 1
    
    # Ejecutar todos los tests
    tests = [
        test_dockerfile_exists,
        test_docker_compose_files_exist,
        test_docker_compose_syntax,
        test_deployment_scripts_exist,
        test_build_production_image,
        test_build_test_image
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
        print("✅ ¡Todos los tests de Docker build pasaron!")
        return 0
    else:
        print("❌ Algunos tests fallaron")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 