#!/usr/bin/env python3
import subprocess
import sys
import re

VM_NAME = "langgraph"
ZONE = "us-central1-c"
TIMER = "product-engine.timer"
SERVICE = "product-engine.service"

def run_gcloud_ssh(command):
    full_cmd = [
        "gcloud", "compute", "ssh", VM_NAME, f"--zone={ZONE}",
        f"--command={command}"
    ]
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando: {' '.join(full_cmd)}")
        print(e.stderr)
        sys.exit(1)

def print_section(title):
    print("\n" + "="*60)
    print(f"{title}")
    print("="*60)

def main():
    print_section("Estado del timer (systemd)")
    timer_status = run_gcloud_ssh(f"sudo systemctl status {TIMER}")
    print(timer_status)

    print_section("Próxima y última ejecución del timer")
    timers = run_gcloud_ssh(f"sudo systemctl list-timers {TIMER} --no-pager")
    print(timers)

    print_section("Últimos 50 logs del servicio (última ejecución)")
    logs = run_gcloud_ssh(f"sudo journalctl -u {SERVICE} -n 50 --no-pager")
    print(logs)

    # Resumen rápido de éxito/fracaso
    print_section("Resumen de la última ejecución")
    # Busca líneas de éxito o error en los logs
    success = re.search(r"execution completed|completed successfully|success=True", logs, re.IGNORECASE)
    error = re.search(r"error|fail|exception|traceback", logs, re.IGNORECASE)
    if success and not error:
        print("✅ Última ejecución exitosa.")
    elif error:
        print("❌ Hubo errores en la última ejecución. Revisa los logs arriba.")
    else:
        print("⚠️  No se pudo determinar el estado de la última ejecución. Revisa los logs arriba.")

if __name__ == "__main__":
    main() 