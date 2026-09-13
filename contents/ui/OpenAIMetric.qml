import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

Item {
    id: metric
    required property real percent
    property string style: "text"
    readonly property color usageColor: percent < 50 ? Kirigami.Theme.positiveTextColor : percent < 80 ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.negativeTextColor
    implicitWidth: style === "text" ? textRow.implicitWidth : style === "bar" ? 32 : 28
    implicitHeight: style === "text" ? textRow.implicitHeight : 28

    RowLayout {
        id: textRow
        anchors.centerIn: parent
        visible: metric.style === "text"
        spacing: Kirigami.Units.smallSpacing
        Rectangle { implicitWidth: 10; implicitHeight: 10; radius: 5; color: metric.usageColor }
        PlasmaComponents.Label { text: Math.round(metric.percent) + "%"; font.bold: true }
    }
    Canvas {
        id: ring
        anchors.fill: parent
        visible: metric.style === "circular"
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.lineWidth = 3
            ctx.strokeStyle = Kirigami.Theme.disabledTextColor
            ctx.globalAlpha = 0.3
            ctx.beginPath()
            ctx.arc(width / 2, height / 2, Math.min(width, height) / 2 - 2, 0, 2 * Math.PI)
            ctx.stroke()
            if (metric.percent > 0) {
                ctx.globalAlpha = 1
                ctx.strokeStyle = metric.usageColor
                ctx.lineCap = "round"
                ctx.beginPath()
                ctx.arc(width / 2, height / 2, Math.min(width, height) / 2 - 2, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * metric.percent / 100)
                ctx.stroke()
            }
        }
        onVisibleChanged: requestPaint()
    }
    Rectangle {
        anchors.fill: parent
        visible: metric.style === "bar"
        radius: 3
        color: Kirigami.Theme.backgroundColor
        border.color: Kirigami.Theme.disabledTextColor
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 1
            height: (parent.height - 2) * metric.percent / 100
            radius: 2
            color: metric.usageColor
        }
    }
    PlasmaComponents.Label {
        visible: metric.style !== "text"
        anchors.centerIn: parent
        text: Math.round(metric.percent)
        font.pixelSize: 9
        font.bold: true
    }
    onPercentChanged: ring.requestPaint()
    onUsageColorChanged: ring.requestPaint()
}
