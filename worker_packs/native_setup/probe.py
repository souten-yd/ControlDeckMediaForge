"""Non-root, non-interactive OS setup discovery; never installs packages.

Runs with the OS Python so GI does not become a core dependency. Only fixed
read-only D-Bus calls are allowed. No raw D-Bus errors/details reach stdout.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

SCHEMA = "media-forge.native-setup-probe@1"
ACTION = "org.freedesktop.packagekit.package-install-untrusted"
CALL_TIMEOUT_MS = 2000


def result(error_code: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "provider": "packagekit",
        "state": "unavailable" if error_code else "detected", "error_code": error_code,
        "version": None, "backend": None, "local_deb_mime": False, "locked": None,
        "authorization": "not_checked", "interactive_agent": "not_checked",
        "installation": "not_implemented",
    }


def discover(connection: Any, gio: Any, glib: Any) -> dict[str, Any]:
    value = result()
    try:
        reply = connection.call_sync(
            "org.freedesktop.PackageKit", "/org/freedesktop/PackageKit",
            "org.freedesktop.DBus.Properties", "GetAll",
            glib.Variant("(s)", ("org.freedesktop.PackageKit",)),
            glib.VariantType.new("(a{sv})"), gio.DBusCallFlags.NONE,
            CALL_TIMEOUT_MS, None,
        )
        properties = reply.unpack()[0]
        version = [properties[name] for name in ("VersionMajor", "VersionMinor", "VersionMicro")]
        if any(type(item) is not int or not 0 <= item <= 65535 for item in version):
            return result("native_setup_invalid_reply")
        backend = properties["BackendName"]
        if not isinstance(backend, str) or len(backend) > 64 or not backend.isascii() or not backend.replace("-", "").replace("_", "").isalnum():
            return result("native_setup_invalid_reply")
        if type(properties["Locked"]) is not bool or not isinstance(properties["MimeTypes"], list):
            return result("native_setup_invalid_reply")
        value.update(version=".".join(map(str, version)), backend=backend,
                     locked=properties["Locked"],
                     local_deb_mime=bool({"application/vnd.debian.binary-package", "application/x-deb"}
                                         .intersection(properties["MimeTypes"])))
    except (KeyError, TypeError, ValueError, glib.Error):
        return result("native_setup_packagekit_unavailable")
    try:
        # No caller-controlled subject and no ALLOW_USER_INTERACTION flag.
        subject = ("system-bus-name", {"name": glib.Variant("s", connection.get_unique_name())})
        reply = connection.call_sync(
            "org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority",
            "org.freedesktop.PolicyKit1.Authority", "CheckAuthorization",
            glib.Variant("((sa{sv})sa{ss}us)", (subject, ACTION, {}, 0, "")),
            glib.VariantType.new("((bba{ss}))"), gio.DBusCallFlags.NONE,
            CALL_TIMEOUT_MS, None,
        )
        authorized, challenge, _details = reply.unpack()[0]
        if type(authorized) is not bool or type(challenge) is not bool:
            return result("native_setup_invalid_reply")
        value["authorization"] = "granted" if authorized else "challenge" if challenge else "denied"
    except (TypeError, ValueError, glib.Error):
        value["authorization"] = "unavailable"
        value["error_code"] = "native_setup_authorization_unavailable"
    return value


def main() -> int:
    if len(sys.argv) != 1:
        print(json.dumps(result("native_setup_arguments_forbidden")))
        return 2
    if os.getuid() == 0 or os.geteuid() == 0:
        print(json.dumps(result("native_setup_root_forbidden")))
        return 2
    try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
    except (ImportError, ValueError):
        print(json.dumps(result("native_setup_gi_unavailable")))
        return 0
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except GLib.Error:
        value = result("native_setup_system_bus_unavailable")
    else:
        value = discover(connection, Gio, GLib)
    print(json.dumps(value, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
