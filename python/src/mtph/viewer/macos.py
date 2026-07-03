"""Build a native macOS viewer app (Swift + WKWebView) for ``.mtph`` files.

The app registers as the handler for ``.mtph``; when you open one it reads the file, asks
``mtph open - --stdout`` to render the reader HTML, and shows it in its **own window** — no
browser. Built with ``swiftc`` (Command Line Tools), ad-hoc signed for local use.
"""
from __future__ import annotations

import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path

# The mtph executable path is injected at build time (must live outside protected folders).
SWIFT_SOURCE = r'''
import AppKit
import WebKit

let mtphBin = "__MTPH_BIN__"

final class AppDelegate: NSObject, NSApplicationDelegate {
    var controllers: [NSWindowController] = []

    func application(_ application: NSApplication, open urls: [URL]) {
        for u in urls { openDoc(u) }
    }
    func application(_ sender: NSApplication, openFile filename: String) -> Bool {
        openDoc(URL(fileURLWithPath: filename)); return true
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { return true }

    func openDoc(_ url: URL) {
        let content = (try? String(contentsOf: url, encoding: .utf8)) ?? ""
        let html = render(content)
        showWindow(title: url.deletingPathExtension().lastPathComponent, html: html)
    }

    func render(_ content: String) -> String {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: mtphBin)
        proc.arguments = ["open", "-", "--stdout"]
        let inPipe = Pipe(), outPipe = Pipe()
        proc.standardInput = inPipe
        proc.standardOutput = outPipe
        do { try proc.run() } catch {
            return "<html><body style='font:16px -apple-system;padding:40px'>Could not run mtph at \(mtphBin)<br>\(error)</body></html>"
        }
        if let d = content.data(using: .utf8) { inPipe.fileHandleForWriting.write(d) }
        inPipe.fileHandleForWriting.closeFile()
        let out = outPipe.fileHandleForReading.readDataToEndOfFile()
        proc.waitUntilExit()
        return String(data: out, encoding: .utf8) ?? "<html><body>render failed</body></html>"
    }

    func showWindow(title: String, html: String) {
        let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 940, height: 1120),
                           styleMask: [.titled, .closable, .resizable, .miniaturizable],
                           backing: .buffered, defer: false)
        win.isReleasedWhenClosed = false
        win.title = title.isEmpty ? "mtph" : title
        let web = WKWebView(frame: win.contentView!.bounds)
        web.autoresizingMask = [.width, .height]
        web.loadHTMLString(html, baseURL: nil)
        win.contentView!.addSubview(web)
        win.center()
        let wc = NSWindowController(window: win)
        wc.showWindow(nil)
        controllers.append(wc)
        NSApp.activate(ignoringOtherApps: true)
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = AppDelegate()
app.delegate = delegate
app.run()
'''


def _info_plist() -> dict:
    return {
        "CFBundleName": "mtph Viewer",
        "CFBundleDisplayName": "mtph Viewer",
        "CFBundleIdentifier": "dev.mtph.viewer",
        "CFBundleExecutable": "mtph-viewer",
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": "11.0",
        "NSPrincipalClass": "NSApplication",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": [{
            "CFBundleTypeName": "mtph problem",
            "CFBundleTypeExtensions": ["mtph"],
            "CFBundleTypeRole": "Viewer",
            "LSHandlerRank": "Owner",
            "LSItemContentTypes": ["dev.mtph.problem"],
        }],
        "UTExportedTypeDeclarations": [{
            "UTTypeIdentifier": "dev.mtph.problem",
            "UTTypeDescription": "mtph problem",
            "UTTypeConformsTo": ["public.plain-text"],
            "UTTypeTagSpecification": {"public.filename-extension": ["mtph"]},
        }],
    }


def build_native_app(mtph_bin: Path, app_path: Path) -> Path:
    """Compile and bundle the native viewer at ``app_path``. Raises on swiftc failure."""
    if app_path.exists():
        shutil.rmtree(app_path)
    contents = app_path / "Contents"
    macos = contents / "MacOS"
    macos.mkdir(parents=True)

    (contents / "Info.plist").write_bytes(plistlib.dumps(_info_plist()))
    (contents / "PkgInfo").write_text("APPL????")

    source = SWIFT_SOURCE.replace("__MTPH_BIN__", str(mtph_bin))
    with tempfile.NamedTemporaryFile("w", suffix=".swift", delete=False, encoding="utf-8") as tf:
        tf.write(source)
        swift_src = tf.name

    subprocess.run(
        ["swiftc", "-swift-version", "5", "-O", swift_src,
         "-o", str(macos / "mtph-viewer"), "-framework", "AppKit", "-framework", "WebKit"],
        check=True, capture_output=True, text=True,
    )
    # ad-hoc sign so macOS will launch the locally built app
    subprocess.run(["codesign", "--force", "--sign", "-", str(app_path)],
                   capture_output=True, text=True)
    return app_path


