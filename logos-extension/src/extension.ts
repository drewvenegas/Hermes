/**
 * Hermes VS Code/Logos Extension
 * 
 * Provides integration with the Hermes Prompt Engineering Platform:
 * - List and manage prompts
 * - Push/pull prompts from Hermes
 * - Run benchmarks and view results
 * - Get improvement suggestions
 * - View version history
 */

import * as vscode from 'vscode';
import { HermesClient } from './hermesClient';
import { PromptTreeProvider } from './promptTreeProvider';
import { SuggestionsProvider } from './suggestionsProvider';
import { BenchmarkPanel } from './benchmarkPanel';

let client: HermesClient;
let promptTreeProvider: PromptTreeProvider;
let suggestionsProvider: SuggestionsProvider;

export function activate(context: vscode.ExtensionContext) {
    console.log('Hermes extension activating...');
    
    // Initialize client
    const config = vscode.workspace.getConfiguration('hermes');
    client = new HermesClient(
        config.get('serverUrl', 'https://hermes.bravozero.ai'),
        config.get('grpcUrl', 'localhost:50051')
    );
    
    // Initialize tree view provider
    promptTreeProvider = new PromptTreeProvider(client);
    vscode.window.registerTreeDataProvider('hermesPrompts', promptTreeProvider);
    
    // Initialize suggestions provider
    suggestionsProvider = new SuggestionsProvider(client);
    
    // Register commands
    const commands = [
        vscode.commands.registerCommand('hermes.listPrompts', listPrompts),
        vscode.commands.registerCommand('hermes.pullPrompt', pullPrompt),
        vscode.commands.registerCommand('hermes.pushPrompt', pushPrompt),
        vscode.commands.registerCommand('hermes.benchmark', runBenchmark),
        vscode.commands.registerCommand('hermes.critique', getCritique),
        vscode.commands.registerCommand('hermes.versionHistory', showVersionHistory),
        vscode.commands.registerCommand('hermes.diff', compareVersions),
        vscode.commands.registerCommand('hermes.qualityGate', checkQualityGate),
    ];
    
    commands.forEach(cmd => context.subscriptions.push(cmd));
    
    // Auto-save on document save
    if (config.get('autoSave', true)) {
        context.subscriptions.push(
            vscode.workspace.onDidSaveTextDocument(async (doc) => {
                if (isPromptFile(doc)) {
                    await autoSavePrompt(doc);
                }
            })
        );
    }
    
    // Register inline suggestions
    if (config.get('showInlineSuggestions', true)) {
        context.subscriptions.push(
            vscode.languages.registerCodeActionsProvider(
                { pattern: '**/*.{md,prompt.md}' },
                suggestionsProvider,
                { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }
            )
        );
    }
    
    // Status bar item
    const statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    statusBarItem.text = '$(beaker) Hermes';
    statusBarItem.tooltip = 'Hermes Prompt Engineering';
    statusBarItem.command = 'hermes.listPrompts';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);
    
    console.log('Hermes extension activated');
}

export function deactivate() {
    client?.close();
}

// Command implementations

async function listPrompts() {
    promptTreeProvider.refresh();
    vscode.commands.executeCommand('hermesPrompts.focus');
}

async function pullPrompt() {
    const slug = await vscode.window.showInputBox({
        prompt: 'Enter prompt slug',
        placeHolder: 'my-prompt-slug',
    });
    
    if (!slug) return;
    
    try {
        const prompt = await client.getPromptBySlug(slug);
        
        if (!prompt) {
            vscode.window.showErrorMessage(`Prompt "${slug}" not found`);
            return;
        }
        
        // Create new document with prompt content
        const doc = await vscode.workspace.openTextDocument({
            content: formatPromptFile(prompt),
            language: 'markdown',
        });
        
        await vscode.window.showTextDocument(doc);
        vscode.window.showInformationMessage(`Pulled prompt: ${prompt.name}`);
        
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to pull prompt: ${error}`);
    }
}

async function pushPrompt() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    
    const doc = editor.document;
    if (!isPromptFile(doc)) {
        vscode.window.showWarningMessage('Not a prompt file');
        return;
    }
    
    try {
        const content = doc.getText();
        const metadata = parsePromptMetadata(content);
        
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Pushing prompt to Hermes...',
                cancellable: false,
            },
            async () => {
                if (metadata.id) {
                    // Update existing
                    await client.updatePrompt(
                        metadata.id,
                        extractPromptContent(content),
                        `Updated from Logos IDE`
                    );
                } else {
                    // Create new
                    await client.createPrompt({
                        name: metadata.name || getFileName(doc),
                        slug: metadata.slug || generateSlug(getFileName(doc)),
                        content: extractPromptContent(content),
                        type: metadata.type || 'user_template',
                    });
                }
            }
        );
        
        vscode.window.showInformationMessage('Prompt saved to Hermes');
        
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to push prompt: ${error}`);
    }
}

