import * as THREE from 'three';

export class SceneSetup {
    constructor(container) {
        this.container = container;
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a2e); // Dark blue night sky

        this.camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 1000); // Narrower FOV for better focus
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.appendChild(this.renderer.domElement);

        this.initLights();
        this.initEnvironment();
    }

    initLights() {
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
        directionalLight.position.set(10, 20, 10);
        this.scene.add(directionalLight);
    }

    initEnvironment() {
        // Ground
        const groundGeo = new THREE.PlaneGeometry(100, 100);
        const groundMat = new THREE.MeshStandardMaterial({ color: 0x228b22 }); // Forest Green
        const ground = new THREE.Mesh(groundGeo, groundMat);
        ground.rotation.x = -Math.PI / 2;
        this.scene.add(ground);

        // Mound
        const moundGeo = new THREE.CylinderGeometry(2, 2.5, 0.2, 32);
        const moundMat = new THREE.MeshStandardMaterial({ color: 0x8b4513 });
        const mound = new THREE.Mesh(moundGeo, moundMat);
        mound.position.set(0, 0.1, 0);
        this.scene.add(mound);

        // Catcher's Glow / Target Area - Enlarged for better visibility
        const strikeZoneGeo = new THREE.BoxGeometry(1.2, 1.8, 0.05); // Bigger strike zone
        const strikeZoneMat = new THREE.MeshStandardMaterial({
            color: 0x00f2fe,
            transparent: true,
            opacity: 0.3,
            emissive: 0x00f2fe,
            emissiveIntensity: 0.5,
            metalness: 0.8,
            roughness: 0.2
        });
        const strikeZone = new THREE.Mesh(strikeZoneGeo, strikeZoneMat);
        strikeZone.position.set(0, 1.5, -18.44);
        this.scene.add(strikeZone);

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
        const mat = new THREE.MeshStandardMaterial({ color: 0xffffff });
        // Add texture or lines later
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
