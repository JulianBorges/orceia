import React, { useState } from "react";
import { useSortable } from '@dnd-kit/sortable';
import { flexRender } from "@tanstack/react-table";
import { List, Box, Wand2, Trash2, ChevronUp, GripVertical, ChevronDown } from "lucide-react";
import { recalculateNumbers } from '@/utils/budgetUtils';

export const SortableRow = React.memo( ({ row, virtualRow, data, addRow, deleteRow, updateRow, onOpenCreatorModal, rowVirtualizer, activeAutocompleteRowId }: any) => {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: row.original.id });
    
    const isAutocompleteOpen = activeAutocompleteRowId === row.original.id;
    const isProcessing = row.original.ai_status === 'PROCESSANDO';
    
    const [isFocused, setIsFocused] = useState(false);

    // O transform do sortable (que move no eixo Y durante o arraste) é somado ao translateY da virtualização
    const style: React.CSSProperties = {
        minHeight: '52px',
        transform: transform 
            ? `translate3d(${transform.x}px, ${virtualRow.start + transform.y}px, 0)` 
            : `translateY(${virtualRow.start}px)`,
        transition: transition || undefined,
        // Força z-index alto quando o autocomplete está aberto ou quando a linha tem hover/focus, para não ser coberta por irmãos virtuais
        zIndex: isDragging ? 999 : (isAutocompleteOpen ? 900 : undefined),
        opacity: isDragging ? 0.8 : 1,
    };

    return (
        <div 
            ref={(node) => {
                setNodeRef(node);
                rowVirtualizer.measureElement(node);
            }}
            data-index={virtualRow.index}
            className={`group transition-colors duration-150 absolute top-0 left-0 w-full flex items-stretch z-10 hover:z-[30] hover:bg-zinc-100 dark:hover:bg-zinc-800/60 focus-within:z-[30] ${row.original.is_macro_item ? 'bg-zinc-100/80 dark:bg-zinc-800/50 border-y border-zinc-200 dark:border-zinc-700/50' : ''}`}
            style={style}
            onFocus={(e) => {
                // Ignore focus se for no botão do menu
                if ((e.target as HTMLElement).closest('.row-menu-btn')) return;
                setIsFocused(true);
            }}
            onBlur={(e) => {
                // Timeout para evitar flickers ao pular entre inputs da mesma linha
                setTimeout(() => {
                    if (!document.activeElement?.closest(`[data-index="${virtualRow.index}"]`)) {
                        setIsFocused(false);
                    }
                }, 0);
            }}
        >
            {isProcessing && (
                <div className="absolute inset-0 bg-zinc-200/40 dark:bg-zinc-700/30 animate-[pulse_1.5s_ease-in-out_infinite] pointer-events-none z-0"></div>
            )}
            {/* Menu de Contexto */}
            {!activeAutocompleteRowId && !isFocused && !isProcessing && (
                <div 
                    className="absolute left-8 top-[80%] z-[70] hidden group-hover:flex justify-center items-center pointer-events-auto shadow-lg rounded-full border border-zinc-200/60 dark:border-zinc-700/60 bg-white/95 dark:bg-zinc-800/95 backdrop-blur-md px-1"
                >
                    <div className="flex flex-row items-center p-0.5 gap-0.5 h-8">
                    <button 
                        onClick={() => {
                            const originalIdx = data.findIndex((d: any) => d.id === row.original.id);
                            addRow(originalIdx + 1, {
                                id: `macro_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`, 
                                item: "-", codigo: "", base: "", descricao: "Novo Item", und: "-", quant: 0, valorUnit: 0, total: 0, is_macro_item: true, 
                                level: row.original.level
                            });
                        }}
                        className="row-menu-btn flex flex-row items-center justify-center px-2 py-1 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors gap-1.5 h-full">
                        <List className="w-3 h-3" />
                        <span className="text-[10px] font-medium whitespace-nowrap">Item</span>
                    </button>

                    <button 
                        onClick={() => {
                            const originalIdx = data.findIndex((d: any) => d.id === row.original.id);
                            addRow(originalIdx + 1, {
                                id: `serv_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`, 
                                item: "-", codigo: "", base: "SINAPI", descricao: "Novo Serviço", und: "-", quant: 1, valorUnit: 0, total: 0, is_macro_item: false, 
                                level: (row.original.level || 0) + (row.original.is_macro_item ? 1 : 0)
                            });
                        }}
                        className="row-menu-btn flex flex-row items-center justify-center px-2 py-1 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors gap-1.5 h-full">
                        <Box className="w-3 h-3" />
                        <span className="text-[10px] font-medium whitespace-nowrap">Serviço</span>
                    </button>
                    
                    <div className="w-px h-4 bg-zinc-200 dark:bg-zinc-700 mx-0.5"></div>

                    {row.original.is_macro_item && (
                        <>
                            <button 
                                onClick={() => {
                                    const originalIdx = data.findIndex((d: any) => d.id === row.original.id);
                                    const currentLvl = data[originalIdx].level || 0;
                                    if (currentLvl > 0) {
                                        updateRow(originalIdx, { level: currentLvl - 1 });
                                    }
                                }}
                                className="row-menu-btn flex flex-row items-center justify-center px-2 py-1 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors h-full"
                                title="Recuar Nível do Bloco"
                            >
                                <span className="text-[12px] font-bold">{"<"}</span>
                            </button>

                            <button 
                                onClick={() => {
                                    const originalIdx = data.findIndex((d: any) => d.id === row.original.id);
                                    const currentLvl = data[originalIdx].level || 0;
                                    if (currentLvl < 5) {
                                        updateRow(originalIdx, { level: currentLvl + 1 });
                                    }
                                }}
                                className="row-menu-btn flex flex-row items-center justify-center px-2 py-1 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors h-full"
                                title="Avançar Nível do Bloco"
                            >
                                <span className="text-[12px] font-bold">{">"}</span>
                            </button>
                            <div className="w-px h-4 bg-zinc-200 dark:bg-zinc-700 mx-0.5"></div>
                        </>
                    )}

                    <button 
                        onClick={() => {
                            const originalIdx = data.findIndex((d: any) => d.id === row.original.id);
                            if (onOpenCreatorModal) onOpenCreatorModal(row.original.descricao, originalIdx);
                        }}
                        className="row-menu-btn flex flex-row items-center justify-center px-2 py-1 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 rounded text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors gap-1.5 h-full"
                        title="Criar Composição Inédita baseada nesta linha"
                    >
                        <Wand2 className="w-3 h-3" />
                        <span className="text-[10px] font-medium whitespace-nowrap">Auto IA</span>
                    </button>
                    
                    <div className="w-px h-4 bg-zinc-200 dark:bg-zinc-700 mx-0.5"></div>

                    <button 
                        onClick={() => {
                            deleteRow(row.original.id);
                        }}
                        className="row-menu-btn flex flex-row items-center justify-center px-2 py-1 hover:bg-red-50 dark:hover:bg-red-500/10 rounded text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 transition-colors gap-1.5 h-full">
                        <Trash2 className="w-3 h-3" />
                        <span className="text-[10px] font-medium whitespace-nowrap">Excluir</span>
                    </button>
                    </div>
                </div>
            )}
            
            <div className="flex flex-1 w-full relative">
                <div 
                    className="absolute left-1 top-1/2 -translate-y-1/2 flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-colors z-50 w-6 py-1 rounded-md text-indigo-400/50 hover:text-indigo-400 hover:bg-indigo-500/10"
                >
                    <div 
                        {...attributes} 
                        {...listeners} 
                        className="cursor-grab active:cursor-grabbing hover:text-indigo-600 dark:hover:text-indigo-300 p-1 text-inherit transition-colors"
                        title="Arrastar e Soltar"
                    >
                        <GripVertical className="w-4 h-4" />
                    </div>
                </div>
                {row.getVisibleCells().map((cell: any) => (
                    <div key={cell.id} style={{ width: cell.column.getSize(), flexGrow: cell.column.id === 'descricao' ? 1 : 0 }} className="px-3 shrink-0 flex items-center py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </div>
                ))}
            </div>
        </div>
    );
});