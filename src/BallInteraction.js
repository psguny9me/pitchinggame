export class BallInteraction {
    constructor(canvas, onRelease) {
        this.canvas = canvas;
        this.onRelease = onRelease;

        this.isTouching = false;
        this.touches = new Map(); // Store touch start positions
        this.startTime = 0;

        this.lastTouchPos = null;
        this.lastVelocity = { x: 0, y: 0 };
        this.spinIntensity = 0;
        this.velocity = { x: 0, y: 0 };

        this.gaugeValue = 0;
        this.gaugeInterval = null;

        this.init();
    }

    init() {
        this.canvas.addEventListener('touchstart', (e) => this.handleStart(e), { passive: false });
        this.canvas.addEventListener('touchmove', (e) => this.handleMove(e), { passive: false });
        this.canvas.addEventListener('touchend', (e) => this.handleEnd(e), { passive: false });
    }

    handleStart(e) {
        e.preventDefault();
        if (this.isTouching) return;

        this.isTouching = true;
        this.startTime = Date.now();

        for (let i = 0; i < e.touches.length; i++) {
            const touch = e.touches[i];
            this.touches.set(touch.identifier, {
                x: touch.clientX,
                y: touch.clientY,
                startTime: Date.now()
            });
        }

        this.startGauge();
    }

    handleMove(e) {
        e.preventDefault();
        if (!this.isTouching) return;

        const touch = e.touches[0];
        if (this.lastTouchPos) {
            this.lastVelocity = {
                x: touch.clientX - this.lastTouchPos.x,
                y: touch.clientY - this.lastTouchPos.y
            };
        }
        this.lastTouchPos = { x: touch.clientX, y: touch.clientY };

        // Multi-touch spin logic
        if (e.touches.length >= 2) {
            const t1 = e.touches[0];
            const t2 = e.touches[1];
            const dist = Math.hypot(t1.clientX - t2.clientX, t1.clientY - t2.clientY);
            this.spinIntensity = dist / 100;
        }
    }

    handleEnd(e) {
        e.preventDefault();
        if (!this.isTouching) return;

        if (e.touches.length === 0) {
            this.isTouching = false;
            this.stopGauge();

            const vX = this.lastVelocity.x * 0.15;
            const vY = -this.lastVelocity.y * 0.15; // Screen to World
            const vZ = -Math.max(15, Math.abs(this.lastVelocity.y) * 0.25); // Z depth

            const spinMag = Math.abs(this.lastVelocity.x) * 2 + this.spinIntensity * 100;
            const spinX = (Math.random() - 0.5) * spinMag;
            const spinY = (Math.random() - 0.5) * spinMag;
            const spinZ = (Math.random() - 0.5) * spinMag;

            this.onRelease({
                velocity: { x: vX, y: vY, z: vZ },
                spin: { x: spinX, y: spinY, z: spinZ },
                releasePoint: this.gaugeValue
            });

            this.gaugeValue = 0;
            this.updateGaugeUI();
            this.lastVelocity = { x: 0, y: 0 };
        }
    }

    startGauge() {
        this.gaugeValue = 0;
        this.gaugeInterval = setInterval(() => {
            this.gaugeValue += 0.05;
            if (this.gaugeValue > 1) this.gaugeValue = 1;
            this.updateGaugeUI();
        }, 50);
    }

    stopGauge() {
        clearInterval(this.gaugeInterval);
    }

    updateGaugeUI() {
        const gaugeElem = document.getElementById('release-gauge');
        if (gaugeElem) {
            gaugeElem.style.height = `${this.gaugeValue * 100}%`;
        }
    }
}
