import * as THREE from 'three';

export class SceneSetup {
    constructor(container) {
        this.container = container;
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x334466); // Brighter blue sky

        this.camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 1000);
        // Narrower FOV for better focus
        this.renderer = new THREE.WebGLRenderer({
            antialias: false,
            alpha: false,
            powerPreference: 'high-performance'
        });
        this.renderer.setClearColor(0x334466, 1);
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // Limit pixel ratio for mobile performance
        this.container.appendChild(this.renderer.domElement);

        console.log("Renderer initialized: ", window.innerWidth, "x", window.innerHeight);

        this.initLights();
        this.initEnvironment();
    }

    initLights() {
        // High intensity ambient light to ensure visibility
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
        this.scene.add(ambientLight);

        // Hemisphere light provides a nice sky/ground gradient fill
        const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 1.0);
        this.scene.add(hemiLight);

        const spotLight = new THREE.SpotLight(0xffffff, 2.0);
        spotLight.position.set(10, 20, 10);
        this.scene.add(spotLight);
    }

    initEnvironment() {
        // Ground - using MeshBasicMaterial to ensure it shows up without lighting
        const groundGeo = new THREE.PlaneGeometry(100, 100);
        const groundMat = new THREE.MeshBasicMaterial({ color: 0x44aa44 });
        const ground = new THREE.Mesh(groundGeo, groundMat);
        ground.rotation.x = -Math.PI / 2;
        this.scene.add(ground);

        // Debug Cube - Very bright, should be visible even if lights fail
        const testGeo = new THREE.BoxGeometry(1, 1, 1);
        const testMat = new THREE.MeshBasicMaterial({ color: 0xff00ff });
        const testCube = new THREE.Mesh(testGeo, testMat);
        testCube.position.set(-2, 0.5, -5);
        this.scene.add(testCube);

        // Mound - MeshBasicMaterial
        const moundGeo = new THREE.CylinderGeometry(2, 2.5, 0.2, 32);
        const moundMat = new THREE.MeshBasicMaterial({ color: 0x8b4513 });
        const mound = new THREE.Mesh(moundGeo, moundMat);
        mound.position.set(0, 0.1, 0);
        this.scene.add(mound);

        // Catcher's Glow / Target Area - MeshBasicMaterial for guaranteed visibility
        const strikeZoneGeo = new THREE.BoxGeometry(1.2, 1.8, 0.05);
        const strikeZoneMat = new THREE.MeshBasicMaterial({
            color: 0x00f2fe,
            transparent: true,
            opacity: 0.4
        });
        const strikeZone = new THREE.Mesh(strikeZoneGeo, strikeZoneMat);
        strikeZone.position.set(0, 1.5, -18.44);
        this.scene.add(strikeZone);

        // Strike Zone Frame
        const edges = new THREE.EdgesGeometry(strikeZoneGeo);
        const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x00f2fe }));
        strikeZone.add(line);

        this.strikeZone = strikeZone;

        // Camera initial position - moved closer for "zoom" feel
        this.camera.position.set(0, 1.5, 3.5);
    }

    createImpactMarker() {
        const geo = new THREE.RingGeometry(0.1, 0.15, 32);
        const mat = new THREE.MeshBasicMaterial({ color: 0xff4d4d, side: THREE.DoubleSide });
        const marker = new THREE.Mesh(geo, mat);
        marker.rotation.x = 0; // Face the pitcher
        marker.visible = false;
        this.scene.add(marker);
        return marker;
    }

    createBallMesh(radius) {
        const geo = new THREE.SphereGeometry(radius, 32, 32);
        const mat = new THREE.MeshBasicMaterial({ color: 0xffffff });
        const mesh = new THREE.Mesh(geo, mat);
        this.scene.add(mesh);
        return mesh;
    }

    onWindowResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }
}
