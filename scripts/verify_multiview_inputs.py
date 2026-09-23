"""Read-only operator preflight for calibrated native Pixal multiview fixtures."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from PIL import Image
from mediaforge.multiview_inputs import InvalidViews, verify_directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--count', type=int)
    args = parser.parse_args()
    try:
        result = verify_directory(args.directory, count=args.count)
    except InvalidViews as exc:
        result = {'valid': False, 'reason': str(exc)}
    except (OSError, ValueError, Image.DecompressionBombError):
        result = {'valid': False, 'reason': 'input_unreadable'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
