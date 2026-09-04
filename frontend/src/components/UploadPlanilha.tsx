import React, { useRef, useState } from 'react';
import * as XLSX from 'xlsx';
import { useBudgetStore } from '@/store/useBudgetStore';
import { CloudUpload, Plus, FileSpreadsheet } from 'lucide-react';
import { BudgetItem } from '@/utils/budgetUtils';
import { FlatListModal } from './FlatListModal';

interface UploadPlanilhaProps {
    children?: React.ReactNode;
    className?: string;
    append?: boolean;
    iconOnly?: boolean;
    isFloatingAdd?: boolean;
}

export function UploadPlanilha({ children, className, append = false, iconOnly = false, isFloatingAdd = false }: UploadPlanilhaProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const { tableData, loadTableData, setTableData, setPlanilhaId, processarOrcamentoIA, estruturarEAP } = useBudgetStore();
    
    const [isFlatListModalOpen, setIsFlatListModalOpen] = useState(false);
    const [isStructuringEAP, setIsStructuringEAP] = useState(false);
    const [pendingData, setPendingData] = useState<BudgetItem[]>([]);

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

            const numMacroItems = parsedData.filter(d => d.is_macro_item).length;
            const isFlatList = numMacroItems === 0 && parsedData.length > 0;

            if (append) {
                if (isFlatList) {
                    setPendingData(parsedData);
                    setIsFlatListModalOpen(true);
                } else {
                    setTableData([...tableData, ...parsedData]);
                    setTimeout(() => processarOrcamentoIA(), 100);
                }
            } else {
                const newPlanilhaId = crypto.randomUUID();
                setPlanilhaId(newPlanilhaId);
                
                if (isFlatList) {
                    // Lista Plana Detectada
                    setPendingData(parsedData);
                    setIsFlatListModalOpen(true);
                } else {
                    // Tem macro itens, segue o fluxo normal
                    loadTableData(parsedData);
                    setTimeout(() => processarOrcamentoIA(), 100);
                }
            }
            
            // Reseta o input para permitir carregar o mesmo arquivo novamente se precisar
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        };
        reader.readAsBinaryString(file);
    };

    const handleMapearComoListaPlana = () => {
        setIsFlatListModalOpen(false);
        if (append) {
            setTableData([...tableData, ...pendingData]);
        } else {
            loadTableData(pendingData);
        }
        setTimeout(() => processarOrcamentoIA(), 100);
    };

    const handleUsarIAParaEAP = async () => {
        setIsStructuringEAP(true);
        try {
            await estruturarEAP(pendingData, append);
            setIsFlatListModalOpen(false);
            // Após estruturar EAP, dispara automaticamente o motor de orçamentação
            setTimeout(() => processarOrcamentoIA(), 100);
        } catch (error) {
            console.error("Erro ao estruturar EAP", error);
            alert("Ocorreu um erro ao tentar estruturar a EAP. Por favor, tente novamente.");
        } finally {
            setIsStructuringEAP(false);
        }
    };

    const defaultClassName = "flex items-center gap-2 bg-zinc-50 hover:bg-zinc-100 border border-zinc-200/80 text-zinc-700 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:border-zinc-700 dark:text-zinc-200 px-4 py-2 rounded-lg font-medium transition-colors text-sm";
    const iconOnlyClassName = "group relative p-2 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-400 transition-colors flex items-center justify-center";
    const floatingClassName = "group flex items-center justify-center w-8 h-8 bg-white hover:bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:text-zinc-400 rounded-full shadow-sm transition-transform hover:scale-110 border border-zinc-200 dark:border-zinc-700 absolute left-1/2 -bottom-4 -translate-x-1/2 z-10";

    const getButtonContent = () => {
        if (children) return children;
        if (isFloatingAdd) {
            return (
                <>
                    <Plus className="w-4 h-4" />
                    <span className="absolute -top-8 left-1/2 -translate-x-1/2 bg-zinc-800 text-white text-[11px] font-medium px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                        Carregar mais itens
                    </span>
                </>
            );
        }
        if (iconOnly) {
            return (
                <>
                    <FileSpreadsheet className="w-5 h-5" />
                    <span className="absolute -top-8 left-1/2 -translate-x-1/2 bg-zinc-800 text-white text-[11px] font-medium px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                        {append ? "Adicionar Itens" : "Substituir Excel"}
                    </span>
                </>
            );
        }
        return (
            <>
                <CloudUpload className="w-4 h-4" />
                {append ? "Adicionar Excel" : "Importar Excel"}
            </>
        );
    };

    const resolveClassName = () => {
        if (className) return className;
        if (isFloatingAdd) return floatingClassName;
        if (iconOnly) return iconOnlyClassName;
        return defaultClassName;
    };

    return (
        <>
            <div className={isFloatingAdd ? "" : ""}>
                <input 
                    type="file" 
                    accept=".xlsx, .xls" 
                    className="hidden" 
                    ref={fileInputRef} 
                    onChange={handleFileUpload} 
                />
                <button 
                    onClick={() => fileInputRef.current?.click()}
                    className={resolveClassName()}
                >
                    {getButtonContent()}
                </button>
            </div>
            
            <FlatListModal 
                isOpen={isFlatListModalOpen}
                isLoading={isStructuringEAP}
                onMapearComoListaPlana={handleMapearComoListaPlana}
                onUsarIAParaEAP={handleUsarIAParaEAP}
            />
        </>
    );
}
