import { useEffect, useRef } from 'react';
import { useBudgetStore } from '../store/useBudgetStore';

export function useAutoSave() {
  const isDirty = useBudgetStore((state) => state.isDirty);
  const dirtyRowIds = useBudgetStore((state) => state.dirtyRowIds);
  const clearDirtyRows = useBudgetStore((state) => state.clearDirtyRows);
  const planilhaId = useBudgetStore((state) => state.planilhaId);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!isDirty) return;

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(async () => {
      if (dirtyRowIds.length === 0) return;
      
      // Early Return: Previne erro de Violação de Chave Estrangeira se a Planilha não existe ainda
      if (!planilhaId) {
          console.warn("[AutoSave] Salvamento bloqueado: planilhaId é nulo. Aguardando geração do ID da planilha.");
          return;
      }
      
      const tableData = useBudgetStore.getState().tableData;
      // Dicionário para acesso O(1) ao invés de buscar (find) repetidamente num array de 5.000 itens
      const rowDict = new Map(tableData.map(r => [r.id, r]));
      
      // Mapeia os dados reais em O(1) ignorando IDs que não estão mais na tabela (deletados)
      const linhasToSave = dirtyRowIds.map(id => {
        const row = rowDict.get(id);
        if (!row) return null;
        
        return {
           id: row.id,
           id_planilha: planilhaId,
           codigo: row.codigo || null,
           descricao: row.descricao || "",
           unidade: row.und || "-",
           quantidade: Number(row.quant) || 0.0,
           preco_unitario: Number(row.valorUnit) || 0.0
        };
      }).filter(Boolean) as any[];

      if (linhasToSave.length === 0) {
          clearDirtyRows(dirtyRowIds); 
          return;
      }

      console.log(`[AutoSave] Disparando salvamento debounced para ${linhasToSave.length} linhas (planilha: ${planilhaId})...`);
      
      // Mecanismo de Chunking para evitar erro 413 (Payload Too Large) na nuvem
      const CHUNK_SIZE = 200;
      let idsProcessados: string[] = [];

      for (let i = 0; i < linhasToSave.length; i += CHUNK_SIZE) {
         const chunk = linhasToSave.slice(i, i + CHUNK_SIZE);
         const payload = { linhas: chunk };
         
         try {
           const res = await fetch('/api/proxy/orcamento/save-linhas', {
             method: 'POST',
             headers: {
               'Content-Type': 'application/json',
             },
             body: JSON.stringify(payload)
           });
           
           if (res.ok) {
              idsProcessados.push(...chunk.map(r => r.id));
           } else {
              console.error(`[AutoSave] Erro ao salvar lote ${i/CHUNK_SIZE}`, await res.text());
           }
         } catch (e) {
           console.error(`[AutoSave] Exceção na requisição do lote ${i/CHUNK_SIZE}:`, e);
         }
      }

      if (idsProcessados.length > 0) {
          console.log(`[AutoSave] ${idsProcessados.length} linhas salvas com sucesso! Limpando estado sujo...`);
          // Limpa cirurgicamente apenas as que a nuvem aceitou, protegendo edições paralelas (Race Condition Fix)
          clearDirtyRows(idsProcessados); 
      }
      
    }, 3000); // 3 Segundos de Debounce

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [isDirty, dirtyRowIds, clearDirtyRows, planilhaId]);
}
