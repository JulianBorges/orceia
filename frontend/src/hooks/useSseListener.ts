import { useEffect, useRef } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { useBudgetStore } from '../store/useBudgetStore';

/**
 * Consome o canal SSE do backend via fetch-event-source.
 * Vantagem sobre EventSource nativo: suporta Last-Event-ID para reconexao resiliente.
 */
export function useSseListener(planilhaId: string | null) {
  const updateRowById = useBudgetStore((state) => state.updateRowById);
  const currentStreamToken = useBudgetStore((state) => state.currentStreamToken);
  const lastEventIdRef = useRef<string>('$');
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Só conecta se tivermos a planilha e o Token Efêmero (Bypass de Proxy aprovado)
    if (!planilhaId || !currentStreamToken) return;

    console.log(`[SSE] Conectando ao barramento direto (Bypass Vercel) da Planilha: ${planilhaId}`);
    abortControllerRef.current = new AbortController();

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://127.0.0.1:8000';

    fetchEventSource(`${backendUrl}/orcamento/stream/${planilhaId}?token=${currentStreamToken}`, {
      signal: abortControllerRef.current.signal,
      headers: {
        'Last-Event-ID': lastEventIdRef.current,
      },

      onopen: async (response) => {
        if (!response.ok) {
          console.error(`[SSE] Falha ao abrir conexao: HTTP ${response.status}`);
          if (response.status === 401) {
            throw new Error("Token SSE expirado ou inválido (401). Abortando reconexão.");
          }
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
          
          if (payload.status === 'processando') {
            useBudgetStore.getState().setCurrentAnalyzingItemName(payload.descricao || 'Processando item...');
          } else if (payload.status === 'sucesso' && payload.dados_ia) {
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
            
            checkCompletion();

          } else if (payload.status === 'erro') {
            console.error(`[SSE] Erro no item ${payload.id}: ${payload.mensagem}`);
            updateRowById(payload.id, {
              ai_status: 'ERRO DE PROCESSAMENTO',
              ai_parecer_tecnico: payload.mensagem,
            });
            useBudgetStore.getState().incrementProcessedItemsCount();

            checkCompletion();

          } else if (payload.status === 'lote_concluido') {
            console.log(`[SSE] Lote de ${payload.total} itens reportou conclusão parcial (background thread terminou).`);
            checkCompletion();
          }

        } catch (e) {
          console.error('[SSE] Erro ao traduzir os pacotes do Redis:', e);
        }
      },

      onerror: (err) => {
        if (err && err.message && err.message.includes("401")) {
            console.error('[SSE] Token rejeitado pelo servidor (401). Abortando retries.');
            throw err; // Cancela os retries automáticos
        }
        console.warn('[SSE] Desconexao/Erro. fetch-event-source fara retry automatico...', err);
      },
    });

    return () => {
      console.log(`[SSE] Encerrando conexao (Planilha: ${planilhaId})`);
      abortControllerRef.current?.abort();
    };
  }, [planilhaId, updateRowById, currentStreamToken]);
}
