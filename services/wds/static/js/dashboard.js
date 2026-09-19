let map = null;

let cameraMarkers = {};

let montenegroLayer = null;

let dashboardData = {
    devices: [],
    batches: [],
    logs: []
};


// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        initializeMap();

        await loadGeoJSON();

        await refreshDashboard();

        setInterval(
            refreshDashboard,
            10000
        );

        document
            .getElementById(
                "refresh-button"
            )
            .addEventListener(
                "click",
                refreshDashboard
            );


        document
            .getElementById(
                "close-modal"
            )
            .addEventListener(
                "click",
                closeModal
            );


        document
            .getElementById(
                "device-modal"
            )
            .addEventListener(
                "click",
                event => {

                    if (
                        event.target.id ===
                        "device-modal"
                    ) {

                        closeModal();

                    }

                }
            );

    }
);


// ============================================================
// MAP
// ============================================================

function initializeMap() {

    /*
     * Montenegro center.
     *
     * This is only the initial view.
     * When GeoJSON is loaded, the map is fitted
     * to the actual boundary.
     */

    map = L.map(
        "map",
        {
            zoomControl: true,
        }
    ).setView(
        [42.7087, 19.3744],
        8
    );


    /*
     * OpenStreetMap tiles.
     */

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,

            attribution:
                '&copy; OpenStreetMap contributors'
        }
    ).addTo(
        map
    );
}


// ============================================================
// MONTENEGRO GEOJSON
// ============================================================

async function loadGeoJSON() {

    try {

        const response =
            await fetch(
                "/api/map/geojson"
            );


        if (!response.ok) {

            throw new Error(
                "Could not load GeoJSON"
            );

        }


        const geojson =
            await response.json();


        if (
            !geojson.features ||
            geojson.features.length === 0
        ) {

            console.warn(
                "No Montenegro GeoJSON loaded."
            );

            return;

        }


        montenegroLayer =
            L.geoJSON(
                geojson,
                {
                    style: {
                        color: "#475569",

                        weight: 1.5,

                        fillColor:
                            "#cbd5e1",

                        fillOpacity: 0.18
                    }
                }
            ).addTo(
                map
            );


        map.fitBounds(
            montenegroLayer.getBounds(),
            {
                padding: [20, 20]
            }
        );


    } catch (error) {

        console.error(
            "GeoJSON error:",
            error
        );

    }
}


// ============================================================
// DASHBOARD
// ============================================================

async function refreshDashboard() {

    const button =
        document.getElementById(
            "refresh-button"
        );


    button.disabled = true;

    button.textContent =
        "↻ Loading...";


    try {

        const response =
            await fetch(
                "/api/dashboard"
            );


        if (!response.ok) {

            throw new Error(
                "Dashboard request failed"
            );

        }


        dashboardData =
            await response.json();


        updateStatistics();

        updateMap();

        updateCameraList();

        updateActivity();

        updateBatchTable();

        updateSystemStatus();


        document
            .getElementById(
                "last-update"
            )
            .textContent =
            formatTime(
                new Date()
            );


    } catch (error) {

        console.error(
            "Dashboard error:",
            error
        );


        setSystemStatus(
            "Unavailable"
        );

    } finally {

        button.disabled = false;

        button.textContent =
            "↻ Refresh";

    }
}


// ============================================================
// STATISTICS
// ============================================================

function updateStatistics() {

    const devices =
        dashboardData.devices;


    const total =
        devices.length;


    const online =
        devices.filter(
            d =>
                d.status === "ONLINE"
        ).length;


    const degraded =
        devices.filter(
            d =>
                d.status === "DEGRADED"
        ).length;


    const fires =
        dashboardData.batches.filter(
            b =>
                b.prediction === "FIRE"
        ).length;


    setText(
        "total-devices",
        total
    );


    setText(
        "online-devices",
        online
    );


    setText(
        "degraded-devices",
        degraded
    );


    setText(
        "fire-detections",
        fires
    );
}


// ============================================================
// SYSTEM STATUS
// ============================================================

