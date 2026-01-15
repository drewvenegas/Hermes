/**
 * Suggestions Provider
 * 
 * Provides inline code actions for prompt improvements.
 */

import * as vscode from 'vscode';
import { HermesClient } from './hermesClient';

export class SuggestionsProvider implements vscode.CodeActionProvider {
    private suggestions: Map<string, any[]> = new Map();
    
    constructor(private client: HermesClient) {}
    
    async provideCodeActions(
        document: vscode.TextDocument,
        range: vscode.Range,
        context: vscode.CodeActionContext,
        token: vscode.CancellationToken
    ): Promise<vscode.CodeAction[]> {
        const actions: vscode.CodeAction[] = [];
        
        // Get cached suggestions for this document
        const docKey = document.uri.toString();
        const suggestions = this.suggestions.get(docKey);
        
        if (!suggestions || suggestions.length === 0) {
            return actions;
        }
        
        // Filter suggestions relevant to the selected range
        for (const suggestion of suggestions) {
            if (this.isRelevantToRange(suggestion, document, range)) {
                const action = new vscode.CodeAction(
                    `💡 ${suggestion.description}`,
                    vscode.CodeActionKind.QuickFix
                );
                
                if (suggestion.suggested_change) {
                    action.edit = new vscode.WorkspaceEdit();
                    // Apply suggestion at appropriate location
                    // This is simplified - real implementation would need
                    // more sophisticated text manipulation
                    action.edit.insert(
                        document.uri,
                        range.start,
                        `// ${suggestion.suggested_change}\n`
                    );
                }
                
                action.diagnostics = [];
                action.isPreferred = suggestion.severity === 'high';
                
                actions.push(action);
            }
        }
        
        return actions;
    }
    
    private isRelevantToRange(
        suggestion: any,
        document: vscode.TextDocument,
        range: vscode.Range
    ): boolean {
        // Check if suggestion location matches the range
        // This is a simplified check
        if (suggestion.location) {
            const lineMatch = suggestion.location.match(/line\s*(\d+)/i);
            if (lineMatch) {
                const line = parseInt(lineMatch[1]) - 1; // 0-indexed
                return range.start.line <= line && range.end.line >= line;
            }
        }
        
        // If no location, show for any selection
        return true;
    }
    
    async loadSuggestions(document: vscode.TextDocument, promptId: string): Promise<void> {
        try {
            const result = await this.client.runSelfCritique(promptId);
            const docKey = document.uri.toString();
            this.suggestions.set(docKey, result.suggestions || []);
        } catch (error) {
            console.error('Failed to load suggestions:', error);
        }
    }
    
    clearSuggestions(document: vscode.TextDocument): void {
        this.suggestions.delete(document.uri.toString());
    }
}
