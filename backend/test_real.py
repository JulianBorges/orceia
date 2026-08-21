import asyncio
import os
import sys
from dotenv import load_dotenv

# Configura o path para importar os módulos da pasta backend corretamente
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from core.db import init_db_pool, close_db_pool
from core.redis_client import init_redis, close_redis
import core.redis_client as rc
from modules.orcamento.schemas import LinhaOrcamentoUpsert
from modules.orcamento.services import iniciar_processamento_lote_em_background

async def main():
    print("🚀 [PASSO 1] Inicializando conexões com Postgres e Redis...")
    await init_db_pool()
    await init_redis()

    print("\n📥 [PASSO 2] Criando lote de dados de teste (Upload Simulado)...")
    planilha_id = "teste-real-123"
    
    # Criando os 4 itens pedidos pelo usuário.
    # Note que preco_unitario foi colocado como 0 pois não foi fornecido na tabela.
    linhas = [
        LinhaOrcamentoUpsert(id="item-1", id_planilha=planilha_id, descricao='PROJETO "AS BUILT" ARQUITETURA', unidade='m²', quantidade=7765.0, preco_unitario=0.0),
        LinhaOrcamentoUpsert(id="item-2", id_planilha=planilha_id, descricao='PLACA DE OBRA-PINTADA/FIXADA ESTRUTURA DE MADEIRA', unidade='un', quantidade=6.0, preco_unitario=0.0),
        LinhaOrcamentoUpsert(id="item-3", id_planilha=planilha_id, descricao='INSTALACAO PROVISORIA UNIDADE SANITARIA - 5,0M2', unidade='un', quantidade=2.0, preco_unitario=0.0),
        LinhaOrcamentoUpsert(id="item-4", id_planilha=planilha_id, descricao='REGULARIZACAO E COMPACTACAO DE SUBLEITO ATÉ 20 CM DE ESPESSURA', unidade='m²', quantidade=4929.51, preco_unitario=0.0),
    ]

    print("⚙️ [PASSO 3] Executando chamada direta...")
    for linha in linhas:
        try:
            from modules.orcamento.services import processar_linha_inteligente
            res = await processar_linha_inteligente(linha, planilha_id)
            print(f"Sucesso: {res}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Erro na execução direta: {e}")
    
    await close_db_pool()
    await close_redis()
    return

    print("📡 [PASSO 4] Escutando Barramento SSE no Redis (Stream em Tempo Real)...\n")
    stream_key = f"stream:planilha:{planilha_id}"
    last_id = "0-0"
    
    try:
        while True:
            # Trava esperando pacotes do Redis (block=5000)
            streams = await rc.redis_client.xread({stream_key: last_id}, block=5000, count=10)
            if streams:
                for stream_name, messages in streams:
                    for message_id, message_data in messages:
                        last_id = message_id
                        payload_str = message_data.get("payload", "{}")
                        import json
                        payload = json.loads(payload_str)
                        
                        if payload.get("status") == "sucesso":
                            dados = payload.get("dados_ia", {})
                            origem = dados.get('origem', 'DESCONHECIDA')
                            print(f"✅ [SUCESSO - {origem}] Item: {dados.get('id')}")
                            print(f"   ↳ Novo Código SINAPI: {dados.get('codigo_novo')}")
                            print(f"   ↳ Rigor da Análise: {dados.get('rigor')}")
                            print(f"   ↳ Parecer Técnico: {dados.get('parecer')}")
                            print("-" * 60)
                        elif payload.get("status") == "lote_concluido":
                            print(f"🎉 [FIM] Lote concluído! Total processado: {payload.get('total')} itens.")
                            return
                        elif payload.get("status") == "erro":
                            print(f"❌ [ERRO] Falha no item {payload.get('id')}: {payload.get('mensagem')}")
            else:
                # Evitar loop infinito se a task falhar silenciosamente
                if task.done():
                    print("⚠️ Tarefa de background já terminou mas o lote não foi concluído corretamente.")
                    return
    finally:
        await close_db_pool()
        await close_redis()

if __name__ == "__main__":
    asyncio.run(main())
