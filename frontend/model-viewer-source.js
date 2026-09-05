import * as THREE from "three";
import {OrbitControls} from "three/addons/controls/OrbitControls.js";
import {GLTFLoader} from "three/addons/loaders/GLTFLoader.js";

const BACKGROUNDS = [0x0b1110, 0x36413f, 0xe7eceb];

function materialsOf(value) {
  return Array.isArray(value) ? value : [value];
}

function disposeMaterial(material, textures, materials) {
  if (!material || materials.has(material)) return;
  materials.add(material);
  for (const value of Object.values(material)) {
    if (value?.isTexture) textures.add(value);
  }
  material.dispose();
}

export async function createModelViewer({canvas, bytes, background = "#0b1110", onContextState}) {
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: false});
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  const scene = new THREE.Scene();
  try { scene.background = new THREE.Color(background); } catch { scene.background = new THREE.Color(0x0b1110); }
  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = false;
  controls.screenSpacePanning = true;
  controls.addEventListener("change", render);

  const hemisphere = new THREE.HemisphereLight(0xffffff, 0x30403d, 1.8);
  const key = new THREE.DirectionalLight(0xffffff, 3.2);
  const fill = new THREE.DirectionalLight(0xaacfff, 1.4);
  key.position.set(4, 7, 5);
  fill.position.set(-5, 2, -4);
  scene.add(hemisphere, key, fill);

  let disposed = false;
  let visible = true;
  let animationFrame = 0;
  let lastTime = 0;
  let animationPlaying = false;
  let backgroundIndex = 0;
  let lightIndex = 0;
  let shadingIndex = 0;
  let boundsVisible = false;
  let boxHelper = null;
  let grid = null;
  let root = null;
  let mixer = null;
  let animations = [];
  const originalMaterials = new Map();
  const neutralMaterial = new THREE.MeshStandardMaterial({color: 0xaab5b2, roughness: 0.72, metalness: 0.08});
  const wireMaterial = new THREE.MeshBasicMaterial({color: 0x63dfbf, wireframe: true});

  function resize() {
    if (disposed) return;
    const rect = canvas.getBoundingClientRect();
    const cssWidth = Math.max(1, Math.floor(rect.width));
    const cssHeight = Math.max(1, Math.floor(rect.height));
    const maxRatio = Math.sqrt(4_000_000 / (cssWidth * cssHeight));
    const ratio = Math.max(1, Math.min(window.devicePixelRatio || 1, 2, maxRatio));
    renderer.setPixelRatio(ratio);
    renderer.setSize(cssWidth, cssHeight, false);
    camera.aspect = cssWidth / cssHeight;
    camera.updateProjectionMatrix();
    render();
  }

  function render() {
    if (!disposed && visible && root) renderer.render(scene, camera);
  }

  function tick(time) {
    animationFrame = 0;
    if (disposed || !visible || !animationPlaying || !mixer) return;
    const delta = lastTime ? Math.min((time - lastTime) / 1000, 0.1) : 0;
    lastTime = time;
    mixer.update(delta);
    render();
    animationFrame = requestAnimationFrame(tick);
  }

  function scheduleAnimation() {
    if (!animationFrame && visible && animationPlaying && mixer) {
      lastTime = 0;
      animationFrame = requestAnimationFrame(tick);
    }
  }

  function fit() {
    const box = new THREE.Box3().setFromObject(root);
    if (box.isEmpty()) throw new Error("model has no renderable bounds");
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const radius = Math.max(sphere.radius, 0.001);
    const halfFov = THREE.MathUtils.degToRad(camera.fov / 2);
    const distance = radius / Math.sin(halfFov) * 1.15;
    const direction = new THREE.Vector3(1, 0.72, 1).normalize();
    camera.position.copy(sphere.center).addScaledVector(direction, distance);
    camera.near = Math.max(distance / 1000, 0.001);
    camera.far = Math.max(distance * 20, 10);
    camera.updateProjectionMatrix();
    controls.target.copy(sphere.center);
    controls.minDistance = radius * 0.05;
    controls.maxDistance = radius * 30;
    controls.update();
    if (grid) scene.remove(grid);
    grid = new THREE.GridHelper(radius * 4, 12, 0x60706c, 0x31413e);
    grid.position.y = box.min.y;
    scene.add(grid);
    if (boxHelper) scene.remove(boxHelper);
    boxHelper = new THREE.Box3Helper(box, 0xffbd63);
    boxHelper.visible = boundsVisible;
    scene.add(boxHelper);
    render();
  }

  function setShading() {
    shadingIndex = (shadingIndex + 1) % 3;
    root.traverse((object) => {
      if (!object.isMesh) return;
      if (shadingIndex === 0) object.material = originalMaterials.get(object);
      else {
        const count = materialsOf(originalMaterials.get(object)).length;
        const replacement = shadingIndex === 1 ? neutralMaterial : wireMaterial;
        object.material = count > 1 ? Array(count).fill(replacement) : replacement;
      }
    });
    render();
    return ["material", "neutral", "wireframe"][shadingIndex];
  }

  function setLight() {
    lightIndex = (lightIndex + 1) % 3;
    const presets = [
      [1.8, 3.2, 1.4],
      [3.4, 0.7, 0.7],
      [0.7, 4.2, 0.3],
    ];
    [hemisphere.intensity, key.intensity, fill.intensity] = presets[lightIndex];
    render();
    return ["studio", "flat", "dramatic"][lightIndex];
  }

  function setBackground() {
    backgroundIndex = (backgroundIndex + 1) % BACKGROUNDS.length;
    scene.background = new THREE.Color(BACKGROUNDS[backgroundIndex]);
    render();
    return backgroundIndex;
  }

  function toggleBounds() {
    boundsVisible = !boundsVisible;
    if (boxHelper) boxHelper.visible = boundsVisible;
    render();
    return boundsVisible;
  }

  function toggleAnimation() {
    if (!mixer) return false;
    animationPlaying = !animationPlaying;
    if (animationPlaying) {
      for (const clip of animations) {
        const action = mixer.clipAction(clip);
        action.paused = false;
        action.play();
      }
      scheduleAnimation();
    } else {
      for (const clip of animations) mixer.clipAction(clip).paused = true;
      if (animationFrame) cancelAnimationFrame(animationFrame);
      animationFrame = 0;
      render();
    }
    return animationPlaying;
  }

  function setVisible(next) {
    visible = Boolean(next);
    if (!visible && animationFrame) {
      cancelAnimationFrame(animationFrame);
      animationFrame = 0;
    }
    if (visible) {
      resize();
      scheduleAnimation();
    }
  }

  function snapshot() {
    render();
    const maximum = 512;
    const scale = Math.min(1, maximum / Math.max(canvas.width, canvas.height));
    const capture = document.createElement("canvas");
    capture.width = Math.max(1, Math.round(canvas.width * scale));
    capture.height = Math.max(1, Math.round(canvas.height * scale));
    const context = capture.getContext("2d", {alpha: false});
    if (!context) return Promise.reject(new Error("snapshot context unavailable"));
    context.drawImage(canvas, 0, 0, capture.width, capture.height);
    return new Promise((resolve, reject) => {
      capture.toBlob(
        (blob) => blob ? resolve(blob) : reject(new Error("snapshot unavailable")),
        "image/webp",
        0.8,
      );
    });
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    if (animationFrame) cancelAnimationFrame(animationFrame);
    observer.disconnect();
    controls.dispose();
    canvas.removeEventListener("webglcontextlost", contextLost);
    canvas.removeEventListener("webglcontextrestored", contextRestored);
    if (mixer) mixer.stopAllAction();
    const geometries = new Set();
    const materials = new Set();
    const textures = new Set();
    if (root) root.traverse((object) => {
      if (object.geometry) geometries.add(object.geometry);
      for (const material of materialsOf(originalMaterials.get(object) || object.material)) {
        disposeMaterial(material, textures, materials);
      }
    });
    for (const texture of textures) {
      const image = texture.source?.data;
      texture.dispose();
      if (typeof image?.close === "function") image.close();
    }
    for (const geometry of geometries) geometry.dispose();
    neutralMaterial.dispose();
    wireMaterial.dispose();
    if (boxHelper) {
      boxHelper.geometry.dispose();
      boxHelper.material.dispose();
    }
    if (grid) {
      grid.geometry.dispose();
      for (const material of materialsOf(grid.material)) material.dispose();
    }
    renderer.renderLists.dispose();
    renderer.dispose();
    renderer.forceContextLoss();
  }

  function contextLost(event) {
    event.preventDefault();
    if (animationFrame) cancelAnimationFrame(animationFrame);
    animationFrame = 0;
    onContextState?.("lost");
  }

  function contextRestored() {
    onContextState?.("restored");
    resize();
    scheduleAnimation();
  }

  canvas.addEventListener("webglcontextlost", contextLost);
  canvas.addEventListener("webglcontextrestored", contextRestored);
  const observer = new ResizeObserver(resize);
  observer.observe(canvas);

  const loader = new GLTFLoader();
  const arrayBuffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  let gltf;
  try {
    gltf = await loader.parseAsync(arrayBuffer, "");
  } catch (error) {
    dispose();
    throw error;
  }
  if (disposed) throw new Error("model viewer was disposed while loading");
  root = gltf.scene;
  animations = gltf.animations || [];
  let triangles = 0;
  let meshes = 0;
  const materialSet = new Set();
  root.traverse((object) => {
    if (!object.isMesh) return;
    meshes += 1;
    originalMaterials.set(object, object.material);
    for (const material of materialsOf(object.material)) materialSet.add(material);
    const geometry = object.geometry;
    triangles += Math.floor((geometry.index?.count || geometry.attributes.position?.count || 0) / 3);
  });
  if (!meshes) {
    dispose();
    throw new Error("model has no renderable mesh");
  }
  scene.add(root);
  if (animations.length) mixer = new THREE.AnimationMixer(root);
  resize();
  fit();
  return {
    stats: {triangles, meshes, materials: materialSet.size, animations: animations.length},
    fit, setShading, setLight, setBackground, toggleBounds, toggleAnimation,
    setVisible, snapshot, dispose,
  };
}
