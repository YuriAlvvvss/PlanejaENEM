#!/usr/bin/env python3
"""
Benchmark manual para comparar modelos gratuitos do OpenRouter.
Executar manualmente: python scripts/benchmark_ai.py --models "modelo1,modelo2,modelo3"

Este script NÃO deve ser executado automaticamente a cada inicialização.
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Adiciona o diretório raiz ao path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

def load_environment():
    """Carrega variáveis de ambiente do .env."""
    try:
        from dotenv import load_dotenv
        env_path = ROOT_DIR / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass

def get_test_tasks() -> List[Dict[str, Any]]:
    """Retorna tarefas de teste para o benchmark."""
    return [
        {
            "name": "Matemática - Questão simples",
            "prompt": "Gere uma questão de matemática sobre equação do 2º grau com 5 alternativas. Responda em JSON com: statement, alternative_a, alternative_b, alternative_c, alternative_d, alternative_e, correct_answer, explanation, difficulty, topic.",
            "expected_keys": ["statement", "alternative_a", "alternative_b", "alternative_c", "alternative_d", "alternative_e", "correct_answer", "explanation", "difficulty", "topic"],
            "structured": True,
        },
        {
            "name": "Química - Questão simples",
            "prompt": "Gere uma questão de química sobre tabela periódica com 5 alternativas. Responda em JSON com: statement, alternative_a, alternative_b, alternative_c, alternative_d, alternative_e, correct_answer, explanation, difficulty, topic.",
            "expected_keys": ["statement", "alternative_a", "alternative_b", "alternative_c", "alternative_d", "alternative_e", "correct_answer", "explanation", "difficulty", "topic"],
            "structured": True,
        },
        {
            "name": "Explicação de erro",
            "prompt": "Explique por que a equação x² + 4 = 0 não tem solução no conjunto dos números reais. Seja breve.",
            "structured": False,
        },
        {
            "name": "Resposta estruturada simples",
            "prompt": "Responda em JSON: {\"status\": \"ok\", \"message\": \"PlanejaENEM\"}",
            "structured": True,
            "expected_keys": ["status", "message"],
        },
    ]

def run_benchmark_task(client, task: Dict[str, Any]) -> Dict[str, Any]:
    """Executa uma tarefa de benchmark e coleta métricas."""
    from app.ai import ChatRequest, Message
    
    result = {
        "name": task["name"],
        "success": False,
        "latency_ms": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "schema_valid": False,
        "error": None,
        "response_preview": "",
    }
    
    try:
        request = ChatRequest(
            messages=[Message(role="user", content=task["prompt"])],
            temperature=0.0,
            max_tokens=200,
        )
        
        start_time = time.time()
        
        if task.get("structured", False):
            response = client.chat_structured(
                request,
                expected_keys=task.get("expected_keys"),
                feature="benchmark",
            )
            result["schema_valid"] = True
            result["response_preview"] = str(response.data)[:200]
        else:
            response = client.chat(request, feature="benchmark")
            result["response_preview"] = response.content[:200]
        
        latency_ms = (time.time() - start_time) * 1000
        
        result["success"] = True
        result["latency_ms"] = latency_ms
        result["input_tokens"] = response.usage.prompt_tokens
        result["output_tokens"] = response.usage.completion_tokens
        result["total_tokens"] = response.usage.total_tokens
        
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    
    return result

def run_benchmark(models: List[str], tasks_per_model: int = 4):
    """Executa o benchmark para uma lista de modelos."""
    from app.ai import AIClient, AIConfig, UsageTracker
    
    print("=== Benchmark de Modelos - PlanejaENEM AI Gateway ===\n")
    
    load_environment()
    
    # Verifica se AI está habilitado
    ai_enabled = os.environ.get("AI_ENABLED", "").lower()
    if ai_enabled not in ("true", "1", "yes", "on"):
        print("[ERRO] AI não está habilitado. Configure AI_ENABLED=true no .env")
        return
    
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("[ERRO] OPENROUTER_API_KEY não configurada.")
        return
    
    tasks = get_test_tasks()[:tasks_per_model]
    
    all_results = {}
    
    for model in models:
        print(f"\n{'='*60}")
        print(f"Testando modelo: {model}")
        print(f"{'='*60}")
        
        # Configura o modelo específico
        config = AIConfig(
            enabled=True,
            api_key=api_key,
            model=model,
            timeout=30.0,
            max_retries=1,
            max_tokens=200,
        )
        
        tracker = UsageTracker()
        client = AIClient(config, tracker)
        
        model_results = []
        
        for i, task in enumerate(tasks, 1):
            print(f"\n[{i}/{len(tasks)}] {task['name']}...")
            
            result = run_benchmark_task(client, task)
            model_results.append(result)
            
            if result["success"]:
                print(f"  ✓ Sucesso ({result['latency_ms']:.0f}ms, {result['total_tokens']} tokens)")
                if result["schema_valid"]:
                    print(f"  ✓ Schema válido")
            else:
                print(f"  ✗ Erro: {result['error']}")
        
        # Resumo do modelo
        successful = [r for r in model_results if r["success"]]
        total_latency = sum(r["latency_ms"] for r in successful)
        total_tokens = sum(r["total_tokens"] for r in successful)
        
        print(f"\nResumo do modelo {model}:")
        print(f"  Sucesso: {len(successful)}/{len(tasks)}")
        print(f"  Latência total: {total_latency:.0f}ms")
        print(f"  Tokens totais: {total_tokens}")
        
        all_results[model] = {
            "tasks": model_results,
            "success_rate": len(successful) / len(tasks),
            "total_latency_ms": total_latency,
            "total_tokens": total_tokens,
        }
        
        client.close()
    
    # Resumo geral
    print(f"\n{'='*60}")
    print("RESUMO GERAL")
    print(f"{'='*60}")
    
    for model, results in all_results.items():
        print(f"\n{model}:")
        print(f"  Taxa de sucesso: {results['success_rate']*100:.0f}%")
        print(f"  Latência total: {results['total_latency_ms']:.0f}ms")
        print(f"  Tokens totais: {results['total_tokens']}")
    
    return all_results

def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description="Benchmark de modelos do OpenRouter")
    parser.add_argument(
        "--models",
        type=str,
        required=True,
        help="Lista de modelos separados por vírgula (ex: 'openrouter/free,openai/gpt-4o-mini')",
    )
    parser.add_argument(
        "--tasks",
        type=int,
        default=4,
        help="Número de tarefas por modelo (máximo 4)",
    )
    
    args = parser.parse_args()
    
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    
    if not models:
        print("ERRO: Nenhum modelo especificado.")
        sys.exit(1)
    
    tasks_per_model = min(args.tasks, 4)
    
    run_benchmark(models, tasks_per_model)

if __name__ == "__main__":
    main()