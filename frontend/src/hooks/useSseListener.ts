import { useEffect, useRef } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { useBudgetStore } from '../store/useBudgetStore';

/**
 * Consome o canal SSE do backend via fetch-event-source.
 * Vantagem sobre EventSource nativo: suporta Last-Event-ID para reconexao resiliente.
 */
export function useSseListener(planilhaId: string | null) {
  const updateRowById = useBudgetStore((state) => state.updateRowById);
  const lastEventIdRef = useRef<string>('0-0');
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!planilhaId) return;

    console.log(`[SSE] Conectando ao barramento de Eventos da Planilha: ${planilhaId}`);
    abortControllerRef.current = new AbortController();

    fetchEventSource(`/api/proxy/orcamento/stream/${planilhaId}`, {
      signal: abortControllerRef.current.signal,
      headers: {
        'Last-Event-ID': lastEventIdRef.current,
      },

      onopen: async (response) => {
        if (!response.ok) {
          console.error(`[SSE] Falha ao abrir conexao: HTTP ${response.status}`);
        }
      },

      onmessage: (event) => {
        if (event.id) {
          lastEventIdRef.current = event.id;
        }

        if (!event.data) return; // Guard clause para ignorar pings ou pacotes vazios

        try {
          const payload = JSON.parse(event.data);

          const checkCompletion = () => {
            const state = useBudgetStore.getState();
            if (state.processedItemsCount >= state.totalItemsToProcess && state.totalItemsToProcess > 0) {
              state.setIsProcessing(false);
              state.setProcessingStatusText('Análise Completa!');
              console.log(`[SSE] Todos os ${state.totalItemsToProcess} itens foram processados com sucesso!`);
            }
          };
          
          if (payload.status === 'sucesso' && payload.dados_ia) {
            const { id, status_ia, parecer, codigo_novo, memoria_calculo } = payload.dados_ia;
            console.log(`[SSE] Linha processada pela IA (ID: ${id})`);

            const updatePayload: Record<string, unknown> = {
              ai_status: status_ia,
              ai_parecer_tecnico: parecer,
              codigo: codigo_novo,
              memoria_calculo: memoria_calculo || [],
            };

            if (codigo_novo && memoria_calculo) {
              const match = memoria_calculo.find((m: { codigo: string; preco?: number; unidade?: string; descricao?: string }) => m.codigo === codigo_novo);
              if (match) {
                updatePayload.valorUnit = Number(match.preco) || 0;
                updatePayload.und = match.unidade || '-';
                if (match.descricao) updatePayload.descricao = match.descricao;
                updatePayload.base = 'SINAPI';
              }
            }

            updateRowById(id, updatePayload);
            useBudgetStore.getState().incrementProcessedItemsCount();
            
            const currentItem = useBudgetStore.getState().tableData.find(r => r.id === id);
            if (currentItem) {
                useBudgetStore.getState().setCurrentAnalyzingItemName(currentItem.descricao);
            }
            
            checkCompletion();

          } else if (payload.status === 'erro') {
            console.error(`[SSE] Erro no item ${payload.id}: ${payload.mensagem}`);
            updateRowById(payload.id, {
              ai_status: 'ERRO DE PROCESSAMENTO',
              ai_parecer_tecnico: payload.mensagem,
            });
            useBudgetStore.getState().incrementProcessedItemsCount();

            const currentItem = useBudgetStore.getState().tableData.find(r => r.id === payload.id);
            if (currentItem) {
                useBudgetStore.getState().setCurrentAnalyzingItemName(currentItem.descricao);
            }
            
            checkCompletion();

          } else if (payload.status === 'lote_concluido') {
            console.log(`[SSE] Lote de ${payload.total} itens reportou conclusão parcial (background thread terminou).`);
            checkCompletion();
          }

        } catch (e) {
          console.error('[SSE] Erro ao traduzir os pacotes do Redis:', e);
        }
      },

      onerror: () => {
        console.warn('[SSE] Desconexao/Erro. fetch-event-source fara retry automatico...');
      },
    });

    return () => {
      console.log(`[SSE] Encerrando conexao (Planilha: ${planilhaId})`);
      abortControllerRef.current?.abort();
    };
  }, [planilhaId, updateRowById]);
}
