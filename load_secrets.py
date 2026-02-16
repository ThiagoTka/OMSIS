"""
Script para carregar secrets do Google Secret Manager como variáveis de ambiente
Necessário porque Cloud Run não expõe secrets diretamente como env vars
"""

import os
import sys


def load_secret(secret_id):
    """Carrega um secret do Google Secret Manager"""
    try:
        from google.cloud import secretmanager
        
        client = secretmanager.SecretManagerServiceClient()
        project_id = os.environ.get("GCP_PROJECT", "imsis-486003")
        
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        secret_string = response.payload.data.decode("UTF-8")
        
        if secret_string:
            print(f"[OK] Secret '{secret_id}' carregado com sucesso")
            return secret_string
        else:
            print(f"[WARN] Secret '{secret_id}' está vazio")
            return None
            
    except Exception as e:
        print(f"[WARN] Erro ao carregar secret {secret_id}: {type(e).__name__}: {e}")
        return None


def load_secrets():
    """Carrega todos os secrets necessários"""
    
    # Se já está em desenvolvimento local com .env, carrega dele
    if os.path.exists(".env"):
        print("[INFO] Arquivo .env encontrado, carregando variaveis...")
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip()
        print("[OK] Variaveis carregadas do .env")
        return
    
    # Carregar secrets do GCP
    print("[INFO] Carregando secrets do Google Secret Manager...")
    
    secrets_to_load = {
        "DB_PASS": "db-pass",
        "SECRET_KEY": "secret-key",
        "SMTP_HOST": "smtp-host",
        "SMTP_PORT": "smtp-port",
        "SMTP_USER": "smtp-user",
        "SMTP_PASS": "smtp-pass",
        "SMTP_FROM": "smtp-from",
    }
    
    loaded_count = 0
    for env_var, secret_id in secrets_to_load.items():
        if os.environ.get(env_var):
            loaded_count += 1
            continue
        secret_value = load_secret(secret_id)
        if secret_value:
            os.environ[env_var] = secret_value
            loaded_count += 1
        else:
            print(f"✗ Erro ao carregar {env_var}")
    
    if loaded_count == len(secrets_to_load):
        print(f"[OK] Todos os {loaded_count} secrets carregados com sucesso")
    else:
        print(f"[WARN] {loaded_count}/{len(secrets_to_load)} secrets carregados")


if __name__ == "__main__":
    load_secrets()