function updateSystemStatus() {

    const devices =
        dashboardData.devices;


    if (
        devices.length === 0
    ) {

        setSystemStatus(
            "No cameras"
        );

        return;

    }


    const offline =
        devices.filter(
            d =>
                d.status === "OFFLINE"
        ).length;


    const degraded =
        devices.filter(
            d =>
                d.status === "DEGRADED"
        ).length;


    if (offline > 0) {

        setSystemStatus(
            `${offline} camera(s) offline`
        );

        return;

    }


    if (degraded > 0) {

        setSystemStatus(
            `${degraded} camera(s) degraded`
        );

        return;

    }


    setSystemStatus(
        "Operational"
    );
}


function setSystemStatus(
    text
) {

    setText(
        "system-status-text",
        text
    );

}


// ============================================================
// MAP MARKERS
// ============================================================

function updateMap() {

    /*
     * Remove old markers.
     */

    Object.values(
        cameraMarkers
    ).forEach(
        marker => {
            map.removeLayer(
                marker
            );
        }
    );


    cameraMarkers = {};


    dashboardData.devices
        .forEach(
            device => {

                if (
                    device.latitude === null ||
                    device.longitude === null ||
                    device.latitude === undefined ||
                    device.longitude === undefined
                ) {

                    return;

                }


                const status =
                    getDeviceVisualStatus(
                        device
                    );


                const marker =
                    L.circleMarker(
                        [
                            device.latitude,
                            device.longitude
                        ],
                        {
                            radius:
                                status === "FIRE"
                                    ? 11
                                    : 8,

                            fillColor:
                                statusColor(
                                    status
                                ),

                            color: "#ffffff",

                            weight: 2,

                            fillOpacity: 0.95
                        }
                    );


                marker.bindTooltip(
                    createTooltip(
                        device,
                        status
                    ),
                    {
                        direction:
                            "top",

                        opacity: 0.95
                    }
                );


                marker.on(
                    "click",
                    () =>
                        openDevice(
                            device.device_id
                        )
                );


                marker.addTo(
                    map
                );


                cameraMarkers[
                    device.device_id
                ] = marker;

            }
        );
}


// ============================================================
// MAP TOOLTIP
// ============================================================

function createTooltip(
    device,
    visualStatus
) {

    const name =
        escapeHtml(
            device.hostname ||
            device.device_id
        );


    const state =
        escapeHtml(
            visualStatus
        );


    return `
        <strong>${name}</strong>
        <br>
        ${escapeHtml(device.device_id)}
        <br>
        Status:
        <strong>${state}</strong>
    `;
}


// ============================================================
// DEVICE VISUAL STATUS
// ============================================================

function getDeviceVisualStatus(
    device
) {

    /*
     * A FIRE result gets priority over
     * camera health for visualization.
     */

    const lastBatch =
        dashboardData.batches.find(
            batch =>
                batch.batch_id ===
                device.last_batch_id
        );


    if (
        lastBatch &&
        lastBatch.prediction ===
        "FIRE"
    ) {

        return "FIRE";

    }


    if (
        device.status ===
        "ONLINE"
    ) {

        return "ONLINE";

    }


    if (
        device.status ===
        "DEGRADED"
    ) {

        return "DEGRADED";

    }


    return "OFFLINE";
}


function statusColor(
    status
) {

    switch (status) {

        case "ONLINE":
            return "#22c55e";

        case "DEGRADED":
            return "#f59e0b";

        case "FIRE":
            return "#ef4444";

        default:
            return "#9ca3af";

    }
}


// ============================================================
// CAMERA LIST
// ============================================================

function updateCameraList() {

    const container =
        document.getElementById(
            "camera-list"
        );


    if (
        dashboardData.devices.length === 0
    ) {

        container.innerHTML = `
            <div class="empty-state">
                No registered cameras.
            </div>
        `;

        return;

    }


    container.innerHTML =
        dashboardData.devices
            .map(
                device => {

                    const status =
                        getDeviceVisualStatus(
                            device
                        );


                    return `
                        <div
                            class="camera-item"
                            onclick="openDevice('${escapeAttribute(device.device_id)}')"
                        >

                            <div
                                class="camera-status"
                                style="
                                    background:
                                    ${statusColor(status)}
                                "
                            ></div>


                            <div
                                class="camera-info"
                            >

                                <div
                                    class="camera-name"
                                >
                                    ${escapeHtml(
                                        device.hostname ||
                                        device.device_id
                                    )}
                                </div>

                                <div
                                    class="camera-id"
                                >
                                    ${escapeHtml(
                                        device.device_id
                                    )}
                                </div>

                            </div>


                            <div
                                class="camera-state"
                                style="
                                    color:
                                    ${statusColor(status)}
                                "
                            >
                                ${status}
                            </div>

                        </div>
                    `;

                }
            )
            .join("");
}


