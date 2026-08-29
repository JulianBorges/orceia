import unicodedata
import re

def normalizar_chave(texto: str) -> str:
    """
    Normaliza texto para uso em cache e banco de dados (RLHF).
    Garante que variações de acentuação e espaços duplos gerem a mesma chave.
    """
    if not texto:
        return ""
    
    # Converte para minúsculas e remove espaços das pontas
    texto = texto.strip().lower()
    
    # Remove acentos e caracteres especiais usando NFD
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    
    # Colapsa múltiplos espaços em um só
    texto = re.sub(r'\s+', ' ', texto)
    
    return texto
