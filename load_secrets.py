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
            print(f"✓ Secret '{secret_id}' carregado com sucesso")
            return secret_string
        else:
            print(f"⚠️  Secret '{secret_id}' está vazio")
            return None
            
    except Exception as e:
        print(f"⚠️  Erro ao carregar secret {secret_id}: {type(e).__name__}: {e}")
        return None


def load_secrets():
    """Carrega todos os secrets necessários"""
    
    # Se já está em desenvolvimento local com .env, não carrega do GCP
    if os.path.exists(".env"):
        print("ℹ️  Arquivo .env encontrado, pulando carregamento de secrets do GCP")
        return
    
    # Se as variáveis já existem, não carrega
    if os.environ.get("DB_PASS") and os.environ.get("SECRET_KEY"):
        print("ℹ️  Variáveis de ambiente já configuradas, pulando Secret Manager")
        return
    
    # Carregar secrets do GCP
    print("ℹ️  Carregando secrets do Google Secret Manager...")
    
    secrets_to_load = {
        "DB_PASS": "db-pass",
        "SECRET_KEY": "secret-key",
    }
    
    loaded_count = 0
    for env_var, secret_id in secrets_to_load.items():
        secret_value = load_secret(secret_id)
        if secret_value:
            os.environ[env_var] = secret_value
            loaded_count += 1
        else:
            print(f"✗ Erro ao carregar {env_var}")
    
    if loaded_count == len(secrets_to_load):
        print(f"✅ Todos os {loaded_count} secrets carregados com sucesso")
    else:
        print(f"⚠️  {loaded_count}/{len(secrets_to_load)} secrets carregados")


if __name__ == "__main__":
    load_secrets()
