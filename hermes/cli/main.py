"""
Hermes CLI Main Entry Point

Command-line interface for managing prompts.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich import print as rprint

app = typer.Typer(
    name="hermes",
    help="Hermes Prompt Engineering CLI",
    add_completion=False,
)
console = Console()

# Config directory
CONFIG_DIR = Path.home() / ".hermes"
CONFIG_FILE = CONFIG_DIR / "config.json"
TOKEN_FILE = CONFIG_DIR / "token.json"


def get_config() -> dict:
    """Load CLI configuration."""
    if not CONFIG_FILE.exists():
        return {
            "hermes_url": os.getenv("HERMES_URL", "https://hermes.bravozero.ai"),
            "persona_url": os.getenv("PERSONA_URL", "https://persona.bravozero.ai"),
        }
    
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config: dict):
    """Save CLI configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_token() -> Optional[str]:
    """Get stored access token."""
    if not TOKEN_FILE.exists():
        return None
    
    with open(TOKEN_FILE) as f:
        data = json.load(f)
        return data.get("access_token")


def save_token(access_token: str, refresh_token: Optional[str] = None):
    """Save access token."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump({
            "access_token": access_token,
            "refresh_token": refresh_token,
        }, f, indent=2)
    # Secure permissions
    TOKEN_FILE.chmod(0o600)


def get_client():
    """Get configured HTTP client."""
    import httpx
    
    config = get_config()
    token = get_token()
    
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    return httpx.Client(
        base_url=config["hermes_url"],
        headers=headers,
        timeout=30.0,
    )


@app.command()
def login():
    """Authenticate with PERSONA via device flow."""
    import httpx
    import time
    import webbrowser
    
    config = get_config()
    persona_url = config["persona_url"]
    
    console.print("[bold blue]Starting PERSONA authentication...[/bold blue]")
    
    # Start device authorization flow
    try:
        with httpx.Client() as client:
            # Request device code
            response = client.post(
                f"{persona_url}/oauth2/device/authorize",
                data={
                    "client_id": "hermes-cli",
                    "scope": "openid profile prompts:read prompts:write benchmarks:run",
                },
            )
            response.raise_for_status()
            data = response.json()
            
            device_code = data["device_code"]
            user_code = data["user_code"]
            verification_uri = data["verification_uri"]
            interval = data.get("interval", 5)
            expires_in = data.get("expires_in", 600)
            
            console.print(f"\n[bold]Visit:[/bold] {verification_uri}")
            console.print(f"[bold]Enter code:[/bold] {user_code}\n")
            
            # Try to open browser
            try:
                webbrowser.open(verification_uri)
            except Exception:
                pass
            
            # Poll for token
            console.print("Waiting for authorization...")
            start_time = time.time()
            
            while time.time() - start_time < expires_in:
                time.sleep(interval)
                
                try:
                    token_response = client.post(
                        f"{persona_url}/oauth2/token",
                        data={
                            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                            "device_code": device_code,
                            "client_id": "hermes-cli",
                        },
                    )
                    
                    if token_response.status_code == 200:
                        tokens = token_response.json()
                        save_token(
                            tokens["access_token"],
                            tokens.get("refresh_token"),
                        )
                        console.print("[bold green]✓ Authentication successful![/bold green]")
                        return
                    
                    error = token_response.json().get("error")
                    if error == "authorization_pending":
                        continue
                    elif error == "slow_down":
                        interval += 1
                        continue
                    else:
                        console.print(f"[red]Authentication failed: {error}[/red]")
                        raise typer.Exit(1)
                
                except httpx.HTTPError as e:
                    console.print(f"[red]Error: {e}[/red]")
                    raise typer.Exit(1)
            
            console.print("[red]Authentication timed out[/red]")
            raise typer.Exit(1)
            
    except httpx.HTTPError as e:
        console.print(f"[red]Failed to start authentication: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def logout():
    """Clear stored credentials."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        console.print("[green]✓ Logged out successfully[/green]")
    else:
        console.print("Not logged in")


@app.command()
def whoami():
    """Show current authenticated user."""
    token = get_token()
    if not token:
        console.print("[yellow]Not logged in. Run 'hermes login' first.[/yellow]")
        raise typer.Exit(1)
    
    with get_client() as client:
        try:
            response = client.get("/auth/me")
            response.raise_for_status()
            user = response.json()
            
            console.print(f"[bold]Email:[/bold] {user.get('email')}")
            console.print(f"[bold]Name:[/bold] {user.get('name')}")
            console.print(f"[bold]Roles:[/bold] {', '.join(user.get('roles', []))}")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)


@app.command("list")
def list_prompts(
    prompt_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results"),
):
    """List prompts."""
    with get_client() as client:
        params = {"limit": limit}
        if prompt_type:
            params["type"] = prompt_type
        if status:
            params["status"] = status
        
        try:
            response = client.get("/api/v1/prompts", params=params)
            response.raise_for_status()
            data = response.json()
            
            table = Table(title="Prompts")
            table.add_column("Slug", style="cyan")
            table.add_column("Name")
            table.add_column("Type", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Version")
            table.add_column("Score")
            
            for prompt in data.get("items", []):
                score = prompt.get("benchmark_score")
                score_str = f"{score:.1f}%" if score else "-"
                table.add_row(
                    prompt["slug"],
                    prompt["name"],
                    prompt["type"],
                    prompt["status"],
                    prompt["version"],
                    score_str,
                )
            
            console.print(table)
            console.print(f"\nTotal: {data.get('total', 0)} prompts")
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)