// ============================================================
// ACTIVITY
// ============================================================

function updateActivity() {

    const container =
        document.getElementById(
            "activity-list"
        );


    if (
        dashboardData.logs.length === 0
    ) {

        container.innerHTML = `
            <div class="empty-state">
                No recent activity.
            </div>
        `;

        return;

    }


    container.innerHTML =
        dashboardData.logs
            .slice(0, 20)
            .map(
                log => {

                    const level =
                        log.level ||
                        "INFO";


                    return `
                        <div
                            class="activity-item"
                        >

                            <div
                                class="
                                    activity-level
                                    ${escapeAttribute(level)}
                                "
                            ></div>


                            <div>

                                <div
                                    class="activity-message"
                                >
                                    ${escapeHtml(
                                        log.message
                                    )}
                                </div>


                                <div
                                    class="activity-time"
                                >
                                    ${formatDate(
                                        log.created_at
                                    )}

                                    ${
                                        log.device_id
                                            ? " · " +
                                              escapeHtml(
                                                  log.device_id
                                              )
                                            : ""
                                    }

                                </div>

                            </div>

                        </div>
                    `;

                }
            )
            .join("");
}


// ============================================================
// BATCH TABLE
// ============================================================

function updateBatchTable() {

    const table =
        document.getElementById(
            "batch-table"
        );


    if (
        dashboardData.batches.length === 0
    ) {

        table.innerHTML = `
            <tr>
                <td
                    colspan="6"
                    class="empty-state"
                >
                    No batches processed yet.
                </td>
            </tr>
        `;

        return;

    }


    table.innerHTML =
        dashboardData.batches
            .slice(0, 20)
            .map(
                batch => {

                    const prediction =
                        batch.prediction ||
                        "UNKNOWN";


                    const predictionClass =
                        prediction === "FIRE"
                            ? "fire"
                            : prediction ===
                              "NON_FIRE"
                                ? "non-fire"
                                : "unknown";


                    const confidence =
                        batch.confidence !==
                        null &&
                        batch.confidence !==
                        undefined
                            ? `${(
                                batch.confidence *
                                100
                              ).toFixed(1)}%`
                            : "—";


                    return `
                        <tr>

                            <td>
                                ${escapeHtml(
                                    batch.device_id
                                )}
                            </td>

                            <td>
                                ${escapeHtml(
                                    batch.batch_id
                                )}
                            </td>

                            <td>
                                ${formatDate(
                                    batch.created_at
                                )}
                            </td>

                            <td>

                                <span
                                    class="
                                        result
                                        ${predictionClass}
                                    "
                                >
                                    ${
                                        prediction ===
                                        "FIRE"
                                            ? "🔥"
                                            : "✓"
                                    }

                                    ${escapeHtml(
                                        prediction
                                    )}

                                </span>

                            </td>

                            <td>
                                ${confidence}
                            </td>

                            <td>
                                ${escapeHtml(
                                    batch.status ||
                                    "UNKNOWN"
                                )}
                            </td>

                        </tr>
                    `;

                }
            )
            .join("");
}


// ============================================================
// DEVICE MODAL
// ============================================================

async function openDevice(
    deviceId
) {

    const modal =
        document.getElementById(
            "device-modal"
        );


    const body =
        document.getElementById(
            "modal-body"
        );


    modal.classList.remove(
        "hidden"
    );


    body.innerHTML = `
        <div class="empty-state">
            Loading camera information...
        </div>
    `;


    try {

        const response =
            await fetch(
                `/api/devices/${encodeURIComponent(deviceId)}`
            );


        if (!response.ok) {

            throw new Error(
                "Device request failed"
            );

        }


        const data =
            await response.json();


        renderDeviceModal(
            data
        );


    } catch (error) {

        body.innerHTML = `
            <div class="empty-state">
                Could not load camera information.
            </div>
        `;

        console.error(
            error
        );

    }
}


