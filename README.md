# Pitching Simulation Game

A high-fidelity 3D baseball pitching simulation built with Three.js and Cannon-es.

## Features
- **Realistic Physics**: Magnus effect and air resistance simulation.
- **Multi-touch Controls**: Swipe speed and finger count determine pitch speed and spin.
- **Release Point System**: Timed release gauge to control pitch accuracy (Early=High, Late=Low).
- **Mobile Optimized**: Custom rendering for mobile Safari and Chrome compatibility.

## How to Play
1. Touch the ball and hold to start the arm swing (gauge starts filling).
2. Swipe upwards to throw.
3. Release (lift finger) when the gauge is near the **Gold Sweet Spot (~85%)** for maximum accuracy.
4. Try to get as many consecutive strikes as possible!

## Tech Stack
- [Three.js](https://threejs.org/) (Rendering)
- [Cannon-es](https://github.com/pmndrs/cannon-es) (Physics Engine)
- Vite (Build Tool)
