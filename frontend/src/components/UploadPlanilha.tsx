import React, { useRef } from 'react';
import * as XLSX from 'xlsx';
import { useBudgetStore } from '@/store/useBudgetStore';
import { Upload } from 'lucide-react';
import { BudgetItem } from '@/utils/budgetUtils';

export function UploadPlanilha() {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const { setTableData, setPlanilhaId } = useBudgetStore();

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

            const newPlanilhaId = crypto.randomUUID();
            setPlanilhaId(newPlanilhaId);
            setTableData(parsedData);
            
            // Reseta o input para permitir carregar o mesmo arquivo novamente se precisar
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        };
        reader.readAsBinaryString(file);
    };

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
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-md font-medium shadow-sm transition-colors text-sm"
            >
                <Upload className="w-4 h-4" />
                Subir Planilha
            </button>
        </div>
    );
}
