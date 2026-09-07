import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv()

from core.db import init_db_pool, close_db_pool, get_db_pool
from modules.orcamento.preprocessor import normalizar_termo_busca
from core.ai_client import openai_client
from pinecone import Pinecone
from core.config import settings

BATCH_SIZE = 100

async def gerar_embeddings_lote(textos: list[str]) -> list[list[float]]:
    try:
        response = await openai_client.embeddings.create(
            input=textos,
            model="text-embedding-3-small"
        )
        # Garantir a ordem dos embeddings
        response_data_sorted = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in response_data_sorted]
    except Exception as e:
        print(f"Erro ao gerar embeddings no lote: {e}")
        return []

async def reindexar_tabela(nome_tabela: str, namespace: str, pinecone_index):
    print(f"\n--- Iniciando re-indexação da tabela {nome_tabela} para o namespace '{namespace}' ---")
    pool = get_db_pool()
    async with pool.acquire() as conn:
        registros = await conn.fetch(f"SELECT codigo, descricao, preco, unidade FROM {nome_tabela}")
    
    total = len(registros)
    print(f"Total de registros a processar: {total}")
    
    for i in range(0, total, BATCH_SIZE):
        lote = registros[i:i+BATCH_SIZE]
        
        ids = []
        textos_limpos = []
        metadatas = []
        
        for reg in lote:
            codigo = str(reg["codigo"]).strip()
            # Ignora lixo do CSV (ex: cabeçalhos que entraram como linha)
            if not codigo or not codigo.isascii() or "\n" in codigo or "digo" in codigo:
                continue
                
            descricao = reg["descricao"]
            preco = float(reg["preco"]) if reg["preco"] is not None else 0.0
            unidade = reg["unidade"]
            
            termo_norm = normalizar_termo_busca(descricao)
            termo_limpo = termo_norm.termo_limpo
            
            ids.append(codigo)
            textos_limpos.append(termo_limpo)
            metadatas.append({
                "codigo": codigo,
                "descricao": descricao,
                "preco": preco,
                "unidade": unidade
            })
            
        if not ids:
            continue
            
        print(f"Processando lote {i} a {i+len(lote)}...")
        
        # Gera embeddings usando a descrição BRUTA oficial (e não a limpa)
        # Isso garante que o Pinecone conheça o item em toda a sua riqueza de detalhes.
        textos_brutos = [reg["descricao"] for reg in lote]
        embeddings = await gerar_embeddings_lote(textos_brutos)
        
        if not embeddings or len(embeddings) != len(ids):
            print(f"Falha na geração de embeddings para o lote {i}. Pulando...")
            continue
            
        # Prepara formato Pinecone
        pinecone_vectors = []
        for idx in range(len(ids)):
            pinecone_vectors.append({
                "id": ids[idx],
                "values": embeddings[idx],
                "metadata": metadatas[idx]
            })
            
        # Upsert
        # O Pinecone Python Client V3 usa operação sincrona para upsert por default,
        # rodamos em thread para nao bloquear o event loop.
        await asyncio.to_thread(pinecone_index.upsert, vectors=pinecone_vectors, namespace=namespace)
        print(f"Lote {i} a {i+len(lote)} concluído com sucesso!")
        
        # Rate limit protection
        await asyncio.sleep(0.5)

async def main():
    print("Conectando ao PostgreSQL...")
    await init_db_pool()
    
    print("Conectando ao Pinecone...")
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    idx = pc.Index(settings.PINECONE_INDEX_NAME)
    
    await reindexar_tabela("sinapi_composicoes", "composicoes_sinapi", idx)
    await reindexar_tabela("sinapi_insumos", "insumos_sinapi", idx)
    
    await close_db_pool()
    print("\nRe-indexação concluída com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