async function runBenchmark() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    
    const doc = editor.document;
    const metadata = parsePromptMetadata(doc.getText());
    
    if (!metadata.id) {
        vscode.window.showWarningMessage('Push prompt to Hermes first to run benchmark');
        return;
    }
    
    const config = vscode.workspace.getConfiguration('hermes');
    const suite = config.get('defaultSuite', 'default');
    
    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Running benchmark...',
                cancellable: false,
            },
            async () => {
                const result = await client.runBenchmark(metadata.id!, suite);
                BenchmarkPanel.show(vscode.Uri.file(doc.fileName), result);
            }
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Benchmark failed: ${error}`);
    }
}

async function getCritique() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    
    const doc = editor.document;
    const metadata = parsePromptMetadata(doc.getText());
    
    if (!metadata.id) {
        vscode.window.showWarningMessage('Push prompt to Hermes first');
        return;
    }
    
    try {
        const result = await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Getting suggestions...',
                cancellable: false,
            },
            async () => client.runSelfCritique(metadata.id!)
        );
        
        // Show suggestions in panel
        showCritiquePanel(result);
        
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to get suggestions: ${error}`);
    }
}

async function showVersionHistory() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    
    const metadata = parsePromptMetadata(editor.document.getText());
    
    if (!metadata.id) {
        vscode.window.showWarningMessage('Push prompt to Hermes first');
        return;
    }
    
    try {
        const history = await client.getVersionHistory(metadata.id!);
        
        const items = history.map(v => ({
            label: `v${v.version}`,
            description: v.change_summary || 'No description',
            detail: `${new Date(v.created_at).toLocaleString()}`,
            version: v.version,
        }));
        
        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: 'Select version to view',
        });
        
        if (selected) {
            const prompt = await client.getPrompt(metadata.id!, selected.version);
            const doc = await vscode.workspace.openTextDocument({
                content: formatPromptFile(prompt),
                language: 'markdown',
            });
            await vscode.window.showTextDocument(doc, { preview: true });
        }
        
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to get history: ${error}`);
    }
}

async function compareVersions() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    
    const metadata = parsePromptMetadata(editor.document.getText());
    
    if (!metadata.id) {
        vscode.window.showWarningMessage('Push prompt to Hermes first');
        return;
    }
    
    const v1 = await vscode.window.showInputBox({
        prompt: 'First version (e.g., 1.0.0)',
    });
    
    if (!v1) return;
    
    const v2 = await vscode.window.showInputBox({
        prompt: 'Second version (e.g., 1.1.0)',
    });
    
    if (!v2) return;
    
    try {
        const diff = await client.diffVersions(metadata.id!, v1, v2);
        
        // Show diff in output channel
        const channel = vscode.window.createOutputChannel('Hermes Diff');
        channel.appendLine(`Diff: ${v1} → ${v2}`);
        channel.appendLine('═'.repeat(50));
        channel.appendLine(diff.diff);
        channel.show();
        
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to compare versions: ${error}`);
    }
}

async function checkQualityGate() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    
    const metadata = parsePromptMetadata(editor.document.getText());
    
    if (!metadata.id) {
        vscode.window.showWarningMessage('Push prompt to Hermes first');
        return;
    }
    
    try {
        const result = await client.checkQualityGate(metadata.id!);
        
        if (result.can_deploy) {
            vscode.window.showInformationMessage(
                `✓ Quality gate passed: ${result.summary}`,
                'View Details'
            );
        } else {
            const action = await vscode.window.showWarningMessage(
                `✗ Quality gate failed: ${result.summary}`,
                'View Details',
                'Run Benchmark'
            );
            
            if (action === 'Run Benchmark') {
                await runBenchmark();
            } else if (action === 'View Details') {
                showGateReport(result);
            }
        }
        
    } catch (error) {
        vscode.window.showErrorMessage(`Quality gate check failed: ${error}`);
    }
}

// Helper functions

function isPromptFile(doc: vscode.TextDocument): boolean {
    return doc.languageId === 'markdown' || 
           doc.fileName.endsWith('.prompt.md') ||
           doc.fileName.endsWith('.prompt');
}

async function autoSavePrompt(doc: vscode.TextDocument) {
    const metadata = parsePromptMetadata(doc.getText());
    if (metadata.id) {
        try {
            await client.updatePrompt(
                metadata.id,
                extractPromptContent(doc.getText()),
                'Auto-saved from Logos IDE'
            );
        } catch (error) {
            console.error('Auto-save failed:', error);
        }
    }
}

interface PromptMetadata {
    id?: string;
    name?: string;
    slug?: string;
    type?: string;
    version?: string;
}

function parsePromptMetadata(content: string): PromptMetadata {
    const metadata: PromptMetadata = {};
    
    // Parse YAML frontmatter
    if (content.startsWith('---')) {
        const endIndex = content.indexOf('---', 3);
        if (endIndex !== -1) {
            const frontmatter = content.slice(3, endIndex);
            const lines = frontmatter.split('\n');
            
            for (const line of lines) {
                const [key, ...valueParts] = line.split(':');
                if (key && valueParts.length > 0) {
                    const value = valueParts.join(':').trim();
                    switch (key.trim()) {
                        case 'hermes_id':
                        case 'id':
                            metadata.id = value;
                            break;
                        case 'name':
                            metadata.name = value;
                            break;
                        case 'slug':
                            metadata.slug = value;
                            break;
                        case 'type':
                            metadata.type = value;
                            break;
                        case 'version':
                            metadata.version = value;
                            break;
                    }
                }
            }
        }
    }
    
    return metadata;
}

