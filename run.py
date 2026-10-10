"""Start Wihanga Nada.

    python run.py                 # real BirdNET, http://127.0.0.1:5000
    python run.py --demo          # fake detections, no TensorFlow needed
    python run.py --host 0.0.0.0 --https   # let a phone on your Wi-Fi/hotspot use it
"""
import argparse

from wihanga.app import create_app
from wihanga.identify import DemoIdentifier


def main() -> None:
    p = argparse.ArgumentParser(description="Offline bird-call identifier for Sri Lanka")
    p.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to allow other devices")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--https", action="store_true", help="self-signed HTTPS (phones need it for the mic)")
    p.add_argument("--demo", action="store_true", help="fake detections; skips BirdNET")
    args = p.parse_args()

    app = create_app(identifier=DemoIdentifier() if args.demo else None)
    app.run(
        host=args.host,
        port=args.port,
        ssl_context="adhoc" if args.https else None,
        threaded=True,
    )


if __name__ == "__main__":
    main()