# A Quick Look preview extension (QLPreviewingController). Sandboxed by the system.
QL_SWIFT_SOURCE = r'''
import Cocoa
import Quartz
import WebKit

let mtphBin = "__MTPH_BIN__"

@objc(PreviewViewController)
class PreviewViewController: NSViewController, QLPreviewingController {
    var web: WKWebView!

    override func loadView() {
        let v = NSView(frame: NSRect(x: 0, y: 0, width: 800, height: 1000))
        web = WKWebView(frame: v.bounds)
        web.autoresizingMask = [.width, .height]
        v.addSubview(web)
        self.view = v
    }

    func preparePreviewOfFile(at url: URL, completionHandler handler: @escaping (Error?) -> Void) {
        let content = (try? String(contentsOf: url, encoding: .utf8)) ?? ""
        web.loadHTMLString(render(content), baseURL: nil)
        handler(nil)
    }

    func render(_ content: String) -> String {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: mtphBin)
        proc.arguments = ["open", "-", "--stdout"]
        let i = Pipe(), o = Pipe()
        proc.standardInput = i
        proc.standardOutput = o
        do { try proc.run() } catch {
            return "<html><body style='font:15px -apple-system;padding:30px'>mtph could not run inside the Quick Look sandbox:<br>\(error)</body></html>"
        }
        if let d = content.data(using: .utf8) { i.fileHandleForWriting.write(d) }
        i.fileHandleForWriting.closeFile()
        let out = o.fileHandleForReading.readDataToEndOfFile()
        proc.waitUntilExit()
        return String(data: out, encoding: .utf8) ?? "<html><body>render failed</body></html>"
    }
}
'''


def _ql_info_plist() -> dict:
    return {
        "CFBundleName": "mtph Quick Look",
        "CFBundleIdentifier": "dev.mtph.viewer.quicklook",
        "CFBundleExecutable": "mtphQuickLook",
        "CFBundlePackageType": "XPC!",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleInfoDictionaryVersion": "6.0",
        "NSExtension": {
            "NSExtensionPointIdentifier": "com.apple.quicklook.preview",
            "NSExtensionPrincipalClass": "PreviewViewController",
            "NSExtensionAttributes": {
                "QLSupportedContentTypes": ["dev.mtph.problem"],
                "QLSupportsSearchableItems": False,
            },
        },
    }


def build_quicklook_extension(mtph_bin: Path, app_path: Path) -> Path:
    """Build a Quick Look preview .appex inside the host app. Raises on swiftc failure."""
    appex = app_path / "Contents" / "PlugIns" / "mtphQuickLook.appex"
    macos = appex / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    (appex / "Contents" / "Info.plist").write_bytes(plistlib.dumps(_ql_info_plist()))

    source = QL_SWIFT_SOURCE.replace("__MTPH_BIN__", str(mtph_bin))
    with tempfile.NamedTemporaryFile("w", suffix=".swift", delete=False, encoding="utf-8") as tf:
        tf.write(source)
        swift_src = tf.name

    subprocess.run(
        ["swiftc", "-swift-version", "5", "-O", "-parse-as-library", "-module-name",
         "mtphQuickLook", swift_src, "-o", str(macos / "mtphQuickLook"),
         "-framework", "Cocoa", "-framework", "Quartz", "-framework", "WebKit",
         "-Xlinker", "-e", "-Xlinker", "_NSExtensionMain"],
        check=True, capture_output=True, text=True,
    )
    # sign the extension, then re-sign the whole app (ad-hoc)
    subprocess.run(["codesign", "--force", "--sign", "-", str(appex)], capture_output=True, text=True)
    subprocess.run(["codesign", "--force", "--sign", "-", str(app_path)], capture_output=True, text=True)
    return appex
