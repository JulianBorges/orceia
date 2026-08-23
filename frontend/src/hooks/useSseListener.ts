import { useEffect } from 'react';
import { useBudgetStore } from '../store/useBudgetStore';

export function useSseListener(planilhaId: string) {
  const updateRowById = useBudgetStore((state) => state.updateRowById);

  useEffect(() => {
    if (!planilhaId) return;

    console.log(`[SSE] Conectando ao barramento de Eventos da Planilha: ${planilhaId}`);
    
    // O Next.js Proxy lidará com a chave secreta. O Client usa apenas a rota nativa de segurança.
    const eventSource = new EventSource(`/api/proxy/orcamento/stream/${planilhaId}`);

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        
        // Se a inteligência artificial terminou de processar uma linha:
        if (payload.status === 'sucesso' && payload.dados_ia) {
            const { id, status_ia, parecer, codigo_novo, memoria_calculo, rigor } = payload.dados_ia;
            console.log(`[SSE] ✨ Linha processada pela IA (ID: ${id})`);
            
            const updatePayload: any = {
                ai_status: status_ia,
                ai_parecer_tecnico: parecer,
                codigo: codigo_novo,
                memoria_calculo: memoria_calculo || []
            };

            // Extrai o preço da resposta da IA para ligar o Motor Matemático
            if (codigo_novo && memoria_calculo) {
                const match = memoria_calculo.find((m: any) => m.codigo === codigo_novo);
                if (match) {
                    updatePayload.valorUnit = Number(match.preco) || 0;
                    updatePayload.und = match.unidade || "-";
                    // Atualiza a descrição apenas se o match tiver nome
                    if (match.descricao) {
                        updatePayload.descricao = match.descricao;
                    }
                    updatePayload.base = "SINAPI";
                }
            }

            // Atualiza a tabela na tela do usuário instantaneamente (60FPS)
            updateRowById(id, updatePayload);
        } else if (payload.status === 'erro') {
            console.error(`[SSE] Erro no item ${payload.id}: ${payload.mensagem}`);
            updateRowById(payload.id, {
                ai_status: "ERRO DE PROCESSAMENTO",
                ai_parecer_tecnico: payload.mensagem
            });
        } else if (payload.status === 'lote_concluido') {
            useBudgetStore.getState().setIsProcessing(false);
            useBudgetStore.getState().setProcessingStatusText('Análise Completa!');
            console.log(`[SSE] 🎉 Lote de ${payload.total} itens processado com sucesso!`);
        }
      } catch (e) {
         console.error("[SSE] Erro ao traduzir os pacotes do Redis:", e);
      }
    };

    eventSource.onerror = (error) => {
      console.warn("[SSE] Desconexão/Erro no Barramento. A nuvem pode ter cortado a conexão. Tentando recuperar automaticamente...");
    };

    return () => {
      console.log(`[SSE] Encerrando conexão (Planilha: ${planilhaId})`);
      eventSource.close();
    };
  }, [planilhaId, updateRowById]);
}
