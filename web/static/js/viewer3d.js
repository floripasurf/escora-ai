/**
 * HouseViewer3D — Three.js viewer for masonry house preview.
 *
 * Consumes the same JSON returned by POST /api/v1/design/preview
 * and renders extruded walls, floor, and roof with orbit controls.
 */

import * as THREE from 'https://unpkg.com/three@0.160.0/build/three.module.js';
import { OrbitControls } from 'https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js';

export class HouseViewer3D {
    constructor(container) {
        this.container = container;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.houseGroup = null;
        this._init();
    }

    _init() {
        const w = this.container.clientWidth;
        const h = this.container.clientHeight || 400;

        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x111114);

        // Camera
        this.camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 200);
        this.camera.position.set(15, 12, 15);
        this.camera.lookAt(0, 0, 0);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(w, h);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.shadowMap.enabled = true;
        this.container.appendChild(this.renderer.domElement);

        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.08;
        this.controls.minDistance = 3;
        this.controls.maxDistance = 60;
        this.controls.maxPolarAngle = Math.PI / 2.1;

        // Lights
        const ambient = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambient);

        const sun = new THREE.DirectionalLight(0xffffff, 0.8);
        sun.position.set(10, 15, 8);
        sun.castShadow = true;
        this.scene.add(sun);

        // Ground grid
        const grid = new THREE.GridHelper(40, 40, 0x26262E, 0x1A1A20);
        this.scene.add(grid);

        // House group
        this.houseGroup = new THREE.Group();
        this.scene.add(this.houseGroup);

        // Resize
        window.addEventListener('resize', () => this._onResize());

        // Animate
        this._animate();
    }

    _onResize() {
        const w = this.container.clientWidth;
        const h = this.container.clientHeight || 400;
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
    }

    _animate() {
        requestAnimationFrame(() => this._animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    /**
     * Load preview JSON and build 3D geometry.
     */
    loadFromPreview(preview) {
        // Clear previous
        while (this.houseGroup.children.length) {
            const child = this.houseGroup.children[0];
            this.houseGroup.remove(child);
            if (child.geometry) child.geometry.dispose();
            if (child.material) child.material.dispose();
        }

        const W = preview.width_m || 8;
        const D = preview.depth_m || 10;
        const ceilingH = preview.ceiling_height_m || 2.80;
        const roofStyle = preview.roof_style || 'gable';

        // Center offset
        const cx = W / 2;
        const cz = D / 2;

        // Materials
        const wallMat = new THREE.MeshLambertMaterial({ color: 0xE8E4DE });
        const wallStructMat = new THREE.MeshLambertMaterial({ color: 0xD5CFC5 });
        const floorMat = new THREE.MeshLambertMaterial({ color: 0x888888 });
        const roofMat = new THREE.MeshLambertMaterial({ color: 0xB85C38, side: THREE.DoubleSide });
        const doorMat = new THREE.MeshLambertMaterial({ color: 0x5C3A1E });
        const windowMat = new THREE.MeshLambertMaterial({
            color: 0x87CEEB, transparent: true, opacity: 0.5,
        });

        // 1. Floor slab
        const floorGeo = new THREE.BoxGeometry(W, 0.10, D);
        const floor = new THREE.Mesh(floorGeo, floorMat);
        floor.position.set(0, -0.05, 0);
        floor.receiveShadow = true;
        this.houseGroup.add(floor);

        // 2. Walls
        (preview.walls || []).forEach(wall => {
            const x1 = wall.start[0] - cx;
            const z1 = wall.start[1] - cz;
            const x2 = wall.end[0] - cx;
            const z2 = wall.end[1] - cz;

            const dx = x2 - x1;
            const dz = z2 - z1;
            const length = Math.sqrt(dx * dx + dz * dz);
            if (length < 0.01) return;

            const thickness = wall.thickness_m || 0.14;
            const height = ceilingH;
            const angle = Math.atan2(dz, dx);

            const mat = wall.is_structural ? wallStructMat : wallMat;

            // Wall body
            const wallGeo = new THREE.BoxGeometry(length, height, thickness);
            const wallMesh = new THREE.Mesh(wallGeo, mat);
            wallMesh.position.set(
                (x1 + x2) / 2,
                height / 2,
                (z1 + z2) / 2
            );
            wallMesh.rotation.y = -angle;
            wallMesh.castShadow = true;
            wallMesh.receiveShadow = true;
            this.houseGroup.add(wallMesh);

            // 3. Openings (cut visual)
            (wall.openings || []).forEach(op => {
                const opW = op.width_m || 0.80;
                const opH = op.type === 'door' ? 2.10 : 1.20;
                const sill = op.type === 'door' ? 0 : 1.10;
                const posAlongWall = op.position_m || 0.15;

                // Position along the wall axis
                const t = (posAlongWall + opW / 2) / length;
                const opX = x1 + dx * t;
                const opZ = z1 + dz * t;

                const opGeo = new THREE.BoxGeometry(opW, opH, thickness * 1.2);
                const opMat = op.type === 'door' ? doorMat : windowMat;
                const opMesh = new THREE.Mesh(opGeo, opMat);
                opMesh.position.set(opX, sill + opH / 2, opZ);
                opMesh.rotation.y = -angle;
                this.houseGroup.add(opMesh);
            });
        });

        // 4. Roof
        this._addRoof(W, D, ceilingH, roofStyle, cx, cz, roofMat);

        // Center camera
        this.controls.target.set(0, ceilingH / 2, 0);
        const dist = Math.max(W, D) * 1.5;
        this.camera.position.set(dist * 0.8, dist * 0.6, dist * 0.8);
        this.controls.update();
    }

    _addRoof(W, D, ceilingH, style, cx, cz, mat) {
        const overhang = 0.40; // beiral
        const ridgeH = 1.50;   // altura da cumeeira

        if (style === 'flat') {
            // Flat roof (laje)
            const geo = new THREE.BoxGeometry(W + overhang * 2, 0.15, D + overhang * 2);
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(0, ceilingH + 0.075, 0);
            this.houseGroup.add(mesh);
            return;
        }

        if (style === 'hip') {
            // Hip roof (4 águas) - simplified as a pyramid
            const shape = new THREE.Shape();
            // Base rectangle with overhang
            const hw = W / 2 + overhang;
            const hd = D / 2 + overhang;

            // 4 triangular faces meeting at ridge
            const geo = new THREE.ConeGeometry(
                Math.max(hw, hd) * 1.2, ridgeH, 4
            );
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(0, ceilingH + ridgeH / 2, 0);
            mesh.rotation.y = Math.PI / 4;
            mesh.scale.set(W / D > 1 ? 1 : D / W * 0.5, 1, W / D > 1 ? W / D * 0.5 : 1);
            this.houseGroup.add(mesh);
            return;
        }

        // Default: gable (duas águas)
        const hw = W / 2 + overhang;
        const hd = D / 2 + overhang;

        // Two inclined planes
        const gableShape = new THREE.Shape();
        gableShape.moveTo(-hw, 0);
        gableShape.lineTo(0, ridgeH);
        gableShape.lineTo(hw, 0);
        gableShape.lineTo(-hw, 0);

        const extrudeSettings = { depth: D + overhang * 2, bevelEnabled: false };
        const gableGeo = new THREE.ExtrudeGeometry(gableShape, extrudeSettings);
        const gableMesh = new THREE.Mesh(gableGeo, mat);
        gableMesh.position.set(0, ceilingH, -hd);
        gableMesh.castShadow = true;
        this.houseGroup.add(gableMesh);
    }

    /**
     * Update with new preview data (called on parameter change).
     */
    updateFromPreview(preview) {
        this.loadFromPreview(preview);
    }

    dispose() {
        this.renderer.dispose();
        this.container.removeChild(this.renderer.domElement);
    }
}
