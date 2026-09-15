#!/usr/bin/env python3
"""
Engineering Studio V3 – Autonomous Repair Controller
Autonomous proof-of-concept: README generation loop
"""

import sys
import argparse
import json
from pathlib import Path

studio_dir = Path(__file__).parent
sys.path.insert(0, str(studio_dir / 'studio_v3'))

from studio_v3.platforms.controller import StudioController

def main():
    parser = argparse.ArgumentParser(description='Engineering Studio V3 Controller')
    parser.add_argument('--cycle', action='store_true', help='Run one repair cycle')
    parser.add_argument('--repo', default='${NEXUS_ROOT}',
                       help='Repository path to scan')
    args = parser.parse_args()

    if args.cycle:
        print("""
╔════════════════════════════════════════════════════════╗
║     Engineering Studio V3 – Autonomous Repair Loop    ║
║                  Proof-of-Concept                     ║
╚════════════════════════════════════════════════════════╝
""")

        config_path = str(studio_dir / 'config.yaml')
        controller = StudioController(config_path, args.repo)
        results = controller.run_repair_loop()

        print("\n" + "="*60)
        print("CYCLE RESULTS")
        print("="*60)
        print(json.dumps(results, indent=2, default=str))

        return 0 if not results.get('failures') else 1
    else:
        parser.print_help()
        return 0

if __name__ == '__main__':
    sys.exit(main())
