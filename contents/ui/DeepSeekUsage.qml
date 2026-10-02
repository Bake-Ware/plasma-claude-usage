import QtQuick
import org.kde.plasma.plasma5support as Plasma5Support

Item {
    id: usage
    property bool active: true
    property int refreshMinutes: 5
    property real warnBelow: 2
    property var balances: []
    property bool available: true
    property string error: ""
    property bool loading: false
    property double timestamp: 0
    property double now: Date.now()
    readonly property bool stale: timestamp > 0 && (error !== "" || now - timestamp * 1000 > Math.max(1, refreshMinutes) * 180000)
    readonly property string summary: {
        var parts = balances.map(function(balance) { return usage.format(balance) })
        return "DeepSeek: " + (parts.length ? parts.join(" | ") + (stale ? " (outdated)" : "") : error || "Loading…")
    }

    function format(balance) {
        var symbol = balance.currency === "USD" ? "$" : balance.currency === "CNY" ? "¥" : ""
        return symbol + balance.total.toFixed(2) + (symbol ? "" : " " + balance.currency)
    }

    // 0 = fine, 1 = running low, 2 = empty or unusable
    function level(balance) {
        if (!available || balance.total <= 0) return 2
        return balance.total < warnBelow ? 1 : 0
    }

    function refresh(manual) {
        if (!active || loading) return
        loading = true
        var path = decodeURIComponent(Qt.resolvedUrl("../scripts/deepseek_usage.py").toString().replace("file://", ""))
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
                usage.balances = result.balances || []
                usage.available = result.available !== false
                usage.timestamp = result.timestamp || 0
                usage.error = result.error || ""
                usage.now = Date.now()
            } catch (e) {
                usage.error = "Could not read DeepSeek balance. Check that Python 3 is installed."
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
