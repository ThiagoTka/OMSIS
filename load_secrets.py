"""
Script para carregar secrets do Google Secret Manager como variáveis de ambiente
Necessário porque Cloud Run não expõe secrets diretamente como env vars
"""

import os
import json
from google.cloud import secretmanager


def load_secret(secret_id):
    """Carrega um secret do Google Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        project_id = os.environ.get("GCP_PROJECT", "imsis-486003")
        
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        secret_string = response.payload.data.decode("UTF-8")
        
        return secret_string
    except Exception as e:
        print(f"⚠️  Erro ao carregar secret {secret_id}: {e}")
        return None


def load_secrets():
    """Carrega todos os secrets necessários"""
    
    # Se já está em desenvolvimento local com .env, não carrega do GCP
    if os.path.exists(".env"):
        print("ℹ️  Arquivo .env encontrado, usando variáveis locais")
        return
    
    # Carregar secrets do GCP
    print("ℹ️  Carregando secrets do Google Secret Manager...")
    
    secrets_to_load = {
        "DB_PASS": "db-pass",
        "SECRET_KEY": "secret-key",
    }
    
    for env_var, secret_id in secrets_to_load.items():
        secret_value = load_secret(secret_id)
        if secret_value:
            os.environ[env_var] = secret_value
            print(f"✓ {env_var} carregado do Secret Manager")
        else:
            print(f"✗ Erro ao carregar {env_var}")


if __name__ == "__main__":
    load_secrets()
