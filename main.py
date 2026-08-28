import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def serve(host: str, port: int, config_path: str):
    import uvicorn

    os.environ.setdefault("GJALLARHORN_CONFIG", config_path)
    print("=" * 65)
    print(" Gjallarhorn - Asgard Centralized Alerting Hub")
    print("=" * 65)
    uvicorn.run("api.server:app", host=host, port=port)


def test_notify(source: str, severity: str, title: str, message: str, channels, hub_url: str, api_key: str, config_path: str):
    print("=" * 65)
    print(" Gjallarhorn - Test Notification")
    print("=" * 65)

    if hub_url:
        # Send over HTTP to an already-running hub.
        from gjallarhorn_client import notify

        ok = notify(
            hub_url=hub_url,
            api_key=api_key or os.environ.get("GJALLARHORN_API_KEY", ""),
            source=source,
            severity=severity,
            title=title,
            message=message,
            channels=channels,
        )
        print(f"HTTP notify to {hub_url}: {'OK' if ok else 'FAILED'}")
        sys.exit(0 if ok else 1)

    # No hub URL given: dispatch locally against the configured channels,
    # so the configuration can be validated without a server running.
    from core.channels import build_channels
    from core.config import load_config
    from core.db import NotificationDB
    from core.hub import NotificationHub

    config = load_config(config_path)
    db = NotificationDB(db_path=config["hub"]["db_path"])
    hub = NotificationHub(
        channels=build_channels(config),
        db=db,
        dedup_window_seconds=config["hub"]["dedup_window_seconds"],
        default_channels=config["hub"]["default_channels"],
    )

    result = hub.notify(
        source=source,
        severity=severity,
        title=title,
        message=message,
        channels=channels,
    )
    print(f"Status: {result['status']}")
    print(f"Sent to channels: {result['sent_to'] or '(none - check configuration)'}")
    if result["status"] == "suppressed":
        print(f"Suppressed count: {result['suppressed_count']}")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Gjallarhorn: Asgard Centralized Alerting Hub")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    serve_p = subparsers.add_parser("serve", help="Start the Gjallarhorn HTTP hub")
    serve_p.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    serve_p.add_argument("--port", type=int, default=8090, help="Port to bind to")
    serve_p.add_argument("--config", default="config.yaml", help="Path to config.yaml")

    test_p = subparsers.add_parser("test-notify", help="Send a test notification")
    test_p.add_argument("--source", required=True, help="Source module name (e.g. heimdall)")
    test_p.add_argument("--severity", required=True, choices=["low", "medium", "high", "critical"])
    test_p.add_argument("--title", required=True, help="Notification title")
    test_p.add_argument("--message", required=True, help="Notification body")
    test_p.add_argument("--channels", default=None, help="Comma-separated channel names (default: configured defaults)")
    test_p.add_argument("--hub-url", default=None, help="If set, send over HTTP to a running hub instead of dispatching locally")
    test_p.add_argument("--api-key", default=None, help="API key to use with --hub-url (defaults to GJALLARHORN_API_KEY env var)")
    test_p.add_argument("--config", default="config.yaml", help="Path to config.yaml (used when --hub-url is not set)")

    args = parser.parse_args()

    if args.command == "serve":
        serve(args.host, args.port, args.config)
    elif args.command == "test-notify":
        channels = [c.strip() for c in args.channels.split(",")] if args.channels else None
        test_notify(
            source=args.source,
            severity=args.severity,
            title=args.title,
            message=args.message,
            channels=channels,
            hub_url=args.hub_url,
            api_key=args.api_key,
            config_path=args.config,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
