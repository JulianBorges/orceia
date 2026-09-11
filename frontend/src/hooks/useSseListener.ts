import { useEffect, useRef } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { useBudgetStore } from '../store/useBudgetStore';

/**
 * Consome o canal SSE do backend via fetch-event-source.
 * Vantagem sobre EventSource nativo: suporta Last-Event-ID para reconexao resiliente.
 * ADIÇÃO: Detecta proxies corporativos que bloqueiam streams (Timeout de 5s) e aciona o Fallback de Polling.
 */
export function useSseListener(planilhaId: string | null) {
  const updateRowById = useBudgetStore((state) => state.updateRowById);
  const currentStreamToken = useBudgetStore((state) => state.currentStreamToken);
  
  // Extrai as novas propriedades do Polling
  const isPollingFallback = useBudgetStore((state) => state.isPollingFallback);
  const isProcessing = useBudgetStore((state) => state.isProcessing);
  const enablePollingFallback = useBudgetStore((state) => state.enablePollingFallback);
  const pollProgress = useBudgetStore((state) => state.pollProgress);

  const lastEventIdRef = useRef<string>('$');
  const abortControllerRef = useRef<AbortController | null>(null);
  const pingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // EFEITO 1: O Loop de Fallback (Polling Seguro via GET comum)
  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval>;
    
    if (isPollingFallback && isProcessing) {
      console.log('[POLLING] Modo Fallback ativado. Buscando progresso via GET HTTP comum a cada 3s...');
      
      // Busca imediatamente
      pollProgress();
      
      // E depois a cada 3 segundos
      intervalId = setInterval(() => {
        if (useBudgetStore.getState().isProcessing) {
          pollProgress();
        } else {
          clearInterval(intervalId);
        }
      }, 3000);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isPollingFallback, isProcessing, pollProgress]);

  // EFEITO 2: O Canal SSE (Tempo Real)
  useEffect(() => {
    // Só conecta se tivermos a planilha, o token, e se o fallback NÃO estiver ativo
    if (!planilhaId || !currentStreamToken || isPollingFallback) return;

    console.log(`[SSE] Conectando via Proxy Next.js para Planilha: ${planilhaId}`);
    abortControllerRef.current = new AbortController();

    // Função de Guarda do Proxy:
    // O backend manda um ping " " a cada 1 segundo. Se ficarmos 5 segundos de silêncio absoluto,
    // significa que o Firewall do Estado bufferizou o stream e bloqueou a comunicação.
    const resetPingTimeout = () => {
        if (pingTimeoutRef.current) clearTimeout(pingTimeoutRef.current);
        pingTimeoutRef.current = setTimeout(() => {
            console.error('[SSE] TIMEOUT: Nenhum pacote (nem ping) em 5s. Proxy corporativo detectado! Acionando Fallback...');
            enablePollingFallback();
            abortControllerRef.current?.abort();
        }, 5000);
    };

    fetchEventSource(`/api/proxy/orcamento/stream/${planilhaId}?token=${currentStreamToken}`, {
      signal: abortControllerRef.current.signal,
      credentials: 'include', // Essencial para proxies corporativos (NTLM/Negotiate) responderem ao desafio 407
      headers: {
        'Last-Event-ID': lastEventIdRef.current,
      },

      onopen: async (response) => {
        if (!response.ok) {
          console.error(`[SSE] Falha ao abrir conexao: HTTP ${response.status}`);
          if (response.status === 401) {
            throw new Error("Token SSE expirado ou inválido (401). Abortando reconexão.");
          }
          // Qualquer outro erro 500/502/403/407 persistente no proxy do governo:
          enablePollingFallback();
          throw new Error(`Conexão rejeitada pelo proxy com status ${response.status}`);
        }
        // Conexão abriu com sucesso. Dispara o timer contra proxies silenciosos:
        resetPingTimeout();
      },

      onmessage: (event) => {
        // Recebeu qualquer coisa (ping vazio, padding inicial, ou payload real): O canal está vivo!
        resetPingTimeout();

        if (event.id) {
          lastEventIdRef.current = event.id;
        }

        if (!event.data) return; // Ignora o conteúdo de pings ou paddings

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
        console.warn('[SSE] Conexão abortada ou Erro de rede (Proxy). Acionando Polling Fallback...', err);
        enablePollingFallback();
        throw err; // Lança erro para abortar retries do SSE, passando a bola pro Polling.
      },
    });

    return () => {
      console.log(`[SSE] Encerrando conexao (Planilha: ${planilhaId})`);
      if (pingTimeoutRef.current) clearTimeout(pingTimeoutRef.current);
      abortControllerRef.current?.abort();
    };
  }, [planilhaId, updateRowById, currentStreamToken, isPollingFallback, enablePollingFallback]);
}
