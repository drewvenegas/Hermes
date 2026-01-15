"""
Hermes gRPC CLI

Command-line interface for managing the Hermes gRPC server.
"""

import asyncio
import typer
from typing import Optional

app = typer.Typer(name="grpc", help="gRPC server management commands")


@app.command("serve")
def serve(
    port: int = typer.Option(50051, "--port", "-p", help="gRPC server port"),
    workers: int = typer.Option(10, "--workers", "-w", help="Number of worker threads"),
):
    """Start the gRPC server standalone."""
    from hermes.grpc.server import GRPCServer
    from hermes.services.database import init_db
    
    async def run():
        # Initialize database
        await init_db()
        
        # Start gRPC server
        server = GRPCServer(port=port, max_workers=workers)
        await server.start()
        
        typer.echo(f"gRPC server running on port {port}")
        typer.echo("Press Ctrl+C to stop")
        
        await server.wait_for_termination()
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        typer.echo("\nServer stopped")


@app.command("compile")
def compile_protos(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """Compile proto files to Python."""
    import subprocess
    import sys
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent.parent
    proto_dir = project_root / "protos"
    output_dir = Path(output) if output else project_root / "hermes" / "grpc" / "generated"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    typer.echo(f"Compiling protos from {proto_dir}")
    typer.echo(f"Output directory: {output_dir}")
    
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={output_dir}",
        f"--grpc_python_out={output_dir}",
        f"--pyi_out={output_dir}",
        str(proto_dir / "hermes.proto"),
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        typer.echo(f"Error: {result.stderr}", err=True)
        raise typer.Exit(1)
    
    typer.echo("Proto compilation complete!")


@app.command("health")
def health_check(
    host: str = typer.Option("localhost", "--host", "-h", help="gRPC server host"),
    port: int = typer.Option(50051, "--port", "-p", help="gRPC server port"),
):
    """Check gRPC server health."""
    import grpc
    from grpc_health.v1 import health_pb2, health_pb2_grpc
    
    target = f"{host}:{port}"
    typer.echo(f"Checking health of {target}...")
    
    try:
        with grpc.insecure_channel(target) as channel:
            stub = health_pb2_grpc.HealthStub(channel)
            response = stub.Check(health_pb2.HealthCheckRequest())
            
            status = health_pb2.HealthCheckResponse.ServingStatus.Name(response.status)
            if response.status == health_pb2.HealthCheckResponse.SERVING:
                typer.echo(f"✓ Server is healthy: {status}")
            else:
                typer.echo(f"✗ Server status: {status}")
                raise typer.Exit(1)
    except grpc.RpcError as e:
        typer.echo(f"✗ Cannot reach server: {e.details()}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