function extractPromptContent(content: string): string {
    // Remove frontmatter
    if (content.startsWith('---')) {
        const endIndex = content.indexOf('---', 3);
        if (endIndex !== -1) {
            content = content.slice(endIndex + 3).trim();
        }
    }
    return content;
}

function formatPromptFile(prompt: any): string {
    const lines = [
        '---',
        `hermes_id: ${prompt.id}`,
        `name: ${prompt.name}`,
        `slug: ${prompt.slug}`,
        `version: ${prompt.version}`,
        `type: ${prompt.type}`,
        '---',
        '',
        prompt.content,
    ];
    return lines.join('\n');
}

function getFileName(doc: vscode.TextDocument): string {
    const parts = doc.fileName.split('/');
    const filename = parts[parts.length - 1];
    return filename.replace(/\.(md|prompt\.md|prompt)$/, '');
}

function generateSlug(name: string): string {
    return name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');
}

function showCritiquePanel(result: any) {
    const panel = vscode.window.createWebviewPanel(
        'hermesCritique',
        'Hermes Suggestions',
        vscode.ViewColumn.Beside,
        {}
    );
    
    const suggestions = result.suggestions || [];
    const suggestionsHtml = suggestions.map((s: any) => `
        <div class="suggestion ${s.severity}">
            <span class="badge ${s.severity}">${s.severity}</span>
            <span class="category">${s.category}</span>
            <p>${s.description}</p>
            ${s.suggested_change ? `<code>${s.suggested_change}</code>` : ''}
        </div>
    `).join('');
    
    panel.webview.html = `
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: var(--vscode-font-family); padding: 20px; }
                .score { font-size: 2em; margin-bottom: 20px; }
                .suggestion { 
                    border-left: 3px solid #888; 
                    padding: 10px; 
                    margin: 10px 0;
                    background: var(--vscode-editor-background);
                }
                .suggestion.high { border-color: #f88; }
                .suggestion.medium { border-color: #ff8; }
                .suggestion.low { border-color: #8f8; }
                .badge {
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 0.8em;
                    margin-right: 8px;
                }
                .badge.high { background: #f44; color: white; }
                .badge.medium { background: #fa0; color: black; }
                .badge.low { background: #4a4; color: white; }
                .category { color: var(--vscode-descriptionForeground); }
                code { 
                    display: block; 
                    margin-top: 10px; 
                    padding: 10px;
                    background: var(--vscode-textCodeBlock-background);
                }
            </style>
        </head>
        <body>
            <h1>Prompt Analysis</h1>
            <div class="score">Quality Score: ${result.quality_score?.toFixed(1) || 'N/A'}%</div>
            <p>${result.overall_assessment || ''}</p>
            
            <h2>Suggestions (${suggestions.length})</h2>
            ${suggestionsHtml || '<p>No suggestions</p>'}
        </body>
        </html>
    `;
}

function showGateReport(result: any) {
    const panel = vscode.window.createWebviewPanel(
        'hermesGate',
        'Quality Gate Report',
        vscode.ViewColumn.Beside,
        {}
    );
    
    const evaluations = result.gate_report?.evaluations || [];
    const evaluationsHtml = evaluations.map((e: any) => `
        <div class="evaluation ${e.status}">
            <span class="status ${e.status}">${e.status === 'passed' ? '✓' : e.status === 'failed' ? '✗' : '!'}</span>
            <strong>${e.gate_name}</strong>
            <p>${e.message}</p>
        </div>
    `).join('');
    
    panel.webview.html = `
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: var(--vscode-font-family); padding: 20px; }
                .evaluation { 
                    padding: 10px; 
                    margin: 10px 0;
                    border-radius: 4px;
                }
                .evaluation.passed { background: rgba(0, 200, 0, 0.1); }
                .evaluation.failed { background: rgba(200, 0, 0, 0.1); }
                .evaluation.warning { background: rgba(200, 200, 0, 0.1); }
                .status { font-size: 1.2em; margin-right: 10px; }
                .status.passed { color: #0c0; }
                .status.failed { color: #c00; }
                .status.warning { color: #cc0; }
            </style>
        </head>
        <body>
            <h1>Quality Gate Report</h1>
            <p><strong>Status:</strong> ${result.can_deploy ? '✓ Ready to Deploy' : '✗ Not Ready'}</p>
            <p>${result.gate_report?.summary || ''}</p>
            
            <h2>Gate Evaluations</h2>
            ${evaluationsHtml}
            
            ${result.blockers?.length ? `<h3>Blockers</h3><ul>${result.blockers.map((b: string) => `<li>${b}</li>`).join('')}</ul>` : ''}
            ${result.warnings?.length ? `<h3>Warnings</h3><ul>${result.warnings.map((w: string) => `<li>${w}</li>`).join('')}</ul>` : ''}
        </body>
        </html>
    `;
}