function renderDeviceModal(
    data
) {

    const device =
        data.device;


    const batches =
        data.batches || [];


    const lastBatch =
        batches.length > 0
            ? batches[0]
            : null;


    const lastImage =
        device.last_image;


    const body =
        document.getElementById(
            "modal-body"
        );


    let imageHtml = "";


    /*
     * Images are stored in the shared
     * storage volume.
     *
     * WDS exposes /storage below.
     */

    if (
        lastImage &&
        lastImage.storage_path
    ) {

        imageHtml = `
            <img
                class="latest-image"
                src="/storage/${encodeURI(
                    lastImage.storage_path
                )}"
                alt="Latest camera image"
                onerror="
                    this.style.display='none'
                "
            >
        `;

    }


    body.innerHTML = `

        <h2
            class="modal-title"
        >
            ${escapeHtml(
                device.hostname ||
                device.device_id
            )}
        </h2>


        <div
            class="modal-subtitle"
        >
            ${escapeHtml(
                device.device_id
            )}
        </div>


        <div
            class="detail-grid"
        >

            <div
                class="detail-item"
            >

                <span>
                    Health
                </span>

                <strong>
                    ${escapeHtml(
                        device.status ||
                        "UNKNOWN"
                    )}
                </strong>

            </div>


            <div
                class="detail-item"
            >

                <span>
                    Camera
                </span>

                <strong>
                    ${escapeHtml(
                        device.camera_model ||
                        "Unknown"
                    )}
                </strong>

            </div>


            <div
                class="detail-item"
            >

                <span>
                    CPU
                </span>

                <strong>
                    ${formatNumber(
                        device.last_health?.cpu_usage_percent
                    )}
                    %
                </strong>

            </div>


            <div
                class="detail-item"
            >

                <span>
                    Temperature
                </span>

                <strong>
                    ${formatNumber(
                        device.last_health?.temperature_celsius
                    )}
                    °C
                </strong>

            </div>


            <div
                class="detail-item"
            >

                <span>
                    Memory
                </span>

                <strong>
                    ${formatNumber(
                        device.last_health?.memory_usage_percent
                    )}
                    %
                </strong>

            </div>


            <div
                class="detail-item"
            >

                <span>
                    Camera availability
                </span>

                <strong>
                    ${
                        device.last_health?.camera_available
                            ? "Available"
                            : "Unavailable"
                    }
                </strong>

            </div>

        </div>


        ${
            lastBatch
                ? `
                    <div
                        class="detail-grid"
                    >

                        <div
                            class="detail-item"
                        >

                            <span>
                                Latest prediction
                            </span>

                            <strong>
                                ${escapeHtml(
                                    lastBatch.prediction ||
                                    "—"
                                )}
                            </strong>

                        </div>


                        <div
                            class="detail-item"
                        >

                            <span>
                                Confidence
                            </span>

                            <strong>
                                ${
                                    lastBatch.confidence !==
                                    null &&
                                    lastBatch.confidence !==
                                    undefined
                                        ? (
                                            lastBatch.confidence *
                                            100
                                          ).toFixed(1) +
                                          "%"
                                        : "—"
                                }
                            </strong>

                        </div>

                    </div>
                `
                : ""
        }


        ${
            imageHtml
                ? `
                    <h3>
                        Latest Image
                    </h3>

                    ${imageHtml}
                `
                : `
                    <div class="empty-state">
                        No image available.
                    </div>
                `
        }

    `;
}


function closeModal() {

    document
        .getElementById(
            "device-modal"
        )
        .classList.add(
            "hidden"
        );
}


// ============================================================
// HELPERS
// ============================================================

function setText(
    id,
    value
) {

    const element =
        document.getElementById(
            id
        );


    if (element) {

        element.textContent =
            value;

    }
}


function formatDate(
    value
) {

    if (!value) {

        return "—";

    }


    const date =
        new Date(value);


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return value;

    }


    return date.toLocaleString();
}


function formatTime(
    date
) {

    return date.toLocaleTimeString();

}


function formatNumber(
    value
) {

    if (
        value === undefined ||
        value === null
    ) {

        return "—";

    }


    return Number(
        value
    ).toFixed(1);
}


function escapeHtml(
    value
) {

    if (
        value === undefined ||
        value === null
    ) {

        return "";

    }


    return String(value)
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}


function escapeAttribute(
    value
) {

    return escapeHtml(
        value
    )
    .replaceAll(
        "`",
        ""
    );
}