import { useEffect, useRef } from 'react';
import { useBudgetStore } from '../store/useBudgetStore';

export function useAutoSave() {
  const isDirty = useBudgetStore((state) => state.isDirty);
  const dirtyRowIds = useBudgetStore((state) => state.dirtyRowIds);
  const clearDirtyRows = useBudgetStore((state) => state.clearDirtyRows);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!isDirty) return;

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(async () => {
      if (dirtyRowIds.length === 0) return;
      
      console.log(`[AutoSave] Disparando salvamento debounced para ${dirtyRowIds.length} linhas...`);
      const payload = {
        linhas: dirtyRowIds.map(id => ({
           id,
           id_planilha: "planilha-fake", // A ser dinâmico no futuro
           descricao: "Serviço editado reativamente",
           unidade: "M2",
           quantidade: 1.0,
           preco_unitario: 100.0
        }))
      };

      try {
        const res = await fetch('/api/proxy/orcamento/save-linhas', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload)
        });
        
        if (res.ok) {
           console.log("[AutoSave] Salvo com sucesso!");
           clearDirtyRows(); // Reseta o status O(1) usando a função portada
        } else {
           console.error("[AutoSave] Erro ao salvar", await res.text());
        }
      } catch (e) {
        console.error("[AutoSave] Exceção na requisição:", e);
      }
    }, 3000); // 3 Segundos de Debounce

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [isDirty, dirtyRowIds, clearDirtyRows]);
}
