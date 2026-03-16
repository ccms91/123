/**
 * qr_scanner.js
 * Reusable camera-based QR code scanner for clinic station apps.
 * Uses jsQR library (loaded via CDN in the HTML).
 *
 * Usage:
 *   QRScanner.start(onResultCallback)
 *   QRScanner.stop()
 *
 * onResultCallback receives the raw decoded QR string.
 */

const QRScanner = (() => {
    let video = null;
    let canvas = null;
    let ctx = null;
    let animationId = null;
    let onResult = null;
    let overlay = null;

    function _buildUI() {
        // Overlay backdrop
        overlay = document.createElement("div");
        overlay.id = "qr-overlay";
        overlay.innerHTML = `
            <div id="qr-modal">
                <p id="qr-label">Point camera at QR code</p>
                <div id="qr-viewport">
                    <video id="qr-video" playsinline autoplay muted></video>
                    <canvas id="qr-canvas"></canvas>
                    <div id="qr-crosshair"></div>
                </div>
                <button id="qr-cancel">Cancel</button>
            </div>
        `;

        const style = document.createElement("style");
        style.textContent = `
            #qr-overlay {
                position: fixed; inset: 0;
                background: rgba(0,0,0,0.85);
                display: flex; align-items: center; justify-content: center;
                z-index: 9999;
            }
            #qr-modal {
                background: #1a1a2e;
                border-radius: 16px;
                padding: 20px;
                width: min(95vw, 420px);
                display: flex; flex-direction: column; align-items: center; gap: 16px;
            }
            #qr-label {
                color: #fff; font-size: 16px; margin: 0; font-family: sans-serif;
            }
            #qr-viewport {
                position: relative;
                width: 100%; aspect-ratio: 1;
                border-radius: 12px; overflow: hidden;
                background: #000;
            }
            #qr-video {
                width: 100%; height: 100%;
                object-fit: cover; display: block;
            }
            #qr-canvas { display: none; }
            #qr-crosshair {
                position: absolute;
                inset: 15%;
                border: 3px solid rgba(255,255,255,0.8);
                border-radius: 8px;
                box-shadow: 0 0 0 2000px rgba(0,0,0,0.3);
                pointer-events: none;
            }
            #qr-cancel {
                background: #e74c3c; color: #fff;
                border: none; border-radius: 8px;
                padding: 12px 32px; font-size: 16px; cursor: pointer;
                font-family: sans-serif;
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(overlay);

        video = document.getElementById("qr-video");
        canvas = document.getElementById("qr-canvas");
        ctx = canvas.getContext("2d", { willReadFrequently: true });

        document.getElementById("qr-cancel").addEventListener("click", stop);
    }

    function _scan() {
        if (!video || video.readyState !== video.HAVE_ENOUGH_DATA) {
            animationId = requestAnimationFrame(_scan);
            return;
        }
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const code = jsQR(imageData.data, imageData.width, imageData.height, {
            inversionAttempts: "dontInvert",
        });

        if (code && code.data) {
            // Flash the crosshair green on success
            const crosshair = document.getElementById("qr-crosshair");
            if (crosshair) crosshair.style.borderColor = "#2ecc71";

            stop();
            if (onResult) onResult(code.data);
        } else {
            animationId = requestAnimationFrame(_scan);
        }
    }

    async function start(callback) {
        onResult = callback;
        _buildUI();

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment" }, // rear camera on Android
                audio: false,
            });
            video.srcObject = stream;
            video.play();
            animationId = requestAnimationFrame(_scan);
        } catch (err) {
            stop();
            // Camera not available - tell the caller
            const msg = err.name === "NotAllowedError"
                ? "Camera permission denied. Please allow camera access in your browser settings."
                : "Camera not available. Please enter the QR data manually.";
            throw new Error(msg);
        }
    }

    function stop() {
        if (animationId) cancelAnimationFrame(animationId);
        if (video && video.srcObject) {
            video.srcObject.getTracks().forEach(t => t.stop());
            video.srcObject = null;
        }
        if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
        overlay = null; video = null; canvas = null; ctx = null;
    }

    return { start, stop };
})();
