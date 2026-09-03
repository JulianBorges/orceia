import React, { useRef } from 'react';
import * as XLSX from 'xlsx';
import { useBudgetStore } from '@/store/useBudgetStore';
import { CloudUpload } from 'lucide-react';
import { BudgetItem } from '@/utils/budgetUtils';

interface UploadPlanilhaProps {
    children?: React.ReactNode;
    className?: string;
    append?: boolean;
}

export function UploadPlanilha({ children, className, append = false }: UploadPlanilhaProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const { tableData, loadTableData, setTableData, setPlanilhaId, processarOrcamentoIA } = useBudgetStore();

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (evt) => {
            const bstr = evt.target?.result;
            const wb = XLSX.read(bstr, { type: 'binary' });
            
            // Assume the first sheet is the target
            const wsname = wb.SheetNames[0];
            const ws = wb.Sheets[wsname];
            
            // Convert to array of arrays to handle headers flexibly
            const data = XLSX.utils.sheet_to_json(ws, { header: 1 }) as any[][];
            
            if (data.length === 0) return;

            // Encontra a linha de cabeçalho
            let headerRowIndex = 0;
            for (let i = 0; i < data.length; i++) {
                const rowStr = data[i].join(' ').toLowerCase();
                if (rowStr.includes('item') || rowStr.includes('descri')) {
                    headerRowIndex = i;
                    break;
                }
            }

            const headers = data[headerRowIndex].map(h => String(h || '').toLowerCase().trim());
            
            const getIndex = (keywords: string[]) => {
                return headers.findIndex(h => keywords.some(kw => h.includes(kw)));
            };

            const idxItem = getIndex(['item']);
            const idxDesc = getIndex(['descri', 'serviço']);
            const idxUnd = getIndex(['und', 'unidade', 'un', 'ud']);
            const idxQuant = getIndex(['quant', 'qtd']);
            const idxValor = getIndex(['valor unit', 'preço unit']);

            const parsedData: BudgetItem[] = [];
            
            for (let i = headerRowIndex + 1; i < data.length; i++) {
                const row = data[i];
                if (!row || row.length === 0) continue;
                
                const item = idxItem !== -1 ? String(row[idxItem] || '') : '';
                const desc = idxDesc !== -1 ? String(row[idxDesc] || '') : '';
                const und = idxUnd !== -1 ? String(row[idxUnd] || '') : '';
                
                // Trata virgula pra ponto no parseFloat
                const parseNumber = (val: any) => parseFloat(String(val).replace(',', '.')) || 0;
                
                const quant = idxQuant !== -1 ? parseNumber(row[idxQuant]) : 0;
                const valor = idxValor !== -1 ? parseNumber(row[idxValor]) : 0;

                // Ignora linhas totalmente vazias
                if (!item && !desc && quant === 0) continue;

                parsedData.push({
                    id: crypto.randomUUID(),
                    item: item,
                    descricao: desc,
                    descricao_legada: desc,
                    und: und,
                    quant: quant,
                    valorUnit: valor,
                    total: quant * valor,
                    is_macro_item: !und || und.trim() === '-' || und.trim() === '',
                    base: '',
                    codigo: '',
                    level: item ? item.split('.').length - 1 : 0
                });
            }

            if (parsedData.length === 0) {
                alert("Nenhum item válido foi encontrado. Verifique se sua planilha possui colunas claras como 'Item' e 'Descrição'.");
                if (fileInputRef.current) {
                    fileInputRef.current.value = '';
                }
                return;
            }

            if (append) {
                // No modo append, unir ao existente (marca dirty para auto-save sincronizar)
                setTableData([...tableData, ...parsedData]);
            } else {
                const newPlanilhaId = crypto.randomUUID();
                setPlanilhaId(newPlanilhaId);
                // loadTableData: não marca dirty — evita auto-save desnecessário no upload inicial
                loadTableData(parsedData);
            }
            
            // Inicia a inteligência artificial automaticamente
            setTimeout(() => {
                processarOrcamentoIA();
            }, 100);
            
            // Reseta o input para permitir carregar o mesmo arquivo novamente se precisar
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        };
        reader.readAsBinaryString(file);
    };

    const defaultClassName = "flex items-center gap-2 bg-white hover:bg-zinc-50 border border-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:border-zinc-700 dark:text-zinc-200 px-4 py-2 rounded-lg font-medium shadow-sm transition-colors text-sm";

    return (
        <div>
            <input 
                type="file" 
                accept=".xlsx, .xls" 
                className="hidden" 
                ref={fileInputRef} 
                onChange={handleFileUpload} 
            />
            <button 
                onClick={() => fileInputRef.current?.click()}
                className={className || defaultClassName}
            >
                {children || (
                    <>
                        <CloudUpload className="w-4 h-4" />
                        Importar Excel
                    </>
                )}
            </button>
        </div>
    );
}
