"""Compatibility entry point: python -m agent run ..."""
import sys
from .run import main
if __name__ == '__main__':
    raise SystemExit(main(sys.argv[2:] if sys.argv[1:2] == ['run'] else sys.argv[1:]))
