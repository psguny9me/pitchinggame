import * as THREE from 'three';
import { SceneSetup } from './SceneSetup';
import { Physics } from './Physics';
import { BallInteraction } from './BallInteraction';

class Game {
  constructor() {
    this.container = document.getElementById('app');
    this.sceneSetup = new SceneSetup(this.container);
    this.physics = new Physics();

    this.ballBody = this.physics.initBall();
    this.ballMesh = this.sceneSetup.createBallMesh(this.physics.ballRadius);
    this.impactMarker = this.sceneSetup.createImpactMarker();

    this.state = 'WAIT'; // WAIT, FLYING, RESULT
    this.streak = 0;
    this.balls = 0;

    this.interaction = new BallInteraction(this.sceneSetup.renderer.domElement, (data) => this.throwBall(data));

    window.addEventListener('resize', () => this.sceneSetup.onWindowResize());

    this.lastTime = performance.now();
    this.animate();

    this.resetGame();
  }

  resetGame() {
    this.state = 'WAIT';
    this.physics.resetBall(new THREE.Vector3(0, 1.2, 1)); // Start closer to camera for 30% look
    this.updateStats('-', '-');
    this.impactMarker.visible = false;
    this.impactMarker.rotation.x = 0; // Reset to face the camera
  }

  throwBall(data) {
    if (this.state !== 'WAIT') return;

    this.state = 'FLYING';

    // Velocity from interaction (simplified mapping)
    this.ballBody.velocity.set(data.velocity.x, data.velocity.y, data.velocity.z);
    this.ballBody.angularVelocity.set(data.spin.x, data.spin.y, data.spin.z);

    // Show speed and spin in UI
    const speedKmh = Math.round(Math.abs(data.velocity.z) * 3.6 * 2); // Factor to make it feel like baseball speeds
    const spinRpm = Math.round(Math.sqrt(data.spin.x ** 2 + data.spin.y ** 2 + data.spin.z ** 2) * 60);
    this.updateStats(speedKmh, spinRpm);
  }

  updateStats(speed, spin) {
    document.getElementById('speed-text').innerText = `SPEED: ${speed} km/h`;
    document.getElementById('spin-text').innerText = `SPIN: ${spin} RPM`;
  }

  checkResult() {
    const ballPos = this.ballBody.position;
    const targetZ = -18.44;

    if (ballPos.z <= targetZ && this.state === 'FLYING') {
      this.state = 'RESULT';

      // Show impact marker
      this.impactMarker.position.set(ballPos.x, ballPos.y, targetZ + 0.1);
      this.impactMarker.visible = true;

      // Updated Strike zone: x: [-0.6, 0.6], y: [0.6, 2.4] based on size (1.2x1.8)
      const isStrike = (
        ballPos.x >= -0.6 && ballPos.x <= 0.6 &&
        ballPos.y >= 0.6 && ballPos.y <= 2.4
      );

      this.showResult(isStrike);

      setTimeout(() => {
        this.resetGame();
      }, 3000);
    } else if (ballPos.y < this.physics.ballRadius || ballPos.z < -25) {
      // Ball touched the ground or missed the target area entirely
      if (this.state === 'FLYING') {
        this.state = 'RESULT';

        // If it hit the ground, show impact marker on the ground
        if (ballPos.y < this.physics.ballRadius) {
          this.impactMarker.position.set(ballPos.x, 0.01, ballPos.z);
          this.impactMarker.rotation.x = -Math.PI / 2; // Flat on ground
          this.impactMarker.visible = true;
        }

        this.showResult(false);
        setTimeout(() => this.resetGame(), 2000);
      }
    }
  }

  showResult(isStrike) {
    const msgOverlay = document.getElementById('message-overlay');
    msgOverlay.innerText = isStrike ? 'STRIKE!' : 'BALL';
    msgOverlay.style.color = isStrike ? '#ff4d4d' : '#4d94ff';
    msgOverlay.style.opacity = 1;

    if (isStrike) {
      this.streak++;
    } else {
      this.streak = 0;
      this.balls++;
    }

    document.getElementById('streak-count').innerText = this.streak;

    setTimeout(() => {
      msgOverlay.style.opacity = 0;
    }, 1500);
  }

  animate() {
    requestAnimationFrame(() => this.animate());

    const now = performance.now();
    const dt = (now - this.lastTime) / 1000;
    this.lastTime = now;

    if (this.state === 'FLYING') {
      this.physics.update(dt);
      this.checkResult();
    }

    // Sync Mesh with Physics Body
    this.ballMesh.position.copy(this.ballBody.position);
    this.ballMesh.quaternion.copy(this.ballBody.quaternion);

    this.sceneSetup.renderer.render(this.sceneSetup.scene, this.sceneSetup.camera);
  }
}

new Game();
