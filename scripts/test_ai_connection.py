#!/usr/bin/env python3
"""
Script de diagnóstico para testar a conexão com o OpenRouter.
Executar manualmente: python scripts/test_ai_connection.py

Este script NÃO deve ser executado durante a suíte normal de pytest.
"""

import os
import sys
import time
from pathlib import Path

# Adiciona o diretório raiz ao path para importar o app
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

def load_environment():
    """Carrega variáveis de ambiente do .env."""
    try:
        from dotenv import load_dotenv
        env_path = ROOT_DIR / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[OK] Variáveis de ambiente carregadas de {env_path}")
        else:
            print(f"[AVISO] Arquivo .env não encontrado em {env_path}")
    except ImportError:
        print("[AVISO] python-dotenv não instalado. Usando variáveis de ambiente do sistema.")

def check_ai_enabled():
    """Verifica se AI está habilitado."""
    ai_enabled = os.environ.get("AI_ENABLED", "").lower()
    if ai_enabled in ("true", "1", "yes", "on"):
        print("[OK] AI_ENABLED está habilitado")
        return True
    else:
        print(f"[ERRO] AI_ENABLED não está habilitado (valor: '{ai_enabled}')")
        return False

def check_api_key():
    """Verifica se a API key está configurada (sem expor a chave)."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if api_key:
        # Mostra apenas os primeiros e últimos caracteres
        if len(api_key) > 8:
            masked = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]
        else:
            masked = "****"
        print(f"[OK] OPENROUTER_API_KEY configurada: {masked}")
        return True
    else:
        print("[ERRO] OPENROUTER_API_KEY não está configurada")
        return False

def check_model():
    """Verifica se o modelo está configurado."""
    model = os.environ.get("OPENROUTER_MODEL", "")
    if model:
        print(f"[OK] OPENROUTER_MODEL configurado: {model}")
        return model
    else:
        print("[ERRO] OPENROUTER_MODEL não está configurado")
        return None

def test_connection(model):
    """Testa a conexão com o OpenRouter usando o AIClient."""
    try:
        from app.ai import AIClient, ChatRequest, Message, load_ai_config, UsageTracker
        
        config = load_ai_config()
        tracker = UsageTracker()
        
        print(f"\n[INFO] Testando conexão com modelo: {config.model}")
        print(f"[INFO] Base URL: {config.base_url}")
        print(f"[INFO] Timeout: {config.timeout}s")
        
        client = AIClient(config, tracker)
        
        # Cria um request mínimo
        request = ChatRequest(
            messages=[Message(role="user", content="Responda apenas: OK")],
            temperature=0.0,
            max_tokens=10,
        )
        
        print("[INFO] Enviando request mínimo...")
        start_time = time.time()
        response = client.chat(request, feature="connection_test")
        latency_ms = (time.time() - start_time) * 1000
        
        print(f"[SUCESSO] Resposta recebida em {latency_ms:.0f}ms")
        print(f"[INFO] Conteúdo: {response.content[:100]}...")
        print(f"[INFO] Modelo usado: {response.model}")
        print(f"[INFO] Tokens: {response.usage.total_tokens}")
        
        client.close()
        return True, latency_ms
        
    except Exception as e:
        print(f"[ERRO] Falha na conexão: {type(e).__name__}: {e}")
        return False, 0

def main():
    """Função principal."""
    print("=== Teste de Conexão - PlanejaENEM AI Gateway ===\n")
    
    load_environment()
    
    ai_enabled = check_ai_enabled()
    api_key_exists = check_api_key()
    model = check_model()
    
    if not ai_enabled:
        print("\n[AVISO] AI está desabilitado. Habilitando temporariamente para teste...")
        os.environ["AI_ENABLED"] = "true"
    
    if not api_key_exists:
        print("\n[ERRO] Não é possível testar sem API key.")
        sys.exit(1)
    
    if not model:
        print("\n[ERRO] Não é possível testar sem modelo configurado.")
        sys.exit(1)
    
    success, latency = test_connection(model)
    
    print("\n=== Resumo ===")
    print(f"AI Habilitado: {'Sim' if ai_enabled else 'Não (ativado para teste)'}")
    print(f"API Key Configurada: {'Sim' if api_key_exists else 'Não'}")
    print(f"Modelo: {model}")
    print(f"Conexão: {'Sucesso' if success else 'Falha'}")
    if success:
        print(f"Latência: {latency:.0f}ms")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()