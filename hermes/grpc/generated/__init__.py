"""
Generated gRPC code for Hermes API.

This module contains auto-generated protobuf and gRPC code.
Regenerate using: scripts/compile_protos.sh

Note: If the generated modules are not available, the gRPC server will
be disabled at runtime. Install grpcio-tools and run the compile script:

    pip install grpcio-tools
    ./scripts/compile_protos.sh
"""

try:
    from hermes.grpc.generated.hermes_pb2 import *
    from hermes.grpc.generated.hermes_pb2_grpc import *
    GRPC_GENERATED = True
except ImportError:
    GRPC_GENERATED = False
    # Placeholder - modules will be available after proto compilation
