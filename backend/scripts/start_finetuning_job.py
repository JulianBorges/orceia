import os
import sys
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Ajusta o PYTHONPATH
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
load_dotenv()

from pathlib import Path

async def main():
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    dataset_path = os.path.join(os.path.dirname(__file__), "dataset_orceia_v1.jsonl")
    
    if not os.path.exists(dataset_path):
        print(f"Erro: Arquivo não encontrado em {dataset_path}")
        print("Execute o script 'export_finetuning_dataset.py' primeiro.")
        return
        
    print(f"Fazendo upload do dataset ({dataset_path})...")
    
    try:
        with open(dataset_path, "rb") as file_obj:
            response = await client.files.create(
                file=("dataset_orceia_v1.jsonl", file_obj),
                purpose="fine-tune"
            )
        
        file_id = response.id
        print(f"Upload concluído! File ID: {file_id}")
        
        print("Aguardando o processamento do arquivo (isso pode levar alguns segundos)...")
        await asyncio.sleep(10)
        
        print("Iniciando o Job de Fine-Tuning...")
        job = await client.fine_tuning.jobs.create(
            training_file=file_id,
            model="gpt-4o-mini-2024-07-18",
            suffix="orceia-v1"
        )
        
        print("\n" + "="*50)
        print("🎉 JOB INICIADO COM SUCESSO!")
        print("="*50)
        print(f"Job ID: {job.id}")
        print(f"Status: {job.status}")
        print("\nVocê pode acompanhar o progresso no painel da OpenAI:")
        print("https://platform.openai.com/finetune")
        print("\nQuando o status mudar para 'succeeded', copie o nome do modelo gerado")
        print("e cole-o na variável 'OPENAI_FT_MODEL' dentro do seu arquivo '.env'!")
        
    except Exception as e:
        print(f"Erro ao interagir com a OpenAI: {e}")

if __name__ == "__main__":
    asyncio.run(main())