@app.command()
def pull(
    slug: str = typer.Argument(..., help="Prompt slug"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    version: Optional[str] = typer.Option(None, "--version", "-v", help="Specific version"),
):
    """Download a prompt."""
    with get_client() as client:
        try:
            response = client.get(f"/api/v1/prompts/by-slug/{slug}")
            response.raise_for_status()
            prompt = response.json()
            
            content = prompt["content"]
            
            if output:
                output.write_text(content)
                console.print(f"[green]✓ Saved to {output}[/green]")
            else:
                syntax = Syntax(content, "markdown", theme="monokai", line_numbers=True)
                console.print(f"\n[bold]{prompt['name']}[/bold] (v{prompt['version']})\n")
                console.print(syntax)
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)


@app.command()
def push(
    file: Path = typer.Argument(..., help="Prompt file to upload"),
    slug: Optional[str] = typer.Option(None, "--slug", "-s", help="Prompt slug"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Prompt name"),
    prompt_type: str = typer.Option("user_template", "--type", "-t", help="Prompt type"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Change message"),
):
    """Upload or update a prompt."""
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)
    
    content = file.read_text()
    prompt_slug = slug or file.stem.replace("_", "-").lower()
    prompt_name = name or file.stem.replace("_", " ").title()
    
    with get_client() as client:
        # Check if prompt exists
        try:
            response = client.get(f"/api/v1/prompts/by-slug/{prompt_slug}")
            exists = response.status_code == 200
        except Exception:
            exists = False
        
        try:
            if exists:
                # Update existing
                prompt = response.json()
                update_data = {
                    "content": content,
                    "change_summary": message or f"Updated from CLI",
                }
                response = client.put(f"/api/v1/prompts/{prompt['id']}", json=update_data)
                response.raise_for_status()
                console.print(f"[green]✓ Updated {prompt_slug}[/green]")
            else:
                # Create new
                create_data = {
                    "slug": prompt_slug,
                    "name": prompt_name,
                    "type": prompt_type,
                    "content": content,
                }
                response = client.post("/api/v1/prompts", json=create_data)
                response.raise_for_status()
                console.print(f"[green]✓ Created {prompt_slug}[/green]")
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)


@app.command()
def diff(
    slug: str = typer.Argument(..., help="Prompt slug"),
    v1: str = typer.Argument(..., help="First version"),
    v2: str = typer.Argument(..., help="Second version"),
):
    """Show diff between two versions of a prompt."""
    with get_client() as client:
        try:
            response = client.get(f"/api/v1/prompts/by-slug/{slug}/versions/{v1}/diff/{v2}")
            response.raise_for_status()
            diff_data = response.json()
            
            console.print(f"\n[bold]Diff: {slug}[/bold]")
            console.print(f"[dim]{v1} → {v2}[/dim]\n")
            
            syntax = Syntax(diff_data["diff"], "diff", theme="monokai")
            console.print(syntax)
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)


@app.command()
def benchmark(
    slug: str = typer.Argument(..., help="Prompt slug"),
    model: str = typer.Option("aria-01", "--model", "-m", help="Model to benchmark against"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for results"),
):
    """Trigger a benchmark run on a prompt."""
    with get_client() as client:
        try:
            # Get prompt first
            response = client.get(f"/api/v1/prompts/by-slug/{slug}")
            response.raise_for_status()
            prompt = response.json()
            
            # Trigger benchmark
            response = client.post(
                f"/api/v1/prompts/{prompt['id']}/benchmark",
                json={"model_id": model, "suite_id": "default"},
            )
            response.raise_for_status()
            result = response.json()
            
            console.print(f"[green]✓ Benchmark queued[/green]")
            console.print(f"Benchmark ID: {result.get('benchmark_id')}")
            
            if wait:
                console.print("\n[dim]Waiting for results...[/dim]")
                # Would poll for results here
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)


@app.command()
def config(
    hermes_url: Optional[str] = typer.Option(None, "--hermes-url", help="Set Hermes URL"),
    persona_url: Optional[str] = typer.Option(None, "--persona-url", help="Set PERSONA URL"),
    show: bool = typer.Option(False, "--show", help="Show current config"),
):
    """Manage CLI configuration."""
    cfg = get_config()
    
    if show:
        rprint(cfg)
        return
    
    if hermes_url:
        cfg["hermes_url"] = hermes_url
    if persona_url:
        cfg["persona_url"] = persona_url
    
    if hermes_url or persona_url:
        save_config(cfg)
        console.print("[green]✓ Configuration saved[/green]")
    else:
        console.print("Use --show to display current config, or set values with --hermes-url / --persona-url")


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
