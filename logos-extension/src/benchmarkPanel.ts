/**
 * Benchmark Results Panel
 * 
 * Displays benchmark results in a webview panel.
 */

import * as vscode from 'vscode';
import { BenchmarkResult } from './hermesClient';

export class BenchmarkPanel {
    private static panel: vscode.WebviewPanel | undefined;
    
    public static show(uri: vscode.Uri, result: BenchmarkResult): void {
        const column = vscode.ViewColumn.Beside;
        
        if (BenchmarkPanel.panel) {
            BenchmarkPanel.panel.reveal(column);
        } else {
            BenchmarkPanel.panel = vscode.window.createWebviewPanel(
                'hermesBenchmark',
                'Benchmark Results',
                column,
                {
                    enableScripts: true,
                    retainContextWhenHidden: true,
                }
            );
            
            BenchmarkPanel.panel.onDidDispose(() => {
                BenchmarkPanel.panel = undefined;
            });
        }
        
        BenchmarkPanel.panel.webview.html = BenchmarkPanel.getHtml(result);
    }
    
    private static getHtml(result: BenchmarkResult): string {
        const scoreColor = result.overall_score >= 80 ? '#4caf50' : 
                          result.overall_score >= 60 ? '#ff9800' : '#f44336';
        
        const dimensionBars = Object.entries(result.dimension_scores || {})
            .map(([dim, score]) => {
                const color = score >= 80 ? '#4caf50' : score >= 60 ? '#ff9800' : '#f44336';
                return `
                    <div class="dimension">
                        <div class="dim-label">${dim}</div>
                        <div class="dim-bar">
                            <div class="dim-fill" style="width: ${score}%; background: ${color};"></div>
                        </div>
                        <div class="dim-score">${score.toFixed(1)}%</div>
                    </div>
                `;
            })
            .join('');
        
        const gateStatus = result.gate_passed 
            ? '<span class="gate passed">✓ Gate Passed</span>'
            : '<span class="gate failed">✗ Gate Failed</span>';
        
        const deltaDisplay = result.delta !== undefined
            ? `<div class="delta ${result.delta >= 0 ? 'positive' : 'negative'}">
                 ${result.delta >= 0 ? '+' : ''}${result.delta.toFixed(1)}%
               </div>`
            : '';
        
        return `
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Benchmark Results</title>
                <style>
                    body {
                        font-family: var(--vscode-font-family);
                        padding: 20px;
                        color: var(--vscode-foreground);
                        background: var(--vscode-editor-background);
                    }
                    
                    h1 {
                        font-size: 1.5em;
                        margin-bottom: 20px;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    }
                    
                    .score-container {
                        text-align: center;
                        margin: 30px 0;
                    }
                    
                    .score-circle {
                        width: 150px;
                        height: 150px;
                        border-radius: 50%;
                        border: 8px solid ${scoreColor};
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        flex-direction: column;
                    }
                    
                    .score-value {
                        font-size: 2.5em;
                        font-weight: bold;
                        color: ${scoreColor};
                    }
                    
                    .score-label {
                        font-size: 0.9em;
                        color: var(--vscode-descriptionForeground);
                    }
                    
                    .delta {
                        font-size: 1.2em;
                        margin-top: 10px;
                    }
                    
                    .delta.positive { color: #4caf50; }
                    .delta.negative { color: #f44336; }
                    
                    .gate {
                        display: inline-block;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-weight: bold;
                        margin: 10px 0;
                    }
                    
                    .gate.passed {
                        background: rgba(76, 175, 80, 0.2);
                        color: #4caf50;
                    }
                    
                    .gate.failed {
                        background: rgba(244, 67, 54, 0.2);
                        color: #f44336;
                    }
                    
                    .dimensions {
                        margin: 30px 0;
                    }
                    
                    .dimension {
                        display: flex;
                        align-items: center;
                        margin: 10px 0;
                        gap: 10px;
                    }
                    
                    .dim-label {
                        width: 120px;
                        text-transform: capitalize;
                    }
                    
                    .dim-bar {
                        flex: 1;
                        height: 20px;
                        background: var(--vscode-editor-inactiveSelectionBackground);
                        border-radius: 4px;
                        overflow: hidden;
                    }
                    
                    .dim-fill {
                        height: 100%;
                        border-radius: 4px;
                        transition: width 0.5s ease;
                    }
                    
                    .dim-score {
                        width: 60px;
                        text-align: right;
                    }
                    
                    .meta {
                        margin-top: 30px;
                        padding-top: 20px;
                        border-top: 1px solid var(--vscode-widget-border);
                    }
                    
                    .meta-item {
                        display: flex;
                        justify-content: space-between;
                        margin: 5px 0;
                    }
                    
                    .meta-label {
                        color: var(--vscode-descriptionForeground);
                    }
                </style>
            </head>
            <body>
                <h1>
                    <span>📊</span>
                    Benchmark Results
                </h1>
                
                <div class="score-container">
                    <div class="score-circle">
                        <div class="score-value">${result.overall_score.toFixed(1)}</div>
                        <div class="score-label">Overall Score</div>
                    </div>
                    ${deltaDisplay}
                    <div>${gateStatus}</div>
                </div>
                
                <div class="dimensions">
                    <h3>Dimension Scores</h3>
                    ${dimensionBars}
                </div>
                
                <div class="meta">
                    <div class="meta-item">
                        <span class="meta-label">Suite</span>
                        <span>${result.suite_id}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Model</span>
                        <span>${result.model_id}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Execution Time</span>
                        <span>${result.execution_time_ms}ms</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Version</span>
                        <span>${result.prompt_version}</span>
                    </div>
                </div>
            </body>
            </html>
        `;
    }
}
