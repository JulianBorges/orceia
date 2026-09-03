# backend/core/vocabulario_obra.py
"""
Dicionário de sinônimos de canteiro de obras para a OrceIA V3.

Traduz jargões populares para a terminologia técnica formal do SINAPI,
melhorando a qualidade da busca vetorial no Pinecone.

Regras de curadoria:
  - Apenas entradas que TRADUZEM (chave != valor após normalização).
  - Entradas que mapeiam um termo para si mesmo são inúteis e não pertencem aqui.
  - Para termos com acento, incluir também a versão sem acento como alias.
  - A aplicação é feita em preprocessor.py ANTES do Regex dimensional.
"""

SINONIMOS_CANTEIRO = {
    # --- Equipamentos de Terraplenagem e Carga ---
    "bobcat": "minicarregadeira",
    "retro": "retroescavadeira",
    "pc": "escavadeira hidraulica",
    "escavadeira pc": "escavadeira hidraulica",

    # --- Guindastes e Içamento ---
    "munck": "guindauto",
    "muck": "guindauto",
    "caminhao munck": "caminhao carroceria com guindauto",
    "caminhão munck": "caminhao carroceria com guindauto",

    # --- Compactação e Vibração ---
    "sapinho": "compactador de solos",
    "placa vibratoria": "placa compactadora",
    "wacker": "compactador de solos",
    "vibrador": "vibrador de imersao",
    "mangote": "vibrador de imersao",

    # --- Granulometria / Britagem ---
    "brita zero": "pedrisco",
    "po de pedra": "pedrisco",
    "pó de pedra": "pedrisco",

    # --- Corte, Esmerilhamento e Perfuração ---
    "martelete": "martelo rompedor",
    "makita": "serra marmore",
    "lixadeira": "esmerilhadeira",
    "policorte": "serra de corte",

    # --- Transporte Manual ---
    "jerica": "carrinho de mao",
    "girica": "carrinho de mao",

    # --- Compressores ---
    "compressor": "compressor de ar",

    # --- Andaimes e Acesso Vertical ---
    "balancim": "andaime suspenso",
    "jaú": "andaime suspenso",   # com acento
    "jau": "andaime suspenso",   # sem acento (alias — previne miss de acentuação)
    "cadeirinha": "cadeira suspensa",

    # --- EPI (Equipamentos de Proteção Individual) ---
    "cinto": "cinto de seguranca",
    "capacete": "capacete de seguranca",
    "botina": "botina de seguranca",
    "luva": "luva de seguranca",
    "oculos": "oculos de seguranca",
    "protetor auricular": "protetor auditivo",
    "abafador": "protetor auditivo",
    "mascara": "respirador",
    "capa de chuva": "vestimenta de seguranca",
    "uniforme": "vestimenta de trabalho",

    # --- Formas e Madeiramentos ---
    "madeirite": "chapa compensado",
    "compensado": "chapa compensado",

    # --- Materiais Metálicos / Armadura ---
    "ferro": "aco",
    "vergalhao": "aco",

    # --- Tubulações e Conexões Hidráulicas ---
    "cano": "tubo",
    "conexoes": "conexao",
    "caixa d'agua": "reservatorio",

    # --- Instalações Elétricas ---
    "fio": "cabo",
    "conduite": "eletroduto",
    "conduíte": "eletroduto",   # com acento (alias)

    # --- Pintura e Solventes ---
    "thinner": "solvente",
    "aguarras": "solvente",
    "pincel": "trincha",

    # --- Ferramentas de Pedreiro ---
    "colher": "colher de pedreiro",
}

