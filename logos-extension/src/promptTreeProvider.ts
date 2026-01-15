/**
 * Prompt Tree Data Provider
 * 
 * Provides the tree view for browsing Hermes prompts.
 */

import * as vscode from 'vscode';
import { HermesClient, Prompt } from './hermesClient';

export class PromptTreeProvider implements vscode.TreeDataProvider<PromptItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<PromptItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    
    private prompts: Prompt[] = [];
    private categorized: Map<string, Prompt[]> = new Map();
    
    constructor(private client: HermesClient) {
        this.refresh();
    }
    
    refresh(): void {
        this.loadPrompts();
        this._onDidChangeTreeData.fire(undefined);
    }
    
    private async loadPrompts(): Promise<void> {
        try {
            const result = await this.client.listPrompts({ limit: 100 });
            this.prompts = result.items;
            
            // Categorize prompts
            this.categorized.clear();
            for (const prompt of this.prompts) {
                const category = prompt.category || 'Uncategorized';
                if (!this.categorized.has(category)) {
                    this.categorized.set(category, []);
                }
                this.categorized.get(category)!.push(prompt);
            }
        } catch (error) {
            console.error('Failed to load prompts:', error);
        }
    }
    
    getTreeItem(element: PromptItem): vscode.TreeItem {
        return element;
    }
    
    async getChildren(element?: PromptItem): Promise<PromptItem[]> {
        if (!element) {
            // Root level - show categories
            const categories = Array.from(this.categorized.keys()).sort();
            return categories.map(
                (cat) => new PromptItem(
                    cat,
                    vscode.TreeItemCollapsibleState.Collapsed,
                    'category',
                    { category: cat }
                )
            );
        }
        
        if (element.itemType === 'category') {
            // Show prompts in category
            const prompts = this.categorized.get(element.label as string) || [];
            return prompts.map(
                (p) => new PromptItem(
                    p.name,
                    vscode.TreeItemCollapsibleState.None,
                    'prompt',
                    { prompt: p }
                )
            );
        }
        
        return [];
    }
}

class PromptItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly itemType: 'category' | 'prompt',
        public readonly data: { category?: string; prompt?: Prompt }
    ) {
        super(label, collapsibleState);
        
        if (itemType === 'prompt' && data.prompt) {
            const prompt = data.prompt;
            
            this.tooltip = `${prompt.name}\nv${prompt.version}\n${prompt.type}`;
            this.description = `v${prompt.version}`;
            
            // Set icon based on status
            if (prompt.benchmark_score) {
                if (prompt.benchmark_score >= 80) {
                    this.iconPath = new vscode.ThemeIcon('pass', new vscode.ThemeColor('testing.iconPassed'));
                } else if (prompt.benchmark_score >= 60) {
                    this.iconPath = new vscode.ThemeIcon('warning', new vscode.ThemeColor('testing.iconFailed'));
                } else {
                    this.iconPath = new vscode.ThemeIcon('error', new vscode.ThemeColor('testing.iconErrored'));
                }
            } else {
                this.iconPath = new vscode.ThemeIcon('file');
            }
            
            // Context value for menus
            this.contextValue = 'prompt';
            
            // Command to open prompt
            this.command = {
                command: 'hermes.pullPrompt',
                title: 'Open Prompt',
                arguments: [prompt.slug],
            };
        } else if (itemType === 'category') {
            this.iconPath = new vscode.ThemeIcon('folder');
            this.contextValue = 'category';
        }
    }
}
