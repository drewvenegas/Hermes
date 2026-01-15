# Hermes - Logos IDE Extension

VS Code/Logos extension for the Hermes Prompt Engineering Platform.

## Features

- **Prompt Management**: List, create, and edit prompts directly from the IDE
- **Push/Pull**: Sync prompts between local files and Hermes
- **Benchmarking**: Run benchmarks and view results inline
- **Suggestions**: Get AI-powered improvement suggestions via ASRBS
- **Version History**: Browse and compare prompt versions
- **Quality Gates**: Check deployment readiness before release

## Installation

1. Install from VS Code Marketplace (coming soon)
2. Or install from VSIX:
   ```bash
   npm install
   npm run package
   code --install-extension hermes-logos-0.1.0.vsix
   ```

## Configuration

Configure in VS Code settings:

```json
{
  "hermes.serverUrl": "https://hermes.bravozero.ai",
  "hermes.grpcUrl": "localhost:50051",
  "hermes.autoSave": true,
  "hermes.autoBenchmark": false,
  "hermes.showInlineSuggestions": true,
  "hermes.defaultSuite": "default"
}
```

## Commands

| Command | Keybinding | Description |
|---------|------------|-------------|
| `Hermes: List Prompts` | - | Open prompt browser |
| `Hermes: Pull Prompt` | - | Download prompt from Hermes |
| `Hermes: Push Prompt` | `Ctrl+Shift+S` | Upload prompt to Hermes |
| `Hermes: Run Benchmark` | `Ctrl+Shift+B` | Run benchmark on current prompt |
| `Hermes: Get Suggestions` | - | Get ASRBS improvement suggestions |
| `Hermes: Show Version History` | - | View version history |
| `Hermes: Compare Versions` | - | Diff two versions |
| `Hermes: Check Quality Gate` | - | Check deployment readiness |

## Prompt File Format

Hermes prompts use markdown with YAML frontmatter:

```markdown
---
hermes_id: uuid-here
name: My Prompt
slug: my-prompt
version: 1.0.0
type: user_template
---

# My Prompt

Your prompt content here...
```

## Development

```bash
# Install dependencies
npm install

# Compile
npm run compile

# Watch mode
npm run watch

# Package
npm run package
```

## License

Proprietary - Bravo Zero
