import QtQuick
import org.kde.plasma.plasma5support as Plasma5Support

Item {
    id: usage
    property bool active: true
    property int refreshMinutes: 5
    property var windows: []
    property string plan: ""
    property string error: ""
    property bool loading: false
    property double timestamp: 0
    property double now: Date.now()
    readonly property bool stale: timestamp > 0 && (error !== "" || now - timestamp * 1000 > Math.max(1, refreshMinutes) * 180000)
    readonly property string summary: {
        var parts = windows.map(function(window) { return window.label + ": " + Math.round(window.usedPercent) + "% used" })
        return "OpenAI Codex: " + (parts.length ? parts.join(" | ") + (stale ? " (outdated)" : "") : error || "Loading…")
    }

    function refresh(manual) {
        if (!active || loading) return
        loading = true
        var path = decodeURIComponent(Qt.resolvedUrl("../scripts/openai_usage.py").toString().replace("file://", ""))
        var quotedPath = "'" + path.replace(/'/g, "'\\''") + "'"
        reader.connectSource("python3 " + quotedPath + " --max-age " + (manual ? 55 : Math.max(1, refreshMinutes) * 60))
    }

    Plasma5Support.DataSource {
        id: reader
        engine: "executable"
        connectedSources: []
        onNewData: function(sourceName, data) {
            disconnectSource(sourceName)
            usage.loading = false
            try {
                var result = JSON.parse(data["stdout"] || "")
                usage.windows = result.windows || []
                usage.plan = result.plan || ""
                usage.timestamp = result.timestamp || 0
                usage.error = result.error || ""
                usage.now = Date.now()
            } catch (e) {
                usage.error = "Could not read OpenAI usage. Check that Python 3 and Codex CLI are installed."
            }
        }
    }

    Timer {
        interval: Math.max(1, usage.refreshMinutes) * 60000
        running: usage.active
        repeat: true
        onTriggered: usage.refresh(false)
    }
    Timer {
        interval: 30000
        running: usage.active
        repeat: true
        onTriggered: usage.now = Date.now()
    }
    onActiveChanged: { if (active) refresh(false) }
    Component.onCompleted: refresh(false)
}
