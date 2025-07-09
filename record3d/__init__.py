try:
    from .record3d._record3d import *  # noqa: F403
except ImportError as e:
    import sys

    print("Error: The record3d C++ extension module could not be imported.", file=sys.stderr)
    print("This usually means the package needs to be built and installed.", file=sys.stderr)
    print(
        "Please run: pip install -e . (for development) or pip install . (for installation)",
        file=sys.stderr,
    )
    print(f"Original error: {e}", file=sys.stderr)
    raise
