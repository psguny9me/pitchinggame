import * as THREE from 'https://esm.sh/three@0.160.0';
import { SceneSetup } from './SceneSetup';
import { Physics } from './Physics';
import { BallInteraction } from './BallInteraction';

alert("MAIN.JS LOADED - STARTING ENGINE...");
console.log("Main.js Entry point hit");

class Game {
  constructor() {
    console.log("Game Constructor Started");
    const jsCheck = document.getElementById('js-check');
    if (jsCheck) {
      jsCheck.innerText = "JS STATUS: RUNNING (v5)";
      jsCheck.style.background = "orange";
    }

    try {
      console.log("Initializing Scene...");
      alert("STEP 1: INITIALIZING SCENE...");
      this.container = document.getElementById('app');
      this.sceneSetup = new SceneSetup(this.container);

      alert("STEP 2: INITIALIZING PHYSICS...");
      console.log("Initializing Physics...");
      this.physics = new Physics();

      alert("STEP 3: CREATING BALL...");
      console.log("Creating Ball...");
      this.ballBody = this.physics.initBall();
      this.ballMesh = this.sceneSetup.createBallMesh(this.physics.ballRadius);
      this.impactMarker = this.sceneSetup.createImpactMarker();

      this.state = 'WAIT';
      this.streak = 0;
      this.balls = 0;

      alert("STEP 4: INTERACTION...");
      console.log("Setting up Interaction...");
      this.interaction = new BallInteraction(this.sceneSetup.renderer.domElement, (data) => this.throwBall(data));

      window.addEventListener('resize', () => this.sceneSetup.onWindowResize());

      this.lastTime = performance.now();
      console.log("Starting Animation Loop...");
      this.animate();

      this.resetGame();

      if (jsCheck) {
        jsCheck.innerText = "JS STATUS: OK (v5 active)";
        jsCheck.style.background = "green";
      }
    } catch (e) {
      console.error("Game Init Error: ", e);
      if (jsCheck) {
        jsCheck.innerText = "CRITICAL ERROR: " + e.message;
        jsCheck.style.background = "red";
      }
      alert("Critical Game Error: " + e.message);
    }
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

    // Release accuracy logic - Sweet Spot 0.85
    const sweetSpot = 0.85;
    const diff = data.releasePoint - sweetSpot; // negative = early, positive = late
    const accuracyError = Math.abs(diff);

    // Simulation accuracy:
    // Early release (diff < 0) -> Ball tends to stay HIGH
    // Late release (diff > 0) -> Ball tends to sink LOW
    const verticalPenalty = -diff * 30; // Early release (+Y), Late release (-Y)
    const horizontalPenalty = (Math.random() - 0.5) * accuracyError * 10;

    // Velocity from interaction + penalty
    const finalVX = data.velocity.x + horizontalPenalty;
    const finalVY = data.velocity.y + verticalPenalty;
    const finalVZ = data.velocity.z;

    this.ballBody.velocity.set(finalVX, finalVY, finalVZ);
    this.ballBody.angularVelocity.set(data.spin.x, data.spin.y, data.spin.z);

    // Show speed and spin in UI
    const speedKmh = Math.round(Math.abs(data.velocity.z) * 3.6 * 2.5);
    const spinRpm = Math.round(Math.sqrt(data.spin.x ** 2 + data.spin.y ** 2 + data.spin.z ** 2) * 60);
    this.updateStats(speedKmh, spinRpm);

    // Visual feedback for release timing
    this.showReleaseFeedback(accuracyError, diff);
  }

  showReleaseFeedback(error, diff) {
    const msgOverlay = document.getElementById('message-overlay');
    let text = 'PERFECT!';
    let color = '#ffd700';

    if (error > 0.15) {
      text = diff < 0 ? 'EARLY (HIGH)' : 'LATE (LOW)';
      color = '#ff4d4d';
    } else if (error > 0.05) {
      text = 'GOOD';
      color = '#4facfe';
    }

    msgOverlay.innerText = text;
    msgOverlay.style.color = color;
    msgOverlay.style.opacity = 1;

    setTimeout(() => {
      if (this.state === 'FLYING') msgOverlay.style.opacity = 0;
    }, 800);
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
