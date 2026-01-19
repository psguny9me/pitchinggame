import * as CANNON from 'cannon-es';

export class Physics {
    constructor() {
        this.world = new CANNON.World();
        this.world.gravity.set(0, -9.81, 0); // Ground is Y-up in Three.js default if we set it so

        this.ballBody = null;
        this.dragCoefficient = 0.3; // Approx for baseball
        this.magnusCoefficient = 0.0005; // Tuning parameter for spin effect
        this.airDensity = 1.225;
        this.ballRadius = 0.3; // Increased from 0.0366 for visual emphasis (30% screen request)
        this.ballArea = Math.PI * Math.pow(this.ballRadius, 2);
    }

    initBall() {
        const shape = new CANNON.Sphere(this.ballRadius);
        this.ballBody = new CANNON.Body({
            mass: 0.145, // 145g
            shape: shape,
            linearDamping: 0,
            angularDamping: 0.1
        });

        this.world.addBody(this.ballBody);
        return this.ballBody;
    }

    applyForces() {
        if (!this.ballBody) return;

        const v = this.ballBody.velocity;
        const w = this.ballBody.angularVelocity;
        const speed = v.length();

        if (speed < 0.1) return;

        // 1. Drag Force: Fd = -0.5 * rho * v^2 * Cd * A * unit(v)
        const dragMagnitude = 0.5 * this.airDensity * Math.pow(speed, 2) * this.dragCoefficient * this.ballArea;
        const dragForce = v.scale(-1).unit().scale(dragMagnitude);
        this.ballBody.applyForce(dragForce, this.ballBody.position);

        // 2. Magnus Effect: Fm = S * (w x v)
        // Cannon.js Vec3 cross product
        const magnusForce = w.cross(v).scale(this.magnusCoefficient);
        this.ballBody.applyForce(magnusForce, this.ballBody.position);
    }

    update(dt) {
        this.applyForces();
        this.world.step(dt);
    }

    resetBall(position) {
        this.ballBody.position.copy(position);
        this.ballBody.velocity.set(0, 0, 0);
        this.ballBody.angularVelocity.set(0, 0, 0);
        this.ballBody.force.set(0, 0, 0);
        this.ballBody.torque.set(0, 0, 0);
    }
}
